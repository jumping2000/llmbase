# Personalizzazione

LLMBase è personalizzabile, ma il contratto di progetto predefinito resta inglese e italiano.

## Struttura articoli

Sovrascrivi gli header di sezione degli articoli:

```python
import llmwiki.compile as compile_mod

compile_mod.SECTION_HEADERS = [
    ("english", "## English"),
    ("italian", "## Italiano"),
]
```

## Toni di risposta

Aggiungi un tono personalizzato:

```python
import llmwiki.query as query_mod

query_mod.TONE_INSTRUCTIONS["formal_it"] = "Rispondi in italiano formale e preciso."
```

## Tokenizzazione della ricerca

Sostituisci il tokenizer predefinito:

```python
import re
import llmwiki.search as search_mod

def my_tokenizer(text: str) -> list[str]:
    return re.findall(r"\\w+", text.lower())

search_mod.SEARCH_TOKENIZER = my_tokenizer
```

## Etichette della tassonomia

Cambia le lingue delle etichette di tassonomia:

```python
import llmwiki.taxonomy as tax_mod

tax_mod.TAXONOMY_LABEL_KEYS = ["it"]
```

## Generazione della tassonomia

Sostituisci completamente il generatore integrato:

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

## Punti di estensione web

Registra route aggiuntive prima della creazione dell'app:

```python
import llmwiki.web as web_mod

def my_handler():
    return {"status": "ok"}

web_mod.EXTRA_ROUTES.append(("/api/custom", my_handler, {"methods": ["GET"]}))
```

Aggiungi hook del ciclo di vita delle richieste prima della creazione dell'app:

```python
import llmwiki.web as web_mod

def before_request_hook():
    ...

def after_request_hook(response):
    return response

web_mod.BEFORE_REQUEST_HOOKS.append(before_request_hook)
web_mod.AFTER_REQUEST_HOOKS.append(after_request_hook)
```

## Operazioni personalizzate

Esponi nuovo comportamento a CLI, HTTP e MCP tramite il registro condiviso:

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
