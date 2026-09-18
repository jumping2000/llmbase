"""Tests for orphan article linking (llmwiki/lint/orphans.py)."""

import inspect
import json
from pathlib import Path

import frontmatter

from llmwiki.compile import rebuild_index
from llmwiki.config import load_config
from llmwiki.lint import auto_fix, check_orphans, lint
from llmwiki.lint.orphans import (
    fix_orphans,
    insert_see_also,
    link_orphan,
    orphan_slugs,
    scan_corpus,
    suggest_link_sources,
)


def _add(tmp_kb, slug, tags, content, **metadata):
    """Write an extra article into the fixture KB."""
    concepts_dir = Path(load_config(tmp_kb)["paths"]["concepts"])
    post = frontmatter.Post(content)
    post.metadata.update({
        "title": f"{slug} EN / {slug} IT",
        "summary": f"Summary of {slug}",
        "tags": tags,
        "created": "2026-04-01T00:00:00+00:00",
        "updated": "2026-04-01T00:00:00+00:00",
        **metadata,
    })
    (concepts_dir / f"{slug}.md").write_text(frontmatter.dumps(post), encoding="utf-8")
    return concepts_dir / f"{slug}.md"


BILINGUAL = "## English\n\nSome text.\n\n## Italiano\n\nDel testo.\n"


def _corpus(tmp_kb):
    return scan_corpus(load_config(tmp_kb))


# ─── Candidate suggestion ────────────────────────────────────────────

def test_suggest_ranks_by_shared_tags(tmp_kb):
    """More shared tags wins; zero shared tags is not a candidate."""
    _add(tmp_kb, "xiao", ["confucianism", "ethics"], BILINGUAL)   # 2 shared with ren
    _add(tmp_kb, "li", ["confucianism"], BILINGUAL)               # 1 shared
    _add(tmp_kb, "dao", ["daoism"], BILINGUAL)                    # 0 shared
    rebuild_index(tmp_kb)

    cands = suggest_link_sources("ren", _corpus(tmp_kb))

    assert [c["slug"] for c in cands] == ["xiao", "li"]
    assert cands[0]["shared_tags"] == ["confucianism", "ethics"]


def test_suggest_excludes_existing_linkers_and_stubs(tmp_kb):
    """Articles that already link the orphan, and stubs, are not proposed."""
    _add(tmp_kb, "xiao", ["confucianism", "ethics"],
         "## English\n\nSee [[ren]].\n\n## Italiano\n\nVedi [[ren]].\n")
    _add(tmp_kb, "li", ["confucianism", "ethics"], BILINGUAL, stub=True)
    _add(tmp_kb, "yi", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)

    cands = suggest_link_sources("ren", _corpus(tmp_kb))

    assert [c["slug"] for c in cands] == ["yi"]


def test_suggest_is_deterministic(tmp_kb):
    """Ties break alphabetically, stable across repeated calls."""
    for slug in ["zeta", "alpha", "mid"]:
        _add(tmp_kb, slug, ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)

    corpus = _corpus(tmp_kb)
    runs = [[c["slug"] for c in suggest_link_sources("ren", corpus)] for _ in range(3)]

    assert runs[0] == ["alpha", "mid", "zeta"]
    assert runs[0] == runs[1] == runs[2]


# ─── Link insertion ──────────────────────────────────────────────────

def test_insert_creates_bilingual_lines(tmp_kb):
    """Both language sections get the link, and `updated` moves."""
    path = _add(tmp_kb, "xiao", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)

    result = insert_see_also("xiao", "ren", tmp_kb)

    assert result["changed"] is True
    assert result["sections"] == ["english", "italian"]
    post = frontmatter.load(str(path))
    english, italian = post.content.split("## Italiano")
    assert "See also: [[ren]]" in english
    assert "Vedi anche: [[ren]]" in italian
    assert post.metadata["updated"] != "2026-04-01T00:00:00+00:00"


def test_insert_appends_to_existing_line_keeping_label(tmp_kb):
    """An existing see-also line is extended, its wording untouched."""
    path = _add(tmp_kb, "xiao", ["confucianism", "ethics"],
                "## English\n\nText.\n\nSee also: [[kong]]\n\n"
                "## Italiano\n\nTesto.\n\nVedasi anche: [[kong]]\n")
    rebuild_index(tmp_kb)

    insert_see_also("xiao", "ren", tmp_kb)

    content = frontmatter.load(str(path)).content
    assert "See also: [[kong]], [[ren]]" in content
    assert "Vedasi anche: [[kong]], [[ren]]" in content
    assert content.count("See also:") == 1
    assert content.count("anche:") == 1


def test_insert_is_idempotent(tmp_kb):
    """Re-applying changes nothing — not even the file bytes."""
    path = _add(tmp_kb, "xiao", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)

    insert_see_also("xiao", "ren", tmp_kb)
    before = path.read_bytes()
    second = insert_see_also("xiao", "ren", tmp_kb)

    assert second["changed"] is False
    assert second["reason"] == "already_linked"
    assert path.read_bytes() == before
    assert frontmatter.load(str(path)).content.count("[[ren]]") == 2


