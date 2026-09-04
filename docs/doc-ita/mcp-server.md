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

## Avvio in streamable-http (unificato)

L'MCP streamable HTTP è ora parte della web app — non serve un servizio separato.
Avvia l'app ASGI unificata:

```bash
uvicorn asgi:app --host 127.0.0.1 --port 5555
```

L'endpoint MCP è servito su `http://localhost:5555/mcp` con risposte JSON pure
(`json_response=True`, niente SSE sulle POST).

### Auth

Se `MCP_API_KEY` è impostata nell'ambiente, le richieste a `/mcp` devono includere
l'header `X-API-Key: <chiave>`. In sviluppo locale (senza `MCP_API_KEY`), l'endpoint
è aperto.

### CLI (deprecato)

```bash
# Deprecato — usare uvicorn asgi:app
llmbase mcp --transport streamable-http --http-port 8100
```

`stdio` resta il transport predefinito e non è deprecato:

```bash
llmbase mcp
```

## Deploy con Docker Compose

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

Le variabili `MCP_TRANSPORT`, `MCP_HTTP_PORT` e `MCP_HTTP_URL` sono rimosse.

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
- `kb_domains_list`
- `kb_domains_create`
- `kb_domains_rename`
- `kb_domains_delete`
- `kb_domains_bulk_assign`

## Filtro per dominio

`kb_search` e `kb_ask` accettano un parametro opzionale `domain` per circoscrivere
la query a un singolo dominio (default `generale`). Gli strumenti `kb_domains_*`
gestiscono l'elenco domini salvato in `wiki/_meta/domains.json`.

## Toni di `kb_ask`

I toni integrati per `kb_ask` sono:
- `default`
- `caveman`
- `scholar`
- `eli5`
