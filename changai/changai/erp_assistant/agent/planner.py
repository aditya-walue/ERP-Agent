"""
The troubleshooting agentic loop. Seven logical stages, mapped onto exactly
two Gemini calls (this repo's Gemini quota has been the tightest constraint
all session — extra round-trips per question aren't free):

    1. Understand Problem       ─┐
    2. Generate Investigation    ├─ one JSON-mode call: understand_problem_and_plan()
       Plan                     ─┘
    3. Run Diagnostic Tools      ─── run_diagnostic_tools() — zero LLM calls,
                                      real Frappe queries (agent/tools.py)
    4. Collect Evidence          ─── collect_evidence() — zero LLM calls,
                                      orders findings before clean checks
    5. Find Root Cause           ─┐
    6. Generate Explanation      ├─ ask_agent()'s EXISTING synthesis call,
    7. Suggest Fix               ─┘  Cause / Reason / Resolution format
                                      (response_format.py) — unchanged by
                                      this module entirely

Stages 5-7 aren't implemented here on purpose: this module's job ends at
handing back chunks in the same (primary_chunks, supplement_chunks,
used_fallback, any_provider_ready) shape the old static router/retrieve
loop already produced, so ask_agent()'s downstream half — permission
filtering, the no-hallucination gate (which IS "Validate Results", reused
unmodified, not reimplemented here), prompt building, the actual
root-cause/explanation/fix synthesis, citations — needs zero changes.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import frappe

from changai.changai.erp_assistant import llm
from changai.changai.erp_assistant.agent.entities import resolve_doctype, resolve_record_id
from changai.changai.erp_assistant.agent.tools import TOOL_REGISTRY, ToolContext, ToolResult
from changai.changai.erp_assistant.providers.base import Chunk

# Safety-net tool list used when the planning call fails outright (bad JSON,
# model unavailable) — not a per-question routing rule, the same "unrecognized
# -> safe default" idiom intent.classify() already uses. Deterministic tools
# only, since those don't depend on the same Gemini call that just failed.
_FALLBACK_TOOLS = [
    "error_log_check", "workflow_check", "permission_check", "mandatory_fields_check",
    "custom_fields_check", "naming_series_check", "client_scripts_check",
    "server_scripts_check", "linked_documents_check",
]

_PLAN_SYS_PROMPT = """You are planning which checks to run to diagnose an ERP problem.
Reply with JSON only, no markdown fences, no commentary."""


@dataclass
class InvestigationPlan:
    """Output of stages 1+2. `goal` is stage 1 (Understand Problem); `doctype`
    /`record_id`/`tools` are stage 2 (Generate Investigation Plan) — kept as
    separate named fields even though one Gemini call produces both, so the
    two ideas stay distinguishable in code, not just in a comment."""

    goal: str
    doctype: Optional[str]
    record_id: Optional[str]
    tools: List[str] = field(default_factory=list)


def _tool_menu() -> str:
    return "\n".join(
        f"- {t.name}: {t.description} (needs: {t.needs})"
        for t in TOOL_REGISTRY.values()
    )


def _build_plan_prompt(question: str, intent_hint: str, conversation_context: Optional[str]) -> str:
    context_block = (
        f"RECENT CONVERSATION (may contain the actual error the user saw — ground truth if present):\n{conversation_context}\n\n"
        if conversation_context else ""
    )
    return f"""{context_block}QUESTION: {question}

INTENT HINT: {intent_hint} (a hint from a separate classifier, not a rule — pick whichever checks are actually relevant regardless of this label)

AVAILABLE TOOLS:
{_tool_menu()}

Identify the DocType and, if a specific record is mentioned or implied by RECENT CONVERSATION, its record id.
Pick every tool from the list above that's relevant to actually answering this question — for a
"why did X fail" question that usually means most or all of the structured checks, not just one.

