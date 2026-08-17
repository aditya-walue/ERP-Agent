"""
Runs once, right after `bench install-app erp_assistant`. Without this, a
fresh deploy has no implementation_docs/erp_docs vector store on disk (see
vectorstore.py's exists() check), so every HOWTO question falls through to
an ungrounded LLM answer instead of the grounded one — the admin would have
to know to call api.rebuild_index manually before the assistant is usable.
"""

import frappe


def after_install():
    from erp_assistant.agent.orchestrator import build_all

    try:
        build_all()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "erp_assistant.install.after_install")
