# LLMBase

LLMBase is an LLM-assisted knowledge base that turns raw documents into a structured wiki.

## Language model

The repository currently targets English and Italian output across compilation, search, export, taxonomy, and guided-introduction flows.

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

Optional runtime dependencies:
- `flask` for the web UI and HTTP API
- `requests` for URL ingest

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

The web UI `/ingest` page also supports multi-PDF upload with configurable page chunking.

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
- `llmbase lint fix`
- `llmbase lint heal`

Services:
- `llmbase web`
- `llmbase serve`
- `llmbase mcp`

## Configuration Notes

Important defaults:
- `worker.learn_source: url`
- ask tones: `default`, `caveman`, `scholar`, `eli5`
- taxonomy labels: English and Italian

See `config.yaml` and the docs under `docs/` for details.
