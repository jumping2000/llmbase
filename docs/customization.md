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

## Web extension points

Register extra routes before app creation:

```python
import llmwiki.web as web_mod

def my_handler():
    return {"status": "ok"}

web_mod.EXTRA_ROUTES.append(("/api/custom", my_handler, {"methods": ["GET"]}))
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
