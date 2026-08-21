"""
Tools the troubleshooting planner can run. Six are deterministic, LLM-free
Frappe queries — real workflow/permission/field/script/link state, not an
embedding-similarity guess. Three are thin wrappers around the existing
semantic-search Providers, so the planner can still reach those when a
deterministic check doesn't cover it. Every tool returns the same shape
(`List[ToolResult]`) so the planner's execution loop doesn't need to know
which kind it's running.

Deterministic tools never call `llm.py` — none of them touch embeddings or
chat completion — so a dead Gemini quota can only ever take out the three
wrapper tools, never these six.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import frappe

from changai.changai.erp_assistant.agent.doctype_meta import missing_mandatory_fields
from changai.changai.erp_assistant.providers.base import Chunk


@dataclass
class ToolContext:
    question: str
    doctype: Optional[str]
    record_id: Optional[str]
    user: str
    conversation_context: Optional[str] = None
    _record_cache: Dict[str, Any] = field(default_factory=dict)

    def get_record(self):
        """Cached frappe.get_doc(doctype, record_id); None if either is
        missing or the record doesn't exist."""
        if not self.doctype or not self.record_id:
            return None
        key = f"{self.doctype}:{self.record_id}"
        if key not in self._record_cache:
            try:
                self._record_cache[key] = frappe.get_doc(self.doctype, self.record_id)
            except Exception:
                self._record_cache[key] = None
        return self._record_cache[key]


@dataclass
class ToolResult:
    tool: str
    ok: bool                    # ran without error / had what it needed
    found: bool                 # surfaced a concrete, blocking finding
    summary: str                # human text — states EITHER "found X" OR "checked, clean"
    citation: Dict[str, Any] = field(default_factory=dict)

    def to_chunk(self) -> Chunk:
        return Chunk(
            provider=self.tool,
            title=self.tool.replace("_", " ").title(),
            text=self.summary,
            score=1.0,
            citation=self.citation,
        )


def _skip(tool: str, reason: str) -> List[ToolResult]:
    return [ToolResult(tool=tool, ok=False, found=False, summary=f"skipped: {reason}")]


# ---------------------------------------------------------------------------
# Deterministic tools — real Frappe queries, no LLM, no embeddings.
# ---------------------------------------------------------------------------

def workflow_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        return _skip("workflow_check", "no doctype resolved")

    wf_name = frappe.db.get_value("Workflow", {"document_type": ctx.doctype, "is_active": 1})
    if not wf_name:
        return [ToolResult(
            "workflow_check", True, False,
            f"No active workflow is configured for {ctx.doctype} — submission isn't gated by a workflow state.",
        )]

    wf = frappe.get_doc("Workflow", wf_name)
    record = ctx.get_record()
    state_field = wf.workflow_state_field or "workflow_state"
    current_state = getattr(record, state_field, None) if record else None

    if not current_state:
        states = ", ".join(s.state for s in wf.states)
        return [ToolResult(
            "workflow_check", True, False,
            f"Workflow '{wf_name}' is active for {ctx.doctype} (states: {states}), "
            f"but no specific record was resolved to check its current state.",
            citation={"workflow": wf_name},
        )]

    user_roles = set(frappe.get_roles(ctx.user))
    transitions = [t for t in wf.transitions if t.state == current_state]
    blocked = [t for t in transitions if t.allowed not in user_roles]

    if transitions and len(blocked) == len(transitions):
        actions = ", ".join(f"{t.action} (needs role: {t.allowed})" for t in transitions)
        return [ToolResult(
            "workflow_check", True, True,
            f"Record is in workflow state '{current_state}'. None of the roles required for the "
            f"available transitions ({actions}) are assigned to the current user.",
            citation={"workflow": wf_name, "state": current_state},
        )]

    return [ToolResult(
        "workflow_check", True, False,
        f"Record is in workflow state '{current_state}'; the current user's roles allow at least "
        f"one transition out of it, so the workflow isn't what's blocking this.",
        citation={"workflow": wf_name, "state": current_state},
    )]


