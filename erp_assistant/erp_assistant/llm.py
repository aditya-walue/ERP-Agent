"""
Provider-pluggable LLM + embeddings client.

No model training. The model is used off-the-shelf; ERP knowledge is supplied at
inference time via the retrieved cards. Provider + models are read from
site_config.json under the "erp_assistant" key, e.g.:

    "erp_assistant": {
        "provider": "ollama",
        "chat_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "ollama_url": "http://localhost:11434"
    }

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
    conf = frappe.conf.get("erp_assistant") or {}
    # Default: fully hosted, free API tier (no local model to run).
    conf.setdefault("provider", "gemini")
    conf.setdefault("chat_model", "gemini-3.1-flash-lite")
    conf.setdefault("embed_model", "gemini-embedding-2")
    conf.setdefault("ollama_url", "http://localhost:11434")
    return conf


# ---------------------------------------------------------------------------
# Public API — the rest of the app only calls these two.
# ---------------------------------------------------------------------------

def embed(texts):
    """texts: list[str] -> list[list[float]]."""
    conf = _conf()
    provider = conf["provider"]
    if provider == "ollama":
        return _ollama_embed(conf, texts)
    if provider == "gemini":
        return _gemini_embed(conf, texts)
    if provider == "groq":
        # Groq serves no embeddings endpoint. Use hosted Gemini embeddings
        # (set gemini_api_key). Keeps everything off-local.
        return _gemini_embed(conf, texts)
    raise frappe.ValidationError(f"Unknown erp_assistant provider: {provider}")


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
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _gemini_headers(conf):
    key = conf.get("api_key") or frappe.conf.get("gemini_api_key")
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def _gemini_embed(conf, texts):
    headers = _gemini_headers(conf)
    model = conf.get("embed_model", "gemini-embedding-2")
    url = f"{_GEMINI_BASE}/{model}:batchEmbedContents"

    out = []
    for i in range(0, len(texts), _EMBED_BATCH):
        batch = texts[i:i + _EMBED_BATCH]
        body = {
            "requests": [
                {"model": f"models/{model}", "content": {"parts": [{"text": t}]}}
                for t in batch
            ]
        }
        data = _post_with_retry(url, headers, body)
        embeddings = data["embeddings"]
        if len(embeddings) != len(batch):
            raise RuntimeError(
                f"Gemini batchEmbedContents returned {len(embeddings)} "
                f"embeddings for {len(batch)} inputs — batch/response misaligned."
            )
        out.extend(e["values"] for e in embeddings)
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
    """POST with retry on 429 (rate limit), respecting the server's
    suggested retryDelay when present."""
    last_error = None
    for attempt in range(_MAX_RETRIES):
        r = requests.post(url, headers=headers, json=body, timeout=_TIMEOUT)
        if r.status_code == 429 and attempt < _MAX_RETRIES - 1:
            last_error = requests.HTTPError(response=r)
            time.sleep(_retry_delay(r, default=10) * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise last_error


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
