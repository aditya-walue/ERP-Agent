"""
Lightweight vector store.

No chromadb (fragile wheels on Python 3.14). The whole index is a single
in-site file: an .npz of embeddings + a JSON sidecar of card metadata.
Retrieval is numpy cosine similarity with a ranking boost for customized
doctypes, matching the "implementation first" priority of the ROLE prompt.
"""

import json
import os

import numpy as np

import frappe
from erp_assistant import extractor, llm

# Cards longer than this are truncated before embedding (protects the embed
# model's context; the full text is still stored for the LLM prompt).
_EMBED_CHAR_LIMIT = 8000

# Extra cosine score added to customized doctypes so OUR implementation wins
# ties against generic ERPNext doctypes.
_CUSTOM_BOOST = 0.05


def _index_dir():
    path = frappe.get_site_path("private", "files", "erp_assistant")
    os.makedirs(path, exist_ok=True)
    return path


def _vec_path():
    return os.path.join(_index_dir(), "vectors.npz")


def _meta_path():
    return os.path.join(_index_dir(), "cards.json")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def rebuild(cards):
    """Embed every card and overwrite the on-disk index."""
    texts, metas = [], []
    for card in cards:
        text = extractor.card_to_text(card)
        texts.append(text[:_EMBED_CHAR_LIMIT])
        metas.append({
            "doctype": card["doctype"],
            "app": card.get("app"),
            "is_customized": card["is_customized"],
            "text": text,
        })

    vectors = llm.embed(texts)  # -> list[list[float]]
    matrix = np.asarray(vectors, dtype="float32")
    matrix = _normalize(matrix)

    np.savez_compressed(_vec_path(), matrix=matrix)
    with open(_meta_path(), "w") as f:
        json.dump(metas, f)
    return len(metas)


def _normalize(matrix):
    if matrix.ndim != 2:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------

_CACHE = {"matrix": None, "metas": None, "mtime": None}


def _load():
    if not (os.path.exists(_vec_path()) and os.path.exists(_meta_path())):
        return None, None
    mtime = os.path.getmtime(_vec_path())
    if _CACHE["mtime"] != mtime:
        _CACHE["matrix"] = np.load(_vec_path())["matrix"]
        with open(_meta_path()) as f:
            _CACHE["metas"] = json.load(f)
        _CACHE["mtime"] = mtime
    return _CACHE["matrix"], _CACHE["metas"]


def retrieve(query, k=6, allowed_doctypes=None):
    """
    Return up to k cards most relevant to `query`, most relevant first.

    allowed_doctypes: if given, restrict results to this set (permission filter).
    Each result: {doctype, app, is_customized, text, score}.
    """
    matrix, metas = _load()
    if matrix is None:
        return []

    qvec = llm.embed([query])[0]
    qvec = _normalize(np.asarray([qvec], dtype="float32"))[0]

    scores = matrix @ qvec  # cosine (both normalized)
    boost = np.array(
        [_CUSTOM_BOOST if m["is_customized"] else 0.0 for m in metas],
        dtype="float32",
    )
    scores = scores + boost

    order = np.argsort(-scores)
    results = []
    for idx in order:
        meta = metas[idx]
        if allowed_doctypes is not None and meta["doctype"] not in allowed_doctypes:
            continue
        results.append({**meta, "score": float(scores[idx])})
        if len(results) >= k:
            break
    return results


def index_exists():
    return os.path.exists(_vec_path()) and os.path.exists(_meta_path())
