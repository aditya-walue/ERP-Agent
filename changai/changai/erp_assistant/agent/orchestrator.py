"""
Top-level entry point: classify -> route -> retrieve -> synthesize.

This is the only place that calls the LLM for the final answer. Providers
never call the chat model themselves (erp_docs/implementation_docs only use
it for embeddings); the orchestrator is where retrieval results become a
user-facing answer, so the no-hallucination gate and the "never say I found
nothing" HOWTO rule both live here, in exactly one place each.
"""

import re
from typing import Dict, List, Optional

import frappe

from changai.changai.erp_assistant import llm
from changai.changai.erp_assistant.agent import intent as intent_mod
from changai.changai.erp_assistant.agent.router import PRIMARY, PRIMARY_FALLBACK, SUPPLEMENT, routes_for
from changai.changai.erp_assistant.agent.response_format import build_system_prompt, build_user_prompt
from changai.changai.erp_assistant.providers.base import Chunk
from changai.changai.erp_assistant.providers.code_search_provider import CodeSearchProvider
from changai.changai.erp_assistant.providers.customization_provider import CustomizationProvider
from changai.changai.erp_assistant.providers.database_provider import DatabaseProvider
from changai.changai.erp_assistant.providers.erp_docs_provider import ERPDocsProvider
from changai.changai.erp_assistant.providers.implementation_docs_provider import ImplementationDocsProvider

# Below this cosine score, an embedding-backed chunk is treated as "not
# actually relevant". Non-embedding providers (database, code_search) emit
# score=1.0 and always clear this bar.
_MIN_SCORE = 0.25

_NO_INDEX_FALLBACK = (
    "I'm still being set up and can't answer questions yet — please check "
    "back shortly, or contact support if this continues."
)
_NO_MATCH_FALLBACK = (
    "I couldn't find an answer to that. Try rephrasing your question, or "
    "contact support for help."
)
_STANDARD_FALLBACK_NOTE = "\n\n_This is based on standard ERPNext guidance._"

# Which intents get the agentic plan/run-tools/validate loop (agent/planner.py)
# instead of the static per-intent provider table in router.py. Deliberately
# narrow for now — record_lookup/howto/definition already work well with one
# provider call and don't need a planning round-trip. workflow is the natural
# next addition (the tool menu already covers it) once troubleshooting is
# proven.
_PLANNER_INTENTS = {intent_mod.TROUBLESHOOTING}

# Whole message is just a greeting / who-are-you (allows repeated letters like
# "hii", "heyy", optional trailing punctuation). Matched before any retrieval.
_GREETING_RE = re.compile(
    r"^\s*(hi+|he+y+|he+llo+|hii+|hola|yo|good\s*(morning|afternoon|evening)|"
    r"who\s+are\s+you|what\s+can\s+you\s+do|what\s+do\s+you\s+do)"
    r"[\s!.?]*$",
    re.I,
)


def _is_greeting(question: str) -> bool:
    return bool(_GREETING_RE.match(question or ""))

_REGISTRY = {}


def _provider(name: str):
    if name not in _REGISTRY:
        _REGISTRY[name] = {
            "database": DatabaseProvider,
            "erp_docs": ERPDocsProvider,
            "implementation_docs": ImplementationDocsProvider,
            "customization": CustomizationProvider,
            "code_search": CodeSearchProvider,
        }[name]()
    return _REGISTRY[name]


def _permission_filter(chunks: List[Chunk]) -> List[Chunk]:
    out = []
    for c in chunks:
        dt = c.citation.get("doctype")
        if not dt:
            out.append(c)
            continue
        try:
            if frappe.has_permission(dt, "read"):
                out.append(c)
        except Exception:
            continue
    return out


