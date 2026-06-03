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

## Start with streamable-http

```bash
llmbase mcp --transport streamable-http --http-port 8100
```

Supported settings:

- `MCP_TRANSPORT`: `stdio` or `streamable-http`
- `MCP_HTTP_PORT`: local listen port for HTTP mode
- `MCP_HTTP_URL`: optional full upstream URL used by the proxy layer
- `MCP_API_KEY`: shared secret validated by the Nginx `/mcp` proxy

CLI flags override `.env`, and `.env` overrides built-in defaults.

## Docker Compose deployment

The bundled Compose stack runs a dedicated `llmbase-mcp` service and exposes it through Nginx on `/mcp`.

Nginx always validates `X-API-Key` against `MCP_API_KEY` before forwarding to the upstream MCP service.

Typical `.env` values:

```dotenv
MCP_TRANSPORT=streamable-http
MCP_HTTP_PORT=8100
MCP_HTTP_URL=http://llmbase-mcp:8100/mcp
MCP_API_KEY=change-me
```

Public clients connect to the existing host on `/mcp` and must send `X-API-Key`.

If you change `MCP_HTTP_PORT` in Compose, set `MCP_HTTP_URL` to the matching upstream URL so Nginx keeps forwarding to the correct internal port.

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
- `kb_rebuild_index`
- `kb_xici`

## Ask tone values

The built-in `kb_ask` tone options are:
- `default`
- `caveman`
- `scholar`
- `eli5`