def permission_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        return _skip("permission_check", "no doctype resolved")

    record = ctx.get_record()
    # "create" matters when there's no record yet (why can't I make a new
    # X); the other four matter once one exists. Checking all five covers
    # both a creation-failure and a submit-failure question with one tool.
    actions = ["create", "read", "write", "submit", "cancel"]
    denied = []
    for action in actions:
        try:
            allowed = frappe.has_permission(ctx.doctype, action, doc=record, user=ctx.user)
        except Exception:
            allowed = False
        if not allowed:
            denied.append(action)

    if not denied:
        return [ToolResult(
            "permission_check", True, False,
            f"The current user has create/read/write/submit/cancel permission on {ctx.doctype} — "
            f"this isn't a permission issue.",
        )]

    perms = frappe.get_all(
        "Custom DocPerm", filters={"parent": ctx.doctype},
        fields=["role", "create", "read", "write", "submit", "cancel"],
    ) or frappe.get_all(
        "DocPerm", filters={"parent": ctx.doctype},
        fields=["role", "create", "read", "write", "submit", "cancel"],
    )
    user_roles = set(frappe.get_roles(ctx.user))
    missing_roles = sorted({
        p["role"] for p in perms
        if any(p.get(a) for a in denied) and p["role"] not in user_roles
    })
    role_note = f" Role(s) that grant it: {', '.join(missing_roles)}." if missing_roles else ""
    return [ToolResult(
        "permission_check", True, True,
        f"The current user is missing permission to: {', '.join(denied)} on {ctx.doctype}.{role_note}",
        citation={"denied": denied, "missing_roles": missing_roles},
    )]


def mandatory_fields_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        return _skip("mandatory_fields_check", "no doctype resolved")

    record = ctx.get_record()
    if not record:
        # Creation scenario — no record exists yet to check values against,
        # but the doctype's mandatory-field list itself is still useful
        # context for "why can't I create X" (a field the user doesn't know
        # is required is a common creation blocker).
        required = missing_mandatory_fields(ctx.doctype, {})
        if not required:
            return [ToolResult(
                "mandatory_fields_check", True, False,
                f"{ctx.doctype} has no mandatory fields beyond what's auto-filled.",
            )]
        return [ToolResult(
            "mandatory_fields_check", True, False,
            f"Fields required to create a {ctx.doctype}: {', '.join(required)}. "
            f"(No specific record to check actual values against.)",
            citation={"required_fields": required},
        )]

    missing = missing_mandatory_fields(ctx.doctype, record.as_dict())
    if missing:
        return [ToolResult(
            "mandatory_fields_check", True, True,
            f"This record is missing required field(s): {', '.join(missing)}.",
            citation={"missing_fields": missing},
        )]
    return [ToolResult(
        "mandatory_fields_check", True, False,
        "All mandatory fields on this record are filled in — missing data isn't the cause.",
    )]


def client_scripts_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        return _skip("client_scripts_check", "no doctype resolved")

    scripts = frappe.get_all(
        "Client Script", filters={"dt": ctx.doctype, "enabled": 1},
        fields=["name", "view"],
    )
    if not scripts:
        return [ToolResult(
            "client_scripts_check", True, False,
            f"No active Client Scripts on {ctx.doctype} — client-side script logic isn't blocking this.",
        )]
    names = ", ".join(f"{s['name']} ({s['view']})" for s in scripts)
    return [ToolResult(
        "client_scripts_check", True, True,
        f"{len(scripts)} active Client Script(s) on {ctx.doctype} could be involved: {names}. "
        f"Worth reviewing for form validation or field-visibility logic that might block submit.",
        citation={"scripts": [s["name"] for s in scripts]},
    )]


_SUBMIT_RELEVANT_EVENTS = {"Before Submit", "Before Save", "Validate", "Before Cancel"}


def server_scripts_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        return _skip("server_scripts_check", "no doctype resolved")

    scripts = frappe.get_all(
        "Server Script", filters={"reference_doctype": ctx.doctype, "disabled": 0},
        fields=["name", "script_type", "doctype_event", "script"],
    )
    relevant = [s for s in scripts if s.get("doctype_event") in _SUBMIT_RELEVANT_EVENTS]
    if not relevant:
        return [ToolResult(
            "server_scripts_check", True, False,
            f"No active Server Scripts on {ctx.doctype} run during save/submit/cancel — "
            f"server-side script logic isn't blocking this.",
        )]
    parts = []
    for s in relevant:
        body = (s.get("script") or "")[:500]
        parts.append(f"{s['name']} ({s['doctype_event']}):\n{body}")
    return [ToolResult(
        "server_scripts_check", True, True,
        f"{len(relevant)} active Server Script(s) run on {'/'.join(sorted({s['doctype_event'] for s in relevant}))} "
        f"for {ctx.doctype} — a frappe.throw() in one of these is a common cause of a blocked submit:\n\n"
        + "\n\n".join(parts),
        citation={"scripts": [s["name"] for s in relevant]},
    )]


