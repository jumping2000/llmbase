# API Reference

The web server exposes a JSON HTTP API alongside the frontend.

## Read endpoints

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
- `GET /api/search?q=<query>&top_k=<n>&domain=<domain>`
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
- `GET /api/domains`
- `POST /api/lint`

## Write endpoints

- `POST /api/ask`
- `POST /api/entities/extract`
- `POST /api/ingest`
- `POST /api/ingest/browser`
- `POST /api/upload`
- `POST /api/compile`
- `POST /api/lint/fix`
- `POST /api/wiki/clean`
- `POST /api/taxonomy/update`
- `POST /api/index/rebuild`
- `POST /api/xici/generate`
- `POST /api/trails`
- `POST /api/trails/<trail_id>/delete`
- `DELETE /api/articles/<slug>`
- `POST /api/domains`
- `POST /api/domains/<domain_id>/rename`
- `DELETE /api/domains/<domain_id>`
- `POST /api/articles/bulk-domain`

When `LLMBASE_API_SECRET` is set, write endpoints require authentication.
Some operational read endpoints are also auth-gated because they expose job state or internal activity:

- `GET /api/compile/status`
- `GET /api/llm/usage/summary`
- `GET /api/llm/usage/recent`
- `GET /api/trails`
- `GET /api/worker/status`

`GET /api/healthz` is a fast liveness probe.
`GET /api/health` returns the last persisted health report from `wiki/_meta/health.json`.

`POST /api/compile` runs in the background and returns `202 Accepted` when the job starts.
Poll `GET /api/compile/status` for explicit `running`, `completed`, or `failed` state.

`POST /api/ingest` uses direct server-side HTTP fetching for URLs.
If a remote site blocks automated access, the endpoint returns `400` with a user-facing error instead of a generic `500`.

`POST /api/ingest/browser` is an explicit browser-assisted fallback for blocked sites.
It requires browser automation support (`opencli`) on the llmbase host and ingests the result as `type = browser_article`.

`GET /api/worker/status` returns `{ "busy": true|false }` based on the shared write-job lock.

`GET /api/entities` returns cached extracted entities.
`POST /api/entities/extract` triggers entity extraction immediately; the feature is only useful when `entities.enabled: true` in `config.yaml`.

`GET /api/wiki/export` exports the whole compiled wiki as JSON for backup or downstream sync.

`GET /api/trails` lists stored research trails and `POST /api/trails` appends a step or creates a trail.

`GET /api/domains` lists all domains (the implicit `generale` plus any custom ones).
`POST /api/domains` creates a domain from a `{"label": "..."}` body; `POST /api/domains/<domain_id>/rename` renames it; `DELETE /api/domains/<domain_id>` deletes it and reassigns its documents to `generale`.
`POST /api/articles/bulk-domain` with `{"slugs": [...], "domain": "..."}` assigns a domain to many articles at once and rebuilds the index.

Articles carry a `domain` field (default `generale`). `/api/search`, `/api/ask`, and `/api/upload` accept it for per-domain filtering; the article list and article detail responses include it.

`GET /api/compile/status` returns the latest persisted compile state:

- idle: `{ "status": "idle" }`
- running: `{ "status": "running", "full": false, "started_at": "..." }`
- completed: `{ "status": "completed", "articles_created": 3, "articles": [...], "started_at": "...", "finished_at": "..." }`
- failed: `{ "status": "failed", "error": "...", "started_at": "...", "finished_at": "..." }`

Like `GET /api/worker/status`, this endpoint is auth-gated when `LLMBASE_API_SECRET` is set because it exposes write-job state.

`GET /api/llm/usage/summary` returns aggregated token accounting from the append-only log at `wiki/_meta/llm-usage.jsonl`.
Each line in that file represents one real provider attempt, including retries, fallbacks, empty responses, and hard failures.

Optional query params:

- `last=24h|7d|30d|365d`
- `from=<ISO8601>`
- `to=<ISO8601>`

When `last` is present, it takes precedence over `from` and `to`. Time filtering is evaluated in UTC. Records with missing or invalid timestamps are excluded from filtered windows and counted in `skipped_timestamp_count`.

Summary shape:

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

This endpoint is auth-gated when `LLMBASE_API_SECRET` is set because it exposes operational usage data.

`GET /api/llm/usage/recent?limit=<n>` returns the most recent logical LLM requests reconstructed from the same append-only log.
Each logical request groups all provider attempts that share the same `request_id`, so retry and fallback token consumption is summed into one request-level view.

It accepts the same optional time-filter query params as the summary endpoint: `last`, `from`, and `to`.

Example shape:

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

This endpoint is also auth-gated when `LLMBASE_API_SECRET` is set.

## Authentication

- Direct app deployments can send `Authorization: Bearer <LLMBASE_API_SECRET>` to authenticated endpoints.
- In the bundled Nginx deployment, the public `Authorization` header is used by Basic Auth at the proxy boundary.
- Browser UI requests still work because the frontend receives the derived `llmbase_auth` cookie from the SPA response.
- Direct API clients behind Nginx should send `X-LLMBASE-Authorization: Bearer <LLMBASE_API_SECRET>` when they need llmbase application auth; the proxy forwards that value upstream as `Authorization`.

## Upload payload

`POST /api/upload` accepts `multipart/form-data`.

- send one or more `file` parts
- optional `chunk_pages` form field controls PDF chunking only
- PDF files are expanded into one or more raw chunks
- Markdown files are ingested as uploaded source files with their frontmatter preserved when present
- other non-PDF files are ingested as uploaded source files

## Ask payload

Example:

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

Supported tones:
- `default`
- `caveman`
- `scholar`
- `eli5`

## Reference plugins

`GET /api/refs/plugins` returns the currently registered reference plugins. The project no longer ships built-in corpus-specific plugins; downstream projects can register their own.
