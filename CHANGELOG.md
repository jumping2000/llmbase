# Changelog

| Versione | Highlights |
|----------|-----------|
| **v0.9.1** | Domini UX (menu a tendina, badge), fix vari |
| **v0.9.0** | Domini, bot Telegram, email ingestion |
| **v0.8.9** | MCP streamable-http, doc fixes |
| **v0.8.8** | Docker config read-only mount |
| **v0.8.7** | LLM token tracking, error handling |
| **v0.8.6** | Compile snippet UI, async fix |
| **v0.8.5–v0.8.4** | CI/CD workflow updates |
| **v0.8.3** | Worker seed URL learning |
| **v0.8.2** | Nginx Basic Auth, PDF upload, Chinese removal |
| **v0.8.1** | Initial EN/IT release |

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
