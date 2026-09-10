# Sviluppo plugin

LLMBase supporta ancora punti di estensione in stile plugin, ma il repository non distribuisce più plugin corpus-specific incorporati.

## Plugin di riferimento

Un plugin di riferimento definisce tipicamente:
- `PLUGIN_ID`
- `PLUGIN_NAME`
- `get_source_url(source: dict) -> str`

Usa per default nomi di visualizzazione in inglese e italiano.

## Plugin di operazioni

Se vuoi che una funzionalità appaia in CLI, HTTP e MCP, registrala tramite `llmwiki.operations.register`.

## Fonti di apprendimento

Le custom learn sources possono essere registrate downstream.
Il repository predefinito non assume più alcuna fonte esterna incorporata.

## Sincronizzazione remota dello stato

`llmwiki/sync.py` è un adattatore PostgREST generico che salva lo stato di
ingest e compile su una tabella Postgres remota, così un filesystem effimero
(reset del volume, ricostruzione del container) non provoca il re-ingest di
sorgenti già note. Funziona con qualsiasi endpoint PostgREST — Supabase,
PostgREST self-hosted e simili.

**È opt-in e non è collegato di default.** Nessun modulo core lo importa: un
progetto a valle lo attiva registrando gli hook di ciclo di vita.

```python
from llmwiki.hooks import register
from llmwiki import sync

register("ingested", lambda source, title, path, **kw: sync.push_ingested(source, path, title=title))
register("compiled", lambda source, work_id, **kw: sync.mark_compiled(source, work_id))
```

L'evento `"ingested"` non porta un `work_id`: un progetto a valle deve
derivarne uno proprio, qui da `path`. `"compiled"` porta invece `work_id`.

La configurazione avviene interamente per variabile d'ambiente, e il modulo non
fa nulla se non sono impostate:

| Variabile | Default | Descrizione |
|---|---|---|
| `LLMBASE_SYNC_URL` | *(vuoto)* | URL base dell'endpoint PostgREST. In alternativa è accettata `SUPABASE_URL`. |
| `LLMBASE_SYNC_KEY` | *(vuoto)* | Bearer token / API key. In alternativa è accettata `SUPABASE_KEY`. |
| `LLMBASE_SYNC_TABLE` | `llmbase_ingested` | Nome della tabella. |
| `LLMBASE_REMOTE_TABLE` | *(vuoto)* | Alias legacy di `LLMBASE_SYNC_TABLE`, consultato quando quest'ultima non è impostata. |

Lo schema di tabella atteso è documentato nella docstring in testa a
`llmwiki/sync.py`.
