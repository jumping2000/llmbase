"""Tests for llmwiki/taxonomy.py — category tags must not feed back in.

The taxonomy writes `category:<id>` tags into articles; the tag-based fallback
used to count those as ordinary tags, turn one into a category id, and write it
back as `category:category:<id>` — compounding on every run.
"""

import json
from pathlib import Path

import frontmatter

from llmwiki.config import load_config
from llmwiki.taxonomy import (
    _apply_category_tags,
    _fallback_taxonomy,
    _sync_taxonomy_to_tags,
    _taxonomy_tokens,
    assign_new_articles,
    is_category_tag,
)


def _concepts(tmp_kb) -> Path:
    return Path(load_config(tmp_kb)["paths"]["concepts"])


def _write(tmp_kb, slug, tags):
    post = frontmatter.Post("## English\n\nText.\n\n## Italiano\n\nTesto.\n")
    post.metadata.update({
        "title": f"{slug} EN / {slug} IT",
        "summary": f"Summary of {slug}",
        "tags": tags,
        "created": "2026-04-01T00:00:00+00:00",
        "updated": "2026-04-01T00:00:00+00:00",
    })
    path = _concepts(tmp_kb) / f"{slug}.md"
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def _tags_on(path: Path) -> list:
    return frontmatter.load(str(path)).metadata.get("tags", [])


def _articles(tmp_kb) -> list[dict]:
    """Article dicts in the shape _fallback_taxonomy expects."""
    out = []
    for p in sorted(_concepts(tmp_kb).glob("*.md")):
        meta = frontmatter.load(str(p)).metadata
        out.append({
            "slug": p.stem,
            "title": meta.get("title", p.stem),
            "tags": meta.get("tags", []) or [],
            "summary": meta.get("summary", ""),
        })
    return out


# ─── The bug ─────────────────────────────────────────────────────────

def test_fallback_ignores_category_tags(tmp_kb):
    """A category:* tag must never become a category id.

    Shaped like the real corpus: the articles that ended up under
    `category:middleware` were those whose own topic tag was too rare to make
    the top-10, so the greedy pass reached them with only the category tag
    left to match. Before the fix this produced an id of `category:middleware`.
    """
    for slug in ["a1", "a2", "a3"]:
        _write(tmp_kb, slug, ["middleware"])
    _write(tmp_kb, "b1", ["uniq1", "category:middleware"])
    _write(tmp_kb, "b2", ["uniq2", "category:middleware"])

    tree = _fallback_taxonomy(_articles(tmp_kb))

    assert tree, "expected at least one category"
    assert not any(is_category_tag(c["id"]) for c in tree)
    assert "middleware" in [c["id"] for c in tree]
    # b1/b2 have nothing in common but the category tag → Other, not a category
    other = next(c for c in tree if c["id"] == "other")
    assert {"b1", "b2"} <= set(other["article_slugs"])


def test_round_trip_is_idempotent(tmp_kb):
    """fallback → sync → fallback must not drift, and must not double prefixes.

    This is the invariant the bug broke. On the old code the same input gave
    `other` → `category:other` → `category:category:other` over three rounds,
    with the articles' tags gaining a prefix each time.
    """
    for slug in ["a1", "a2", "a3"]:
        _write(tmp_kb, slug, ["middleware"])
    _write(tmp_kb, "b1", ["uniq1"])
    _write(tmp_kb, "b2", ["uniq2"])

    rounds = []
    for _ in range(3):
        tree = _fallback_taxonomy(_articles(tmp_kb))
        _sync_taxonomy_to_tags(tree, _concepts(tmp_kb))
        rounds.append([c["id"] for c in tree])

    assert rounds[0] == rounds[1] == rounds[2]
    assert not any(is_category_tag(cat_id) for cat_id in rounds[-1])
    every_tag = [t for p in _concepts(tmp_kb).glob("*.md") for t in _tags_on(p)]
    assert not any(t.startswith("category:category:") for t in every_tag)


# ─── Tag application ─────────────────────────────────────────────────

def test_apply_replaces_old_category_tags(tmp_kb):
    path = _write(tmp_kb, "c1", ["middleware", "category:old", "category:category:old"])

    _apply_category_tags(_concepts(tmp_kb), "c1", ["new"])

    assert _tags_on(path) == ["middleware", "category:new"]


def test_apply_does_not_rewrite_unchanged_file(tmp_kb):
    path = _write(tmp_kb, "c2", ["middleware", "category:new"])
    before = path.read_bytes()

    _apply_category_tags(_concepts(tmp_kb), "c2", ["new"])

    assert path.read_bytes() == before


def test_apply_survives_non_string_tag(tmp_kb):
    """check_dirty_tags expects non-string tags to exist; they must not crash."""
    path = _write(tmp_kb, "c3", ["middleware", 42])

    _apply_category_tags(_concepts(tmp_kb), "c3", ["new"])

    assert "category:new" in _tags_on(path)


def test_sync_strips_tags_of_articles_left_out_of_the_tree(tmp_kb):
    """A tag must not outlive the category that produced it."""
    kept = _write(tmp_kb, "d1", ["middleware"])
    dropped = _write(tmp_kb, "d2", ["middleware", "category:stale"])

    tree = [{"id": "middleware", "label": {"en": "M", "it": "M"},
             "children": [], "article_slugs": ["d1"]}]
    _sync_taxonomy_to_tags(tree, _concepts(tmp_kb))

    assert "category:middleware" in _tags_on(kept)
    assert not any(is_category_tag(t) for t in _tags_on(dropped))


# ─── Assignment of new articles ──────────────────────────────────────

def test_assign_new_articles_ignores_category_tags(tmp_kb):
    """Sharing only a category:* tag is not evidence of belonging."""
    _write(tmp_kb, "e1", ["middleware", "category:middleware"])
    _write(tmp_kb, "e2", ["cooking", "category:middleware"])

    meta_dir = Path(load_config(tmp_kb)["paths"]["meta"])
    (meta_dir / "taxonomy.json").write_text(json.dumps({
        "categories": [{"id": "middleware", "label": {"en": "M", "it": "M"},
                        "children": [], "article_slugs": ["e1"]}],
    }), encoding="utf-8")

    assign_new_articles(tmp_kb)

    cats = json.loads((meta_dir / "taxonomy.json").read_text(encoding="utf-8"))["categories"]
    middleware = next(c for c in cats if c["id"] == "middleware")
    assert "e2" not in middleware["article_slugs"]


# ─── Token budget ────────────────────────────────────────────────────

def test_taxonomy_tokens_actually_doubles():
    """The old min(x*2, 16384) cap cancelled the doubling at the default 16384."""
    assert _taxonomy_tokens({"llm": {"max_tokens": 16384}}) == 32768
