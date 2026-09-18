# Changelog

| Versione | Highlights |
|----------|-----------|
| **v0.9.7** | Markdown download, actionable orphans, taxonomy tag loop fixed |
| **v0.9.6** | Doc/code alignment audit, Windows encoding fix |
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

## v0.9.7

- Added a **"Download Markdown"** button to the article page: saves the currently
displayed language (EN, IT, or the combined EN/IT view) as a `.md` file, titled
and summarized, entirely client-side — the article body already arrives as raw
markdown from `/api/articles/<slug>`, so no new backend route was needed.
- Added the same button to the Q&A answer panel. The saved file carries a small
YAML front-matter (question as `title`, `date`, selected `tone`), the question as
an `# H1`, the answer body, and — when the query was a deep-research ask — a
"Consulted sources" section listing the articles the LLM drew on
(`[[slug]] Title`), wikilink-style so it can be pasted back into the KB. The
`consulted` list returned by `/api/ask` was previously read once for trail
recording and discarded; it is now kept in state.
- **Broke the taxonomy's tag feedback loop.** `_sync_taxonomy_to_tags` writes a
`category:<id>` tag into every classified article, and `_fallback_taxonomy` — the
tag-frequency path used whenever LLM generation fails — counted those tags like any
other and promoted one to a category id. The next sync then wrote it back as
`category:category:middleware`, one prefix deeper per run. 38 of 206 articles already
carried the doubled tag and the taxonomy held two rival categories, `middleware` (128)
and `category:middleware` (38). Category inference now ignores the taxonomy's own
output, through a single `is_category_tag()` helper applied at the four points that fed
the loop: the fallback, the two-phase tag summary, the profile/matching pass in
`assign_new_articles`, and the article list sent to the LLM.
- Made the sync self-healing rather than adding a one-off migration: articles no longer
present in the tree get their stale `category:*` tags stripped, so a tag can't outlive
the category that produced it. `_apply_category_tags` now writes only when the tag list
actually changes — the pass covers the whole corpus, and rewriting 200 unchanged files
per rebuild was pure churn.
- Fixed a token cap that cancelled its own intent: `tax_tokens = min(max_tokens * 2,
16384)` sat next to a comment explaining that thinking models need double the room, but
`config.yaml` already sets `max_tokens: 16384`, so the doubling never happened. Taxonomy
generation had failed 99 times out of 172, and on 119 of 124 measurable failures the
model's reasoning tokens had met or exceeded the completion budget, returning empty
content. First run after the fix succeeded and produced an 82-node hierarchy.
- Added `tests/test_taxonomy.py` — the module had no test at all. Both headline tests
were checked against a replica of the old code first, to confirm they actually reproduce
the drift (`other` → `category:other` → `category:category:other`) rather than passing
either way.
- **Orphan articles became actionable.** `check_orphans` has always reported articles
nobody links to — 67 of 226 on a real KB — but nothing could act on the report: the
Health page printed the raw strings and no fixer touched them. The Orphans section now
lists, per article, the existing articles that could cite it, ranked by shared tags
(no LLM call), and offers both routes the same write: pick the source yourself, or let
the server take the best candidate. A new `llmwiki/lint/orphans.py` inserts the
wiki-link as a `See also:` / `Vedi anche:` line at the end of each language section,
reusing the convention already present in the corpus and appending to that line when it
exists. Reachable as `llmbase lint orphans [--fix]`, three `kb_orphan*` MCP tools, and
`GET /api/lint/orphans` plus two POST routes.
- Kept orphan linking **out** of `auto_fix()`: it rewrites existing articles, so the
global "Repair" button and the background worker must not trigger it. A test asserts
`auto_fix` never mentions orphans so the separation cannot erode.
- The insertion edits the article body with a targeted regex rather than
`_split_sections`/`_assemble_sections`, whose round-trip drops `---` rules inside
sections and renormalizes spacing and section order; a regression test pins that.
Re-linking is a no-op down to the byte, so a double click costs nothing.
- Fixed a bug this surfaced: reopening a question from "Previous queries" restored
its question/answer but left the *previous* answer's "Promoted to concept" panel
on screen, since that state was never part of the swap — it could point at an
unrelated article. History entries now carry their own promotion outcome and it
is restored together with the rest of the pair.

## v0.9.6

- **Documentation audited against the code.** Every documented surface was diffed
mechanically against its source of truth — HTTP routes against `llmwiki/web.py`,
MCP tools against the `operations.py` registry, CLI commands against the `click`
tree, `LLMBASE_*` variables against their reads — in all three directions:
documented-but-absent, present-but-undocumented, and diverging signature. Ten
misalignments were found and fixed.
- **Text reads no longer depend on the platform locale.** `Path.read_text()` without
`encoding=` resolves its codec from the locale: UTF-8 on Linux, cp1252 on Windows.
The package writes UTF-8 everywhere — all 38 `write_text()` calls pass it — but read
it back without specifying one at 31 sites, so `kb_stats`, `llmbase stats` and
`GET /api/stats` all failed on Windows against 11 of 226 wiki articles. The bug dated
to April and survived because CI runs on `ubuntu-latest` only.

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
