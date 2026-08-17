"""
Provider 5 — Code Search.

Used for Troubleshooting: searches installed apps' source (Python,
JavaScript, DocType/Workflow JSON) for the term the question is about, live,
at query time. Deliberately un-indexed — troubleshooting-relevant code
(validate hooks, client scripts) changes with every deploy, and a stale
search index for "why is this failing" is worse than a live grep that's
always accurate. Restricted to installed apps only, `.py`/`.js`/`.json`
files, skipping build output and dependency folders.
"""

import os
import re
import subprocess
from typing import List, Optional

import frappe

from erp_assistant.providers.base import Chunk, Provider

_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "public", "dist", "build", ".venv"}
_EXTS = (".py", ".js", ".json")
_MAX_MATCHES = 8
_CONTEXT_LINES = 2


class CodeSearchProvider(Provider):
    name = "code_search"

    def is_ready(self):
        return True

    def retrieve(self, question: str, *, k: int = 6, **kwargs) -> List[Chunk]:
        term = self._search_term(question)
        if not term:
            return []

        bench_path = frappe.utils.get_bench_path()
        apps = frappe.get_installed_apps()
        matches = []
        for app in apps:
            app_dir = os.path.join(bench_path, "apps", app)
            if not os.path.isdir(app_dir):
                continue
            matches.extend(self._search_app(app_dir, app, term))
            if len(matches) >= _MAX_MATCHES:
                break

        return [self._match_to_chunk(m) for m in matches[:k]]

    # -- term extraction -------------------------------------------------

    def _search_term(self, question: str) -> Optional[str]:
        # Prefer an explicit DocType name mentioned in the question.
        from erp_assistant.providers.database_provider import _SYNONYMS, _all_doctype_names

        q = question.lower()
        for key in sorted(_SYNONYMS, key=len, reverse=True):
            if key in q:
                return _SYNONYMS[key]
        for dt in _all_doctype_names():
            if dt.lower() in q:
                return dt
        # Fall back to the longest capitalized token (likely a doctype/status).
        words = [w.strip("?,.") for w in question.split()]
        candidates = [w for w in words if len(w) > 3 and w[0].isupper()]
        return max(candidates, key=len) if candidates else None

    # -- search ------------------------------------------------------------

    def _search_app(self, app_dir: str, app: str, term: str) -> List[dict]:
        results = self._search_with_ripgrep(app_dir, app, term)
        if results is not None:
            return results
        return self._search_with_walk(app_dir, app, term)

    def _search_with_ripgrep(self, app_dir: str, app: str, term: str):
        try:
            proc = subprocess.run(
                ["rg", "--line-number", "--no-heading", "--max-count", "2",
                 "--ignore-case", "-g", "*.py", "-g", "*.js", "-g", "*.json",
                 term, app_dir],
                capture_output=True, text=True, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

        if proc.returncode not in (0, 1):
            return None

        results = []
        for line in proc.stdout.splitlines()[:_MAX_MATCHES]:
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            path, lineno, content = parts
            results.append({
                "app": app, "path": path, "line": int(lineno),
                "snippet": content.strip()[:300],
            })
        return results

    def _search_with_walk(self, app_dir: str, app: str, term: str) -> List[dict]:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        results = []
        for root, dirs, files in os.walk(app_dir):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if not fname.endswith(_EXTS):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if pattern.search(line):
                                results.append({
                                    "app": app, "path": path, "line": i,
                                    "snippet": line.strip()[:300],
                                })
                                break  # one hit per file keeps this walk bounded
                except OSError:
                    continue
                if len(results) >= _MAX_MATCHES:
                    return results
        return results

    def _match_to_chunk(self, m: dict) -> Chunk:
        rel = m["path"]
        return Chunk(
            provider=self.name,
            title=f"{m['app']}:{rel}:{m['line']}",
            text=f"{rel} (line {m['line']}):\n{m['snippet']}",
            score=1.0,
            citation={"app": m["app"], "file": rel, "line": m["line"]},
        )
