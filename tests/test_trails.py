# tests/test_trails.py
import pytest

from llmwiki.web import create_web_app


@pytest.fixture(autouse=True)
def _clear_ambient_secret(monkeypatch):
    """Prevent ambient LLMBASE_API_SECRET / PORT from gating write endpoints."""
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    monkeypatch.delenv("PORT", raising=False)


@pytest.fixture()
def client(tmp_path):
    app = create_web_app(tmp_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_trail_step_stores_answer(client):
    step = {
        "type": "query",
        "question": "Che cos'è il contesto multicanale?",
        "answer": "La risposta generata completa.",
    }
    r = client.post("/api/trails", json={"name": "Test", "step": step})
    assert r.status_code == 200
    trail = r.get_json()["trail"]
    assert trail["steps"][0]["type"] == "query"
    assert trail["steps"][0]["answer"] == "La risposta generata completa."

    # Round-trip via GET
    r2 = client.get("/api/trails")
    trails = r2.get_json()["trails"]
    found = next(t for t in trails if t["id"] == trail["id"])
    assert found["steps"][0]["answer"] == "La risposta generata completa."


def test_trail_step_without_answer_is_fine(client):
    step = {"type": "article", "slug": "foo", "title": "Foo"}
    r = client.post("/api/trails", json={"name": "Test2", "step": step})
    assert r.status_code == 200
    trail = r.get_json()["trail"]
    assert "answer" not in trail["steps"][0]
