# ChangAI — Implementation Reference

Technical reference for how this system is actually built: request flow,
intent classification, Gemini API wiring, the create-record safety net,
frontend architecture, and the config/settings model. Complements
`README.md` (product-facing setup guide) — this doc is for anyone changing
the code.

## 1. One app

`changai` is the only installed app. What used to be a separate
`erp_assistant` app (implementation/config-grounded "how does *our* ERP
work" answers) is now a subpackage at `changai/changai/erp_assistant/`,
imported as `changai.changai.erp_assistant.*`. It has no doctypes, no
`hooks.py`, no separate install — it's plain Python merged into changai's
own package tree. The nightly reindex job it needs
(`changai.changai.erp_assistant.extractor.build_index`) lives in changai's
`hooks.py` under `scheduler_events`.

Two logically distinct concerns still live in that subpackage vs. the rest
of `changai`, they just aren't separate apps anymore:

| Concern | Owns |
|---|---|
| `changai/changai/api/v2/` | Chat widget UI, the SQL/RAG pipeline for ERP data questions ("how many users do we have?"), entity creation, report navigation, site-wide settings (`ERP Assistant Settings`). |
| `changai/changai/erp_assistant/` | "How does *our* ERP work" questions — implementation/config-grounded answers (custom fields, workflows, client scripts, "how do I create X"). No UI of its own; the SQL pipeline calls into it. |

## 2. Request flow

Every message from the widget hits one Frappe whitelisted method:

```
changai.changai.api.v2.text2sql_pipeline_v2.run_text2sql_pipeline
```

```
User message
    │
    ▼
1. _try_erp_assistant_for_intent(question)     [gate — runs BEFORE the SQL pipeline]
    │  delegates to changai.changai.erp_assistant.agent.orchestrator.try_answer_if_relevant()
    │  which classifies via intent.classify(question) — single LLM call, one of:
    │    record_lookup | howto | troubleshooting | definition | workflow
    │
    ├─ record_lookup ──────────────────────────────────► fall through to step 2
    │
    ├─ troubleshooting ─► agentic plan → run tools → validate → answer (§4a)
    │
    └─ everything else ► static router table (§4) retrieves from live site data
                          │
                          ├─ real answer  ──────────────► returned directly, DONE
                          └─ giveup fallback text ──────► treated as None, fall through to step 2
    │
    ▼
2. find_similar_log_question(question)     — cache hit on a previously-logged
    │                                          identical/near-identical question
    ▼ (cache miss)
3. _invoke_pipeline() — LangGraph state machine:
    │
    ├─ rewrite_question   — LLM turns the raw question into a standalone query,
    │                        detects create_entity / open_report / stop_followup / is_cud flags
    ├─ route_action        — branches on those flags
    │
    ├─ CREATE_ENTITY ──► detect doctype, return {create_entity, doc, entity_name}
    │                     → frontend opens a prefilled Frappe form (no silent insert)
    ├─ OPEN_REPORT   ──► detect report + filters, frontend calls frappe.set_route('query-report', ...)
    ├─ STOP_FOLLOW   ──► canned short reply (e.g. "you're welcome")
    ├─ NON_ERP       ──► routeNonErpToAI() → send_non_erp_request()
    │                     → try_answer() then Gemini generic chat fallback
    └─ CONTINUE      ──► schema/entity retrieval → SQL generation → permission-checked
                          execution → natural-language formatting (format_data)
    ▼
Response returned to frontend, saved to chat log + session history
```

Key file: `changai/changai/api/v2/text2sql_pipeline_v2.py` (the whole graph
lives in this one file — nodes, routing functions, and `run_text2sql_pipeline`
itself). The two erp_assistant call sites (`_try_erp_assistant`,
`_try_erp_assistant_for_intent`) are thin wrappers — all erp_assistant-
specific logic (classification, routing, the "is this a real answer or a
giveup string" check) lives inside
`changai.changai.erp_assistant.agent.orchestrator.try_answer` /
`try_answer_if_relevant`, not duplicated in the SQL pipeline file.

## 3. Intent classification

`changai/changai/erp_assistant/agent/intent.py` — **pure LLM
classification, no regex/keyword rules.** `classify(question)` makes one
call to `_llm_classify()`, which prompts Gemini to label the question. The
prompt gives the model a definition + short description of what
distinguishes each label (not worked examples with specific doctype names —
those read as hardcoded associations and were deliberately stripped back
out once found). `RECORD_LOOKUP` is the fallback only if the model call
itself fails or returns something unparseable — not a routing shortcut.

This used to be a regex fast-path (rules for "how to X", "why can't X",
etc.) with LLM fallback only for ambiguous cases; that table couldn't track
every real phrasing ("want to create a new Project" didn't match any
question-shaped rule). It was replaced with an always-on LLM call. The bare
label list without definitions was itself a live bug for a while: mentioning
a real DocType name ("how to create a new Task?") got misread as a data
query and sent into a live `SELECT * FROM tabTask` instead of explaining how
to create one — fixed by giving the model explicit criteria (what the user
*wants*, not whether a DocType name appears in the question).

A separate, narrow regex (`_GREETING_RE` in `orchestrator.py`) still
short-circuits bare greetings ("hi", "who are you") to a fixed reply with
zero model calls — the one deliberately-kept exception, since routing that
degenerate case through the LLM classifier makes it worse, not better (empty
retrieval → "couldn't find an answer" instead of a greeting).

## 4. Routing + providers

`changai/changai/erp_assistant/agent/router.py` maps each intent to an
ordered list of providers, each tagged `primary` / `primary_fallback` /
`supplement`:

| Intent | Providers |
|---|---|
| `record_lookup` | `database` (primary) |
| `howto` | `implementation_docs` (primary) → `erp_docs` (fallback if no implementation docs) → `customization` (supplement) |
| `troubleshooting` | **not this table** — routed to the agentic planner instead, see §4a |
| `definition` | `erp_docs` (primary) + `customization` (supplement) |
| `workflow` | `customization` (primary) + `erp_docs` (supplement) |

Providers live in `changai/changai/erp_assistant/providers/` — `database`,
`erp_docs`, `implementation_docs`, `customization`, `code_search`. All
answers are grounded in **this site's live metadata** (real DocTypes, real
custom fields, real workflow config pulled at request time via embedding
retrieval), not the model's generic training knowledge.

`orchestrator.ask_agent()` enforces a no-hallucination gate: if no provider
returned relevant content (score ≥ 0.25) and no conversation context is
available, it returns a fixed "couldn't find an answer" string — except for
`howto`, exempt and always answering with standard ERPNext procedure as a
last resort. `_BASE_ROLE`'s "answer only from CONTEXT" instruction used to
apply even to *generic* ERPNext procedure knowledge, causing it to hedge on
plain how-to questions when retrieval failed (empty CONTEXT); it now
explicitly separates "OUR instance-specific facts" (context-only) from
"standard ERPNext procedure" (fine to state confidently regardless of
CONTEXT) — see `response_format.py`.

If a DocType genuinely isn't in the retrieval index (a custom app's
DocType added after the last schema sync), no prompt fix helps — the model
has nothing to ground on. Run **ERP Assistant Settings → Training tab → Update
Schema / Update Master Data** to reindex.