def test_insert_preserves_body(tmp_kb):
    """A `---` rule and a sub-heading survive — they would not via
    _split_sections/_assemble_sections."""
    body = (
        "## English\n\nIntro.\n\n---\n\n### Details\n\nMore.\n\n"
        "## Italiano\n\nIntro.\n\n### Dettagli\n\nAltro.\n"
    )
    path = _add(tmp_kb, "xiao", ["confucianism", "ethics"], body)
    rebuild_index(tmp_kb)

    insert_see_also("xiao", "ren", tmp_kb)

    content = frontmatter.load(str(path)).content
    assert "---" in content
    assert "### Details" in content
    assert "### Dettagli" in content
    assert content.index("## English") < content.index("## Italiano")


def test_insert_without_sections_appends_to_document(tmp_kb):
    """A flat legacy article gets one line, no synthesized headers."""
    path = _add(tmp_kb, "flat", ["confucianism", "ethics"], "Just prose, no headers.\n")
    rebuild_index(tmp_kb)

    result = insert_see_also("flat", "ren", tmp_kb)

    content = frontmatter.load(str(path)).content
    assert result["sections"] == ["_document"]
    assert content.rstrip().endswith("See also: [[ren]]")
    assert "## English" not in content


def test_insert_rejects_unsafe_slug(tmp_kb):
    """Path traversal is refused before anything is written."""
    concepts_dir = Path(load_config(tmp_kb)["paths"]["concepts"])
    before = (concepts_dir / "kong.md").read_bytes()

    result = insert_see_also("kong", "../../evil", tmp_kb)

    assert result["changed"] is False
    assert result["reason"] == "invalid_slug"
    assert (concepts_dir / "kong.md").read_bytes() == before


# ─── Batch and single fixes ──────────────────────────────────────────

def test_fix_orphans_clears_the_orphan(tmp_kb):
    """After the fix the article has a backlink and is no longer reported."""
    _add(tmp_kb, "xiao", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)
    assert "ren" in orphan_slugs(load_config(tmp_kb), tmp_kb)

    result = fix_orphans(tmp_kb)

    assert result["fix_count"] >= 1
    cfg = load_config(tmp_kb)
    assert not any("ren" in i for i in check_orphans(cfg))
    backlinks = json.loads((Path(cfg["paths"]["meta"]) / "backlinks.json").read_text(encoding="utf-8"))
    assert backlinks["ren"] == ["xiao"]


def test_fix_orphans_respects_max_links(tmp_kb):
    """The cap stops the run, flagged once instead of per remaining orphan."""
    for slug in ["o1", "o2", "o3"]:
        _add(tmp_kb, slug, ["confucianism", "ethics"], BILINGUAL)
    _add(tmp_kb, "hub", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)

    result = fix_orphans(tmp_kb, max_links=2)

    assert result["fix_count"] == 2
    assert result["capped"] is True
    assert len(result["skipped"]) < 3


def test_fix_orphans_reports_missing_candidates(tmp_kb):
    """An orphan nobody shares tags with is skipped, not forced."""
    result = fix_orphans(tmp_kb)

    assert any(
        s["slug"] == "ren" and s["reason"] == "no_candidate"
        for s in result["skipped"]
    )


def test_fix_orphans_never_creates_orphans(tmp_kb):
    """Inserting outgoing links cannot orphan anyone new."""
    _add(tmp_kb, "xiao", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)
    cfg = load_config(tmp_kb)
    before = set(orphan_slugs(cfg, tmp_kb))

    fix_orphans(tmp_kb)

    after = set(orphan_slugs(cfg, tmp_kb))
    assert after <= before


def test_fix_orphans_rebuilds_missing_backlinks(tmp_kb):
    """A missing backlinks.json is rebuilt, never parsed as a slug."""
    _add(tmp_kb, "xiao", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)
    (Path(load_config(tmp_kb)["paths"]["meta"]) / "backlinks.json").unlink()

    result = fix_orphans(tmp_kb)

    assert all("Backlinks map" not in s["slug"] for s in result["skipped"])


def test_link_orphan_picks_a_source_automatically(tmp_kb):
    """The automatic path resolves its own source."""
    _add(tmp_kb, "xiao", ["confucianism", "ethics"], BILINGUAL)
    rebuild_index(tmp_kb)

    result = link_orphan("ren", None, tmp_kb)

    assert result["changed"] is True
    assert result["source"] == "xiao"


def test_link_orphan_without_candidates(tmp_kb):
    """No candidate → a clear reason, no write."""
    rebuild_index(tmp_kb)

    result = link_orphan("ren", None, tmp_kb)

    assert result["changed"] is False
    assert result["reason"] == "no_candidate"


# ─── Contract guards ─────────────────────────────────────────────────

def test_lint_results_shape_unchanged(tmp_kb):
    """No new key in lint() — total_issues feeds the health score."""
    assert set(lint(tmp_kb)) == {
        "structural", "broken_links", "orphans", "missing_metadata",
        "dirty_tags", "duplicates", "stubs", "uncategorized", "total_issues",
    }


def test_auto_fix_does_not_touch_orphans():
    """Orphan linking stays out of the global repair pipeline."""
    assert "orphan" not in inspect.getsource(auto_fix).lower()
