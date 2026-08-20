import time

import requests
from langchain_core.embeddings import Embeddings
from google.genai import errors as genai_errors

import frappe

@frappe.whitelist(allow_guest=False)
def get_local_embedding(text: str):
    try:
        res = requests.post(
            "http://127.0.0.1:8001/embed",
            json={"text": text},
            timeout=30
        )
        res.raise_for_status()
        return res.json()["embedding"]
    except Exception as e:
        frappe.throw(f"Embedding service error :{str(e)}")

class LocalEmbeddingService(Embeddings):
    def embed_query(self, text: str) -> list[float]:
        return get_local_embedding(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [get_local_embedding(t) for t in texts]


# ---------------------------------------------------------------------------
# Gemini (hosted, free-tier) — no local model to download or run. Reuses the
# same cached client and Gemini API key as chat (clients.gemini_client(),
# fed from ChangAI Settings), so there is nothing new to configure. Batching
# and retry mirror erp_assistant/llm.py's _gemini_embed, the proven pattern
# already used for this same API elsewhere in this repo.
# ---------------------------------------------------------------------------

_GEMINI_EMBED_MODEL = "gemini-embedding-001"
_EMBED_CHAR_BUDGET = 20000
_EMBED_BATCH_MAX = 100
_EMBED_BATCH_DELAY = 1.0
_EMBED_MAX_RETRIES = 5


def _chunk_by_char_budget(texts, budget=_EMBED_CHAR_BUDGET, max_items=_EMBED_BATCH_MAX):
    batch, batch_chars = [], 0
    for t in texts:
        t = t or ""
        if batch and (batch_chars + len(t) > budget or len(batch) >= max_items):
            yield batch
            batch, batch_chars = [], 0
        batch.append(t)
        batch_chars += len(t)
    if batch:
        yield batch


def _quota_details(e: genai_errors.ClientError):
    """google-genai raises ClientError with the parsed Gemini error body
    already attached as .details (APIError.__init__ stores response_json
    there) — same violations/retryDelay payload erp_assistant's REST-based
    _is_daily_quota_exhausted/_retry_delay parse from raw JSON, just reached
    through the SDK's own attribute instead."""
    try:
        return (e.details or {}).get("error", {}).get("details", [])
    except Exception:
        return []


def _is_daily_quota_exhausted(e: genai_errors.ClientError) -> bool:
    violations = [
        v
        for d in _quota_details(e)
        if d.get("@type", "").endswith("QuotaFailure")
        for v in d.get("violations", [])
    ]
    if not violations:
        return False
    return all("PerDay" in v.get("quotaId", "") for v in violations)


def _retry_delay_seconds(e: genai_errors.ClientError, default: float = 20.0) -> float:
    for d in _quota_details(e):
        if d.get("@type", "").endswith("RetryInfo"):
            try:
                return float(str(d["retryDelay"]).rstrip("s"))
            except Exception:
                break
    return default


def _embed_batch(client, batch: list[str]) -> list[list[float]]:
    from changai.changai.api.v2.clients import _handle_gemini_api_exception

    last_error = None
    for attempt in range(_EMBED_MAX_RETRIES):
        try:
            resp = client.models.embed_content(model=_GEMINI_EMBED_MODEL, contents=batch)
            values = [e.values for e in resp.embeddings]
            if len(values) != len(batch):
                raise RuntimeError(
                    f"Gemini embed_content returned {len(values)} embeddings "
                    f"for {len(batch)} inputs — batch/response misaligned."
                )
            return values
        except genai_errors.ClientError as e:
            last_error = e
            if e.code != 429:
                _handle_gemini_api_exception(e)
            # A daily-quota 429 won't clear within any retry window this
            # process could reasonably wait out — fail fast instead of
            # burning the retry budget on a guaranteed repeat failure.
            if _is_daily_quota_exhausted(e):
                _handle_gemini_api_exception(e)
            if attempt < _EMBED_MAX_RETRIES - 1:
                time.sleep(_retry_delay_seconds(e) + 1)
                continue
            _handle_gemini_api_exception(e)
        except Exception as e:
            _handle_gemini_api_exception(e)
    _handle_gemini_api_exception(last_error)


class GeminiEmbeddingService(Embeddings):
    """Hosted Gemini embeddings — the langchain_core.Embeddings interface,
    so it's a drop-in for LocalEmbeddingService/HuggingFaceEmbeddings
    anywhere one of those is passed in (FAISS.from_texts, get_embedding_engine())."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from changai.changai.api.v2.clients import gemini_client

        client = gemini_client()
        out: list[list[float]] = []
        batches = list(_chunk_by_char_budget(texts))
        for idx, batch in enumerate(batches):
            out.extend(_embed_batch(client, batch))
            if idx < len(batches) - 1:
                time.sleep(_EMBED_BATCH_DELAY)
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]