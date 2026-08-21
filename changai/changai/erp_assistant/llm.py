"""
Provider-pluggable LLM + embeddings client.

No model training. The model is used off-the-shelf; ERP knowledge is supplied at
inference time via the retrieved cards. Provider + models default from
site_config.json under the "erp_assistant" key, e.g.:

    "erp_assistant": {
        "provider": "ollama",
        "chat_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "ollama_url": "http://localhost:11434"
    }

The Gemini API key itself is never hardcoded here or in site_config — it's
read from ERP Assistant Settings (single doctype, Desk UI), the one place this repo
already has a UI-editable Gemini key. See _changai_gemini_key() below. An
admin rotates it from ERP Assistant Settings and every provider call picks up the
new key immediately, no restart.

Supported providers: "ollama" (local, free, private), "gemini", "groq"
(free API tiers; data leaves the server). Add a new provider by writing two
functions and registering them below.
"""

import time

import requests

import frappe

_TIMEOUT = 120
_MAX_RETRIES = 5


def _conf():
    conf = dict(frappe.conf.get("erp_assistant") or {})
    # Default: fully hosted, free API tier (no local model to run).
    conf.setdefault("provider", "gemini")
    conf.setdefault("chat_model", "gemini-3.1-flash-lite")
    conf.setdefault("embed_model", "gemini-embedding-2")
    conf.setdefault("ollama_url", "http://localhost:11434")
    return conf


# ---------------------------------------------------------------------------
# Public API — the rest of the app only calls these two.
# ---------------------------------------------------------------------------

# Cache single-text (query) embeddings for the life of the process. During one
# question, every provider embeds the SAME query string — this collapses those
# N identical Gemini embed calls into one, the biggest per-question latency win.
_QUERY_EMBED_CACHE = {}
_QUERY_EMBED_CACHE_MAX = 512


def _embed_raw(texts, tolerate_failures=False):
    conf = _conf()
    provider = conf["provider"]
    if provider == "ollama":
        return _ollama_embed(conf, texts)
    if provider in ("gemini", "groq"):
        # Groq serves no embeddings endpoint; use hosted Gemini embeddings.
        return _gemini_embed(conf, texts, tolerate_failures=tolerate_failures)
    raise frappe.ValidationError(f"Unknown erp_assistant provider: {provider}")


def embed(texts, tolerate_failures=False):
    """texts: list[str] -> list[list[float]]. Single-text calls (query
    embeddings) are cached so repeated providers don't re-embed the same
    query. tolerate_failures=True (used by the bulk index build, never by
    live query-time retrieval) returns None for any item whose batch
    couldn't be embedded instead of raising, so a rate-limited/flaky batch
    partway through doesn't throw away every card embedded before it."""
    if isinstance(texts, (list, tuple)) and len(texts) == 1:
        key = texts[0]
        hit = _QUERY_EMBED_CACHE.get(key)
        if hit is not None:
            return [hit]
        vec = _embed_raw(texts)[0]
        if len(_QUERY_EMBED_CACHE) >= _QUERY_EMBED_CACHE_MAX:
            _QUERY_EMBED_CACHE.clear()
        _QUERY_EMBED_CACHE[key] = vec
        return [vec]
    return _embed_raw(texts, tolerate_failures=tolerate_failures)


def chat(system_prompt, user_prompt):
    """Return the model's answer string. Non-streaming."""
    conf = _conf()
    provider = conf["provider"]
    if provider == "ollama":
        return _ollama_chat(conf, system_prompt, user_prompt)
    if provider == "gemini":
        return _gemini_chat(conf, system_prompt, user_prompt)
    if provider == "groq":
        return _groq_chat(conf, system_prompt, user_prompt)
    raise frappe.ValidationError(f"Unknown erp_assistant provider: {provider}")


# ---------------------------------------------------------------------------
# Ollama (local)
# ---------------------------------------------------------------------------

