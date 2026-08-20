"""
Provider 4 — Customizations.

Thin adapter over the original erp_assistant retrieval (extractor.py +
rag.py): custom fields, property setters, client/server scripts, workflows,
notifications, permissions, keyed per DocType. Unchanged behavior — this
class exists only so the orchestrator can address it through the common
Provider interface alongside the newer providers. Existing indexes built via
the old `erp_assistant.extractor.build_index` keep working as-is.
"""

from typing import List

from changai.changai.erp_assistant import extractor, rag
from changai.changai.erp_assistant.providers.base import Chunk, Provider

_CUSTOM_BOOST = 0.05


class CustomizationProvider(Provider):
    name = "customization"

    def is_ready(self):
        return rag.index_exists()

    def retrieve(self, question: str, *, k: int = 6, **kwargs) -> List[Chunk]:
        if not rag.index_exists():
            return []
        results = rag.retrieve(question, k=k)
        return [
            Chunk(
                provider=self.name,
                title=r["doctype"],
                text=r["text"],
                score=r["score"],
                citation={
                    "doctype": r["doctype"],
                    "app": r.get("app"),
                    "is_customized": r["is_customized"],
                },
            )
            for r in results
        ]

    def build(self, only_customized=False, **kwargs):
        cards = extractor.extract_all(only_customized=only_customized)
        rag.rebuild(cards)
        return {"provider": self.name, "indexed": len(cards)}
