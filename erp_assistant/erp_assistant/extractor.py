"""
Knowledge extractor.

Reads live metadata for every doctype across every installed app and emits one
"implementation card" per doctype: fields, custom fields, property setters,
client/server scripts, workflow, notifications, permissions, plus an
`is_customized` flag used to boost retrieval ranking.

No model training happens anywhere. This is the sole source of ERP-specific
knowledge; re-run `build_index` after customizing the ERP.
"""

import json

import frappe


# ---------------------------------------------------------------------------
# Per-source collectors. Each returns plain dicts/lists so a card is JSON-safe.
# ---------------------------------------------------------------------------

def _fields(meta):
    out = []
    for df in meta.fields:
        if df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
            continue
        out.append({
            "fieldname": df.fieldname,
            "label": df.label,
            "fieldtype": df.fieldtype,
            "options": df.options,
            "reqd": bool(df.reqd),
            "read_only": bool(df.read_only),
            "depends_on": df.depends_on,
            "is_custom": bool(getattr(df, "is_custom_field", 0)),
        })
    return out


def _custom_fields(doctype):
    return frappe.get_all(
        "Custom Field",
        filters={"dt": doctype},
        fields=["fieldname", "label", "fieldtype", "options", "reqd",
                "depends_on", "insert_after"],
    )


def _property_setters(doctype):
    return frappe.get_all(
        "Property Setter",
        filters={"doc_type": doctype},
        fields=["field_name", "property", "value", "property_type"],
    )


def _client_scripts(doctype):
    return frappe.get_all(
        "Client Script",
        filters={"dt": doctype, "enabled": 1},
        fields=["name", "view", "script"],
    )


def _server_scripts(doctype):
    return frappe.get_all(
        "Server Script",
        filters={"reference_doctype": doctype, "disabled": 0},
        fields=["name", "script_type", "doctype_event", "script"],
    )


def _workflow(doctype):
    wf_name = frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1})
    if not wf_name:
        return None
    wf = frappe.get_doc("Workflow", wf_name)
    return {
        "name": wf.name,
        "states": [
            {"state": s.state, "doc_status": s.doc_status,
             "allow_edit": s.allow_edit}
            for s in wf.states
        ],
        "transitions": [
            {"state": t.state, "action": t.action,
             "next_state": t.next_state, "allowed": t.allowed}
            for t in wf.transitions
        ],
    }


def _notifications(doctype):
    return frappe.get_all(
        "Notification",
        filters={"document_type": doctype, "enabled": 1},
        fields=["name", "subject", "channel", "event"],
    )


def _permissions(doctype):
    """Merged standard + custom docperms, keyed by role."""
    perms = frappe.get_all(
        "Custom DocPerm",
        filters={"parent": doctype},
        fields=["role", "read", "write", "create", "delete", "submit",
                "cancel", "amend"],
    )
    if not perms:
        perms = frappe.get_all(
            "DocPerm",
            filters={"parent": doctype},
            fields=["role", "read", "write", "create", "delete", "submit",
                    "cancel", "amend"],
        )
    return perms


# ---------------------------------------------------------------------------
# Card assembly
# ---------------------------------------------------------------------------

def build_card(doctype):
    """Build one implementation card. Returns None if the doctype is unreadable."""
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return None

    custom_fields = _custom_fields(doctype)
    property_setters = _property_setters(doctype)
    client_scripts = _client_scripts(doctype)
    server_scripts = _server_scripts(doctype)
    workflow = _workflow(doctype)
    notifications = _notifications(doctype)

    is_customized = bool(
        custom_fields or property_setters or client_scripts
        or server_scripts or workflow or getattr(meta, "custom", 0)
    )

    dt_meta = frappe.db.get_value(
        "DocType", doctype,
        ["module", "custom", "issingle", "is_submittable", "description"],
        as_dict=True,
    ) or {}

    return {
        "doctype": doctype,
        "module": dt_meta.get("module"),
        "app": _app_for_module(dt_meta.get("module")),
        "description": dt_meta.get("description"),
        "is_custom_doctype": bool(dt_meta.get("custom")),
        "is_single": bool(dt_meta.get("issingle")),
        "is_submittable": bool(dt_meta.get("is_submittable")),
        "is_customized": is_customized,
        "fields": _fields(meta),
        "custom_fields": custom_fields,
        "property_setters": property_setters,
        "client_scripts": client_scripts,
        "server_scripts": server_scripts,
        "workflow": workflow,
        "notifications": notifications,
        "permissions": _permissions(doctype),
    }


