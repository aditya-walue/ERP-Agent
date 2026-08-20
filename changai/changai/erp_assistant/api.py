"""
Whitelisted API for the Vue chat frontend.

Flow: classify intent -> route to knowledge providers -> retrieve
(permission-filtered) -> synthesize with the configured LLM -> return answer
+ citations. See erp_assistant/agent/orchestrator.py for the pipeline itself
— this module is intentionally thin, just the whitelist boundary.
"""

import frappe

from changai.changai.erp_assistant.agent import orchestrator


@frappe.whitelist()
def ask_agent(question, conversation_context=None):
    return orchestrator.ask_agent(question, conversation_context=conversation_context)


@frappe.whitelist()
def index_status():
    """Per-provider index status for the frontend/admin."""
    from changai.changai.erp_assistant import rag
    from changai.changai.erp_assistant.providers.erp_docs_provider import ERPDocsProvider
    from changai.changai.erp_assistant.providers.implementation_docs_provider import ImplementationDocsProvider

    return {
        "customization": rag.index_exists(),
        "erp_docs": ERPDocsProvider().is_ready(),
        "implementation_docs": ImplementationDocsProvider().is_ready(),
        # Backward-compatible key some older frontend builds may still read.
        "index_exists": rag.index_exists(),
    }


@frappe.whitelist()
def rebuild_index(only_customized=0):
    """Admin-triggered reindex of every provider. System Manager only."""
    frappe.only_for("System Manager")
    return orchestrator.build_all(only_customized=bool(int(only_customized)))
