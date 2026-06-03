from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_has_mcp_service():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert "llmbase-mcp" in compose["services"]
    assert compose["services"]["llmbase-mcp"]["command"] == ["llmbase", "mcp"]
    assert compose["services"]["llmbase-mcp"]["environment"]["MCP_TRANSPORT"] == "streamable-http"
    assert compose["services"]["llmbase-mcp"]["environment"]["MCP_HTTP_PORT"] == "${MCP_HTTP_PORT:-8100}"


def test_compose_build_has_mcp_service():
    compose = yaml.safe_load((ROOT / "compose.build.yaml").read_text(encoding="utf-8"))
    assert "llmbase-mcp" in compose["services"]
    assert compose["services"]["llmbase-mcp"]["command"] == ["llmbase", "mcp"]
    assert compose["services"]["llmbase-mcp"]["environment"]["MCP_TRANSPORT"] == "streamable-http"
    assert compose["services"]["llmbase-mcp"]["environment"]["MCP_HTTP_PORT"] == "${MCP_HTTP_PORT:-8100}"
    assert any(
        "default.conf.template" in volume
        for volume in compose["services"]["nginx"]["volumes"]
    )


def test_nginx_template_exists_and_has_mcp_block():
    text = (ROOT / "nginx" / "default.conf.template").read_text(encoding="utf-8")
    assert "location /mcp" in text
    assert "${MCP_API_KEY}" in text or "$MCP_API_KEY" in text


def test_compose_uses_envsubst_with_escaped_vars():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "$$MCP_API_KEY" in text
    assert "$$MCP_HTTP_URL" in text
    assert "$${MCP_HTTP_PORT:-8100}" in text
    compose = yaml.safe_load(text)
    assert compose["services"]["nginx"]["env_file"] == ".env"