## 4a. Troubleshooting — agentic plan → run tools → validate → answer

`troubleshooting` is the one intent that skips the static router table above
entirely (`orchestrator.py`'s `_PLANNER_INTENTS` whitelist). It used to get
the same treatment as everything else — one opaque similarity search over a
per-doctype "customization card" that bundles workflow + permissions +
scripts + custom fields into a single embedding-searched blob, plus a blind
grep. That's unreliable for "why can't I submit/create this?": whether the
real cause (say, a missing role permission) surfaces at all depends on
whether its text happened to rank in the top-4 chunks for that specific
question's embedding — not on whether it's actually the cause.

Replaced with a real loop, in `agent/planner.py` + `agent/tools.py`:

```
question
    │
    ▼
_plan()  — one JSON-mode Gemini call: "what's the goal, what DocType/record
    │        is this about, which of these tools are relevant?"
    │        (Understand Goal + Create Execution Plan merged into one call —
    │         a deliberate quota-efficiency tradeoff, not two separate stages)
    ▼
run_tools()  — execute each planned tool, one try/except per tool
    ▼
[primary_chunks, supplement_chunks=[], used_fallback=False, any_provider_ready=True]
    │            — same shape the old router/retrieve loop produced
    ▼
ask_agent()'s EXISTING has_signal gate + llm.chat() synthesis — completely unchanged
```

**"Validate Results" is not a new function** — it's the `has_signal` gate
`ask_agent()` already had, reused unmodified against planner-built chunks
instead of router-built ones. Every tool result that ran (`ok=True`) scores
1.0, whether or not it found something wrong — a clean check is evidence
too, not silence. This is the single biggest lever keeping this change
low-risk: everything downstream of chunk-building in `ask_agent` — permission
filtering, the no-hallucination gate, prompt building, citations — is
byte-for-byte the same code path every other intent uses.

**Nine tools**, registered in `agent/tools.py:TOOL_REGISTRY` (the planner
builds its prompt's tool menu from this at runtime, so adding a tool needs
no prompt edit):

| Tool | What it actually queries |
|---|---|
| `workflow_check` | Active `Workflow` for the DocType, the record's current state, transitions out of it vs. the user's roles |
| `permission_check` | `frappe.has_permission` for create/read/write/submit/cancel; names the missing role if denied |
| `mandatory_fields_check` | Record's actual field values vs. real mandatory fields (`agent/doctype_meta.py`, shared with `operations.py`'s CUD insert guard) — or, with no record yet (a creation question), just lists what's required |
| `custom_fields_check` | Custom Field rows on the DocType, flagging mandatory/conditionally-shown ones |
| `naming_series_check` | Whether the Naming Series (or autoname pattern) actually has options configured — a missing series silently blocks every new record |
| `client_scripts_check` | Active `Client Script` rows for the DocType |
| `server_scripts_check` | Active `Server Script` rows filtered to save/validate/submit/cancel events, script body included — a `frappe.throw()` in one of these is often the literal answer |
| `linked_documents_check` | The record's Link fields → whether any target is Cancelled |
| `error_log_check` | Frappe's real `Error Log`, last 30 min, narrowed to this DocType when tagged, otherwise the most recent entries system-wide (best-effort — Error Log isn't always doctype-tagged, so in a busy multi-user site this can occasionally surface unrelated noise instead of skipping) |

