from unittest.mock import patch

import frontmatter
import pytest


def _client(tmp_kb):
    from llmwiki.web import create_web_app

    app = create_web_app(tmp_kb)
    app.config["TESTING"] = True
    return app.test_client()


def test_ingest_url_wraps_http_errors_as_value_error(tmp_kb, monkeypatch):
    from llmwiki import ingest as _ing

    class FakeResp:
        status_code = 403

        def raise_for_status(self):
            raise _ing.requests.HTTPError("403 Client Error", response=self)

    captured = {}

    def fake_get(*args, **kwargs):
        captured["kwargs"] = kwargs
        return FakeResp()

    monkeypatch.setattr(_ing, "_validate_url", lambda url: None)
    monkeypatch.setattr(_ing.requests, "get", fake_get)

    with pytest.raises(ValueError, match="HTTP 403"):
        _ing.ingest_url("https://medium.com/example-post", base_dir=tmp_kb)

    assert captured["kwargs"]["allow_redirects"] is True
    assert "Mozilla/5.0" in captured["kwargs"]["headers"]["User-Agent"]


def test_api_ingest_returns_400_for_remote_fetch_failures(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)

    def fake_ingest_url(url, base_dir=None):
        raise ValueError("Failed to fetch URL (medium.com): HTTP 403. The remote site blocked automated access.")

    monkeypatch.setattr("llmwiki.ingest.ingest_url", fake_ingest_url)

    client = _client(tmp_kb)
    response = client.post("/api/ingest", json={"source": "https://medium.com/example-post"})

    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "HTTP 403" in data["error"]


def test_api_ingest_returns_400_for_missing_source(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)

    client = _client(tmp_kb)
    response = client.post("/api/ingest", json={})

    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "requires 'source'" in data["error"]


def test_ingest_url_browser_persists_browser_article(tmp_kb, monkeypatch):
    from llmwiki import ingest as _ing

    monkeypatch.setattr(_ing, "_validate_url", lambda url: None)
    monkeypatch.setattr("llmwiki.browser.is_opencli_available", lambda: True)
    monkeypatch.setattr(
        "llmwiki.browser.fetch_article",
        lambda url: {
            "title": "Browser Title",
            "content": "Extracted body text from browser automation.",
            "url": url,
        },
    )

    path = _ing.ingest_url_browser("https://medium.com/example-post", base_dir=tmp_kb)
    post = frontmatter.load(str(path))

    assert post.metadata["type"] == "browser_article"
    assert post.metadata["source"] == "https://medium.com/example-post"
    assert post.metadata["compiled"] is False
    assert "Extracted body text" in post.content


def test_ingest_url_browser_requires_opencli(tmp_kb, monkeypatch):
    from llmwiki import ingest as _ing

    monkeypatch.setattr(_ing, "_validate_url", lambda url: None)
    monkeypatch.setattr("llmwiki.browser.is_opencli_available", lambda: False)

    with pytest.raises(ValueError, match="opencli is not installed"):
        _ing.ingest_url_browser("https://example.com/post", base_dir=tmp_kb)


def test_api_ingest_browser_returns_ok(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)

    def fake_ingest_url_browser(url, base_dir=None):
        return base_dir / "raw" / "browser-title" / "index.md"

    monkeypatch.setattr("llmwiki.ingest.ingest_url_browser", fake_ingest_url_browser)

    client = _client(tmp_kb)
    response = client.post("/api/ingest/browser", json={"source": "https://medium.com/example-post"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert str(data["path"]).endswith("browser-title\\index.md") or str(data["path"]).endswith("browser-title/index.md")


def test_api_ingest_browser_returns_400_for_unavailable_browser(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)

    def fake_ingest_url_browser(url, base_dir=None):
        raise ValueError("Browser-assisted ingest is unavailable: opencli is not installed.")

    monkeypatch.setattr("llmwiki.ingest.ingest_url_browser", fake_ingest_url_browser)

    client = _client(tmp_kb)
    response = client.post("/api/ingest/browser", json={"source": "https://medium.com/example-post"})

    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "opencli is not installed" in data["error"]