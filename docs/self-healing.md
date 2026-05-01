# Self-Healing

Self-healing in LLMBase is the combination of lint checks, auto-fixes, cleanup, and duplicate handling.

## Main tools

1. `llmbase lint check`
2. `llmbase lint fix`
3. `llmbase lint clean`
4. `llmbase lint dedup`
5. `llmbase lint heal`

## What gets detected

- empty or placeholder articles
- broken links
- duplicated concepts with overlapping tags and content
- malformed summaries and metadata
- taxonomy drift after content changes

## Duplicate handling

Current duplicate detection is based on overlaps such as:
- slug similarity
- tag overlap
- content similarity

## Alias rebuilding

Alias rebuilding uses article slug, title parts, and merge history. There is no built-in simplified/traditional conversion layer anymore.
