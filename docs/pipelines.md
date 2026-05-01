# Pipelines

LLMBase uses simple file-backed pipelines for repeatable long-running stages.

## Typical stages

1. ingest
2. compile
3. taxonomy
4. lint
5. export

## Guarantees

- stage names are validated before touching the filesystem
- stage keys are hashed before being used in filenames
- torn or partially written log lines are tolerated during rebuild
- write-oriented operations use explicit locking where required

## Practical guidance

- keep stage names ASCII and descriptive
- treat stage logs as append-only JSONL
- prefer rebuilding state from log history over trusting in-memory state after a crash