def linked_documents_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype or not ctx.record_id:
        return _skip("linked_documents_check", "no specific record resolved")

    record = ctx.get_record()
    if not record:
        return _skip("linked_documents_check", f"{ctx.doctype} {ctx.record_id} not found")

    meta = frappe.get_meta(ctx.doctype)
    problems = []
    for f in meta.fields:
        if f.fieldtype != "Link" or not f.options:
            continue
        target_name = record.get(f.fieldname)
        if not target_name:
            continue
        try:
            docstatus = frappe.db.get_value(f.options, target_name, "docstatus")
        except Exception:
            continue
        if docstatus == 2:
            problems.append(f"{f.label or f.fieldname} -> {f.options} {target_name} is Cancelled")

    if problems:
        return [ToolResult(
            "linked_documents_check", True, True,
            "Linked document issue(s) found: " + "; ".join(problems) + ".",
            citation={"problems": problems},
        )]
    return [ToolResult(
        "linked_documents_check", True, False,
        "No cancelled/problematic linked documents found on this record.",
    )]


def custom_fields_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        return _skip("custom_fields_check", "no doctype resolved")

    fields = frappe.get_all(
        "Custom Field", filters={"dt": ctx.doctype},
        fields=["fieldname", "label", "reqd", "depends_on"],
    )
    if not fields:
        return [ToolResult(
            "custom_fields_check", True, False,
            f"No custom fields on {ctx.doctype} — not a factor here.",
        )]

    mandatory = [f for f in fields if f.get("reqd")]
    conditional = [f for f in fields if f.get("depends_on")]
    if not mandatory and not conditional:
        return [ToolResult(
            "custom_fields_check", True, False,
            f"{len(fields)} custom field(s) on {ctx.doctype}, none mandatory or conditionally shown — unlikely to be blocking this.",
        )]
    parts = []
    if mandatory:
        parts.append("mandatory: " + ", ".join(f.get("label") or f["fieldname"] for f in mandatory))
    if conditional:
        parts.append("conditionally shown/required: " + ", ".join(f.get("label") or f["fieldname"] for f in conditional))
    return [ToolResult(
        "custom_fields_check", True, True,
        f"Custom field(s) on {ctx.doctype} that could be involved — " + "; ".join(parts) + ".",
        citation={"mandatory": [f["fieldname"] for f in mandatory], "conditional": [f["fieldname"] for f in conditional]},
    )]


def naming_series_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        return _skip("naming_series_check", "no doctype resolved")

    meta = frappe.get_meta(ctx.doctype)
    ns_field = meta.get_field("naming_series")

    if not ns_field:
        if meta.autoname and meta.autoname.lower() not in ("prompt", "hash"):
            return [ToolResult(
                "naming_series_check", True, False,
                f"{ctx.doctype} uses a fixed autoname pattern ('{meta.autoname}'), not a Naming Series field — nothing to misconfigure here.",
            )]
        return [ToolResult(
            "naming_series_check", True, False,
            f"{ctx.doctype} has no Naming Series field — not a factor here.",
        )]

    options = [o for o in (ns_field.options or "").split("\n") if o.strip()]
    if not options:
        return [ToolResult(
            "naming_series_check", True, True,
            f"{ctx.doctype}'s Naming Series field has no series options configured — this would block creating a new record.",
        )]
    return [ToolResult(
        "naming_series_check", True, False,
        f"{ctx.doctype}'s Naming Series is configured with options ({', '.join(options)}) — not a factor here.",
        citation={"options": options},
    )]


def error_log_check(ctx: ToolContext) -> List[ToolResult]:
    if not ctx.doctype:
        # No resolved DocType means no ERP-specific grounding for this
        # question at all (e.g. gibberish input) — falling back to whatever
        # is in the Error Log regardless of relevance would hand the model
        # a real but unrelated error to present as "the cause". Every other
        # tool already skips cleanly on a missing doctype; match that here.
        return _skip("error_log_check", "no DocType identified for this question")

    filters = {"creation": [">", frappe.utils.add_to_date(None, minutes=-30)]}
    # Error Log doesn't always tag reference_doctype, so this is a
    # best-effort narrowing, not a hard filter.
    doctype_matches = frappe.get_all(
        "Error Log", filters={**filters, "reference_doctype": ctx.doctype},
        fields=["name", "method", "error", "creation"],
        order_by="creation desc", limit=3,
    )
    if doctype_matches:
        return _error_log_result(doctype_matches)

    recent = frappe.get_all(
        "Error Log", filters=filters,
        fields=["name", "method", "error", "creation"],
        order_by="creation desc", limit=3,
    )
    if not recent:
        return [ToolResult(
            "error_log_check", True, False,
            "No entries in the Error Log in the last 30 minutes.",
        )]
    return _error_log_result(recent)


