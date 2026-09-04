# Customization

LLMBase is customizable, but the default project contract is English and Italian.

## Article structure

Override article section headers:

```python
import llmwiki.compile as compile_mod

compile_mod.SECTION_HEADERS = [
    ("english", "## English"),
    ("italian", "## Italiano"),
]
```

## Ask tones

Add a custom tone:

```python
import llmwiki.query as query_mod

query_mod.TONE_INSTRUCTIONS["formal_it"] = "Rispondi in italiano formale e preciso."
```

## Search tokenization

Replace the default tokenizer:

```python
import re
import llmwiki.search as search_mod

def my_tokenizer(text: str) -> list[str]:
    return re.findall(r"\\w+", text.lower())

search_mod.SEARCH_TOKENIZER = my_tokenizer
```

## Taxonomy labels

Switch taxonomy label languages:

```python
import llmwiki.taxonomy as tax_mod

tax_mod.TAXONOMY_LABEL_KEYS = ["it"]
```

## Taxonomy generation

Replace the built-in taxonomy generator entirely:

```python
import llmwiki.taxonomy as tax_mod

def my_taxonomy_generator(articles, cfg):
    return {
        "categories": [
            {
                "id": "custom",
                "label": {"en": "Custom", "it": "Personalizzato"},
                "children": [],
            }
        ]
    }

tax_mod.TAXONOMY_GENERATOR = my_taxonomy_generator
```

## Web extension points

Register extra routes before app creation:

```python
import llmwiki.web as web_mod

def my_handler():
    return {"status": "ok"}

web_mod.EXTRA_ROUTES.append(("/api/custom", my_handler, {"methods": ["GET"]}))
```

Add request lifecycle hooks before app creation:

```python
import llmwiki.web as web_mod

def before_request_hook():
    ...

def after_request_hook(response):
    return response

web_mod.BEFORE_REQUEST_HOOKS.append(before_request_hook)
web_mod.AFTER_REQUEST_HOOKS.append(after_request_hook)
```

## Custom operations

Expose new behavior to CLI, HTTP, and MCP through the shared registry:

```python
from llmwiki.operations import Operation, register

def my_handler(base_dir, value: str):
    return {"value": value}

register(Operation(
    name="kb_custom",
    description="Custom operation",
    handler=my_handler,
    params={
        "type": "object",
        "properties": {"value": {"type": "string"}},
    },
))
```

## Document dates (`docdate`)

`doc_date` (ISO `YYYY-MM-DD` / `YYYY-MM` / `YYYY`) is extracted at ingest time
from the document's opening text (regex first, LLM fallback). It lives in the
raw document's frontmatter, is propagated to article `sources[]` at compile
time, and query answers prefer the most recent source on conflicts.

```yaml
docdate:
  enabled: true        # disable the whole module
  llm_fallback: true   # regex-only when false (zero LLM cost)
```

Backfill existing documents: `llmbase backfill-doc-dates [--force]`.
Edit from the UI: raw document preview → "Data stesura" field.

## Domains

Domains are first-class facets on articles. The implicit default domain is
`generale`; additional domains live in `wiki/_meta/domains.json` and are managed
through the web UI (Dashboard → Domini), the HTTP API, or the `kb_domains_*`
operations. Documents without an explicit domain fall back to `generale`.

## Telegram and email

Both integrations are optional and configured exclusively through environment
variables (see `.env.example`):

- Telegram long-polling bot — `llmwiki/telegram.py` (`LLMBASE_TG_TOKEN`,
  `LLMBASE_TG_ALLOWED_CHAT_IDS`, `LLMBASE_TG_DEFAULT_DOMAIN`).
- Email ingestion via IMAP — `llmwiki/mail.py` (`LLMBASE_MAIL_*`).

They start and stop in the ASGI lifespan alongside the worker; setting the
relevant env vars enables them.
