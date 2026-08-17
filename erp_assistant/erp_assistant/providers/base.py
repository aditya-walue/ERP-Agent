"""
Provider interface. Every knowledge source the agent can consult — live
database, ERPNext documentation, implementation SOPs, customizations, code
search — implements this one contract. The router only ever talks to
`Provider.retrieve()`; it does not know or care how a given provider finds
its answers. Adding a new knowledge source means writing one class here and
registering it in `agent/router.py` — nothing else in the pipeline changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Chunk:
    """One retrieved piece of evidence, normalized across all providers."""

    provider: str          # provider.name that produced this chunk
    title: str              # short human label, e.g. doctype name or doc title
    text: str                # the actual content shown to the LLM
    score: float = 0.0       # 0..1-ish relevance score (providers don't need to
                              # be perfectly calibrated against each other; the
                              # router treats providers as a priority waterfall,
                              # not a single merged ranking — see router.py)
    citation: Dict[str, Any] = field(default_factory=dict)  # shown to the user


class Provider(ABC):
    #: short machine name, used in routing tables and citations
    name: str = "base"

    @abstractmethod
    def retrieve(self, question: str, *, k: int = 6, **kwargs) -> List[Chunk]:
        """Return up to k relevant Chunks for `question`, best first."""
        raise NotImplementedError

    def build(self, **kwargs) -> Dict[str, Any]:
        """
        Optional: (re)build this provider's index. Providers that need no
        indexing (live DB, code search) can leave this as a no-op.
        """
        return {"provider": self.name, "indexed": 0, "note": "no index needed"}

    def is_ready(self) -> bool:
        """Whether this provider has anything to retrieve from right now."""
        return True
