# AGENTS

Use this file as the repo-level entry point for AI coding agents. Keep it minimal, and follow the linked docs for detailed behavior.

## Project Shape

LLMBase is a domain-agnostic knowledge-base compiler: raw sources in `raw/`, compiled articles in `wiki/concepts/`, generated metadata in `wiki/_meta/`, and the product surface exposed through CLI, HTTP, and MCP.

- Architecture overview: [README.md](README.md)
- Quick setup and local run flow: [docs/getting-started.md](docs/getting-started.md)
- Customization contract: [docs/customization.md](docs/customization.md)
- Pipeline primitives and crash recovery: [docs/pipelines.md](docs/pipelines.md)
- HTTP and operation surface: [docs/api-reference.md](docs/api-reference.md)
- MCP usage: [docs/mcp-server.md](docs/mcp-server.md)
- Release and commit rules: [CLAUDE.md](CLAUDE.md)

## Working Rules

- Keep the project domain-agnostic. Do not hardcode domain categories, retrieval heuristics, or article structure when the existing LLM- or config-driven abstractions already cover it.
- Route LLM calls through `llmwiki.llm`. Use `chat()` or `chat_with_meta()` instead of calling provider SDKs directly.
- Route wiki-link targets through `llmwiki.resolve.resolve_link()`. Do not hand-roll alias or slug resolution.
- Preserve the two-layer retrieval model: compiled concept search plus raw-source fallback. Retrieval work should fit the existing concept-search plus raw-search pattern rather than introducing a separate memory stack.
- Treat trilingual output as the default. Use `SECTION_HEADERS` and related module constants instead of assuming English-only article structure.
- Prefer import-time constant overrides and hook registration over forking core functions. The stable extension points are documented in [docs/customization.md](docs/customization.md).
- When adding a new user-facing KB capability, prefer registering it once in `llmwiki/operations.py` so MCP and the shared operation surface stay aligned. Follow the existing contract instead of duplicating behavior in each surface.
- For long-running or resumable content workflows, prefer the existing pipeline primitives such as `ChunkCache`, `run_stage()`, normalization helpers, and `split_by_heading()`.
- Preserve existing auth and extension contracts in `llmwiki.web` and `llmwiki.worker` when touching routes, middleware, or background jobs.
- Avoid exposing specific LLM provider names in public code, prompts, or commit messages.

## Code Map

- `llmwiki/`: Python backend, CLI, ingestion, compile, query, lint, web, worker, MCP, operations.
- `frontend/src/`: React UI pages, shared components, API client, theme/lang helpers.
- `tests/`: pytest suite covering backend behavior and recent feature additions.
- `wiki/` and `raw/`: workspace data, generated content, and local KB state.

## Commands

- Python tests: `pytest`
- Python health check: `python llmbase.py lint check`
- Python import check: `python -c "from llmwiki.lint import lint; print('OK')"`
- Frontend type check: `cd frontend && npx tsc --noEmit`
- Frontend build: `cd frontend && npm run build`
- Local web app: `llmbase web`

## Validation

- Run the narrowest relevant test first, then widen only if needed.
- For backend-only changes, prefer targeted `pytest` coverage before broad repo checks.
- For frontend changes, run `cd frontend && npx tsc --noEmit`; use `npm run build` when the change can affect bundling.
- Before any commit, follow the required flow in [CLAUDE.md](CLAUDE.md): TypeScript check, Python import check, Codex review on the staged diff, wait for the result, fix any HIGH findings, then commit.

## Common Starting Points

- LLM behavior, retries, truncation, or token budgeting: `llmwiki/llm.py`
- Compile and article-shape behavior: `llmwiki/compile.py`
- Query, tone, retrieval, and promotion behavior: `llmwiki/query.py`
- Alias resolution and wiki-link handling: `llmwiki/resolve.py`
- Taxonomy generation: `llmwiki/taxonomy.py`
- Unified operation registration: `llmwiki/operations.py`
- Web auth and extension hooks: `llmwiki/web.py`
- Background learning and jobs: `llmwiki/worker.py`

## Agent Style For This Repo

- Favor small, local changes and validate them quickly.
- Link to existing docs instead of copying large reference sections into new instructions or comments.
- Keep architecture explanations simple and concrete. If a behavior is already documented, point to the source doc rather than restating it.
