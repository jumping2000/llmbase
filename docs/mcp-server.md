# MCP Server

LLMBase can run as a Model Context Protocol server.

## Start it

Install the optional MCP dependency first:

```bash
pip install -e ".[mcp]"
```

```bash
llmbase mcp
```

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