def _error_log_result(entries: List[dict]) -> List[ToolResult]:
    parts = []
    for e in entries:
        last_line = (e.get("error") or "").strip().splitlines()[-1:] or [""]
        parts.append(f"{e['creation']} ({e.get('method') or 'unknown method'}): {last_line[0][:300]}")
    return [ToolResult(
        "error_log_check", True, True,
        f"{len(entries)} recent Error Log entr{'y' if len(entries) == 1 else 'ies'}:\n" + "\n".join(parts),
        citation={"error_log_names": [e["name"] for e in entries]},
    )]


# ---------------------------------------------------------------------------
# Wrapper tools — reach the existing semantic-search Providers when a
# deterministic check above doesn't cover it. Each Chunk becomes one
# ToolResult so the planner's execution loop treats every tool uniformly.
# ---------------------------------------------------------------------------

def _wrap_provider(tool_name: str, provider_name: str, k: int = 4) -> Callable[[ToolContext], List[ToolResult]]:
    def run(ctx: ToolContext) -> List[ToolResult]:
        from changai.changai.erp_assistant.agent.orchestrator import _provider
        try:
            chunks = _provider(provider_name).retrieve(ctx.question, k=k)
        except Exception as e:
            return [ToolResult(tool_name, False, False, f"search failed: {e}")]
        if not chunks:
            return [ToolResult(tool_name, True, False, f"No relevant {provider_name} results found.")]
        return [
            ToolResult(tool_name, True, True, f"[{c.title}] {c.text}", citation=c.citation)
            for c in chunks
        ]
    return run


customization_search = _wrap_provider("customization_search", "customization")
code_search = _wrap_provider("code_search", "code_search")
erp_docs_search = _wrap_provider("erp_docs_search", "erp_docs")


# ---------------------------------------------------------------------------
# Registry — the planner builds its tool menu from this at runtime, so
# adding a tool later needs no prompt edit.
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    name: str
    description: str
    needs: str  # human-readable note on what it needs (doctype / record_id) — informational only
    run: Callable[[ToolContext], List[ToolResult]]


TOOL_REGISTRY: Dict[str, Tool] = {
    t.name: t for t in [
        Tool(
            "workflow_check",
            "Checks whether an active workflow governs this DocType, what state the record is in, "
            "and whether the current user's roles allow moving out of that state.",
            "doctype (record helps but not required)",
            workflow_check,
        ),
        Tool(
            "permission_check",
            "Checks whether the current user actually has read/write/submit/cancel permission on "
            "this DocType, and if not, names which role would grant it.",
            "doctype",
            permission_check,
        ),
        Tool(
            "mandatory_fields_check",
            "Checks a specific existing record's actual field values against the DocType's real "
            "mandatory fields, and names any that are still blank.",
            "doctype and record id",
            mandatory_fields_check,
        ),
        Tool(
            "client_scripts_check",
            "Lists active Client Scripts on this DocType, which can add form validation or hide/lock "
            "fields in ways that block submission.",
            "doctype",
            client_scripts_check,
        ),
        Tool(
            "server_scripts_check",
            "Lists active Server Scripts on this DocType that run on save/validate/submit/cancel, "
            "including their code — a frappe.throw() in one of these is a common cause of a blocked submit.",
            "doctype",
            server_scripts_check,
        ),
        Tool(
            "linked_documents_check",
            "Checks a specific record's linked documents (Link fields) for a cancelled or otherwise "
            "problematic linked document that could block this record.",
            "doctype and record id",
            linked_documents_check,
        ),
        Tool(
            "custom_fields_check",
            "Lists custom fields on this DocType, flagging any that are mandatory or conditionally "
            "shown/required — a field the user doesn't know is required is a common creation blocker.",
            "doctype",
            custom_fields_check,
        ),
        Tool(
            "naming_series_check",
            "Checks whether this DocType's Naming Series (or autoname pattern) is actually configured "
            "with valid options — a missing/misconfigured series blocks creating any new record.",
            "doctype",
            naming_series_check,
        ),
        Tool(
            "error_log_check",
            "Checks Frappe's Error Log for a recent traceback (last 30 min), narrowed to this DocType "
            "when possible — often contains the literal error the user is hitting.",
            "none required, doctype narrows it",
            error_log_check,
        ),
        Tool(
            "customization_search",
            "Semantic search over this DocType's custom fields, property setters, and general "
            "customization notes — use when the deterministic checks above don't explain it.",
            "doctype helps, not required",
            customization_search,
        ),
        Tool(
            "code_search",
            "Live search of installed apps' source code for a term from the question — use for "
            "anything not covered by the structured checks above.",
            "none",
            code_search,
        ),
        Tool(
            "erp_docs_search",
            "Semantic search over standard ERPNext documentation.",
            "none",
            erp_docs_search,
        ),
    ]
}
