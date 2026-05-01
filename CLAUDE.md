# Claude Notes

This repository is configured around a compact set of customization points.

## Core assumptions

- Default article sections are English and Italian.
- Built-in ask tones are `default`, `caveman`, `scholar`, and `eli5`.
- Worker autonomous learning defaults to URL-based sources.
- Search uses Unicode word tokenization by default.

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
