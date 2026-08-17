"""
Routing table: intent -> ordered providers, each tagged with a role.

    primary            required for this intent; result count feeds the
                        fallback rule directly.
    primary_fallback    only consulted if no `primary` chunks were found —
                        this is how HOWTO "fall back to standard ERPNext
                        when no implementation docs exist" is expressed as
                        data instead of as a special case in the
                        orchestrator.
    supplement          always queried (when the intent uses it) and always
                        appended if it returns anything, regardless of what
                        the primary providers found — this is how "Required
                        Fields / Custom Fields / Workflow Notes" get filled
                        in on top of a How-To answer.

This table is the entire routing algorithm. To change what a given intent
searches, edit the list here — orchestrator.py has no per-intent branching.
"""

from erp_assistant.agent.intent import (
    DEFINITION,
    HOWTO,
    RECORD_LOOKUP,
    TROUBLESHOOTING,
    WORKFLOW,
)

PRIMARY = "primary"
PRIMARY_FALLBACK = "primary_fallback"
SUPPLEMENT = "supplement"

ROUTES = {
    # "What is the customer name?" -> live data, nothing else.
    RECORD_LOOKUP: [
        ("database", PRIMARY),
    ],
    # "How do I create a Sales Invoice?" -> our SOPs first; if we don't have
    # any, standard ERPNext procedure; either way, append any custom-field /
    # workflow notes so the answer reflects this implementation.
    HOWTO: [
        ("implementation_docs", PRIMARY),
        ("erp_docs", PRIMARY_FALLBACK),
        ("customization", SUPPLEMENT),
    ],
    # "Why can't I submit this Sales Invoice?" -> whatever actually enforces
    # behavior: workflow config + validate hooks, then raw source.
    TROUBLESHOOTING: [
        ("customization", PRIMARY),
        ("code_search", PRIMARY),
    ],
    # "What is a BOM?" -> standard definition, with our customizations noted
    # if the doctype has any.
    DEFINITION: [
        ("erp_docs", PRIMARY),
        ("customization", SUPPLEMENT),
    ],
    # "What is the approval flow for Purchase Invoice?" -> our workflow
    # config is the answer; standard docs only as a supplement.
    WORKFLOW: [
        ("customization", PRIMARY),
        ("erp_docs", SUPPLEMENT),
    ],
}


def routes_for(intent: str):
    return ROUTES.get(intent, ROUTES[RECORD_LOOKUP])
