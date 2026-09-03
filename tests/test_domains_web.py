import pytest

from llmwiki.web import create_web_app


@pytest.fixture(autouse=True)
def _clear_ambient_secret(monkeypatch):
    """Prevent ambient LLMBASE_API_SECRET / PORT from gating write endpoints.

    ``llmwiki.llm`` loads ``.env`` at import time; without clearing, the
    repo's ``.env`` would enable auth on POST/DELETE endpoints in dev-mode
    tests (mirrors the fixture in ``tests/test_v064_features.py``).
    """
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    monkeypatch.delenv("PORT", raising=False)


@pytest.fixture()
def client(tmp_path):
    app = create_web_app(tmp_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_domains_crud(client):
    r = client.get("/api/domains")
    assert r.status_code == 200
    assert {"id": "generale", "label": "Generale"} in r.get_json()["domains"]
    r = client.post("/api/domains", json={"label": "Lavoro"})
    assert r.status_code == 200
    assert r.get_json()["domain"]["id"] == "lavoro"


def test_bulk_domain_endpoint(client):
    client.post("/api/domains", json={"label": "Lavoro"})
    r = client.post("/api/articles/bulk-domain", json={"slugs": [], "domain": "lavoro"})
    assert r.status_code == 200
    assert r.get_json()["domain"] == "lavoro"


def test_bulk_domain_unknown_returns_400(client):
    r = client.post("/api/articles/bulk-domain", json={"slugs": [], "domain": "tipooo"})
    assert r.status_code == 400


def test_search_accepts_domain_param(client):
    r = client.get("/api/search?q=x&domain=lavoro")
    assert r.status_code == 200
    assert r.get_json()["query"] == "x"
