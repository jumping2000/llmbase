# MCP Server

LLMBase can run as a Model Context Protocol server over `stdio` or `streamable-http`.

## Install runtime dependencies

The packaged runtime now includes the MCP HTTP dependencies. For editable installs, this is still a safe baseline:

```bash
pip install -e .
```

## Start with stdio

```bash
llmbase mcp
```

`stdio` remains the default transport.

## Streamable HTTP (unified)

MCP streamable HTTP is now part of the web app — no separate service is needed.
Start the unified ASGI app:

```bash
uvicorn asgi:app --host 127.0.0.1 --port 5555
```

The MCP endpoint is served at `http://localhost:5555/mcp` with pure JSON responses
(`json_response=True`, no SSE on POST).

### Auth

If `MCP_API_KEY` is set in the environment, requests to `/mcp` must include the
`X-API-Key: <key>` header. In local development (no `MCP_API_KEY`), the endpoint
is open.

### CLI (deprecated)

```bash
# Deprecated — use uvicorn asgi:app
llmbase mcp --transport streamable-http --http-port 8100
```

`stdio` remains the default and is not deprecated:

```bash
llmbase mcp
```

## Docker Compose deployment

The `llmbase-mcp` service no longer exists. MCP is served by the same container
as the web app, on `/mcp`.

The only MCP environment variable needed is `MCP_API_KEY`:

```dotenv
MCP_API_KEY=change-me
```

Nginx forwards `/mcp` to the same upstream as `/` and passes the `X-API-Key`
header through.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MCP_API_KEY` | *(empty)* | Key for authenticating `/mcp` requests via the `X-API-Key` header. Empty = no auth. |
| `MCP_TRANSPORT` | `stdio` | Transport for the standalone `llmbase mcp` launcher: `stdio` or `streamable-http`. Any other value is rejected at startup. |
| `MCP_HTTP_PORT` | `8100` | Port used when the standalone launcher runs with `streamable-http`. |
| `MCP_HTTP_URL` | *(empty)* | Advertised base URL for the standalone launcher; when set it must parse as `http://…` or `https://…`. |

These three variables are still read and honoured by `llmbase mcp`
(`llmwiki/mcp_config.py`), but they only affect the standalone launcher — the
unified ASGI app ignores them. Running the launcher with
`MCP_TRANSPORT=streamable-http` is deprecated and emits a `DeprecationWarning`:
serve `/mcp` from the unified ASGI app (`uvicorn asgi:app`) instead. The Docker
Compose deployment described above needs none of them.

## Contract source of truth

The MCP server is generated from `llmwiki/operations.py`. If an operation is registered there, it can be surfaced consistently across CLI, HTTP, and MCP.

## Important operations

The list below is illustrative, not exhaustive. The actual MCP tool surface is generated directly from `llmwiki/operations.py`.

- `kb_search`
- `kb_search_raw`
- `kb_ask`
- `kb_get`
- `kb_get_sections`
- `kb_list`
- `kb_backlinks`
- `kb_taxonomy`
- `kb_stats`
- `kb_ingest`
- `kb_ingest_browser`
- `kb_compile`
- `kb_lint`
- `kb_lint_fix`
- `kb_llm_usage_summary`
- `kb_llm_usage_recent`
- `kb_export_article`
- `kb_export_tag`
- `kb_export_graph`
- `kb_export`
- `kb_rebuild_index`
- `kb_backfill_doc_dates`
- `kb_xici`
- `kb_domains_list`
- `kb_domains_create`
- `kb_domains_rename`
- `kb_domains_delete`
- `kb_domains_bulk_assign`

`kb_export` is the unified export: it takes a required `type` (`article`, `tag`
or `graph`) plus a `slug`, and an optional `depth` (default `2`, graph only).
Its own tool description marks it as legacy and points at
`kb_export_article` / `kb_export_tag` / `kb_export_graph`, which are the
preferred entry points. `kb_backfill_doc_dates` extracts `doc_date` for raw
documents missing it and propagates the value to citing articles; `force=true`
re-extracts dates that are already present.

## Domain filtering

`kb_search` and `kb_ask` accept an optional `domain` parameter to scope the
query to a single domain (default `generale`). The `kb_domains_*` tools manage
the domain list stored in `wiki/_meta/domains.json`.

## Ask tone values

The built-in `kb_ask` tone options are:
- `default`
- `caveman`
- `scholar`
- `eli5`
