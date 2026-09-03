# Domini, Email Ingestion e Bot Telegram

**Data:** 2026-09-03
**Stato:** Approvato

## Obiettivo

Aggiungere a llmbase tre funzionalità:

1. **Domini** — suddividere la knowledge base in ambiti (lavoro, studio, casa...) mantenendo una singola wiki, coerente con l'idea di LLM wiki di Andrej Karpathy (una base unica, il modello organizza e collega).
2. **Email ingestion** — inviare una mail a un indirizzo associato all'app e vederne contenuto e allegati PDF inseriti come documenti nella wiki, quasi immediatamente.
3. **Bot Telegram** — interrogare la wiki e inserire documenti via Telegram.

## Stato attuale

- Ingestion pipeline esistente: file/PDF → `raw/` (markdown + frontmatter) → `compile.py` (LLM) → `wiki/concepts/*.md` bilingue EN/IT. Esistono già `/api/upload`, `ingest_file`, `ingest_pdf` (PyMuPDF).
- Worker in background (`llmbase-worker` + thread in-process) compila, rigenera tassonomia, health check. Fonti di apprendimento pluggabili via `register_learn_source` e job custom via `register_job`.
- **KB unica**: un solo `base_dir` con `raw`, `wiki`, `concepts`, `_meta` (index.json). Tutto (search, ask, compile, MCP) opera su quel singolo base. **Nessun concetto di dominio/tenant oggi.**
- Accesso uniforme: 22 operazioni registrate in `operations.py` (`kb_search`, `kb_ask`, `kb_get`, `kb_ingest`...), esposte via web, CLI e MCP.

## Decisioni chiave

| # | Decisione |
|---|---|
| Modello domini | **B** — KB unica + campo `domain` sui documenti |
| Ciclo vita domini | **D** — dinamici da UI, assegnazione esplicita (default `generale`), LLM suggerisce ma non impone |
| Ricezione email | **IMAP polling** + tag nel subject `[lavoro]` |
| Bot Telegram | **long-polling** + whitelist `chat_id` + comando `/dominio` |
| Ordine implementazione | **Domini → Telegram → Email** |

## Architettura

```
Uvicorn :5555 (asgi.py)
└── app
    ├── Flask web UI + API REST (invariato nelle rotte esistenti)
    ├── MCP streamable HTTP  (/mcp, invariato)
    ├── thread Worker        (invariato)
    ├── thread Telegram      (nuovo, long-polling)   ← feature 2
    └── thread Mail poller   (nuovo, IMAP ogni 1 min) ← feature 3

operazioni condivise (operations.py)
├── kb_search / kb_ask / kb_get ...   ← riusate da Telegram
└── ingest_pdf / ingest_file          ← riusate da Email e Telegram

wiki/concepts/*.md  ← frontmatter con campo `domain`
wiki/_meta/domains.json  ← elenco domini gestito da UI
```

### 1. Domini (fondamenta, primo step)

**Modello dati**
- Campo `domain` nel frontmatter dei documenti raw e degli articoli compilati. Valore assente = `generale`.
- Elenco domini persistito in `wiki/_meta/domains.json`: lista di `{"id": "lavoro", "label": "Lavoro"}`. `id` = slug (safe filename), `label` = nome visualizzato.
- Nuovo modulo `llmwiki/domains.py`: `list_domains`, `create_domain`, `rename_domain`, `delete_domain`, `normalize_domain_id`.

