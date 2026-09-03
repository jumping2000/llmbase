from llmwiki.operations import dispatch, get


def test_kb_domains_list(tmp_path):
    result = dispatch("kb_domains_list", tmp_path, {})
    assert {"id": "generale", "label": "Generale"} in result["domains"]


def test_kb_domains_create_and_bulk_assign(tmp_path):
    dispatch("kb_domains_create", tmp_path, {"label": "Casa"})
    ids = [d["id"] for d in dispatch("kb_domains_list", tmp_path, {})["domains"]]
    assert "casa" in ids
    result = dispatch("kb_domains_bulk_assign", tmp_path, {"slugs": [], "domain": "casa"})
    assert result["domain"] == "casa"


def test_kb_search_schema_has_domain():
    op = get("kb_search")
    assert "domain" in op.params["properties"]
    op_ask = get("kb_ask")
    assert "domain" in op_ask.params["properties"]
