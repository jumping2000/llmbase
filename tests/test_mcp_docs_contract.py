from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_english_mcp_docs_cover_unified_deploy():
    doc = (ROOT / "docs" / "mcp-server.md").read_text(encoding="utf-8")

    assert "streamable-http" in doc
    assert "uvicorn asgi:app" in doc
    assert "MCP_API_KEY" in doc
    assert "X-API-Key" in doc
    assert "/mcp" in doc
    assert "llmbase-mcp" in doc  # documented as removed


def test_italian_mcp_docs_cover_unified_deploy():
    doc = (ROOT / "docs" / "doc-ita" / "mcp-server.md").read_text(encoding="utf-8")

    assert "streamable-http" in doc
    assert "uvicorn asgi:app" in doc
    assert "MCP_API_KEY" in doc
    assert "X-API-Key" in doc
    assert "/mcp" in doc
    assert "llmbase-mcp" in doc  # documented as removed
