"""
Intent classification — runs before any retrieval happens. The whole point
is that a How-To question must never fall into a database search (and vice
versa), so this has to decide *before* the router picks providers, not after.

Hybrid: a regex fast-path handles the clear cases (covers every example in
the spec this module was built against) with zero model calls. Only
genuinely ambiguous questions fall through to a one-shot LLM classification
call. This keeps the common path fast/free and keeps the classifier honest
about what it's actually confident in.
"""

import re
from typing import Optional

RECORD_LOOKUP = "record_lookup"
HOWTO = "howto"
TROUBLESHOOTING = "troubleshooting"
DEFINITION = "definition"
WORKFLOW = "workflow"

_ALL_INTENTS = {RECORD_LOOKUP, HOWTO, TROUBLESHOOTING, DEFINITION, WORKFLOW}

# Order matters: first matching rule wins. Troubleshooting and workflow
# phrasing is checked before the generic "what is" DEFINITION/RECORD_LOOKUP
# split so "why is Project not saving" doesn't get caught by anything else.
_RULES = [
    (TROUBLESHOOTING, re.compile(
        r"\b(why can'?t|why cant|why is|why does|why won'?t|not working|"
        r"(?:can'?t|cannot|unable to|not able to|cannot able to) "
        r"(?:submit|save|create|delete|update|cancel|approve)|"
        r"won'?t save|not saving|is failing|"
        r"keeps failing|throwing an error|error when)\b", re.I)),
    (WORKFLOW, re.compile(
        r"\b(approval flow|what happens after|next stage|who approves|"
        r"approval process|workflow (for|of)|approval work|"
        r"approval works|how does .+ approval)\b", re.I)),
    (HOWTO, re.compile(
        r"^\s*(how do i|how to|how can i|how does one|steps to|guide to|"
        r"process for creating|how do you)\b", re.I)),
    # "what is a/an X" -> definition (indefinite article: asking about a
    # concept). "what is the X" -> record lookup (definite article: asking
    # about a specific field/value in context). This is the one place the
    # spec's own examples disagree only in article, so it's matched first.
    (DEFINITION, re.compile(r"^\s*what\s+(is|are)\s+an?\b", re.I)),
    # Implementation/configuration meta-questions ("what customizations are in
    # this system?", "what custom fields/scripts exist", "how is X configured").
    # These are exactly what erp_assistant's customization provider answers, but
    # they'd otherwise fall through to record_lookup and never hand off.
    (DEFINITION, re.compile(
        r"\b(customi[sz]ations?|custom fields?|custom scripts?|client scripts?|"
        r"server scripts?|property setters?|customi[sz]ed|automations?)\b|"
        r"\bwhat.*(implemented|configured|customi[sz]ed|set ?up)\b|"
        r"\bhow (is|are|was|were) .+(configured|customi[sz]ed|set ?up)\b", re.I)),
]

_RECORD_HINTS = re.compile(
    r"\b(show|find|list|who owns|what is the|status of|lookup)\b", re.I
)


def classify(question: str, *, llm_fallback=True) -> str:
    q = (question or "").strip()
    if not q:
        return RECORD_LOOKUP

    for intent, pattern in _RULES:
        if pattern.search(q):
            return intent

    if _RECORD_HINTS.search(q):
        return RECORD_LOOKUP

    # Bare "what is X" with no article info and no record hint — ambiguous
    # between DEFINITION and RECORD_LOOKUP. Try the LLM; if that's not
    # available/fails, default to RECORD_LOOKUP (matches the spec's own
    # first example) rather than guessing DEFINITION.
    if llm_fallback:
        guess = _llm_classify(q)
        if guess:
            return guess

    return RECORD_LOOKUP


def _llm_classify(question: str) -> Optional[str]:
    from erp_assistant import llm

    prompt = (
        "Classify this ERP assistant question into exactly one label:\n"
        "record_lookup, howto, troubleshooting, definition, workflow.\n"
        "Reply with ONLY the label, nothing else.\n\n"
        f"Question: {question}"
    )
    try:
        raw = llm.chat(
            "You are a strict intent classifier. Reply with exactly one "
            "label and nothing else.",
            prompt,
        )
    except Exception:
        return None

    label = (raw or "").strip().lower().strip(".")
    return label if label in _ALL_INTENTS else None
