"""
Provider 1 — Live Database.

Answers factual "what is / show / find" questions against real Frappe
records: Customer, Supplier, Sales Invoice, Purchase Order, Project, Task,
Employee, etc. No LLM-generated SQL here — deliberately: this provider only
ever calls `frappe.get_list()`, which enforces permissions natively, so a
misclassified or adversarial question can't be turned into an arbitrary
query. Precision over cleverness; the doctype/record matching is heuristic
and intentionally conservative — if it can't confidently resolve a doctype
it returns nothing rather than guessing.

If a more capable NL->SQL engine is installed (e.g. the `changai` app's
text2sql pipeline), wire it in here behind the same `retrieve()` contract —
this class is the seam for that upgrade, not a permanent ceiling.
"""

from typing import Dict, List, Optional

import frappe

from changai.changai.erp_assistant.agent.entities import (
    resolve_doctype,
    resolve_record_id,
)
from changai.changai.erp_assistant.providers.base import Chunk, Provider


class DatabaseProvider(Provider):
    name = "database"

    def is_ready(self):
        return True  # always "ready"; individual lookups may just find nothing

    def retrieve(self, question: str, *, k: int = 6, **kwargs) -> List[Chunk]:
        doctype = self._resolve_doctype(question)
        if not doctype:
            return []
        try:
            if not frappe.has_permission(doctype, "read"):
                return []
        except Exception:
            return []

        record_id = self._resolve_record_id(question, doctype)
        meta = frappe.get_meta(doctype)
        fields = self._display_fields(meta)

        try:
            if record_id:
                rows = frappe.get_list(
                    doctype,
                    filters={"name": record_id},
                    fields=fields,
                    limit=1,
                ) or frappe.get_list(
                    doctype,
                    filters={meta.title_field or "name": ["like", f"%{record_id}%"]},
                    fields=fields,
                    limit=k,
                )
            else:
                rows = frappe.get_list(
                    doctype,
                    fields=fields,
                    order_by="modified desc",
                    limit=k,
                )
        except Exception:
            frappe.log_error(frappe.get_traceback(), "erp_assistant.database_provider")
            return []

        return [self._row_to_chunk(doctype, r) for r in rows]

    # -- resolution helpers --------------------------------------------

    def _resolve_doctype(self, question: str) -> Optional[str]:
        return resolve_doctype(question)

    def _resolve_record_id(self, question: str, doctype: str) -> Optional[str]:
        return resolve_record_id(question, doctype)

    def _display_fields(self, meta) -> List[str]:
        fields = ["name"]
        if meta.title_field and meta.title_field not in fields:
            fields.append(meta.title_field)
        for df in meta.fields:
            if df.in_list_view and df.fieldname not in fields:
                fields.append(df.fieldname)
            if len(fields) >= 6:
                break
        return fields

    def _row_to_chunk(self, doctype: str, row: Dict) -> Chunk:
        lines = [f"{k}: {v}" for k, v in row.items() if v not in (None, "")]
        return Chunk(
            provider=self.name,
            title=f"{doctype} {row.get('name')}",
            text=f"{doctype} record:\n" + "\n".join(lines),
            score=1.0,
            citation={"doctype": doctype, "name": row.get("name")},
        )
