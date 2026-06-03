import pytest


def test_create_server_lists_registered_tools(tmp_kb):
    pytest.importorskip("mcp")
    from llmwiki.mcp_server import create_server

    server = create_server(tmp_kb)

    assert server.name == "llmbase"


def test_create_streamable_http_app_returns_starlette_app(tmp_kb):
    pytest.importorskip("mcp")
    from llmwiki.mcp_server import create_streamable_http_app

    app = create_streamable_http_app(tmp_kb)

    assert app is not None
    assert hasattr(app, "routes")
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_run_streamable_http_server_uses_requested_port(tmp_kb, monkeypatch):
    pytest.importorskip("mcp")
    captured = {}

    def fake_run(app, host, port, log_level):
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port
        captured["log_level"] = log_level

    monkeypatch.setattr("uvicorn.run", fake_run)

    from llmwiki.mcp_server import run_streamable_http_server

    run_streamable_http_server(tmp_kb, 8123)

    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8123
    assert captured["log_level"] == "info"
