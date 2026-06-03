from click.testing import CliRunner


def test_cli_mcp_passes_flags(monkeypatch):
    from llmwiki import cli

    captured = {}

    def fake_run(base_dir, settings):
        captured["base_dir"] = base_dir
        captured["settings"] = settings

    monkeypatch.setattr("llmwiki.mcp_server.run_mcp", fake_run)

    runner = CliRunner()
    result = runner.invoke(cli.cli, [
        "mcp",
        "--transport",
        "streamable-http",
        "--http-port",
        "8201",
        "--http-url",
        "http://localhost:8201/mcp",
    ])

    assert result.exit_code == 0
    settings = captured["settings"]
    assert settings.transport == "streamable-http"
    assert settings.http_port == 8201
    assert settings.http_url == "http://localhost:8201/mcp"
