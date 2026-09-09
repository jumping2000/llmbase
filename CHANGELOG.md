# Changelog

| Versione | Highlights |
|----------|-----------|
| **v0.9.5** | Some minor fixes |
| **v0.9.4** | UI strings externalised to JSON translation files |
| **v0.9.3** | "All domains" filter, domain-stamped Q&A outputs |
| **v0.9.2** | Document authoring dates (`doc_date`), recency-aware answers |
| **v0.9.1** | Domains UX (dropdown, badges), misc fixes |
| **v0.9.0** | Domini, bot Telegram, email ingestion |
| **v0.8.9** | MCP streamable-http, doc fixes |
| **v0.8.8** | Docker config read-only mount |
| **v0.8.7** | LLM token tracking, error handling |
| **v0.8.6** | Compile snippet UI, async fix |
| **v0.8.5** | CI/CD workflow updates |
| **v0.8.4** | CI/CD workflow updates |
| **v0.8.3** | Worker seed URL learning |
| **v0.8.2** | Nginx Basic Auth, PDF upload, Chinese removal |
| **v0.8.1** | Initial EN/IT release |

## v0.9.5

- Made the worker's compile task **retry on `OSError`** — three attempts, five seconds apart — instead of giving up on the first one. A Docker bind mount that has not reattached after the host suspends surfaces as `ENOENT` on the first filesystem touch, which is `ensure_dirs()` at the top of `compile_new`; that aborted the whole cycle, and since the loop advances `last_compile` regardless of outcome, a glitch lasting seconds costs a full compile interval. Only `OSError` is retried: `chat()` already retries LLM failures internally (per-model attempts plus fallback models, over an SDK client with `max_retries=2`), so retrying those at task level would multiply the call count during an API outage.
- Fixed the VS Code default interpreter path, which pointed at a bare relative `.venv/Scripts/python.exe` and failed to resolve; it is now anchored with `${workspaceFolder}`.

## v0.9.4

- Moved **every UI string out of the React components** into `frontend/public/translations/{en,it,en-it}.json` (243 keys, flat key → string maps). The files are served at `/translations/<lang>.json` through the existing SPA static route, so the deployed copies under `static/dist/translations/` can be edited and picked up on a browser reload, without a rebuild. The versioned source of truth stays `frontend/public/translations/`.
- Added a `t(key, vars?)` helper on `useLang()`: `{name}` interpolation, `_one` / `_other` plural selection driven by `count`, and a missing key rendering as the key itself plus a console warning — so a hand-edit that drops an entry is visible instead of silent.
- Replaced ~121 inline `it ? 'x' : 'y'` ternaries and ~60 single-language literals; removed the duplicated `const it = lang === 'it' || lang === 'en-it'` flag from 8 components. `isItalianUI()` is now actually used, in `Explore.tsx`, where the flag still selects a localized *data* field rather than UI text.
- Added `en-it.json` as a third file so the bilingual mode's chrome can diverge from Italian; it currently mirrors `it.json`, preserving the previous behaviour.
- Fixed two latent bugs the translation surfaced: the Wiki and Ingest status banners picked their error styling by sniffing an `"Error"` / `"Errore"` prefix out of the message text, which breaks as soon as the text is translated; both now track an explicit boolean.
- Fixed stale era labels in the Explore timeline when switching between `it` and `en-it`: the d3 effect depended on the italian flag, which does not change across that pair.
- Added `tests/test_translations.py`: guards the three files against key drift and against unpaired `_one` / `_other` plural forms.

## v0.9.3

- Added an **"All domains"** option to the top-bar domain selector, and made it the initial value. The selector previously defaulted to `generale` and always sent it, so search and ask silently excluded every article assigned to a custom domain — on a knowledge base where all articles carry a domain, that hid nearly the whole corpus.
- Made the Search page re-run the current search when the domain filter changes; results used to stay stale until the query was resubmitted.
- Stamped the queried `domain` into filed-back Q&A outputs at creation time (`_file_output`), so an answer produced under a domain filter is reachable by that same filter. With no filter active nothing is written, exactly as before. Pre-existing files in `wiki/outputs/` are unaffected — outputs remain outside the reach of `bulk_assign_domain`, which only resolves paths under `concepts/`.
- Fixed `malformed_record_count` in `llm_usage.recent_requests`: the counter was incremented without being initialised in the recent-requests payload. Added it to the response and to the API reference (EN/IT).

