"""
DocType/record-ID resolution from a raw question — a heuristic (synonym
table + real-DocType-name scan, regex for record IDs), not an LLM guess.
Shared by DatabaseProvider (record_lookup) and the troubleshooting planner
(which needs the same doctype/record extraction when the planning LLM call
doesn't resolve one, or as the primary path if JSON parsing fails).
"""

import re
from typing import Dict, List, Optional

import frappe

# A few high-traffic synonyms so "customer", "invoice", "PO" resolve without
# needing an exact DocType name. Extend freely; this is not exhaustive by
# design — the fallback below matches against real DocType names too.
_SYNONYMS = {
    "customer": "Customer",
    "customers": "Customer",
    "supplier": "Supplier",
    "suppliers": "Supplier",
    "vendor": "Supplier",
    "invoice": "Sales Invoice",
    "sales invoice": "Sales Invoice",
    "purchase invoice": "Purchase Invoice",
    "purchase order": "Purchase Order",
    "po": "Purchase Order",
    "sales order": "Sales Order",
    "so": "Sales Order",
    "quotation": "Quotation",
    "project": "Project",
    "task": "Task",
    "employee": "Employee",
    "lead": "Lead",
    "opportunity": "Opportunity",
    "item": "Item",
    "warehouse": "Warehouse",
    "payment": "Payment Entry",
    "payment entry": "Payment Entry",
}

_ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*-[A-Z0-9-]+\b")

_DOCTYPE_CACHE = {"names": None}


def _all_doctype_names() -> List[str]:
    if _DOCTYPE_CACHE["names"] is None:
        _DOCTYPE_CACHE["names"] = frappe.get_all("DocType", pluck="name")
    return _DOCTYPE_CACHE["names"]


def resolve_doctype(question: str) -> Optional[str]:
    q = question.lower()
    # Longest synonym key first so "sales invoice" beats "invoice".
    for key in sorted(_SYNONYMS, key=len, reverse=True):
        if key in q:
            return _SYNONYMS[key]

    # Fall back to a direct scan of real DocType names mentioned verbatim.
    for dt in _all_doctype_names():
        if dt.lower() in q:
            return dt
    return None


def resolve_record_id(question: str, doctype: str) -> Optional[str]:
    m = _ID_PATTERN.search(question)
    if m:
        return m.group(0)
    # e.g. "show customer TEST" / "who owns project ABC" -> trailing
    # capitalized token that isn't itself the doctype name.
    words = question.replace("?", "").split()
    for w in reversed(words):
        if w.isupper() and len(w) > 1 and w.upper() != doctype.upper():
            return w
    return None
