"""
Generalized lightweight vector store — same numpy/npz approach as the
original single-collection rag.py, parametrized by collection name so each
knowledge provider can keep its own independent index under

    sites/<site>/private/files/erp_assistant/<collection>/{vectors.npz,cards.json}

No chromadb / faiss (fragile wheels on Python 3.14, and erp_assistant makes
no local-training or heavy-dependency promises). Retrieval is numpy cosine
similarity. Ranking boosts are the caller's responsibility (pass a
`boost_fn(meta) -> float` at retrieve time) so each provider can define its
own priority signal instead of this module hardcoding one.
"""

import json
import os

import numpy as np

import frappe
from changai.changai.erp_assistant import llm

_EMBED_CHAR_LIMIT = 8000


class VectorStore:
    def __init__(self, collection: str):
        self.collection = collection
        self._cache = {"matrix": None, "metas": None, "mtime": None}

    def _dir(self):
        path = frappe.get_site_path("private", "files", "erp_assistant", self.collection)
        os.makedirs(path, exist_ok=True)
        return path

    def _vec_path(self):
        return os.path.join(self._dir(), "vectors.npz")

    def _meta_path(self):
        return os.path.join(self._dir(), "cards.json")

    def exists(self):
        return os.path.exists(self._vec_path()) and os.path.exists(self._meta_path())

    def rebuild(self, items):
        """
        items: list of dicts, each with at least a "text" key. All other keys
        are stored as metadata and returned verbatim on retrieve.
        """
        texts = [it["text"][:_EMBED_CHAR_LIMIT] for it in items]
        if not texts:
            # Still write an empty index so exists() is stable and retrieve()
            # short-circuits instead of erroring on a missing file.
            np.savez_compressed(self._vec_path(), matrix=np.zeros((0, 0), dtype="float32"))
            with open(self._meta_path(), "w") as f:
                json.dump([], f)
            self._cache = {"matrix": None, "metas": None, "mtime": None}
            return 0

        vectors = llm.embed(texts)
        matrix = _normalize(np.asarray(vectors, dtype="float32"))

        np.savez_compressed(self._vec_path(), matrix=matrix)
        with open(self._meta_path(), "w") as f:
            json.dump(items, f)
        self._cache = {"matrix": None, "metas": None, "mtime": None}
        return len(items)

    def _load(self):
        if not self.exists():
            return None, None
        mtime = os.path.getmtime(self._vec_path())
        if self._cache["mtime"] != mtime:
            matrix = np.load(self._vec_path())["matrix"]
            with open(self._meta_path()) as f:
                metas = json.load(f)
            self._cache = {"matrix": matrix, "metas": metas, "mtime": mtime}
        return self._cache["matrix"], self._cache["metas"]

    def retrieve(self, query, k=6, boost_fn=None):
        matrix, metas = self._load()
        if matrix is None or matrix.shape[0] == 0:
            return []

        qvec = llm.embed([query])[0]
        qvec = _normalize(np.asarray([qvec], dtype="float32"))[0]

        scores = matrix @ qvec
        if boost_fn:
            scores = scores + np.array([boost_fn(m) for m in metas], dtype="float32")

        order = np.argsort(-scores)[:k]
        return [{**metas[i], "score": float(scores[i])} for i in order]


def _normalize(matrix):
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms
