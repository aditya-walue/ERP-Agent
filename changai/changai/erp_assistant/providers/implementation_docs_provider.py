"""
Provider 3 — Implementation Documentation.

Company-specific SOPs, implementation guides, wiki exports — anything an
admin drops (as .md/.txt, see ingestion/doc_loader.py for adding PDF etc.)
into:

    sites/<site>/private/files/erp_assistant_docs/

Empty by default on a fresh install. `is_ready()` reflects that honestly so
the router/orchestrator can apply the fallback rule ("no implementation
documentation was found, answering from standard ERPNext instead") instead
of silently returning nothing.
"""

from typing import List

import frappe

from changai.changai.erp_assistant.ingestion.doc_loader import load_folder
from changai.changai.erp_assistant.providers.base import Chunk, Provider
from changai.changai.erp_assistant.vectorstore import VectorStore

_COLLECTION = "implementation_docs"


def _source_folder():
    return frappe.get_site_path("private", "files", "erp_assistant_docs")


class ImplementationDocsProvider(Provider):
    name = "implementation_docs"

    def __init__(self):
        self.store = VectorStore(_COLLECTION)

    def is_ready(self):
        return self.store.exists()

    def retrieve(self, question: str, *, k: int = 6, **kwargs) -> List[Chunk]:
        if not self.store.exists():
            return []
        results = self.store.retrieve(question, k=k)
        return [
            Chunk(
                provider=self.name,
                title=r["title"],
                text=r["text"],
                score=r["score"],
                citation={"source": r.get("source"), "doc": r["title"]},
            )
            for r in results
        ]

    def build(self, **kwargs):
        items = load_folder(_source_folder())
        n = self.store.rebuild(items)
        return {"provider": self.name, "indexed": n, "folder": _source_folder()}
