"""Tests for alias resolution system."""

from pathlib import Path

from llmwiki.resolve import build_aliases, resolve_link, save_aliases, load_aliases


def test_build_aliases_from_articles(tmp_kb):
    concepts_dir = Path(tmp_kb) / "wiki" / "concepts"
    aliases = build_aliases(concepts_dir)

    # Slug → self
    assert aliases["kong"] == "kong"
    assert aliases["si-di"] == "si-di"
    assert aliases["ren"] == "ren"

    # Title parts → slug
    assert aliases["emptiness"] == "kong"
    assert aliases["vacuita"] == "kong"
    assert aliases["quattro nobili verita"] == "si-di"
    assert aliases["benevolenza"] == "ren"
    assert aliases["benevolence"] == "ren"


def test_resolve_link_exact(tmp_kb):
    concepts_dir = Path(tmp_kb) / "wiki" / "concepts"
    aliases = build_aliases(concepts_dir)

    assert resolve_link("kong", aliases) == "kong"
    assert resolve_link("Emptiness", aliases) == "kong"  # case-insensitive
    assert resolve_link("Vacuita", aliases) == "kong"
    assert resolve_link("  kong  ", aliases) == "kong"  # whitespace


def test_resolve_link_not_found(tmp_kb):
    concepts_dir = Path(tmp_kb) / "wiki" / "concepts"
    aliases = build_aliases(concepts_dir)

    assert resolve_link("nonexistent", aliases) is None
    assert resolve_link("", aliases) is None
    assert resolve_link(None, aliases) is None


def test_resolve_link_fuzzy(tmp_kb):
    concepts_dir = Path(tmp_kb) / "wiki" / "concepts"
    aliases = build_aliases(concepts_dir)

    # Fuzzy: strip punctuation
    assert resolve_link("(Emptiness)", aliases) == "kong"
    assert resolve_link("[Benevolence]", aliases) == "ren"


def test_save_load_aliases(tmp_kb):
    meta_dir = Path(tmp_kb) / "wiki" / "_meta"
    aliases = {"vacuita": "kong", "kong": "kong"}

    save_aliases(aliases, meta_dir)
    loaded = load_aliases(meta_dir)

    assert loaded["vacuita"] == "kong"
    assert loaded["kong"] == "kong"


def test_resolve_link_bilingual_part(tmp_kb):
    concepts_dir = Path(tmp_kb) / "wiki" / "concepts"
    aliases = build_aliases(concepts_dir)

    assert resolve_link("Quattro Nobili Verita", aliases) == "si-di"