The first six of these never call `llm.py` at all — no embeddings, no chat
completion, pure `frappe.get_meta`/`get_all`/`has_permission`/`get_doc`.
That's deliberate: a dead Gemini quota (§8, this repo's most common failure
mode) can't take these out, only the three semantic-search wrapper tools
(`customization_search`, `code_search`, `erp_docs_search`) that reach the
existing Providers when a deterministic check doesn't cover it.

If `_plan()`'s JSON call fails outright (bad JSON, quota dead), it falls
back to a fixed list of all nine deterministic-first tools plus the
existing regex-based entity resolver (`agent/entities.py`, promoted out of
`DatabaseProvider` so both places share one copy) instead of guessing a
doctype from scratch — the same "unavailable → safe default" idiom
`intent.classify()` already uses, not a new hardcoded routing rule.

`response_format.py`'s `TROUBLESHOOTING` prompt was updated to tell the
model explicitly that a clean check result rules a cause *out* rather than
being missing information — otherwise a real 429 in the Error Log entries
sitting alongside five clean checks could get hedged across all six instead
of correctly identified as the answer.

`workflow` intent is a one-line addition to `_PLANNER_INTENTS` whenever
wanted — same tool menu already covers it, no new architecture needed.

## 5. Gemini API — two independent call sites

