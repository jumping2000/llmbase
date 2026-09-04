# tests/test_docdate.py

import pytest


@pytest.fixture(autouse=True)
def _no_llm_fallback(monkeypatch):
    """Default for this module: regex-only. Tests that exercise the LLM
    fallback path monkeypatch _llm_extract themselves and that still works
    because their own monkeypatch runs after this one."""
    monkeypatch.setattr(
        "llmwiki.docdate._docdate_config",
        lambda base_dir: {"enabled": True, "llm_fallback": False},
    )


from llmwiki.docdate import is_plausible, normalize_date, propagate_doc_date


def test_normalize_iso_full():
    assert normalize_date("2024-03-01") == "2024-03-01"


def test_normalize_iso_year_month():
    assert normalize_date("2024-03") == "2024-03"


def test_normalize_italian_slash():
    assert normalize_date("01/03/2024") == "2024-03-01"


def test_normalize_italian_dash():
    assert normalize_date("01-03-2024") == "2024-03-01"


def test_normalize_italian_dot():
    assert normalize_date("01.03.2024") == "2024-03-01"


def test_normalize_two_digit_year_24():
    assert normalize_date("01/03/24") == "2024-03-01"


def test_normalize_two_digit_year_85():
    assert normalize_date("01/03/85") == "1985-03-01"


def test_normalize_day_gt12_is_day():
    # 25 cannot be a month → unambiguous day-first
    assert normalize_date("25/01/2024") == "2024-01-25"


def test_normalize_ambiguous_assumes_italian():
    # both ≤12 → assume DD/MM (Italian editorial context)
    assert normalize_date("01/03/2024") == "2024-03-01"


def test_normalize_year_only():
    assert normalize_date("2024") == "2024"


def test_normalize_invalid_returns_none():
    assert normalize_date("not a date") is None
    assert normalize_date("32/13/2024") is None


def test_is_plausible_rejects_old():
    assert not is_plausible("1899")


def test_is_plausible_rejects_future():
    assert not is_plausible("2099-01-01")


from llmwiki.docdate import extract_doc_date


def test_extract_emissione():
    text = "Manuale tecnico\nData di emissione: 01/03/2024\nAlfamonitor"
    assert extract_doc_date(text) == "2024-03-01"


def test_extract_validazione():
    text = "Procedura P001\nData di validazione: 15/01/2024\nRev. 3"
    assert extract_doc_date(text) == "2024-01-15"


def test_extract_revisione():
    text = "Rev. 5 del 15/01/2024 — Istruzioni operative"
    assert extract_doc_date(text) == "2024-01-15"


def test_extract_ultima_modifica():
    text = "Ultima modifica: 2024-03-01\nSistema Mainframe"
    assert extract_doc_date(text) == "2024-03-01"


def test_extract_last_updated():
    text = "Last updated: March 1, 2024"
    assert extract_doc_date(text) == "2024-03-01"


def test_extract_edizione():
    text = "Edizione 2024\nManuale operativo"
    assert extract_doc_date(text) == "2024"


def test_extract_copyright():
    text = "© 2024 Alfamonitor S.p.A."
    assert extract_doc_date(text) == "2024"


def test_extract_priority_specific_over_generic():
    # Both priority-1 (emissione) and priority-2 (©) present → specific wins
    text = "© 2022\nData di emissione: 01/03/2024"
    assert extract_doc_date(text) == "2024-03-01"


def test_extract_iso_date_after_label():
    text = "Data di emissione: 2024-03-01\nManuale"
    assert extract_doc_date(text) == "2024-03-01"


def test_extract_no_date_returns_none():
    assert extract_doc_date("Un documento senza alcuna data dentro.") is None


def test_extract_implausible_rejected():
    assert extract_doc_date("Data di emissione: 01/03/1899") is None


def test_extract_scans_only_head():
    # A date beyond the ~3000-char window is ignored
    text = "x" * 3000 + "\nData di emissione: 01/03/2024"
    assert extract_doc_date(text) is None


def test_is_plausible_accepts_recent():
    assert is_plausible("2024-03-01")
    assert is_plausible("2024")


