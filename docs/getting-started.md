# Getting Started

## Install dependencies

```bash
pip install -e .
```

If you want the optional MCP server dependency as well:

```bash
pip install -e ".[mcp]"
```

`pip install -r requirements.txt` is still useful when you want repo-local dependency parity, but the `llmbase` CLI entry point is installed by `pip install -e .`.

## Create or choose a KB directory

LLMBase stores its working data under:
- `raw/`
- `wiki/concepts/`
- `wiki/_meta/`
- `wiki/outputs/`

## Minimal config

The shipped `config.yaml` is a valid starting point. The important worker default is:

```yaml
worker:
  learn_source: seed_urls
```

When you enable the worker, populate `wiki/_meta/seed-urls.json` with the URLs you want it to ingest.

## First run

```bash
llmbase ingest file notes.md
llmbase compile new
llmbase query "What is this document about?" --deep
```

## Run the web app

```bash
llmbase web
```

Then open `http://localhost:5555`.

## Domains

Every document has a `domain` (default `generale`). Create and manage domains
from the web UI (Dashboard → Domini), via the HTTP API (`/api/domains`), or via
the `kb_domains_*` MCP tools. Search and ask accept a `domain` parameter to
scope results to one domain.

## Telegram bot

See [Telegram bot](telegram.md) for full configuration. Set `LLMBASE_TG_TOKEN`
and `LLMBASE_TG_ALLOWED_CHAT_IDS` in `.env` to enable it.

## Email ingestion

See [Email ingestion](email-ingestion.md) for full configuration. Set
`LLMBASE_MAIL_HOST`, `LLMBASE_MAIL_USER`, and `LLMBASE_MAIL_PASSWORD` in `.env`
to enable it.

