"""
Provider 2 — ERP Documentation.

Standard ERPNext how-to / definition knowledge — deliberately independent of
this site's customizations (Provider 4 covers those). Ships with a small
seed set under `erp_assistant/seeds/erp_docs/` covering the highest-traffic
how-tos (Sales Invoice, Purchase Order, Project, Stock Receipt, BOM) so
How-To questions work out of the box instead of depending on an admin
uploading anything first. Extend by dropping more .md files in that folder
and calling `build()` again.
"""

import os
from typing import List

from changai.changai.erp_assistant.ingestion.doc_loader import load_folder
from changai.changai.erp_assistant.providers.base import Chunk, Provider
from changai.changai.erp_assistant.vectorstore import VectorStore

_COLLECTION = "erp_docs"


def _seed_folder():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "seeds", "erp_docs")


class ERPDocsProvider(Provider):
    name = "erp_docs"

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
                citation={"source": "ERPNext standard documentation", "doc": r["title"]},
            )
            for r in results
        ]

    def build(self, extra_folders=None, **kwargs):
        items = load_folder(_seed_folder())
        for folder in extra_folders or []:
            items.extend(load_folder(folder))
        n = self.store.rebuild(items)
        return {"provider": self.name, "indexed": n}
