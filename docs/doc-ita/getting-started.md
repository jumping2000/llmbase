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

## Domini

Ogni documento ha un `domain` (default `generale`). Crea e gestisci i domini
dalla UI web (Dashboard → Domini), via API HTTP (`/api/domains`) oppure con gli
strumenti MCP `kb_domains_*`. Search e ask accettano un parametro `domain` per
limitare i risultati a un dominio.

## Bot Telegram

Imposta `LLMBASE_TG_TOKEN` e `LLMBASE_TG_ALLOWED_CHAT_IDS` in `.env` (vedi
`.env.example`). Il bot offre `/ask`, `/cerca`, `/dominio` e l'invio di
documenti, e gira nello stesso processo dell'app web.

## Ingestione email

Imposta `LLMBASE_MAIL_HOST`, `LLMBASE_MAIL_USER` e `LLMBASE_MAIL_PASSWORD` in
`.env`. Il poller controlla la casella ogni minuto; un tag `[dominio]`
nell'oggetto indirizza il messaggio (corpo e allegati PDF) a quel dominio.

