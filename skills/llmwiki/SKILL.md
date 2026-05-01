---
name: llmwiki
description: "LLM-powered knowledge base that compiles raw documents into linked English/Italian wiki articles with search, taxonomy, export, lint, and MCP/HTTP operations."
---

# LLMWiki Skill

Use this skill when you need to work on the LLMBase knowledge-base engine.

## Product model

- Raw material is ingested into `raw/`.
- Compilation produces wiki articles in `wiki/concepts/`.
- Articles are structured for English and Italian output.
- CLI, HTTP, and MCP all route through `llmwiki/operations.py`.

## Primary capabilities

- URL, file, PDF, directory, and browser-assisted ingest
- Incremental or full compilation
- KB question answering and search
- Taxonomy generation and guided introductions
- Lint, auto-fix, duplicate merge, and cleanup workflows
- Structured export for article, tag, and graph views

## Common commands

| Command | Purpose |
| --- | --- |
| `llmbase ingest url <url>` | Ingest a remote article |
| `llmbase ingest file <path>` | Ingest a local file |
| `llmbase ingest pdf <path>` | Ingest a PDF |
| `llmbase compile new` | Compile only new raw documents |
| `llmbase query "<q>" --deep` | Multi-step KB question answering |
| `llmbase search query "<text>"` | Search compiled articles |
| `llmbase lint heal` | Run the health cycle |
| `llmbase web` | Start the web UI and HTTP API |
| `llmbase mcp` | Start the MCP server |

## Design constraints

- Keep prompts, exports, and tests aligned with the English/Italian contract.
- When adding new user-facing behavior, register it in `llmwiki/operations.py` if it should be shared by CLI, HTTP, and MCP.