def _ollama_embed(conf, texts):
    url = conf["ollama_url"].rstrip("/") + "/api/embed"
    r = requests.post(
        url,
        json={"model": conf["embed_model"], "input": texts},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["embeddings"]


def _ollama_chat(conf, system_prompt, user_prompt):
    url = conf["ollama_url"].rstrip("/") + "/api/chat"
    r = requests.post(
        url,
        json={
            "model": conf["chat_model"],
            "stream": False,
            "options": {"temperature": 0.1},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


# ---------------------------------------------------------------------------
# Gemini — plain `requests` against the public REST API. No SDK dependency.
#
# Auth: use the `x-goog-api-key` header, not `?key=` in the URL. Classic
# AIzaSy... Developer API keys work with either; newer tokens (e.g. the
# "AQ...." format some accounts get from Google AI Studio) only work with
# the header — `?key=` 404s and `Authorization: Bearer` 401s on those.
# ---------------------------------------------------------------------------

_EMBED_BATCH = 100
# Free-tier TPM (tokens/minute) caps are easy to blow through with a single
# large batchEmbedContents call — cards can run up to 8000 chars each (see
# rag.py's _EMBED_CHAR_LIMIT), so a 100-item batch can hit ~200k input
# characters in one request versus a ~30k-token/minute budget on the free
# tier. Chunk by a character budget (not just item count) so a single
# request stays well under that regardless of how large individual cards
# are, and space batches out to respect requests/minute too.
_EMBED_CHAR_BUDGET = 20000
_EMBED_BATCH_DELAY = 1.5
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _chunk_by_char_budget(texts, budget=_EMBED_CHAR_BUDGET, max_items=_EMBED_BATCH):
    batch, batch_chars = [], 0
    for t in texts:
        t_len = len(t)
        if batch and (batch_chars + t_len > budget or len(batch) >= max_items):
            yield batch
            batch, batch_chars = [], 0
        batch.append(t)
        batch_chars += t_len
    if batch:
        yield batch


def _changai_gemini_key():
    """Fall back to the key configured in ERP Assistant Settings (single doctype),
    so the Gemini key only needs to be set in one place."""
    try:
        return frappe.db.get_single_value("ERP Assistant Settings", "gemini_api_key")
    except Exception:
        return None


def _gemini_headers(conf):
    key = (
        conf.get("api_key")
        or frappe.conf.get("gemini_api_key")
        or _changai_gemini_key()
    )
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def _gemini_embed(conf, texts, tolerate_failures=False):
    headers = _gemini_headers(conf)
    model = conf.get("embed_model", "gemini-embedding-2")
    url = f"{_GEMINI_BASE}/{model}:batchEmbedContents"

    out = []
    batches = list(_chunk_by_char_budget(texts))
    for idx, batch in enumerate(batches):
        body = {
            "requests": [
                {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
                for t in batch
            ]
        }
        try:
            data = _post_with_retry(url, headers, body)
            embeddings = data["embeddings"]
            if len(embeddings) != len(batch):
                raise RuntimeError(
                    f"Gemini batchEmbedContents returned {len(embeddings)} "
                    f"embeddings for {len(batch)} inputs — batch/response misaligned."
                )
            out.extend(e["values"] for e in embeddings)
        except Exception:
            if not tolerate_failures:
                raise
            try:
                frappe.log_error(frappe.get_traceback(), "erp_assistant.embed_batch_failed")
            except Exception:
                # A stale/dropped DB connection (long build sessions can
                # outlive MySQL's wait_timeout) must never turn a tolerated
                # batch failure back into a fatal one just because logging
                # it failed too.
                pass
            out.extend([None] * len(batch))
        if idx < len(batches) - 1:
            time.sleep(_EMBED_BATCH_DELAY)
    return out


# Free-tier per-model daily quotas are small (as low as 20/day on some
# models) and are hit by normal usage, not just abuse. If the configured
# model is exhausted or deprecated, fall through to these before giving up
# — each is a distinct model with its own separate quota bucket.
_CHAT_MODEL_FALLBACKS = ("gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite")


def _gemini_chat(conf, system_prompt, user_prompt):
    headers = _gemini_headers(conf)
    configured_model = conf.get("chat_model", _CHAT_MODEL_FALLBACKS[0])
    models_to_try = [configured_model] + [
        m for m in _CHAT_MODEL_FALLBACKS if m != configured_model
    ]

    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }

    last_error = None
    for model in models_to_try:
        url = f"{_GEMINI_BASE}/{model}:generateContent"
        try:
            data = _post_with_retry(url, headers, body)
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.HTTPError as e:
            last_error = e
            if e.response.status_code in (429, 404):
                continue  # quota exhausted or model retired — try the next one
            raise
    raise last_error


def _post_with_retry(url, headers, body):
    """POST with retry on 429 (rate limit) and on transient connection/
    timeout errors, respecting the server's suggested retryDelay when
    present. A single slow/dropped connection shouldn't abort an entire
    build_all() run when a short retry would sail through.

    A 429 against a *daily* quota is not transient — it won't clear for
    hours, so retrying it 5x with growing backoff (up to ~4 minutes total)
    just makes the caller wait through a guaranteed failure. Those fail
    immediately instead; only per-minute/short-lived 429s still retry.
    """
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=_TIMEOUT)
        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        if r.status_code == 429 and _is_daily_quota_exhausted(r):
            r.raise_for_status()
        if r.status_code == 429 and attempt < _MAX_RETRIES - 1:
            last_error = requests.HTTPError(response=r)
            time.sleep(_retry_delay(r, default=10) * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise last_error


def _is_daily_quota_exhausted(response) -> bool:
    """True if this 429's QuotaFailure violations are all against a
    PerDay-scoped quota — those don't reset within any retry window this
    process could reasonably wait out."""
    try:
        details = response.json()["error"]["details"]
    except Exception:
        return False

    violations = [
        v
        for d in details
        if d.get("@type", "").endswith("QuotaFailure")
        for v in d.get("violations", [])
    ]
    if not violations:
        return False
    return all("PerDay" in v.get("quotaId", "") for v in violations)


def _retry_delay(response, default=10):
    try:
        for d in response.json()["error"]["details"]:
            if d.get("@type", "").endswith("RetryInfo"):
                return float(str(d["retryDelay"]).rstrip("s"))
    except Exception:
        pass
    return default


# ---------------------------------------------------------------------------
# Groq (free API tier) — chat only
# ---------------------------------------------------------------------------

def _groq_chat(conf, system_prompt, user_prompt):
    key = conf.get("api_key") or frappe.conf.get("groq_api_key")
    model = conf.get("chat_model", "llama-3.1-8b-instant")
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