_MODULE_APP_CACHE = {}


def _app_for_module(module):
    if not module:
        return None
    if module in _MODULE_APP_CACHE:
        return _MODULE_APP_CACHE[module]
    app = frappe.db.get_value("Module Def", module, "app_name")
    _MODULE_APP_CACHE[module] = app
    return app


def card_to_text(card):
    """Flatten a card into the text blob that gets embedded + shown to the LLM."""
    lines = [f"# {card['doctype']}"]
    if card.get("module"):
        lines.append(f"Module: {card['module']} (app: {card.get('app')})")
    if card.get("description"):
        lines.append(f"Description: {card['description']}")
    flags = []
    if card["is_custom_doctype"]:
        flags.append("custom doctype")
    if card["is_submittable"]:
        flags.append("submittable")
    if card["is_single"]:
        flags.append("single")
    if flags:
        lines.append("Flags: " + ", ".join(flags))

    mandatory = [f["label"] or f["fieldname"] for f in card["fields"] if f["reqd"]]
    if mandatory:
        lines.append("Mandatory fields: " + ", ".join(mandatory))

    if card["custom_fields"]:
        cf = ", ".join(
            f"{c['label'] or c['fieldname']} ({c['fieldtype']}"
            + (", mandatory" if c.get("reqd") else "") + ")"
            for c in card["custom_fields"]
        )
        lines.append("Custom fields: " + cf)

    for ps in card["property_setters"]:
        target = f".{ps['field_name']}" if ps.get("field_name") else ""
        lines.append(
            f"Override: {card['doctype']}{target} {ps['property']} = {ps['value']}"
        )

    for cs in card["client_scripts"]:
        lines.append(f"Client Script '{cs['name']}' ({cs['view']}):\n{cs['script']}")

    for ss in card["server_scripts"]:
        lines.append(
            f"Server Script '{ss['name']}' [{ss['script_type']} / "
            f"{ss.get('doctype_event')}]:\n{ss['script']}"
        )

    wf = card["workflow"]
    if wf:
        states = ", ".join(s["state"] for s in wf["states"])
        trans = "; ".join(
            f"{t['state']} --{t['action']}--> {t['next_state']} (role: {t['allowed']})"
            for t in wf["transitions"]
        )
        lines.append(f"Workflow '{wf['name']}'. States: {states}. Transitions: {trans}")

    for n in card["notifications"]:
        lines.append(f"Notification '{n['name']}' on {n['event']} via {n['channel']}")

    if card["permissions"]:
        perm = "; ".join(
            f"{p['role']}(" + ",".join(
                k for k in ("read", "write", "create", "delete", "submit", "cancel", "amend")
                if p.get(k)
            ) + ")"
            for p in card["permissions"]
        )
        lines.append("Permissions: " + perm)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def extract_all(only_customized=False):
    """Yield cards for every doctype. Slow doctypes are skipped gracefully."""
    doctypes = frappe.get_all("DocType", pluck="name")
    cards = []
    for dt in doctypes:
        card = build_card(dt)
        if not card:
            continue
        if only_customized and not card["is_customized"]:
            continue
        cards.append(card)
    return cards


def build_index(only_customized=False):
    """Extract every card, embed it, and (re)write the vector store."""
    from erp_assistant import rag

    cards = extract_all(only_customized=only_customized)
    rag.rebuild(cards)
    frappe.logger("erp_assistant").info(
        f"Indexed {len(cards)} implementation cards "
        f"({sum(1 for c in cards if c['is_customized'])} customized)"
    )
    return {"indexed": len(cards)}
