"""
Document loaders for the doc-backed providers (ERP Documentation,
Implementation Documentation). Each loader turns a source file into one or
more {"title", "text", "source"} chunks ready to embed.

Extensibility point: to add a new source format (PDF, Confluence export,
Notion export, ...) write one function here with the same signature —
`load_<kind>(path) -> list[dict]` — and register its extension in
`load_folder`. Nothing else in the ingestion or retrieval path needs to
change; providers just call `load_folder()`.
"""

import os
from typing import Dict, List

_CHUNK_CHARS = 1500


def load_folder(folder: str) -> List[Dict]:
    """Load every supported file under `folder` (non-recursive extension
    dispatch, recursive walk) into chunks. Unreadable/unsupported files are
    skipped, not fatal — a bad file shouldn't block indexing the rest."""
    if not os.path.isdir(folder):
        return []

    chunks = []
    for root, _dirs, files in os.walk(folder):
        for fname in sorted(files):
            path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            try:
                if ext in (".md", ".markdown", ".txt"):
                    chunks.extend(_load_markdown(path))
                elif ext == ".pdf":
                    chunks.extend(_load_pdf(path))
                # else: silently skip unsupported extensions
            except Exception:
                import frappe
                frappe.log_error(frappe.get_traceback(), f"erp_assistant.doc_loader:{path}")
    return chunks


def _load_markdown(path: str) -> List[Dict]:
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    title = os.path.splitext(os.path.basename(path))[0].replace("_", " ").replace("-", " ")
    return _chunk_text(title, text, path)


def _load_pdf(path: str) -> List[Dict]:
    # Not implemented: no PDF-parsing dependency is bundled with
    # erp_assistant (kept dependency-light: numpy + requests only). Drop a
    # .md/.txt export of the PDF into the same folder instead, or extend
    # this function with a PDF library of your choice — the rest of the
    # pipeline (chunking, embedding, retrieval) needs no changes.
    import frappe
    frappe.log_error(
        f"PDF source skipped (no PDF loader configured): {path}",
        "erp_assistant.doc_loader",
    )
    return []


def _chunk_text(title: str, text: str, source: str) -> List[Dict]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= _CHUNK_CHARS:
        return [{"title": title, "text": text, "source": source}]

    # Split on paragraph boundaries, packing greedily up to _CHUNK_CHARS.
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for p in paragraphs:
        if current and len(current) + len(p) + 2 > _CHUNK_CHARS:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)

    return [
        {"title": f"{title} (part {i + 1})" if len(chunks) > 1 else title,
         "text": c, "source": source}
        for i, c in enumerate(chunks)
    ]
