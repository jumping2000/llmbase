# Riferimento API

Il server web espone un'API HTTP JSON insieme al frontend.

## Endpoint di lettura

- `GET /api/healthz`
- `GET /api/health`
- `GET /api/branding`
- `GET /api/stats`
- `GET /api/taxonomy`
- `GET /api/collections`
- `GET /api/articles`
- `GET /api/articles/lite`
- `GET /api/articles/<slug>`
- `GET /api/articles/<slug>/sections`
- `GET /api/aliases`
- `GET /api/search?q=<query>&top_k=<n>`
- `GET /api/tones`
- `GET /api/sources`
- `GET /api/sources/<slug>`
- `GET /api/compile/status`
- `GET /api/llm/usage/summary`
- `GET /api/llm/usage/recent?limit=<n>`
- `GET /api/export/article/<slug>`
- `GET /api/export/tag/<tag>`
- `GET /api/export/graph/<slug>?depth=<n>`
- `GET /api/entities`
- `GET /api/refs/plugins`
- `GET /api/trails`
- `GET /api/worker/status`
- `GET /api/wiki/export`
- `GET /api/xici`

## Endpoint di scrittura

- `POST /api/ask`
- `POST /api/entities/extract`
- `POST /api/ingest`
- `POST /api/ingest/browser`
- `POST /api/upload`
- `POST /api/compile`
- `POST /api/lint`
- `POST /api/lint/fix`
- `POST /api/wiki/clean`
- `POST /api/taxonomy/update`
- `POST /api/index/rebuild`
- `POST /api/xici/generate`
- `POST /api/trails`
- `POST /api/trails/<trail_id>/delete`
- `DELETE /api/articles/<slug>`

Quando `LLMBASE_API_SECRET` e impostato, gli endpoint di scrittura richiedono autenticazione.
Alcuni endpoint operazionali di lettura sono anch'essi protetti perche espongono stato dei job o attivita interne:

- `GET /api/compile/status`
- `GET /api/llm/usage/summary`
- `GET /api/llm/usage/recent`
- `GET /api/trails`
- `GET /api/worker/status`

`GET /api/healthz` e una sonda di liveness veloce.
`GET /api/health` restituisce l'ultimo report di salute persistito da `wiki/_meta/health.json`.

`POST /api/compile` parte in background e restituisce `202 Accepted` quando il job inizia.
Fai polling su `GET /api/compile/status` per ottenere uno stato esplicito `running`, `completed` o `failed`.

`POST /api/ingest` usa fetching HTTP diretto lato server per gli URL.
Se un sito remoto blocca l'accesso automatizzato, l'endpoint restituisce `400` con un errore user-facing invece di un generico `500`.

`POST /api/ingest/browser` e un fallback esplicito assistito dal browser per i siti bloccati.
Richiede il supporto dell'automazione browser (`opencli`) sull'host llmbase e ingerisce il risultato come `type = browser_article`.

`GET /api/worker/status` restituisce `{ "busy": true|false }` in base al lock condiviso dei write-job.

`GET /api/entities` restituisce le entita estratte in cache.
`POST /api/entities/extract` attiva subito l'estrazione delle entita; e utile solo quando `entities.enabled: true` in `config.yaml`.

`GET /api/wiki/export` esporta l'intera wiki compilata come JSON per backup o sincronizzazione downstream.

`GET /api/trails` elenca i trail di ricerca salvati e `POST /api/trails` aggiunge un passo o crea un trail.

`GET /api/compile/status` restituisce lo stato di compilazione persistito piu recente:

- idle: `{ "status": "idle" }`
- running: `{ "status": "running", "full": false, "started_at": "..." }`
- completed: `{ "status": "completed", "articles_created": 3, "articles": [...], "started_at": "...", "finished_at": "..." }`
- failed: `{ "status": "failed", "error": "...", "started_at": "...", "finished_at": "..." }`

Come `GET /api/worker/status`, questo endpoint e auth-gated quando `LLMBASE_API_SECRET` e impostato perche espone stato di scrittura.

`GET /api/llm/usage/summary` restituisce la contabilita aggregata dei token dal log append-only in `wiki/_meta/llm-usage.jsonl`.
Ogni riga di quel file rappresenta un tentativo reale del provider, inclusi retry, fallback, risposte vuote e fallimenti duri.

Parametri di query opzionali:

- `last=24h|7d|30d|365d`
- `from=<ISO8601>`
- `to=<ISO8601>`

Quando `last` e presente, ha precedenza su `from` e `to`. Il filtro temporale viene valutato in UTC. I record con timestamp mancanti o invalidi vengono esclusi dalle finestre filtrate e conteggiati in `skipped_timestamp_count`.

Forma del riepilogo:

