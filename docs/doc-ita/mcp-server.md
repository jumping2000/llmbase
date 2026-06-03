# Server MCP

LLMBase può essere eseguito come server Model Context Protocol su `stdio` oppure `streamable-http`.

## Installazione delle dipendenze runtime

Il runtime pacchettizzato ora include anche le dipendenze MCP HTTP. Per un'installazione editable va bene anche:

```bash
pip install -e .
```

## Avvio in stdio

```bash
llmbase mcp
```

`stdio` resta il transport predefinito.

## Avvio in streamable-http

```bash
llmbase mcp --transport streamable-http --http-port 8100
```

Impostazioni supportate:

- `MCP_TRANSPORT`: `stdio` oppure `streamable-http`
- `MCP_HTTP_PORT`: porta locale di ascolto in modalità HTTP
- `MCP_HTTP_URL`: URL upstream completo opzionale usato dal layer di proxy
- `MCP_API_KEY`: segreto condiviso validato dal proxy Nginx su `/mcp`

I flag CLI hanno precedenza sul `.env`, e il `.env` ha precedenza sui default interni.

## Deploy con Docker Compose

Lo stack Compose incluso avvia un servizio dedicato `llmbase-mcp` ed espone MCP tramite Nginx su `/mcp`.

Nginx valida sempre `X-API-Key` contro `MCP_API_KEY` prima di inoltrare al servizio MCP upstream.

Valori tipici nel `.env`:

```dotenv
MCP_TRANSPORT=streamable-http
MCP_HTTP_PORT=8100
MCP_HTTP_URL=http://llmbase-mcp:8100/mcp
MCP_API_KEY=change-me
```

I client pubblici si collegano all'host esistente su `/mcp` e devono inviare `X-API-Key`.

## Fonte di verità del contratto

Il server MCP è generato da `llmwiki/operations.py`.
Se un'operazione è registrata lì, può essere esposta in modo coerente su CLI, HTTP e MCP.

## Operazioni importanti

L'elenco seguente è illustrativo, non esaustivo. La superficie reale degli strumenti MCP viene generata direttamente da `llmwiki/operations.py`.

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

## Toni di `kb_ask`

I toni integrati per `kb_ask` sono:
- `default`
- `caveman`
- `scholar`
- `eli5`