Neither uses the `google-genai` SDK for the low-level HTTP calls in
`erp_assistant/llm.py`; both talk to `generativelanguage.googleapis.com` via
plain `requests` (an earlier version used the SDK's async transport and
stalled for minutes when co-imported with changai's torch/langgraph stack).
`changai/api/v2/clients.py` does use the SDK's `client.models.generate_content`.

**`changai/changai/erp_assistant/llm.py`**
- `chat(system_prompt, user_prompt)` → `_gemini_chat()` → `POST .../models/{chat_model}:generateContent`, `temperature=0.1`. On 429/404 retries against `_CHAT_MODEL_FALLBACKS` (other flash-lite variants) before giving up.
- `embed(texts)` → `_gemini_embed()` → `POST .../{embed_model}:batchEmbedContents`, chunked by a character budget to stay under free-tier tokens/minute.
- `_post_with_retry` retries 429s with the server's `retryDelay`, **except** when `_is_daily_quota_exhausted()` — it inspects the 429's `QuotaFailure.violations[].quotaId` and fails immediately if every violation is `PerDay`-scoped, since a daily cap won't clear within any retry window. Previously this retried blindly up to 5x with growing backoff (~4 min total) against a quota that couldn't possibly recover in that time, making the chat UI hang on "Thinking..." for minutes before finally erroring.
- Called from `intent.classify()` (one call per message) and `orchestrator.ask_agent()`'s final answer synthesis.

**`changai/changai/api/v2/clients.py`**
- `call_gemini` / `call_model` — used for question rewriting (`rewrite_question`), entity/doctype extraction, report-intent matching, the non-ERP generic-chat fallback, and `format_data`'s result-to-answer formatting. `temperature=0.1` (added — was running at the SDK default of ~1.0, which meant identical prompts produced wildly inconsistent answers call to call; erp_assistant's own calls had always been pinned at 0.1).

**API key resolution** (`_gemini_headers` in `erp_assistant/llm.py`), first match wins:
1. `conf.get("api_key")` — `site_config.json`'s `erp_assistant` block (legacy/dev fallback, normally unset)
2. `frappe.conf.get("gemini_api_key")` — legacy top-level site_config key
3. `ERP Assistant Settings.gemini_api_key` — **live source of truth**, editable from Desk (Search → "ERP Assistant Settings"), no redeploy needed to rotate

There is deliberately **one** place to configure the key.

Gemini free tier: `gemini-embedding-2` embeddings are capped at **1000
requests/day** per key/project. Each user question makes at least one
classification call, one embedding call (retrieval), and one synthesis
call — all against the same key/quota. That daily cap is the tightest real
constraint and the most likely production failure mode; see §8.

## 6. Non-ERP fallback (chit-chat, "what are you capable of?")

`send_non_erp_request()` in `text2sql_pipeline_v2.py`: tries
`_try_erp_assistant()` first (in case it's actually an implementation
question misrouted here), then falls to `call_gemini` with
`_NON_ERP_SYS_PROMPT`.

That prompt used to run through a static fuzzy-match FAQ table first
(`non_erp_handler.py`'s `IntelligentStaticResponder`, rapidfuzz `WRatio`
cutoff of 65 against ~hundreds of canned Q&A pairs). Loose enough that
ordinary questions matched unrelated canned entries — "can you list them?"
matched a "who are you" entry and returned a canned identity string instead
of a real answer. That matching layer is disconnected from the live path
now; the JSON data files remain on disk but nothing reads them at request
time.

`_NON_ERP_SYS_PROMPT` itself went through a few rounds once it was the only
thing left in this path:
- It initially told the model "the user asked a general question not
  related to ERP" — wrong framing, since this fallback is also reached for
  genuine ERP how-to questions when erp_assistant can't answer (quota).
  That framing caused questions like "how to create a new Sales Invoice?"
  to get vague, ungrounded, sometimes-fabricated answers.