```json
{
  "generated_at": "2026-05-08T10:41:00Z",
  "source_path": ".../wiki/_meta/llm-usage.jsonl",
  "applied_window": "24h",
  "from_ts": "2026-05-07T10:41:00Z",
  "to_ts": "2026-05-08T10:41:00Z",
  "record_count": 42,
  "malformed_record_count": 0,
  "missing_usage_count": 3,
  "skipped_timestamp_count": 1,
  "totals": {
    "prompt_tokens": 12000,
    "completion_tokens": 8400,
    "reasoning_tokens": 900,
    "total_tokens": 20400
  },
  "successful_totals": {
    "prompt_tokens": 11500,
    "completion_tokens": 8200,
    "reasoning_tokens": 900,
    "total_tokens": 19600
  },
  "retry_fallback_totals": {
    "prompt_tokens": 1300,
    "completion_tokens": 700,
    "reasoning_tokens": 0,
    "total_tokens": 2000
  },
  "by_model": [
    {
      "model": "gpt-4o",
      "attempt_count": 30,
      "success_count": 28,
      "retry_count": 2,
      "fallback_count": 0,
      "prompt_tokens": 10000,
      "completion_tokens": 7000,
      "reasoning_tokens": 900,
      "total_tokens": 17900
    }
  ],
  "by_feature": [
    {
      "feature": "ask",
      "attempt_count": 20,
      "success_count": 18,
      "retry_count": 2,
      "fallback_count": 1,
      "prompt_tokens": 5000,
      "completion_tokens": 3200,
      "reasoning_tokens": 200,
      "total_tokens": 8400,
      "by_stage": [
        {
          "stage": "answer",
          "attempt_count": 12,
          "success_count": 11,
          "retry_count": 1,
          "fallback_count": 1,
          "prompt_tokens": 4100,
          "completion_tokens": 3000,
          "reasoning_tokens": 200,
          "total_tokens": 7300
        }
      ]
    }
  ]
}
```

Questo endpoint e auth-gated quando `LLMBASE_API_SECRET` e impostato perche espone dati operazionali di utilizzo.

`GET /api/llm/usage/recent?limit=<n>` restituisce le richieste LLM logiche piu recenti ricostruite dallo stesso log append-only.
Ogni richiesta logica raggruppa tutti i tentativi del provider che condividono lo stesso `request_id`, cosi il consumo di token di retry e fallback viene sommato a livello di richiesta.

Accetta gli stessi parametri temporali opzionali del summary endpoint: `last`, `from` e `to`.

Forma di esempio:

```json
{
  "source_path": ".../wiki/_meta/llm-usage.jsonl",
  "applied_window": "7d",
  "from_ts": "2026-05-01T10:45:00Z",
  "to_ts": "2026-05-08T10:45:00Z",
  "skipped_timestamp_count": 0,
  "requests": [
    {
      "request_id": "4e0e95591f4b4ca087eb7067ef1f3f5e",
      "ts": "2026-05-08T10:45:00Z",
      "feature": "ask",
      "stage": "answer",
      "requested_model": "gpt-4o",
      "actual_models": ["gpt-4o", "gpt-4o-mini"],
      "attempt_count": 2,
      "success": true,
      "retry_count": 0,
      "fallback_count": 1,
      "prompt_tokens": 900,
      "completion_tokens": 500,
      "reasoning_tokens": 0,
      "total_tokens": 1400,
      "last_finish_reason": "stop",
      "last_error_type": null,
      "last_error_message": null,
      "truncated": false
    }
  ]
}
```

Anche questo endpoint e auth-gated quando `LLMBASE_API_SECRET` e impostato.

## Autenticazione

- I deployment diretti dell'app possono inviare `Authorization: Bearer <LLMBASE_API_SECRET>` agli endpoint autenticati.
- Nel deployment Nginx integrato, l'header pubblico `Authorization` viene usato da Basic Auth al confine del proxy.
- Le richieste browser UI continuano a funzionare perche il frontend riceve il cookie derivato `llmbase_auth` dalla risposta SPA.
- I client API diretti dietro Nginx dovrebbero inviare `X-LLMBASE-Authorization: Bearer <LLMBASE_API_SECRET>` quando hanno bisogno dell'autenticazione applicativa llmbase; il proxy inoltra quel valore upstream come `Authorization`.

## Payload di upload

`POST /api/upload` accetta `multipart/form-data`.

- invia una o piu parti `file`
- il campo form opzionale `chunk_pages` controlla solo il chunking dei PDF
- i file PDF vengono espansi in uno o piu chunk raw
- i file Markdown vengono ingeriti come file sorgente caricati, preservando il frontmatter quando presente
- gli altri file non-PDF vengono ingeriti come file sorgente caricati

## Payload di ask

Esempio:

```json
{
  "question": "What is the main idea?",
  "deep": true,
  "tone": "scholar",
  "file_back": false,
  "promote": false,
  "model": null
}
```

Toni supportati:
- `default`
- `caveman`
- `scholar`
- `eli5`

## Plugin di riferimento

`GET /api/refs/plugins` restituisce i plugin di riferimento attualmente registrati. Il progetto non distribuisce piu plugin corpus-specific incorporati; i progetti downstream possono registrare i propri.
