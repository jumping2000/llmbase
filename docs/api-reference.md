# API Reference

The web server exposes a JSON HTTP API alongside the frontend.

## Read endpoints

- `GET /api/healthz`
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
- `GET /api/export/article/<slug>`
- `GET /api/export/tag/<tag>`
- `GET /api/export/graph/<slug>?depth=<n>`
- `GET /api/refs/plugins`
- `GET /api/xici`

## Write endpoints

- `POST /api/ask`
- `POST /api/ingest`
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

When `LLMBASE_API_SECRET` is set, write endpoints require authentication.

`POST /api/compile` runs in the background and returns `202 Accepted` when the job starts.
Poll `GET /api/compile/status` for explicit `running`, `completed`, or `failed` state.

`GET /api/compile/status` returns the latest persisted compile state:

- idle: `{ "status": "idle" }`
- running: `{ "status": "running", "full": false, "started_at": "..." }`
- completed: `{ "status": "completed", "articles_created": 3, "articles": [...], "started_at": "...", "finished_at": "..." }`
- failed: `{ "status": "failed", "error": "...", "started_at": "...", "finished_at": "..." }`

Like `GET /api/worker/status`, this endpoint is auth-gated when `LLMBASE_API_SECRET` is set because it exposes write-job state.

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
