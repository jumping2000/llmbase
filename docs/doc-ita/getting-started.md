# Guida rapida

## Installa le dipendenze

```bash
pip install -e .
```

Se vuoi anche la dipendenza opzionale del server MCP:

```bash
pip install -e ".[mcp]"
```

`pip install -r requirements.txt` resta utile quando vuoi la parità locale delle dipendenze del repository, ma il comando `llmbase` viene installato da `pip install -e .`.

## Crea o scegli una directory KB

LLMBase archivia i dati di lavoro in:
- `raw/`
- `wiki/concepts/`
- `wiki/_meta/`
- `wiki/outputs/`

## Configurazione minima

Il `config.yaml` fornito è un punto di partenza valido. Il default importante del worker è:

```yaml
worker:
  learn_source: seed_urls
```

Quando abiliti il worker, popola `wiki/_meta/seed-urls.json` con gli URL che vuoi ingerire.

## Primo avvio

```bash
llmbase ingest file notes.md
llmbase compile new
llmbase query "What is this document about?" --deep
```

## Avvia l'app web

```bash
llmbase web
```

Poi apri `http://localhost:5555`.