def test_llm_fallback_used_when_regex_fails(monkeypatch):
    calls = []

    def fake_chat(prompt, **kwargs):
        calls.append(prompt)
        return "2023-05-12"

    monkeypatch.setattr(
        "llmwiki.docdate._docdate_config",
        lambda base_dir: {"enabled": True, "llm_fallback": True},
    )
    monkeypatch.setattr("llmwiki.docdate._llm_extract", fake_chat)
    assert extract_doc_date("Documento senza date esplicite.") == "2023-05-12"
    assert len(calls) == 1


def test_llm_fallback_invalid_answer_returns_none(monkeypatch):
    monkeypatch.setattr(
        "llmwiki.docdate._docdate_config",
        lambda base_dir: {"enabled": True, "llm_fallback": True},
    )
    monkeypatch.setattr("llmwiki.docdate._llm_extract", lambda p, **k: "garbage")
    assert extract_doc_date("Documento senza date esplicite.") is None


def test_llm_fallback_none_answer(monkeypatch):
    monkeypatch.setattr(
        "llmwiki.docdate._docdate_config",
        lambda base_dir: {"enabled": True, "llm_fallback": True},
    )
    monkeypatch.setattr("llmwiki.docdate._llm_extract", lambda p, **k: "none")
    assert extract_doc_date("Documento senza date esplicite.") is None


def test_llm_fallback_disabled_by_config(monkeypatch):
    monkeypatch.setattr(
        "llmwiki.docdate._docdate_config",
        lambda base_dir: {"enabled": True, "llm_fallback": False},
    )
    called = []
    monkeypatch.setattr(
        "llmwiki.docdate._llm_extract",
        lambda p, **k: called.append(p) or "2023-05-12",
    )
    assert extract_doc_date("Documento senza date esplicite.") is None
    assert not called


def test_module_disabled(monkeypatch):
    monkeypatch.setattr(
        "llmwiki.docdate._docdate_config",
        lambda base_dir: {"enabled": False, "llm_fallback": True},
    )
    assert extract_doc_date("Data di emissione: 01/03/2024") is None


def _make_raw(tmp_path, slug, doc_date=None, source="doc.pdf"):
    import frontmatter
    raw_dir = tmp_path / "raw" / slug
    raw_dir.mkdir(parents=True)
    post = frontmatter.Post("Contenuto")
    post.metadata["title"] = slug
    post.metadata["source"] = source
    post.metadata["compiled"] = True
    if doc_date:
        post.metadata["doc_date"] = doc_date
    (raw_dir / "index.md").write_text(frontmatter.dumps(post), encoding="utf-8")
    return raw_dir


def _make_article(tmp_path, slug, sources):
    import frontmatter
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post("Articolo")
    post.metadata["sources"] = sources
    (concepts / f"{slug}.md").write_text(frontmatter.dumps(post), encoding="utf-8")


def test_propagate_updates_matching_sources(tmp_path):
    _make_raw(tmp_path, "manuale-a", doc_date="2024-03-01", source="manuale-a.pdf")
    _make_article(tmp_path, "concept-x", [
        {"plugin": "pdf", "url": "manuale-a.pdf", "title": "Manuale A"},
    ])
    n = propagate_doc_date("manuale-a", base_dir=tmp_path)
    assert n == 1
    import frontmatter
    post = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-x.md"))
    assert post.metadata["sources"][0]["doc_date"] == "2024-03-01"


def test_propagate_no_raw_returns_zero(tmp_path):
    assert propagate_doc_date("missing", base_dir=tmp_path) == 0


def test_propagate_raw_without_date_returns_zero(tmp_path):
    _make_raw(tmp_path, "manuale-b")  # no doc_date
    assert propagate_doc_date("manuale-b", base_dir=tmp_path) == 0


def test_propagate_never_overwrites_with_none(tmp_path):
    _make_raw(tmp_path, "manuale-c")  # no doc_date
    _make_article(tmp_path, "concept-y", [
        {"plugin": "pdf", "url": "x.pdf", "title": "X", "doc_date": "2020-01-01"},
    ])
    propagate_doc_date("manuale-c", base_dir=tmp_path)
    import frontmatter
    post = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-y.md"))
    assert post.metadata["sources"][0]["doc_date"] == "2020-01-01"


