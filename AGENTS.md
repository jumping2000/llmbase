# Agent Notes

Use this repository as an English/Italian knowledge base project.

Rules for contributors and coding agents:
- Keep article structure aligned with English and Italian by default.
- Prefer the operation registry in `llmwiki/operations.py` as the public contract for CLI, HTTP, and MCP behavior.
- Keep docs aligned with the actual runtime surface. If a feature is removed from code, remove it from docs in the same change.
- Favor focused tests with generic or English/Italian fixtures over historical corpus-specific fixtures.
