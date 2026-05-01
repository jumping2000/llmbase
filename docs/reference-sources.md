# Reference Sources

Articles can carry structured source metadata. Source citations are merged and exposed through the web API and export surfaces.

## Example source block

```yaml
sources:
  - plugin: docs
    url: https://example.com/spec
    title: Example Specification
```

## How it is used

- article pages can show citations
- exports include `sources`
- downstream reference plugins can build canonical URLs from stored metadata

## Deduplication

When multiple raw documents contribute the same source record, the source list is merged rather than duplicated.
