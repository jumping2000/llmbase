from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _compose(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def _nginx_conf() -> str:
    return (ROOT / "nginx" / "default.conf").read_text(encoding="utf-8")


def test_mcp_is_unified_into_main_app():
    # The standalone llmbase-mcp service was removed; MCP is served by the
    # same container as the web app on /mcp.
    for name in ("docker-compose.yml", "compose.build.yaml"):
        assert "llmbase-mcp" not in _compose(name)["services"]


def test_nginx_mounts_default_conf():
    for name in ("docker-compose.yml", "compose.build.yaml"):
        volumes = _compose(name)["services"]["nginx"]["volumes"]
        assert any("nginx/default.conf" in v for v in volumes)


def test_nginx_default_conf_has_mcp_block():
    text = _nginx_conf()
    assert "location /mcp" in text
    assert "X-API-Key" in text
    assert "auth_basic off" in text


def test_nginx_default_conf_has_no_legacy_mcp_upstream_variable():
    # Regression guard: the old envsubst template referenced $mcp_http_url,
    # which nginx cannot resolve at startup (emerg: unknown variable).
    text = _nginx_conf()
    assert "mcp_http_url" not in text
    assert "MCP_HTTP_URL" not in text
