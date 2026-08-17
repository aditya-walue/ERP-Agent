app_name = "erp_assistant"
app_title = "ERP Implementation Assistant"
app_publisher = "Codeyard"
app_description = "AI Implementation Assistant grounded in this Frappe instance. RAG, no training."
app_email = "tech@codeyard.app"
app_license = "MIT"

required_apps = ["frappe"]

# Vue chat app is bundled here by `bench build`; served on the Desk route.
app_include_js = ["erp_assistant.bundle.js"]

# Rebuild the implementation index nightly so answers track customizations.
scheduler_events = {
    "daily": [
        "erp_assistant.extractor.build_index",
    ],
}

# Build all provider indices once on install, so a fresh deploy answers
# HOWTO questions with grounded docs instead of falling through to an
# ungrounded LLM guess (see install.py).
after_install = "erp_assistant.install.after_install"
