# Claude Notes

This repository is configured around a compact set of customization points.

## Core assumptions

- Default article sections are English and Italian.
- Built-in ask tones are `default`, `caveman`, `scholar`, and `eli5`.
- Worker autonomous learning defaults to the built-in `seed_urls` source backed by `wiki/_meta/seed-urls.json`.
- Search uses Unicode word tokenization by default.
- The implicit article domain is `generale`; custom domains are stored in `wiki/_meta/domains.json` and managed via UI, API, or `kb_domains_*`.
- Optional integrations (Telegram long-polling bot, IMAP email ingestion) are enabled via `LLMBASE_TG_*` / `LLMBASE_MAIL_*` env vars and run as threads in the ASGI lifespan.

## Useful module-level customization points

| Module | Setting | Purpose |
| --- | --- | --- |
| `llmwiki.compile` | `SECTION_HEADERS` | Controls article section layout |
| `llmwiki.query` | `TONE_INSTRUCTIONS` | Adds or overrides response tones |
| `llmwiki.search` | `SEARCH_TOKENIZER` | Replaces default tokenization |
| `llmwiki.taxonomy` | `TAXONOMY_LABEL_KEYS` | Changes taxonomy label languages |
| `llmwiki.taxonomy` | `TAXONOMY_GENERATOR` | Replaces the built-in taxonomy generator |
| `llmwiki.web` | `EXTRA_ROUTES` | Adds custom HTTP routes before app creation |
| `llmwiki.web` | `BEFORE_REQUEST_HOOKS` / `AFTER_REQUEST_HOOKS` | Extends request lifecycle hooks |

## Operational guidance

- Use `llmwiki/operations.py` for behavior that must stay consistent across CLI, HTTP, and MCP.
- Prefer `kb_export_article`, `kb_export_tag`, and `kb_export_graph` over legacy unified export calls.
- Treat optional environment dependencies explicitly in tests when they are not guaranteed in the current interpreter.
- Domain filtering threads through `search.py`, `query.py`, and `compile.py`; domain CRUD lives in `domains.py`. Telegram and email are `telegram.py` / `mail.py`, started in `create_asgi_app`'s lifespan.