## v0.9.2

- Added **document dates** (`doc_date`): the authoring/validation date of a source document is extracted at ingest time (multilingual regex first, LLM fallback) and stored in the raw document's frontmatter.
- Propagated `doc_date` to wiki article `sources[]` at compile time; a new edition of the same document is kept as a distinct source.
- Made query answers date-aware: a recency rule in the system prompt prefers the most recent source and flags conflicts, citing dates; undated sources are considered less reliable.
- Added a `backfill-doc-dates [--force]` CLI command (and `kb_backfill_doc_dates` operation) to extract dates for already-ingested documents, with `extracted`/`skipped`/`missing`/`diverged` counters.
- Added `PATCH /api/sources/<slug>/doc-date` (auth-protected, path-traversal-safe) and an editable "Data stesura" field in the raw document preview UI.
- Added `docdate.enabled` / `docdate.llm_fallback` config options; propagation is fill-only so manual corrections are never overwritten.

## v0.9.1

- Reworked the Domains panel UX: dropdown selector, with rename/delete acting on the selected domain.
- Show the domain badge on the article page, article list, and search results.
- Fixed email ingestion: broken-PDF attachment no longer causes a re-ingest loop; IMAP expunge now iterates in reverse to avoid sequence-number drift.
- Fixed `ask` domain filter in the keyword fallback path; domain deletion now also reassigns raw docs.

## v0.9.0

- Added **domains**: a `domain` frontmatter facet on raw docs and wiki articles; CRUD via `llmwiki/domains.py`; filters on search/ask/index; bulk assignment; LLM domain suggestion at compile; web API (`/api/domains`, `/api/articles/bulk-domain`) and UI.
- Added **Telegram bot**: long-polling gateway (`llmwiki/telegram.py`) with chat-id whitelist and `/ask`, `/cerca`, `/dominio`, and document upload.
- Added **email ingestion**: IMAP polling (`llmwiki/mail.py`) with `[domain]` subject-tag routing, markdown body and PDF attachments.
- Exposed `kb_domains_*` MCP operations and a `domain` parameter on `kb_search` / `kb_ask`.

## v0.8.9

- Added MCP streamable-http transport: `llmbase mcp --transport streamable-http --http-port 8100`.
- Added dedicated `llmbase-mcp` Docker Compose service with Nginx proxy on `/mcp`.
- Added CJK bigram tokenization in search for text without word separators.
- Added fullwidth CJK punctuation support in section anchor normalization.
- Added autouse test fixture to clear ambient `LLMBASE_API_SECRET` before each test.
- Fixed documentation alignment: README, API reference, MCP docs, requirements.txt.

## v0.8.8

- Docker: mount `config.yaml` as read-only runtime file in Compose.

## v0.8.7

- Added LLM token usage tracking for compile and lint operations.
- Added error handling for invalid input in `agent_api` and `web.py`.

## v0.8.6

- Added compile snippet UI in frontend.
- Fixed compile activity with async background thread.

## v0.8.5

- Updated release CI/CD workflow.

## v0.8.4

- Updated CI/CD workflow for Docker image handling.

## v0.8.3

- Implemented worker autonomous learning from seed URLs (`wiki/_meta/seed-urls.json`).
- Updated API and frontend for new features and improvements.

## v0.8.2

- Added Nginx reverse proxy with Basic Auth for the web UI and HTTP API.
- Added PDF and Markdown batch upload from the web UI `/ingest` page.
- Removed all Chinese content from code and wiki; standardized on English and Italian.

## v0.8.1

- Initial English/Italian release.
- Standardized the knowledge-base contract on English and Italian sections.
- Updated worker, taxonomy, guided introductions, web API, and frontend language helpers.
- Replaced historical fixtures and tests with generic or English/Italian-oriented coverage.
- Rewrote project guidance and docs to match the current supported feature set.