**Assegnazione**
- Esplicita all'ingest: form upload, tag mail, comando Telegram scrivono `domain` nel frontmatter del raw.
- Al compile: se il raw ha `domain` esplicito → vince; se vuoto → il LLM suggerisce il dominio (il prompt di compile riceve l'elenco domini) e il valore suggerito viene scritto nell'articolo. Modificabile dopo da UI.
- `ingest_file` / `ingest_pdf` / `api_upload` accettano un parametro `domain` opzionale e lo scrivono nel frontmatter.

**Filtro**
- `search(query, domain=None, ...)` e `query_with_search(..., domain=None, ...)` accettano `domain` opzionale e filtrano il corpus agli articoli con quel dominio.
- `rebuild_index` include `domain` in ogni voce di `index.json`, così il filtro è O(1) sull'indice senza riscan dei file.
- API: `/api/search`, `/api/ask` accettano il query param `domain`; MCP `kb_search` / `kb_ask` accettano il param `domain`; dropdown nel frontend.
- I cross-link `[[slug]]` restano globali: un articolo può linkare un concetto di un altro dominio (scelta B). Nessuna modifica a risoluzione link/backlink.

**Gestione UI**
- API: `GET /api/domains`, `POST /api/domains`, `DELETE /api/domains/<id>`, `POST /api/domains/<id>/rename`.
- Eliminazione di un dominio: i documenti con quel `domain` vengono riassegnati a `generale` (nessun orfano).
- Frontend: selettore dominio nella toolbar + pagina settings per creare/rinominare/eliminare domini.

**Migrazione**
- Backfill una tantum: articoli senza `domain` → `generale` (al primo rebuild index). Nessun downtime.

**File toccati**: nuovo `llmwiki/domains.py`; `config.py` (defaults), `ingest.py`, `compile.py` (prompt + carry), `search.py`, `query.py`, `web.py` (route + param), `operations.py` (`kb_search`/`kb_ask` params + nuove op `kb_domains_*`), `rebuild_index`; frontend (selettore + settings).

### 2. Bot Telegram (secondo step)

- Nuovo `llmwiki/telegram.py`: thread long-polling (`getUpdates`, `timeout=30`) avviato nel ciclo di vita di `asgi.py`, accanto al worker.
- Config `.env`: `LLMBASE_TG_TOKEN`, `LLMBASE_TG_ALLOWED_CHAT_IDS` (lista separata da virgola), `LLMBASE_TG_DEFAULT_DOMAIN`.
- Comandi:
  - `/ask <domanda>` → `operations.dispatch("kb_ask", ..., domain=<dominio corrente>)`
  - `/cerca <testo>` → `kb_search` con dominio corrente
  - `/dominio <nome>` → switch del dominio di default per quella chat (stato per-chat in-memory, reset al riavvio del processo)
  - `/dominio` (senza argomento) → mostra il dominio corrente
  - `/aiuto` → help
  - Upload di PDF/testo → ingest nel dominio corrente via `ingest_pdf` / `ingest_file`
  - Messaggio di testo senza comando → trattato come domanda (`/ask`)
- Auth: messaggi da `chat_id` non in whitelist vengono ignorati (con log a debug).
- Errori: errori API Telegram → log + retry; timeout del long-poll → riconnessione automatica.

### 3. Email ingestion (terzo step)

- Nuovo `llmwiki/mail.py`: poll IMAP ogni N minuti (default 1) in un thread dedicato.
- Config `.env`: `LLMBASE_MAIL_HOST`, `LLMBASE_MAIL_PORT`, `LLMBASE_MAIL_USER`, `LLMBASE_MAIL_PASSWORD`, `LLMBASE_MAIL_FOLDER` (default `INBOX`), `LLMBASE_MAIL_PROCESSED_FOLDER` (default `Processed`), `LLMBASE_MAIL_POLL_MINUTES` (default 1).
- Per ogni messaggio non processato:
  1. Regex `\[([^\]]+)\]` sul subject → slug dominio (case-insensitive). Se non corrisponde a un dominio esistente → `generale` (con warning).
  2. Body HTML/plain → markdown (markdownify già in uso per l'ingest web).
  3. Allegati: PDF → `ingest_pdf`; altri → `ingest_file`.
  4. Body e ogni allegato scritti in `raw/<slug>/` con `domain` nel frontmatter.
- Dedup: sposta il messaggio nella cartella `processed` dopo l'elaborazione (fallback: marca letto).
- Errori: IMAP giù → log + retry al poll successivo (nessun crash); allegato PDF rotto → salta l'allegato, ingerisce comunque il body.

### Trasversale

- Config: sezioni `domains`, `mail`, `telegram` in `config.yaml` (valori non-secret); segreti in `.env` (mai in `config.yaml`).
- Tutte e tre le feature riusano `operations.py` come unica fonte di verità per ask/search/ingest.
- Thread nuovi con avvio/arresto nel lifespan di `asgi.py` (stesso pattern del worker thread).

## Criteri di verifica (definizione di "finito")

1. **Domini**: creo `lavoro` da UI; cerco con filtro `lavoro` e un documento `domain: lavoro` appare, uno `domain: studio` no; `ask` scoped per dominio risponde solo con contenuto del dominio.
2. **Email**: invio una mail con subject `[lavoro] ...` + allegato PDF → entro ~1 min il documento appare in wiki con `domain: lavoro`, contenuto testuale + testo del PDF processati; una mail con tag sconosciuto atterra su `generale`.
3. **Telegram**: `/ask` risponde attingendo alla wiki; invio un PDF al bot → entra in wiki nel dominio corrente; `/dominio studio` cambia il dominio delle operazioni successive; un `chat_id` non whitelisted viene ignorato.

## Testing

- Unit test per: filtro dominio in `search`/`query`, parsing tag subject, routing comandi Telegram (API mockata), parsing messaggi IMAP (mailbox mockata), gestione domini (create/rename/delete con riassegnazione a `generale`).
- Test di integrazione: ingest con `domain` → compile → articolo con `domain` corretto e presente in `index.json`.
- Dipendenze opzionali (imaplib è stdlib; client Telegram via httpx/requests già presenti) vanno guardate con `importorskip` quando non garantite nell'interprete di test.

## Non obiettivi (YAGNI)

- Niente workspace/indici separati per dominio (scelta B).
- Niente push webhook per email in questo step (si aggiunge dopo se serve, il design lo consente).
- Niente multi-utente/bot pubblici: il bot Telegram è personale (whitelist).
- Niente classificazione automatica "imposta" dei domini: il LLM solo suggerisce.