def ask_agent(question: str, conversation_context: str = None) -> Dict:
    """
    conversation_context: recent turns from the caller's own chat history,
    plain text, most relevant when it contains an actual error message the
    user just saw (e.g. "why can't I create this Sales Invoice?" right
    after a failed insert). When present it's treated as ground truth, not
    a retrieval guess — it's included regardless of what the providers find
    and is enough on its own to clear the no-hallucination gate, because an
    LLM explaining a real error message beats a generic "check permissions
    and mandatory fields" answer every time.
    """
    question = (question or "").strip()
    if not question:
        frappe.throw("Empty question")

    # Bare greeting / who-are-you -> short, instant reply. Handled in code (not
    # via the LLM) so a "hi" never gets pulled into the previous topic by the
    # conversation context, and so it costs zero model calls.
    if _is_greeting(question):
        return {
            "answer": "Hi! I'm your ERP Assistant. How can I help you today?",
            "citations": [], "intent": "greeting", "used_fallback": False,
        }

    classified = intent_mod.classify(question)

    used_fallback = False
    any_provider_ready = False

    if classified in _PLANNER_INTENTS:
        # Agentic plan -> run tools -> (validated below, same gate as the
        # static-route path) loop, instead of one fixed per-intent provider
        # list. See agent/planner.py for why: a single opaque semantic
        # search over a bundled "customization card" doesn't reliably
        # surface which of workflow/permissions/mandatory fields/scripts/
        # linked docs is actually blocking a specific record.
        from changai.changai.erp_assistant.agent import planner
        primary_chunks, supplement_chunks, used_fallback, any_provider_ready = (
            planner.investigate(question, classified, conversation_context)
        )
    else:
        primary_chunks: List[Chunk] = []
        supplement_chunks: List[Chunk] = []
        route = routes_for(classified)

        primaries = [r for r in route if r[1] == PRIMARY]
        fallbacks = [r for r in route if r[1] == PRIMARY_FALLBACK]
        supplements = [r for r in route if r[1] == SUPPLEMENT]

        for name, _role in primaries:
            p = _provider(name)
            any_provider_ready = any_provider_ready or p.is_ready()
            primary_chunks.extend(p.retrieve(question, k=4))

        if not primary_chunks and fallbacks:
            for name, _role in fallbacks:
                p = _provider(name)
                any_provider_ready = any_provider_ready or p.is_ready()
                found = p.retrieve(question, k=4)
                if found:
                    primary_chunks.extend(found)
                    used_fallback = True

        for name, _role in supplements:
            p = _provider(name)
            any_provider_ready = any_provider_ready or p.is_ready()
            supplement_chunks.extend(p.retrieve(question, k=3))

    primary_chunks = _permission_filter(primary_chunks)
    supplement_chunks = _permission_filter(supplement_chunks)

    # No-hallucination gate. HOWTO is exempt by spec — it must always answer,
    # falling back to standard ERPNext procedure rather than refusing — but
    # that only works if erp_docs actually has content; if not even that
    # index exists, it's a setup problem, not a "nothing found" answer.
    has_signal = bool(conversation_context) or (
        bool(primary_chunks)
        and max((c.score for c in primary_chunks), default=0) >= _MIN_SCORE
    )
    if not has_signal:
        if not any_provider_ready:
            return {"answer": _NO_INDEX_FALLBACK, "citations": [], "intent": classified}
        if classified != intent_mod.HOWTO:
            return {"answer": _NO_MATCH_FALLBACK, "citations": [], "intent": classified}
        if not supplement_chunks:
            return {"answer": _NO_INDEX_FALLBACK, "citations": [], "intent": classified}

    all_chunks = primary_chunks + supplement_chunks
    system_prompt = build_system_prompt(classified)
    user_prompt = build_user_prompt(
        classified, question, primary_chunks, supplement_chunks,
        conversation_context=conversation_context,
    )

    try:
        answer = llm.chat(system_prompt, user_prompt)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "erp_assistant.ask_agent")
        frappe.throw(f"Assistant model call failed: {e}")

    if used_fallback:
        answer = answer.rstrip() + _STANDARD_FALLBACK_NOTE

    citations = [
        {"provider": c.provider, "title": c.title, "score": round(c.score, 3), **c.citation}
        for c in all_chunks
    ]
    return {"answer": answer, "citations": citations, "intent": classified,
            "used_fallback": used_fallback}


def try_answer(question: str, conversation_context: str = None) -> Optional[str]:
    """
    Best-effort answer for callers outside this app (changai's NON_ERP
    fallback and troubleshooting hand-off). Always retrieves + synthesizes,
    and collapses ask_agent()'s own "couldn't find anything relevant" giveup
    text to None. That collapsing has to live here, not in the caller — a
    caller reaching into `_NO_MATCH_FALLBACK`/`_NO_INDEX_FALLBACK` directly
    would be reading this app's internal fallback strings from across the
    app boundary. Every external caller should be able to treat "erp_assistant
    had nothing for this" the same way: as None, meaning fall back to your
    own next step.
    """
    result = ask_agent(question, conversation_context=conversation_context)
    answer = (result or {}).get("answer")
    if answer in (_NO_MATCH_FALLBACK, _NO_INDEX_FALLBACK):
        return None
    return answer or None


def try_answer_if_relevant(question: str, conversation_context: str = None) -> Optional[str]:
    """
    Gate for callers that want to skip retrieval entirely for questions this
    app has no business answering. changai's own ERP-data/SQL pipeline
    already handles plain record-lookup questions ("what is the customer
    name on SINV-001?") — classifying here first and returning None for
    record_lookup lets that pipeline keep owning those, instead of this app
    spending a retrieval+synthesis call on a question it was never meant to
    answer.
    """
    classified = intent_mod.classify(question)
    if classified == intent_mod.RECORD_LOOKUP:
        return None
    return try_answer(question, conversation_context=conversation_context)


def build_all(only_customized=False) -> Dict:
    """Rebuild every provider's index. Providers with no index are no-ops."""
    results = {}
    for name in ("customization", "erp_docs", "implementation_docs"):
        p = _provider(name)
        kwargs = {"only_customized": only_customized} if name == "customization" else {}
        results[name] = p.build(**kwargs)
    return results
