# ERP Implementation Assistant

AI agent that answers "how does OUR ERP work" grounded in this Frappe/ERPNext
instance — custom fields, client/server scripts, workflows, notifications,
permissions. Pure RAG + prompting. **No model training.**

## How it works

1. `extractor.py` reads live metadata for every doctype across every installed
   app and emits one "implementation card" per doctype (fields, custom fields,
   property setters, scripts, workflow, notifications, permissions,
   `is_customized` flag).
2. `rag.py` embeds the cards and stores vectors in sqlite; retrieval is numpy
   cosine similarity with a boost for customized doctypes.
3. `llm.py` is a provider-pluggable LLM + embeddings client (Ollama / Gemini /
   Groq) selected via `site_config.json`.
4. `api.py` assembles the ROLE system prompt + retrieved cards, enforces the
   no-hallucination fallback and per-user permission filter, and returns the
   answer plus citations.
5. Vue 3 chat frontend mounted on a Desk route calls `ask_agent`.

## Install

```bash
bench get-app erp_assistant apps/erp_assistant   # already in bench: just install
bench --site <site> install-app erp_assistant
```

## Configure the model (no training, no local model)

Default provider is **Gemini** (free API tier — hosted chat + embeddings, nothing
runs locally). Add to `sites/<site>/site_config.json`:

```json
{
  "erp_assistant": {
    "provider": "gemini",
    "chat_model": "gemini-1.5-flash",
    "embed_model": "text-embedding-004",
    "api_key": "YOUR_GEMINI_API_KEY"
  }
}
```

Providers: `gemini` (default, hosted, free tier), `groq` (hosted chat; uses
Gemini for embeddings), `ollama` (local — only if you later want on-prem).
Data leaves the server on hosted providers. See `llm.py`.

## Build the index

```bash
bench --site <site> execute erp_assistant.extractor.build_index
```
