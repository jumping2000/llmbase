def test_docker_compose_has_mcp_service():
    text = open("docker-compose.yml", encoding="utf-8").read()
    assert "llmbase-mcp" in text


def test_nginx_template_exists_and_has_mcp_block():
    text = open("nginx/default.conf.template", encoding="utf-8").read()
    assert "location /mcp" in text
    assert "${MCP_API_KEY}" in text or "$MCP_API_KEY" in text
