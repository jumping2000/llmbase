from __future__ import annotations

import pytest


def _reset_mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MCP_TRANSPORT", "MCP_HTTP_PORT", "MCP_HTTP_URL", "MCP_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_mcp_env(monkeypatch)

    from llmwiki import mcp_config

    monkeypatch.setattr(mcp_config, "_load_env", lambda: None)
    settings = mcp_config.resolve_mcp_settings()

    assert settings == mcp_config.McpSettings(
        transport="stdio",
        http_port=8100,
        http_url=None,
        api_key=None,
    )


def test_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_mcp_env(monkeypatch)
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HTTP_PORT", "9100")
    monkeypatch.setenv("MCP_HTTP_URL", "https://example.test/mcp")
    monkeypatch.setenv("MCP_API_KEY", "secret-token")

    from llmwiki import mcp_config

    monkeypatch.setattr(mcp_config, "_load_env", lambda: None)
    settings = mcp_config.resolve_mcp_settings()

    assert settings == mcp_config.McpSettings(
        transport="streamable-http",
        http_port=9100,
        http_url="https://example.test/mcp",
        api_key="secret-token",
    )


def test_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_mcp_env(monkeypatch)
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("MCP_HTTP_PORT", "9100")
    monkeypatch.setenv("MCP_HTTP_URL", "https://env.example/mcp")
    monkeypatch.setenv("MCP_API_KEY", "env-key")

    from llmwiki import mcp_config

    monkeypatch.setattr(mcp_config, "_load_env", lambda: None)
    settings = mcp_config.resolve_mcp_settings(
        transport="stdio",
        http_port=8200,
        http_url="http://localhost:8200/mcp",
        api_key="cli-key",
    )

    assert settings == mcp_config.McpSettings(
        transport="stdio",
        http_port=8200,
        http_url="http://localhost:8200/mcp",
        api_key="cli-key",
    )


def test_invalid_transport_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_mcp_env(monkeypatch)
    monkeypatch.setenv("MCP_TRANSPORT", "sse")

    from llmwiki import mcp_config

    monkeypatch.setattr(mcp_config, "_load_env", lambda: None)

    with pytest.raises(ValueError, match="MCP_TRANSPORT"):
        mcp_config.resolve_mcp_settings()


def test_invalid_http_url_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_mcp_env(monkeypatch)
    monkeypatch.setenv("MCP_HTTP_URL", "localhost:8100/mcp")

    from llmwiki import mcp_config

    monkeypatch.setattr(mcp_config, "_load_env", lambda: None)

    with pytest.raises(ValueError, match="MCP_HTTP_URL"):
        mcp_config.resolve_mcp_settings()