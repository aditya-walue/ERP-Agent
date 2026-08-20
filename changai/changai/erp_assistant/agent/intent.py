"""
Intent classification — runs before any retrieval happens. The whole point
is that a How-To question must never fall into a database search (and vice
versa), so this has to decide *before* the router picks providers, not after.

Classification is delegated entirely to the LLM rather than a hand-written
table of regex/keyword rules. A fixed rule table can't be kept in sync with
every real way a question gets phrased — statement-style requests like
"want to create a new Project" don't match question-style rules written for
"how do I create a Project?", so they silently fell through to
record_lookup and got a dead-end "no information" answer instead of real
how-to guidance. One classification call per question keeps this correct
by construction instead of accumulating one-off patterns for every phrasing
someone eventually tries.
"""

from typing import Optional

RECORD_LOOKUP = "record_lookup"
HOWTO = "howto"
TROUBLESHOOTING = "troubleshooting"
DEFINITION = "definition"
WORKFLOW = "workflow"

_ALL_INTENTS = {RECORD_LOOKUP, HOWTO, TROUBLESHOOTING, DEFINITION, WORKFLOW}


def classify(question: str) -> str:
    q = (question or "").strip()
    if not q:
        return RECORD_LOOKUP

    # RECORD_LOOKUP is the safe default if the model is unavailable or
    # returns something unrecognized — not a routing rule, just what
    # happens when there's no classification to act on.
    return _llm_classify(q) or RECORD_LOOKUP


def _llm_classify(question: str) -> Optional[str]:
    from changai.changai.erp_assistant import llm

    # A bare label list with no definitions was ambiguous on the exact case
    # this classifier most needs to get right: "how to create a new Task?"
    # mentions a real DocType (Task), so with no other guidance the model
    # would read it as a data query and classify it record_lookup — sending
    # it into a live SQL query for existing Task rows instead of explaining
    # how to create one. The mention of a real DocType name is not itself
    # evidence of a data query; what the user is asking FOR is.
    prompt = (
        "Classify this ERP assistant question into exactly one label:\n\n"
        "record_lookup — asking for the value(s) of an EXISTING record: "
        "\"what is\", \"show me\", \"list\", \"how many\", \"who owns\". "
        "The question wants data back.\n"
        "howto — asking how to DO something (create/update/submit/configure "
        "a record), whether phrased as a question (\"how do I create a "
        "Sales Order?\") or a statement (\"I want to create a Task\", "
        "\"create a new Project\"). The question wants steps/instructions "
        "back, not data. Mentioning a real DocType name (Task, Project, "
        "Sales Order, ...) does NOT make it record_lookup — what matters is "
        "whether the user wants data about existing records, or wants to "
        "know how to perform an action.\n"
        "troubleshooting — something isn't working / an error occurred / "
        "why can't I do X.\n"
        "definition — what IS a concept (asking about the concept in "
        "general, not a specific record's value).\n"
        "workflow — asking about an approval flow or what happens after a "
        "state transition.\n\n"
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
