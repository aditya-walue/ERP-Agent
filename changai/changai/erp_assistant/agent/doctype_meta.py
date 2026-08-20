"""
Real DocType metadata checks — ground truth via `frappe.get_meta`, never an
LLM guess. Shared between changai's CUD insert path (operations.py) and the
troubleshooting planner's mandatory_fields_check tool.
"""

from typing import List

import frappe


def missing_mandatory_fields(doctype: str, data: dict) -> List[str]:
    """
    Mandatory fields the given `data` doesn't cover. Calling doc.insert()
    without this check burns a naming-series number and raises a raw
    "[Doctype, PROJ-0001]: field_name" error on the first missing mandatory
    field it hits — e.g. a natural-language "how to create a new project?"
    that the CUD path misreads as a create command with no extracted field
    values ends up silently attempting an insert with an empty dict. Check
    up front instead so the caller can ask for the missing info rather than
    fail into a confusing error after already reserving a document name.

    Also used (against an existing record's actual field values, not a
    create-time draft) by the troubleshooting planner's
    mandatory_fields_check tool to explain a failed submit.
    """
    meta = frappe.get_meta(doctype)
    missing = []
    for field in meta.fields:
        if not field.reqd:
            continue
        if field.fieldtype in ("Table", "Table MultiSelect"):
            continue
        if field.default:
            continue
        # read_only mandatory fields (e.g. Sales Invoice's grand_total,
        # base_net_total) are computed by the doctype's own controller
        # during insert/validate, never typed by a user — flagging them as
        # "missing" would block inserts that Frappe itself would complete
        # fine once the real fields are filled in.
        if field.read_only:
            continue
        value = data.get(field.fieldname)
        if value in (None, ""):
            missing.append(field.fieldname)
    return missing
