# Plugin Development

LLMBase still supports plugin-style extension points, but the repository no longer ships built-in corpus-specific plugins.

## Reference plugins

A reference plugin typically defines:
- `PLUGIN_ID`
- `PLUGIN_NAME`
- `get_source_url(source: dict) -> str`

Use English/Italian display names by default.

## Operations plugins

If you want a feature to appear in CLI, HTTP, and MCP, register it through `llmwiki.operations.register`.

## Learn sources

Custom autonomous learn sources can be registered downstream. The default repository no longer assumes any bundled external corpus source.

## Remote progress sync

`llmwiki/sync.py` is a generic PostgREST adapter that backs ingestion and
compile state in a remote Postgres table, so an ephemeral filesystem (volume
reset, container rebuild) does not cause re-ingest of already-known sources.
It works against any PostgREST endpoint — Supabase, self-hosted PostgREST, and
so on.

**It is opt-in and not wired by default.** No core module imports it: a
downstream project activates it by registering the lifecycle hooks itself.

```python
from llmwiki.hooks import register
from llmwiki import sync

register("ingested", lambda source, work_id, **kw: sync.push_ingested(source, work_id))
register("compiled", lambda source, work_id, **kw: sync.mark_compiled(source, work_id))
```

Configuration is entirely by environment variable, and the module is a no-op
when they are unset:

| Variable | Default | Description |
|---|---|---|
| `LLMBASE_SYNC_URL` | *(empty)* | Base URL of the PostgREST endpoint. `SUPABASE_URL` is accepted as a fallback. |
| `LLMBASE_SYNC_KEY` | *(empty)* | Bearer token / API key. `SUPABASE_KEY` is accepted as a fallback. |
| `LLMBASE_SYNC_TABLE` | `llmbase_ingested` | Table name. |
| `LLMBASE_REMOTE_TABLE` | *(empty)* | Legacy alias for `LLMBASE_SYNC_TABLE`, consulted when the latter is unset. |

The expected table schema is documented in the module docstring at the top of
`llmwiki/sync.py`.
