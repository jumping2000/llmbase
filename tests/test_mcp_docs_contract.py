from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_english_mcp_docs_cover_http_transport_and_proxy_auth():
    doc = (ROOT / "docs" / "mcp-server.md").read_text(encoding="utf-8")

    assert "streamable-http" in doc
    assert "MCP_TRANSPORT" in doc
    assert "MCP_HTTP_PORT" in doc
    assert "MCP_HTTP_URL" in doc
    assert "MCP_API_KEY" in doc
    assert "X-API-Key" in doc
    assert "/mcp" in doc


def test_italian_mcp_docs_cover_http_transport_and_proxy_auth():
    doc = (ROOT / "docs" / "doc-ita" / "mcp-server.md").read_text(encoding="utf-8")

    assert "streamable-http" in doc
    assert "MCP_TRANSPORT" in doc
    assert "MCP_HTTP_PORT" in doc
    assert "MCP_HTTP_URL" in doc
    assert "MCP_API_KEY" in doc
    assert "X-API-Key" in doc
    assert "/mcp" in doc