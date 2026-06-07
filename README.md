# LLMBase

LLMBase is an LLM-assisted knowledge base that turns raw documents into a structured wiki.

## Language model

The repository currently targets English and Italian output across compilation, search, export, taxonomy, and guided-introduction flows.

## Architecture

```
+---------------------+  +---------------------+  +---------------------+
|  Web UI (Frontend)  |  |  CLI (Click)        |  |  MCP Client         |
|  llmbase web        |  |  llmbase ...        |  |  (stdio / HTTP)     |
+---------+-----------+  +---------+-----------+  +---------+-----------+
          |                        | direct calls           |
          v                        |                        |
+---------+-----------+            |                        |
|  Nginx              |            |                        |
|  Reverse Proxy      |            |                        |
|  :80 (container)    |            |                        |
|  :5555 (host)       |            |                        |
|  /      -> :5555    |            |                        |
|  /mcp   -> :8100    |            |                        |
+---------+-----------+            |                        |
          |                        |                        |
          v                        v                        v
+---------------------+  +---------------------+  +---------------------+
|  Flask Web API      |  |  CLI handlers       |  |  MCP Server         |
|  :5555 (Gunicorn)   |  |  (direct module     |  |  :8100              |
|  Full REST API      |  |   calls)            |  |  stdio / HTTP       |
|  (UI + CRUD + Lint) |  |                     |  |                     |
+----------+----------+  +----------+----------+  +----------+-----------+
           |                        |                        |
           | partial                | direct                 | full
           v                        v                        v
+--------------------------------------------------------------------+
|  Modules & Operations Registry                                     |
|  operations.py  <- MCP + Agent API converge here                   |
|  Direct module calls  <- Web API + CLI use these                   |
|  (ingest, compile, search, query, lint, export, entities, xici)    |
+--------------------------------------------------------------------+
           |
+------------+-----------+-----------+
|            |           |           |
v            v           v           v
+----------+ +----------+ +----------+ +----------+
|  Ingest  | |  Compile | |  Search  | |  Query   |
|  URL     | |  new     | |  (full-  | |  (LLM    |
|  File    | |  all     | |   text)  | |   Q&A)   |
|  PDF     | |  index   | |          | |          |
|  Dir     | |          | |          | |          |
|  Browse  | |          | |          | |          |
+----+-----+ +----+-----+ +----+-----+ +----+-----+
     |            |            |            |
     v            v            v            v
+--------------------------------------------------------------------+
|  Storage                                                           |
|  wiki/ (articles) | wiki/_meta/ (index, taxonomy, aliases,         |
|                   |   backlinks, seed-urls, llm-usage, trails)     |
+--------------------------------------------------------------------+
```

> **Note:** The CLI calls modules directly — it does not go through Gunicorn or the HTTP layer.
> `operations.py` is the convergence point for MCP and Agent API; Web API and CLI call modules directly.
> The Worker (`llmbase-worker`) and MCP (`llmbase-mcp`) are separate Docker services (see `compose.build.yaml`).
>
> **Connection modes:**
> - **partial** — Web API: some routes use `operations.py` (`/api/ask`, `/api/ingest`), others call modules directly (`/api/search`, `/api/lint`, `/api/taxonomy`).
> - **direct** — CLI: imports and calls module functions directly (e.g. `ingest_url()`, `compile_new()`, `search()`), no HTTP involved.
> - **full** — MCP Server: every tool call goes through `ops.dispatch()`, `operations.py` is the only entry point.

## What it does

1. Ingest raw material from URLs, local files, PDFs, or directories.
2. Batch-upload multiple PDF files from the web UI.
3. Compile raw material into linked wiki articles under `wiki/concepts`.
4. Search and ask questions against the compiled knowledge base.
5. Export article, tag, and graph views for downstream tools.
6. Run lint and cleanup workflows to keep the KB consistent.

## Install

```bash
pip install -r requirements.txt
```

Frontend:

```bash
cd frontend
npm install
```

## Quick Start

```bash
llmbase ingest url https://example.com/article
llmbase ingest file notes.md
llmbase ingest pdf manual.pdf

llmbase compile new
llmbase query "What is the main topic?" --deep
llmbase search query "architecture"

llmbase web
```

The web UI `/ingest` page supports PDF and Markdown uploads. Page chunking applies only to PDFs.

## Reverse Proxy Auth

The compose files now support an Nginx front door that protects the entire UI and HTTP API with Basic Auth, while llmbase keeps `LLMBASE_API_SECRET` for sensitive application routes.

Create the local Basic Auth file before starting the stack:

```bash
docker run --rm --entrypoint htpasswd httpd:2.4-alpine -nbB admin change-me > nginx/.htpasswd
```

On Windows/PowerShell you can generate the same file with:

```powershell
.\nginx\generate-htpasswd.ps1 -Username admin -Password change-me
```

Set `LLMBASE_API_SECRET` in `.env`, then start the stack in detached mode:

```bash
docker compose -f compose.build.yaml up -d --build
```

If you run `docker compose up` in the foreground, stopping that process also stops the stack.
In that case Docker may report `nginx exited with code 0`, which is a normal graceful shutdown rather than a proxy failure.

The compose topology starts four services: `nginx`, `llmbase`, `llmbase-worker`, and `llmbase-mcp`.
The dedicated worker container keeps background jobs out of the Gunicorn web processes.
The MCP service exposes the knowledge base to AI clients over the Model Context Protocol.

If the secret contains `$`, escape it as `$$` in `.env` when using Docker Compose, otherwise Compose will try to interpolate it before the value reaches the container.

With this topology:
- Nginx challenges all browser and API traffic with Basic Auth on the public port.
- llmbase still protects write routes internally with the derived `llmbase_auth` cookie or the API secret.
- Browser UI requests work unchanged because the SPA response sets the app cookie.
- Direct API clients behind Nginx must send `X-LLMBASE-Authorization: Bearer <LLMBASE_API_SECRET>` when they need application-level auth, because the standard `Authorization` header is consumed by Nginx Basic Auth.
- The worker container idles safely while `worker.enabled: false`; once you enable it in `config.yaml`, the same service starts ingest/compile/taxonomy/health jobs without changing the deployment topology.

## Main CLI Surfaces

Ingest:
- `llmbase ingest url <url>`
- `llmbase ingest file <path>`
- `llmbase ingest pdf <path> [--chunk-pages N]`
- `llmbase ingest dir <path>`
- `llmbase ingest browse <url>`
- `llmbase ingest list`

Compile:
- `llmbase compile new`
- `llmbase compile all`
- `llmbase compile index`

Ask and search:
- `llmbase query "<question>" --deep`
- `llmbase search query "<text>"`

Maintenance:
- `llmbase lint check`
- `llmbase lint deep`
- `llmbase lint fix`
- `llmbase lint normalize-tags`
- `llmbase lint clean`
- `llmbase lint dedup`
- `llmbase lint heal`

Export:
- `llmbase export article <slug>`
- `llmbase export tag <tag>`
- `llmbase export graph <slug> [--depth N]`

Services:
- `llmbase web`
- `llmbase serve`
- `llmbase mcp`

## Configuration Notes

Important defaults:
- `worker.learn_source: seed_urls`
- ask tones: `default`, `caveman`, `scholar`, `eli5`
- taxonomy labels: English and Italian

See `config.yaml` and the docs under `docs/` for details.