- Then it over-corrected: telling it to "never invent specific record
  data" made it sometimes decline to state even *generic* ERPNext
  procedure (which isn't instance data at all) — same category of bug
  found independently in `erp_assistant`'s own `_BASE_ROLE` (§4). Fixed by
  explicitly splitting "OUR instance data — never invent" from "standard
  procedure — you already know this, state it confidently."
- The Navigation line was initially plain text ("Navigation: /app/x/new")
  and never rendered as a clickable link — the prompt now requires markdown
  link syntax explicitly.
- Dropped a "mention you're ChangAI by ERPGulf when introducing yourself"
  instruction that made every answer open with a self-introduction instead
  of the actual answer.

## 7. `format_data` — SQL-result-to-answer formatting

`changai/changai/api/v2/format_output.py:format_data(qstn, sql_data,
doctype_hint=None)` — the Gemini call that turns a SQL query's raw result
(often `[]`) into the final chat answer for the CONTINUE/SQL branch and the
CUD success path.

Its "if result is empty, respond warmly and suggest refining the search"
instruction was unconditional — applied even when the *question itself*
was never a data lookup. "How to create a new Task?" generates a real but
pointless `SELECT ... FROM tabTask` (empty, since no tasks exist yet), and
the formatter dutifully explained the empty search result instead of
answering the actual how-to question. Fixed the same way as `erp_assistant`'s
prompt: check what the question wants first — a how-to question stays a
how-to question regardless of what an empty/irrelevant DB result contains.

`doctype_hint`: the model used to guess the Navigation slug from whatever
name it used in its own generated prose, which is wrong whenever a
DocType's real name doesn't match its common name (e.g. real DocType is
"BOM", model wrote "Bill of Materials" → guessed `/app/bill-of-material/new`,
wrong). Callers now pass the actual DocType the query targeted — from
`extracted_tables[0]` (the real `tabXxx` table name the executed SQL hit,
stripped of the `tab` prefix) for the SQL branch, or `payload["doctype"]`
for the CUD branch — so the model builds the link from real data instead of
inferring one.

## 8. Entity creation — no silent inserts, no blind field-guessing

When `rewrite_question` detects create-intent, the pipeline does **not**
insert a record directly by default — it returns `{"create_entity": true,
"doc": doctype, "entity_name": ...}` to the frontend, which opens a real
Frappe form pre-filled with detected fields; the user reviews and saves it
themselves.

Direct programmatic inserts go through
`changai/changai/api/v2/operations.py:execute_insert` (the natural-language
CUD path) and always check `frappe.has_permission(..., throw=True)` first.
This path had a real gap: a "how to create X" question can get misread as a
create command with **no extracted field values**, and `execute_insert`
would call `doc.insert()` with an empty `data` dict — which fails on the
first missing mandatory field, but not before Frappe's naming series
counter has already incremented (the counter isn't rolled back on a failed
insert), permanently burning document numbers, and surfacing a raw
`[Doctype, PROJ-0002]: field_name` error to the user.

Fixed with `_missing_mandatory_fields(doctype, data)` — checks the
doctype's actual mandatory fields (via `frappe.get_meta`, skipping
`read_only` fields since those are computed by the doctype's own controller
during insert, e.g. Sales Invoice's `grand_total`) against what's actually
present, **before** calling `.insert()`. If anything's missing,
`_generic_create_howto(doctype, missing_fields)` builds real step-by-step
instructions + a real `/app/<doctype-slug>/new` link straight from meta —
no LLM call needed, works even when Gemini is completely down. The response
carries a `"howto": True` flag so the pipeline's shared error-formatting
step (which normally prefixes failures with "❌") knows this is a real
answer, not a failure to apologize for.

## 9. Frontend — Vue 3 widget in a shadow DOM

`changai/frontend/src/` — built with Vite, output lands in
`changai/public/dist/changai-chatbot.js` + `.css` and is mounted via
`app_include_js` into every Desk page inside a shadow root
(`#changai-chatbot-host`), so host-page styles/keyboard shortcuts never leak
in or out.

```
App.vue
 ├─ ChatbotToggler.vue    the floating bubble button
 └─ ChatbotPopup.vue      the chat window shell (resize modes: compact/half/full)
     ├─ ChatHeader.vue     title bar (wordmark, resize + close buttons)
     ├─ TabBar.vue         Chats / Debug / Support / Settings (single tab hidden by default)
     ├─ ChatTab.vue → ChatMessage.vue → BotIcon.vue
     ├─ DebugTab.vue / SupportTab.vue / SettingsTab.vue
     └─ ChatForm.vue        input, voice input (Web Speech API), send/cancel
```

This floating widget is the only chat UI — a second one used to exist (a
standalone Vue app + Desk page at `/desk/erp-assistant`, shipped by the old
separate `erp_assistant` app). Removed along with the app merge; the
floating widget already routes implementation questions server-side via the
intent gate, so a second frontend was pure duplication.

Styling: Tailwind v4, CSS-first config in `frontend/src/tailwind.css`. Brand
color is a violet scale anchored on `#6d4fc2`/`#5f44ad`, defined as a full
50–900 ramp so every `brand-*` utility used across components actually
resolves (several shades were referenced but undefined for a while, which
silently dropped hover/focus/ring states). Typography: Manrope for UI text,
Fraunces (serif) for the "ERP Assistant" header wordmark only — both loaded
via Google Fonts `@import`, with system-font fallbacks for offline/air-gapped
deployments.

## 10. Settings & configuration

- **`ERP Assistant Settings`** (`changai/changai/doctype/erp_assistant_settings/`) — single doctype, the one place to configure: Gemini API key, provider mode (local/remote), voice (Amazon Polly), translation languages, schema/master-data sync, enable/disable the whole assistant.
- **`site_config.json`** — only non-secret defaults belong here now (`db_*`, unrelated app config). No API keys are hardcoded in site config.
- Config is read through `ChangAIConfig.get()` (`changai/changai/api/v2/schema_utils.py`), cached on `frappe.local` per request, cleared via `frappe.clear_document_cache`.

## 11. Known constraints / things to watch

- **Gemini daily quota** (1000/day free tier on embeddings) is the single
  most likely production failure mode. It now fails fast instead of
  hanging (§5), but a dead quota still means erp_assistant can't answer at
  all and everything falls back to the SQL pipeline / generic Gemini chat —
  lower-quality answers, not crashes. Watch for `RESOURCE_EXHAUSTED` in
  Frappe's error log.
- The in-memory query-embedding cache (`_QUERY_EMBED_CACHE` in
  `erp_assistant/llm.py`) lives in a single worker process — a long-running
  dev server (`bench start` left open across a full day of testing) can
  end up answering some repeated queries from stale cached embeddings even
  while the live API key's quota is exhausted, producing inconsistent
  behavior for what looks like the same request. Restarting the server
  clears it.
- Removing the regex-based intent classifier (§3) means **every** message
  costs at least one extra LLM round-trip versus the old fast-path — a
  deliberate trade for correctness over silently misrouting phrasings a
  fixed table didn't cover. Combined with `temperature=0.1`, this is about
  as consistent as a live-classification approach gets, but it's still a
  live model call each time, not a lookup.
- `changai/changai/erp_assistant/` has no doctypes/migrations of its own by
  design (pure Python, no UI). Anything needing persistent UI-editable
  config belongs in `ERP Assistant Settings`, not a new doctype in that
  subpackage.
- If a custom app's DocType doesn't show up in how-to/implementation
  answers, it's very likely a stale retrieval index, not a code bug — run
  Update Schema / Update Master Data from ERP Assistant Settings first before
  chasing a prompt issue.
