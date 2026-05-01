"""Tests for compilation pipeline."""

import json
from pathlib import Path

import frontmatter

from llmwiki.compile import rebuild_index, _merge_into, _split_sections, _assemble_sections


def test_rebuild_index(tmp_kb):
    entries = rebuild_index(tmp_kb)

    assert len(entries) == 3

    slugs = {e["slug"] for e in entries}
    assert "kong" in slugs
    assert "si-di" in slugs
    assert "ren" in slugs

    # Check index.json written
    meta_dir = Path(tmp_kb) / "wiki" / "_meta"
    index = json.loads((meta_dir / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 3

    # Check aliases.json written
    aliases = json.loads((meta_dir / "aliases.json").read_text(encoding="utf-8"))
    assert aliases["vacuita"] == "kong"

    # Check backlinks.json written
    backlinks = json.loads((meta_dir / "backlinks.json").read_text(encoding="utf-8"))
    assert "kong" in backlinks  # si-di links to kong via [[kong|Emptiness]]


def test_rebuild_creates_backlinks(tmp_kb):
    rebuild_index(tmp_kb)
    meta_dir = Path(tmp_kb) / "wiki" / "_meta"
    backlinks = json.loads((meta_dir / "backlinks.json").read_text(encoding="utf-8"))

    # si-di references kong via [[kong|Emptiness]]
    assert "kong" in backlinks
    assert "si-di" in backlinks["kong"]


def test_split_sections():
    content = """Some preamble text.

## English

English content here.

## Italiano

Contenuto italiano qui."""

    sections = _split_sections(content)
    assert "english" in sections
    assert "italian" in sections
    assert "English content here." in sections["english"]
    assert "Contenuto italiano qui." in sections["italian"]


def test_split_sections_stops_at_unknown_headers():
    content = """## English

English content here.

## Notes

Free-form note here."""

    sections = _split_sections(content)
    assert "english" in sections
    assert "## Notes" in sections["english"]


def test_assemble_sections():
    sections = {
        "_preamble": "",
        "english": "Hello world",
        "italian": "Ciao mondo",
    }
    result = _assemble_sections(sections)
    assert "## English" in result
    assert "## Italiano" in result
    assert "Hello world" in result
    assert "Ciao mondo" in result


def test_assemble_sections_preserves_unknown_sections():
    sections = {
        "_preamble": "",
        "english": "Hello world",
        "italian": "Ciao mondo",
        "notes": "Extra notes",
    }
    result = _assemble_sections(sections)
    assert "## English" in result
    assert "## Italiano" in result
    assert "## notes" in result


def test_merge_into_adds_content(tmp_kb):
    concepts_dir = Path(tmp_kb) / "wiki" / "concepts"
    article_path = concepts_dir / "kong.md"

    article = {
        "content": "## English\n\nNew insight about emptiness.\n\n## Italiano\n\nNuova interpretazione della vacuita, piu ampia e articolata della versione precedente.",
        "tags": ["mahayana"],
    }

    _merge_into(article_path, article)

    post = frontmatter.load(str(article_path))
    assert "mahayana" in post.metadata["tags"]
    assert "## Italiano" in post.content
    assert "Nuova interpretazione della vacuita" in post.content


def test_merge_into_no_duplicate_content(tmp_kb):
    concepts_dir = Path(tmp_kb) / "wiki" / "concepts"
    article_path = concepts_dir / "kong.md"
    original = article_path.read_text(encoding="utf-8")

    # Merge identical content → should not change
    article = {"content": "", "tags": []}
    _merge_into(article_path, article)

    assert article_path.read_text(encoding="utf-8") == original