def test_propagate_title_collision_does_not_cross_pollute(tmp_path):
    # Two raws share a title but have different dates and sources.
    # A source citing raw B (by url) must NOT get raw A's date via title.
    _make_raw(tmp_path, "relazione-2022", doc_date="2022-01-01", source="rel-a.pdf")
    _make_raw(tmp_path, "relazione-2024", doc_date="2024-01-01", source="rel-b.pdf")
    # Both raws have title == slug (per _make_raw), so titles collide.
    _make_article(tmp_path, "concept-coll", [
        {"plugin": "pdf", "url": "rel-b.pdf", "title": "relazione-2022"},
    ])
    # Propagating raw A: url "rel-b.pdf" != A's source "rel-a.pdf";
    # A has no type metadata → plugin+title clause can't fire either.
    assert propagate_doc_date("relazione-2022", base_dir=tmp_path) == 0
    import frontmatter
    post = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-coll.md"))
    assert "doc_date" not in post.metadata["sources"][0]
    # Sanity: propagating raw B (the actually-cited doc) does match by url.
    assert propagate_doc_date("relazione-2024", base_dir=tmp_path) == 1
    post = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-coll.md"))
    assert post.metadata["sources"][0]["doc_date"] == "2024-01-01"


def test_propagate_plugin_title_match(tmp_path):
    # Source without url but matching plugin+title gets the date.
    import frontmatter
    raw_dir = tmp_path / "raw" / "manuale-d"
    raw_dir.mkdir(parents=True)
    post = frontmatter.Post("Contenuto")
    post.metadata["title"] = "Manuale D"
    post.metadata["type"] = "pdf"
    post.metadata["doc_date"] = "2024-02-02"
    (raw_dir / "index.md").write_text(frontmatter.dumps(post), encoding="utf-8")
    _make_article(tmp_path, "concept-d", [
        {"plugin": "pdf", "title": "Manuale D"},
    ])
    n = propagate_doc_date("manuale-d", base_dir=tmp_path)
    assert n == 1
    art = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-d.md"))
    assert art.metadata["sources"][0]["doc_date"] == "2024-02-02"


def test_propagate_non_matching_source_untouched(tmp_path):
    import frontmatter
    _make_raw(tmp_path, "manuale-e", doc_date="2024-03-05", source="e.pdf")
    _make_article(tmp_path, "concept-e", [
        {"plugin": "pdf", "url": "e.pdf", "title": "E"},
        {"plugin": "pdf", "url": "other.pdf", "title": "Other", "doc_date": "2021-01-01"},
    ])
    propagate_doc_date("manuale-e", base_dir=tmp_path)
    art = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-e.md"))
    srcs = art.metadata["sources"]
    assert srcs[0]["doc_date"] == "2024-03-05"
    assert srcs[1]["doc_date"] == "2021-01-01"


def test_propagate_counts_articles_not_sources(tmp_path):
    _make_raw(tmp_path, "manuale-f", doc_date="2024-04-04", source="f.pdf")
    _make_article(tmp_path, "concept-f1", [
        {"plugin": "pdf", "url": "f.pdf", "title": "F"},
    ])
    _make_article(tmp_path, "concept-f2", [
        {"plugin": "pdf", "url": "f.pdf", "title": "F"},
    ])
    assert propagate_doc_date("manuale-f", base_dir=tmp_path) == 2


def test_propagate_does_not_overwrite_existing_different_date(tmp_path):
    # Article cites the doc with an existing (older edition) date —
    # propagate must NOT overwrite it even though it matches by url.
    _make_raw(tmp_path, "manuale-g", doc_date="2024-06-01", source="g.pdf")
    _make_article(tmp_path, "concept-g", [
        {"plugin": "pdf", "url": "g.pdf", "title": "G", "doc_date": "2020-01-01"},
    ])
    n = propagate_doc_date("manuale-g", base_dir=tmp_path)
    assert n == 0
    import frontmatter
    art = frontmatter.load(str(tmp_path / "wiki" / "concepts" / "concept-g.md"))
    assert art.metadata["sources"][0]["doc_date"] == "2020-01-01"
