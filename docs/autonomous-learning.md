# Autonomous Learning

The worker can keep the knowledge base moving forward without manual supervision, but the built-in source model is now deliberately simple.

## Default behavior

- `worker.learn_source` defaults to `url`
- the worker operates on URL-based or locally ingested material
- built-in remote corpus sources are not shipped anymore

## Typical loop

1. New raw material is ingested into `raw/`.
2. The worker compiles new material into `wiki/concepts/`.
3. Taxonomy and guided-introduction outputs can be refreshed.
4. Lint and cleanup workflows can run to keep the KB healthy.

## Config example

```yaml
worker:
  enabled: true
  learn_source: url
```

## Extending learning sources

If you need autonomous learning from a custom upstream system, register a custom learn source in Python and route the worker to it. The repository no longer assumes any bundled external corpus source.
