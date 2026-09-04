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
