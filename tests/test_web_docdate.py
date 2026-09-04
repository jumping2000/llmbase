import frontmatter

from llmwiki.web import create_web_app


def _make_raw(tmp_path, slug):
    raw_dir = tmp_path / "raw" / slug
    raw_dir.mkdir(parents=True)
    post = frontmatter.Post("Contenuto")
    post.metadata["title"] = slug
    post.metadata["source"] = f"{slug}.pdf"
    post.metadata["compiled"] = True
    (raw_dir / "index.md").write_text(frontmatter.dumps(post), encoding="utf-8")


def test_patch_doc_date(tmp_path, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    _make_raw(tmp_path, "doc-p")
    app = create_web_app(base_dir=tmp_path)
    client = app.test_client()
    resp = client.patch(
        "/api/sources/doc-p/doc-date",
        json={"doc_date": "2024-06-15"},
    )
    assert resp.status_code == 200
    post = frontmatter.load(str(tmp_path / "raw" / "doc-p" / "index.md"))
    assert post.metadata["doc_date"] == "2024-06-15"


def test_patch_doc_date_invalid(tmp_path, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    _make_raw(tmp_path, "doc-q")
    app = create_web_app(base_dir=tmp_path)
    client = app.test_client()
    resp = client.patch(
        "/api/sources/doc-q/doc-date",
        json={"doc_date": "not-a-date"},
    )
    assert resp.status_code == 400


def test_patch_doc_date_clear(tmp_path, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    _make_raw(tmp_path, "doc-r")
    app = create_web_app(base_dir=tmp_path)
    client = app.test_client()
    resp = client.patch(
        "/api/sources/doc-r/doc-date",
        json={"doc_date": None},
    )
    assert resp.status_code == 200
    post = frontmatter.load(str(tmp_path / "raw" / "doc-r" / "index.md"))
    assert "doc_date" not in post.metadata
