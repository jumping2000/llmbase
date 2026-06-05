# Changelog

| Versione | Highlights |
|----------|-----------|
| **v0.8.9** | MCP streamable-http, doc fixes |
| **v0.8.8** | Docker config read-only mount |
| **v0.8.7** | LLM token tracking, error handling |
| **v0.8.6** | Compile snippet UI, async fix |
| **v0.8.5–v0.8.4** | CI/CD workflow updates |
| **v0.8.3** | Worker seed URL learning |
| **v0.8.2** | Nginx Basic Auth, PDF upload, Chinese removal |
| **v0.8.1** | Initial EN/IT release |

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
