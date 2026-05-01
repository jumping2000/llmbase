# Getting Started

## Install dependencies

```bash
pip install -r requirements.txt
```

Optional extras commonly needed in development:
- `flask` for the web UI
- `requests` for URL ingest

## Create or choose a KB directory

LLMBase stores its working data under:
- `raw/`
- `wiki/concepts/`
- `wiki/_meta/`
- `wiki/outputs/`

## Minimal config

The shipped `config.yaml` is a valid starting point. The important worker default is:

```yaml
worker:
  learn_source: url
```

## First run

```bash
llmbase ingest file notes.md
llmbase compile new
llmbase query "What is this document about?" --deep
```

## Run the web app

```bash
llmbase web
```

Then open `http://localhost:5555`.
