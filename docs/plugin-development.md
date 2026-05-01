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
