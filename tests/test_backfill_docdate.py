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


def test_backfill_missing_counter(tmp_path, monkeypatch):
    import llmwiki.docdate as dd
    monkeypatch.setattr(
        dd, "_docdate_config", lambda b: {"enabled": True, "llm_fallback": False}
    )
    _make_raw(tmp_path, "doc-nd", "Nessuna data presente in questo documento.")
    result = dispatch("kb_backfill_doc_dates", tmp_path, {"force": False})
    assert result["missing"] == 1
    assert result["extracted"] == 0


def test_backfill_propagates_to_article(tmp_path, monkeypatch):
    import llmwiki.docdate as dd
    monkeypatch.setattr(
        dd, "_docdate_config", lambda b: {"enabled": True, "llm_fallback": False}
    )
    _make_raw(tmp_path, "doc-prop", "Data di emissione: 01/03/2024\nContenuto.")
    # Article citing the doc by url, source lacks doc_date
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    art = frontmatter.Post("Articolo")
    art.metadata["sources"] = [{"plugin": "pdf", "url": "doc-prop.pdf", "title": "doc-prop"}]
    (concepts / "concept-prop.md").write_text(frontmatter.dumps(art), encoding="utf-8")
    dispatch("kb_backfill_doc_dates", tmp_path, {"force": False})
    loaded = frontmatter.load(str(concepts / "concept-prop.md"))
    assert loaded.metadata["sources"][0]["doc_date"] == "2024-03-01"


def test_backfill_skip_still_propagates(tmp_path, monkeypatch):
    # Doc already has doc_date but its article never got it (interrupted batch).
    import llmwiki.docdate as dd
    monkeypatch.setattr(
        dd, "_docdate_config", lambda b: {"enabled": True, "llm_fallback": False}
    )
    _make_raw(tmp_path, "doc-int", "Data di emissione: 01/03/2024", doc_date="2024-03-01")
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    art = frontmatter.Post("Articolo")
    art.metadata["sources"] = [{"plugin": "pdf", "url": "doc-int.pdf", "title": "doc-int"}]
    (concepts / "concept-int.md").write_text(frontmatter.dumps(art), encoding="utf-8")
    result = dispatch("kb_backfill_doc_dates", tmp_path, {"force": False})
    assert result["skipped"] == 1
    loaded = frontmatter.load(str(concepts / "concept-int.md"))
    assert loaded.metadata["sources"][0]["doc_date"] == "2024-03-01"
