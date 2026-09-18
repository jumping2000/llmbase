"""Tests for the /api/lint/orphans routes."""

from pathlib import Path

import frontmatter
import pytest

from llmwiki.compile import rebuild_index
from llmwiki.config import load_config
from llmwiki.web import create_web_app


@pytest.fixture(autouse=True)
def _clear_ambient_secret(monkeypatch):
    """Prevent ambient LLMBASE_API_SECRET from gating the write endpoints.

    ``llmwiki.llm`` loads ``.env`` at import time (same fixture as
    ``tests/test_domains_web.py``).
    """
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    monkeypatch.delenv("PORT", raising=False)


@pytest.fixture
def client(tmp_kb):
    """tmp_kb plus `xiao`, a valid linking source for the orphan `ren`."""
    concepts_dir = Path(load_config(tmp_kb)["paths"]["concepts"])
    post = frontmatter.Post("## English\n\nText.\n\n## Italiano\n\nTesto.\n")
    post.metadata.update({
        "title": "Filial Piety / Pieta filiale",
        "summary": "A Confucian virtue",
        "tags": ["confucianism", "ethics"],
        "created": "2026-04-01T00:00:00+00:00",
        "updated": "2026-04-01T00:00:00+00:00",
    })
    (concepts_dir / "xiao.md").write_text(frontmatter.dumps(post), encoding="utf-8")
    rebuild_index(tmp_kb)

    app = create_web_app(tmp_kb)
    app.config["TESTING"] = True
    return app.test_client()


def test_list_orphans(client):
    res = client.get("/api/lint/orphans")

    assert res.status_code == 200
    data = res.get_json()
    ren = next(o for o in data["orphans"] if o["slug"] == "ren")
    assert [c["slug"] for c in ren["candidates"]] == ["xiao"]


def test_link_then_replay_is_idempotent(client):
    first = client.post("/api/lint/orphans/link", json={"slug": "ren", "source": "xiao"})
    assert first.status_code == 200
    assert first.get_json()["changed"] is True

    second = client.post("/api/lint/orphans/link", json={"slug": "ren", "source": "xiao"})
    assert second.status_code == 200
    body = second.get_json()
    assert body["changed"] is False
    assert body["reason"] == "already_linked"


def test_link_auto_picks_source(client):
    res = client.post("/api/lint/orphans/link", json={"slug": "ren"})

    assert res.status_code == 200
    assert res.get_json()["source"] == "xiao"


def test_link_rejects_bad_input(client):
    assert client.post("/api/lint/orphans/link", json={}).status_code == 400
    assert client.post(
        "/api/lint/orphans/link", json={"slug": "../evil", "source": "xiao"}
    ).status_code == 400
    assert client.post(
        "/api/lint/orphans/link", json={"slug": "nope", "source": "xiao"}
    ).status_code == 404


def test_link_reports_busy_worker(client):
    """A write held by the worker surfaces as 409, not a 500."""
    from llmwiki.worker import job_lock

    job_lock.acquire()
    try:
        res = client.post("/api/lint/orphans/link", json={"slug": "ren", "source": "xiao"})
    finally:
        job_lock.release()

    assert res.status_code == 409
    assert res.get_json()["status"] == "busy"


def test_fix_clamps_max_links(client):
    res = client.post("/api/lint/orphans/fix", json={"max_links": 9999})

    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["fix_count"] <= 50
