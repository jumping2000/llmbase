# tests/test_backfill_docdate.py
import frontmatter

from llmwiki.operations import dispatch


def _make_raw(tmp_path, slug, content, doc_date=None):
    raw_dir = tmp_path / "raw" / slug
    raw_dir.mkdir(parents=True)
    post = frontmatter.Post(content)
    post.metadata["title"] = slug
    post.metadata["source"] = f"{slug}.pdf"
    post.metadata["compiled"] = True
    if doc_date:
        post.metadata["doc_date"] = doc_date
    (raw_dir / "index.md").write_text(frontmatter.dumps(post), encoding="utf-8")


def test_backfill_extracts_and_propagates(tmp_path, monkeypatch):
    import llmwiki.docdate as dd
    monkeypatch.setattr(
        dd, "_docdate_config", lambda b: {"enabled": True, "llm_fallback": False}
    )
    _make_raw(tmp_path, "doc-x", "Data di emissione: 01/03/2024\nContenuto.")
    result = dispatch("kb_backfill_doc_dates", tmp_path, {"force": False})
    assert result["extracted"] == 1
    assert result["skipped"] == 0
    post = frontmatter.load(str(tmp_path / "raw" / "doc-x" / "index.md"))
    assert post.metadata["doc_date"] == "2024-03-01"


def test_backfill_skips_existing_without_force(tmp_path, monkeypatch):
    import llmwiki.docdate as dd
    monkeypatch.setattr(
        dd, "_docdate_config", lambda b: {"enabled": True, "llm_fallback": False}
    )
    _make_raw(tmp_path, "doc-y", "Data di emissione: 01/03/2024", doc_date="2020-01-01")
    result = dispatch("kb_backfill_doc_dates", tmp_path, {"force": False})
    assert result["skipped"] == 1
    assert result["extracted"] == 0
    post = frontmatter.load(str(tmp_path / "raw" / "doc-y" / "index.md"))
    assert post.metadata["doc_date"] == "2020-01-01"


def test_backfill_force_reextracts(tmp_path, monkeypatch):
    import llmwiki.docdate as dd
    monkeypatch.setattr(
        dd, "_docdate_config", lambda b: {"enabled": True, "llm_fallback": False}
    )
    _make_raw(tmp_path, "doc-z", "Data di emissione: 01/03/2024", doc_date="2020-01-01")
    result = dispatch("kb_backfill_doc_dates", tmp_path, {"force": True})
    assert result["extracted"] == 1
    post = frontmatter.load(str(tmp_path / "raw" / "doc-z" / "index.md"))
    assert post.metadata["doc_date"] == "2024-03-01"
