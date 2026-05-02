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

## Upload payload

`POST /api/upload` accepts `multipart/form-data`.

- send one or more `file` parts
- optional `chunk_pages` form field controls PDF chunking
- PDF files are expanded into one or more raw chunks
- non-PDF files are ingested as uploaded source files

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
