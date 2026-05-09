# Server MCP

LLMBase puo essere eseguito come server Model Context Protocol.

## Avvio

Installa prima la dipendenza MCP opzionale:

```bash
pip install -e ".[mcp]"
```

```bash
llmbase mcp
```

## Fonte di verita del contratto

Il server MCP e generato da `llmwiki/operations.py`.
Se un'operazione e registrata li, puo essere esposta in modo coerente su CLI, HTTP e MCP.

## Operazioni importanti

L'elenco seguente e illustrativo, non esaustivo. La superficie reale degli strumenti MCP viene generata direttamente da `llmwiki/operations.py`.

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
