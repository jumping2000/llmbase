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

## Streamable HTTP (JSON mode, unified)

L'MCP streamable HTTP è ora parte della web app — non richiede un servizio separato.
Si avvia con:

```bash
uvicorn asgi:app --host 127.0.0.1 --port 5555
```

L'endpoint MCP è disponibile su `http://localhost:5555/mcp` con risposte JSON pure
(`json_response=True`, niente SSE sulle POST).

### Auth

Se `MCP_API_KEY` è configurata nell'ambiente, le richieste a `/mcp` devono includere
l'header `X-API-Key: <chiave>`. In sviluppo locale (senza `MCP_API_KEY`), l'endpoint
è aperto.

### CLI (deprecato)

```bash
# Deprecato — usare uvicorn asgi:app
llmbase mcp --transport streamable-http --http-port 8100
```

`stdio` rimane il default e non è deprecato:

```bash
llmbase mcp
```

## Docker Compose deployment

Il servizio `llmbase-mcp` non esiste più. L'MCP è servito dallo stesso container
della web app su `/mcp`.

L'unica variabile d'ambiente MCP necessaria è `MCP_API_KEY`:

```dotenv
MCP_API_KEY=change-me
```

Nginx inoltra `/mcp` allo stesso upstream di `/` e passa l'header `X-API-Key`.

## Configurazione

| Variabile | Default | Descrizione |
|---|---|---|
| `MCP_API_KEY` | *(vuoto)* | Chiave per autenticare le richieste `/mcp` via header `X-API-Key`. Vuoto = nessuna auth. |

Le variabili `MCP_TRANSPORT`, `MCP_HTTP_PORT`, `MCP_HTTP_URL` sono rimosse.

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
- `kb_domains_list`
- `kb_domains_create`
- `kb_domains_rename`
- `kb_domains_delete`
- `kb_domains_bulk_assign`

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