Reply with exactly this JSON shape:
{{"goal": "<one sentence — what you're trying to find out>", "doctype": "<DocType name or null>", "record_id": "<record id or null>", "tools": ["<tool name>", ...]}}"""


def _parse_plan(raw: str) -> Optional[dict]:
    try:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def understand_problem_and_plan(
    question: str, intent_hint: str, conversation_context: Optional[str],
) -> InvestigationPlan:
    """Stages 1-2. One JSON-mode Gemini call. Falls back to deterministic
    entity resolution (agent/entities.py) + the fixed deterministic-tool
    list if the call fails or returns unparseable JSON — same "unavailable
    -> safe default" idiom intent.classify() already uses, not a new
    hardcoded routing rule."""
    try:
        raw = llm.chat(_PLAN_SYS_PROMPT, _build_plan_prompt(question, intent_hint, conversation_context))
        data = _parse_plan(raw)
    except Exception:
        data = None

    if not data:
        doctype = resolve_doctype(question)
        record_id = resolve_record_id(question, doctype) if doctype else None
        return InvestigationPlan("Diagnose the reported problem.", doctype, record_id, list(_FALLBACK_TOOLS))

    doctype = data.get("doctype") or resolve_doctype(question)
    record_id = data.get("record_id") or (resolve_record_id(question, doctype) if doctype else None)
    tools = [t for t in (data.get("tools") or []) if t in TOOL_REGISTRY]
    if not tools:
        tools = list(_FALLBACK_TOOLS)
    goal = data.get("goal") or "Diagnose the reported problem."
    return InvestigationPlan(goal, doctype, record_id, tools)


def run_diagnostic_tools(ctx: ToolContext, tool_names: List[str]) -> List[ToolResult]:
    """Stage 3. Zero LLM calls — every tool is a real Frappe query
    (agent/tools.py). One try/except per tool so a single failing tool
    (e.g. an embedding-dependent wrapper tool on a dead quota) can't abort
    the rest."""
    results: List[ToolResult] = []
    for name in tool_names:
        tool = TOOL_REGISTRY.get(name)
        if not tool:
            continue
        try:
            results.extend(tool.run(ctx))
        except Exception as e:
            results.append(ToolResult(name, False, False, f"tool failed: {e}"))
    return results


def collect_evidence(results: List[ToolResult]) -> List[ToolResult]:
    """Stage 4. Drops tools that didn't actually run (ok=False — skipped or
    errored, nothing to show the model), and orders what's left so concrete
    findings (found=True) come before clean checks (found=False). Ordering
    matters here: the synthesis prompt reads chunks top-to-bottom, and a
    real finding buried after five "all clear" results is exactly the kind
    of thing that gets hedged into a vague answer instead of stated
    plainly."""
    evidence = [r for r in results if r.ok]
    return sorted(evidence, key=lambda r: not r.found)


def investigate(
    question: str, intent: str, conversation_context: Optional[str] = None,
) -> Tuple[List[Chunk], List[Chunk], bool, bool]:
    """Runs stages 1-4 and hands back the same shape
    orchestrator.ask_agent()'s old static router/retrieve loop produced:
    (primary_chunks, supplement_chunks, used_fallback, any_provider_ready).
    Stages 5-7 (Find Root Cause / Generate Explanation / Suggest Fix) are
    ask_agent()'s own existing synthesis call against these chunks — see
    module docstring."""
    plan = understand_problem_and_plan(question, intent, conversation_context)

    ctx = ToolContext(
        question=question, doctype=plan.doctype, record_id=plan.record_id,
        user=frappe.session.user, conversation_context=conversation_context,
    )
    raw_results = run_diagnostic_tools(ctx, plan.tools)
    evidence = collect_evidence(raw_results)

    primary_chunks = [r.to_chunk() for r in evidence]
    any_provider_ready = True  # deterministic tools have no index-existence precondition
    return primary_chunks, [], False, any_provider_ready
