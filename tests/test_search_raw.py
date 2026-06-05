"""Tests for raw/ fallback search."""

import os
from pathlib import Path

import frontmatter

from llmwiki.search import search_raw


def _write_raw(raw_dir: Path, subdir: str, title: str, content: str, source: str = ""):
    d = raw_dir / subdir
    d.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(content)
    post.metadata["title"] = title
    if source:
        post.metadata["source"] = source
    (d / "index.md").write_text(frontmatter.dumps(post), encoding="utf-8")


def test_search_raw_finds_verbatim(tmp_kb, monkeypatch):
    monkeypatch.chdir(tmp_kb)
    raw_dir = Path(tmp_kb) / "raw"
    _write_raw(raw_dir, "architettura-soa", "Architettura SOA",
               "## Servizi REST\nI servizi REST espongono le API pubbliche tramite gateway.",
               source="https://example.org/soa")

    results = search_raw("servizi REST", top_k=5, base_dir=tmp_kb)
    assert results, "expected at least one hit for servizi REST"
    top = results[0]
    assert top["source"] == "architettura-soa"
    assert top["source_url"] == "https://example.org/soa"
    assert "servizi" in top["snippet"].lower() or "rest" in top["snippet"].lower()
    assert top["score"] > 0


def test_search_raw_empty_when_no_raw(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        f"paths:\n  raw: {tmp_path}/raw\n  wiki: {tmp_path}/wiki\n"
        f"  outputs: {tmp_path}/wiki/outputs\n  meta: {tmp_path}/wiki/_meta\n"
        f"  concepts: {tmp_path}/wiki/concepts\n"
    )
    assert search_raw("anything", base_dir=tmp_path) == []


def test_search_raw_scrubs_local_paths(tmp_kb):
    """Local-file ingest stores absolute paths in `source`; never leak them."""
    raw_dir = Path(tmp_kb) / "raw"
    _write_raw(raw_dir, "infra-doc", "Infrastruttura Cloud",
               "## Infrastruttura\nL'infrastruttura cloud supporta il deployment automatico.",
               source="/Users/someone/private/notes.md")

    results = search_raw("infrastruttura", top_k=5, base_dir=tmp_kb)
    assert results
    for r in results:
        assert r["source_url"] == "", f"leaked local path: {r['source_url']}"


def test_search_raw_top_k_edges(tmp_kb):
    raw_dir = Path(tmp_kb) / "raw"
    for i in range(3):
        _write_raw(raw_dir, f"doc-{i}", f"Doc {i}",
                   "## Batch\nIl batch notturno elabora le transazioni pendenti.")

    # Negative top_k must not trigger Python slice semantics (results[:-1]).
    assert search_raw("batch notturno", top_k=-1, base_dir=tmp_kb) == []
    # top_k=0 honours caller intent (empty list, not forced to 1).
    assert search_raw("batch notturno", top_k=0, base_dir=tmp_kb) == []


def test_search_raw_no_absolute_paths_in_results(tmp_kb):
    raw_dir = Path(tmp_kb) / "raw"
    _write_raw(raw_dir, "monitor-doc", "Monitoraggio",
               "## Monitoraggio\nIl monitoraggio delle performance viene eseguito ogni ora.")
    results = search_raw("monitoraggio", top_k=5, base_dir=tmp_kb)
    assert results
    for r in results:
        # rel_path stays relative; absolute filesystem path must not be exposed.
        assert "path" not in r
        assert not r["rel_path"].startswith("/")


def test_search_raw_ranks_by_tf_idf(tmp_kb):
    raw_dir = Path(tmp_kb) / "raw"
    _write_raw(raw_dir, "a", "A",
               "## Gateway\nIl gateway gateway gestisce il traffico gateway verso i servizi.")
    _write_raw(raw_dir, "b", "B",
               "## Sicurezza\nIl gateway autentica le singole richieste in ingresso.")

    results = search_raw("gateway", top_k=5, base_dir=tmp_kb)
    sources = [r["source"] for r in results]
    assert sources.index("a") < sources.index("b"), "higher tf document should rank first"
