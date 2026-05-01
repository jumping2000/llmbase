"""Tests for tools.split — flat-section primitive.

Strict primitive: parse only. No corpus heuristics.
"""

import pytest

from llmwiki.split import Section, split_by_heading


# ─── empty / no-match → [] ─────────────────────────────────────────────


def test_empty_body_returns_empty():
    assert split_by_heading("", level=2) == []


def test_no_headings_returns_empty():
    assert split_by_heading("plain prose\nmore prose\n", level=2) == []


def test_no_target_level_returns_empty():
    """Body has # and ### but no ##; asking for level=2 → []."""
    body = "# top\ncontent\n### deep\ndeep content\n"
    assert split_by_heading(body, level=2) == []


# ─── level validation ─────────────────────────────────────────────────


@pytest.mark.parametrize("level", [0, -1, 7, 100])
def test_invalid_level_raises(level):
    with pytest.raises(ValueError):
        split_by_heading("## x\n", level=level)


# ─── single heading ───────────────────────────────────────────────────


def test_single_heading_yields_one_section():
    body = "## Intro\nFirst paragraph.\n"
    out = split_by_heading(body, level=2)
    assert len(out) == 1
    s = out[0]
    assert s.level == 2
    assert s.title == "Intro"
    assert s.header_line == "## Intro"
    assert s.start == 0
    assert s.end == len(body)
    assert s.content == "First paragraph."


def test_single_heading_last_line_no_newline():
    body = "## End"
    out = split_by_heading(body, level=2)
    assert len(out) == 1
    assert out[0].header_line == "## End"
    assert out[0].content == ""


# ─── multiple headings, same level ────────────────────────────────────


def test_two_same_level_sections():
    body = "## One\nFirst paragraph.\n## Two\nSecond paragraph.\n"
    out = split_by_heading(body, level=2)
    assert [s.title for s in out] == ["One", "Two"]
    assert out[0].content == "First paragraph."
    assert out[1].content == "Second paragraph."
    # Offsets are consistent with body slicing.
    assert body[out[0].start:out[0].end].startswith("## One")
    assert body[out[1].start:out[1].end].startswith("## Two")


def test_section_offsets_cover_body_contiguously():
    """Offsets should partition ``body[sections[0].start:]`` with no
    gaps and no overlaps — useful contract for downstream stitching."""
    body = "## A\naaa\n## B\nbbb\n## C\nccc\n"
    out = split_by_heading(body, level=2)
    assert out[0].end == out[1].start
    assert out[1].end == out[2].start
    assert out[2].end == len(body)


# ─── mixed levels: deeper vs higher headings ──────────────────────────


def test_deeper_headings_stay_in_content():
    """### inside a ## section is not a split point — stays in content."""
    body = "## Chapter\nPreface\n### Section\nInside\n## Next Chapter\nx\n"
    out = split_by_heading(body, level=2)
    assert len(out) == 2
    assert out[0].title == "Chapter"
    # The ### line and its content belong to section 0, not a new section.
    assert "### Section" in out[0].content
    assert "Inside" in out[0].content


def test_higher_level_ends_section():
    """# (higher in hierarchy) ends a ## section."""
    body = "## One\naaa\n# Top\nbbb\n## Two\nccc\n"
    out = split_by_heading(body, level=2)
    assert len(out) == 2
    # Section ["One"] must end at "# Top" (not include it).
    assert out[0].content == "aaa"
    assert "# Top" not in out[0].content
    assert out[1].title == "Two"


# ─── preface handling (NOT returned — downstream slices body) ─────────


def test_preface_before_first_heading_not_in_result():
    body = "This is the preface\nAnother line\n## Chapter\nBody\n"
    out = split_by_heading(body, level=2)
    assert len(out) == 1
    # Downstream recovery pattern:
    preface = body[:out[0].start]
    assert preface == "This is the preface\nAnother line\n"


# ─── fenced code blocks — headings inside must NOT split ──────────────


def test_fence_protects_pseudo_heading():
    body = "## real\n```\n## fake in fence\n```\n內文\n"
    out = split_by_heading(body, level=2)
    assert len(out) == 1  # fence-inner ## is not a split point
    assert out[0].title == "real"
    # Fence block stays inside content:
    assert "## fake in fence" in out[0].content


def test_tilde_fence_also_respected():
    body = "## a\n~~~\n## fake\n~~~\ntext\n## b\nx\n"
    out = split_by_heading(body, level=2)
    assert [s.title for s in out] == ["a", "b"]


# ─── CommonMark §4.2: 0-3 space indent tolerated ──────────────────────


def test_three_space_indent_heading_recognized():
    body = "   ## indented\ncontent\n"
    out = split_by_heading(body, level=2)
    assert len(out) == 1
    assert out[0].title == "indented"


def test_four_space_indent_not_heading():
    """4+ leading spaces = indented code block per §4.4, not a heading."""
    body = "    ## not-a-heading\ncontent\n## real\nx\n"
    out = split_by_heading(body, level=2)
    # Only "real" is a true heading.
    assert len(out) == 1
    assert out[0].title == "real"


# ─── line ending variants ──────────────────────────────────────────────


def test_crlf_body():
    body = "## 一\r\nfoo\r\n## 二\r\nbar\r\n"
    out = split_by_heading(body, level=2)
    assert len(out) == 2
    assert out[0].title == "一"
    assert out[0].header_line == "## 一"  # no \r
    assert out[0].content == "foo"
    assert out[1].title == "二"


def test_cr_only_body():
    """Classic-Mac ``\\r``-only line endings (rare but valid) must not
    collapse content into header_line. Codex v0.7.6 MEDIUM regression."""
    body = "## A\rfoo\r## B\rbar\r"
    out = split_by_heading(body, level=2)
    assert len(out) == 2
    assert out[0].header_line == "## A"
    assert out[0].content == "foo"
    assert out[1].header_line == "## B"
    assert out[1].content == "bar"


# ─── content stripping ─────────────────────────────────────────────────


def test_content_leading_trailing_blank_lines_stripped():
    body = "## a\n\n\nBody text.\n\n\n## b\nx\n"
    out = split_by_heading(body, level=2)
    assert out[0].content == "Body text."


def test_content_preserves_internal_blank_lines():
    body = "## a\nFirst paragraph\n\nSecond paragraph\n## b\nx\n"
    out = split_by_heading(body, level=2)
    assert "First paragraph\n\nSecond paragraph" in out[0].content


# ─── various levels ───────────────────────────────────────────────────


@pytest.mark.parametrize("level,hashes", [(1, "#"), (3, "###"), (6, "######")])
def test_splits_at_requested_level(level, hashes):
    body = f"{hashes} a\nfoo\n{hashes} b\nbar\n"
    out = split_by_heading(body, level=level)
    assert [s.title for s in out] == ["a", "b"]
    assert all(s.level == level for s in out)


# ─── representative multi-level structure ─────────────────────────────


def test_book_with_chapters_and_sections():
    """A level-1 book heading may contain multiple level-2 chapters and level-3 sub-sections."""
    body = (
        "# Book One\n"
        "Preface\n"
        "## Chapter One\n"
        "Overview...\n"
        "### Section A\n"
        "Details...\n"
        "### Section B\n"
        "More details...\n"
        "## Chapter Two\n"
        "Chapter two body...\n"
        "### Section A\n"
        "Section text...\n"
    )
    out = split_by_heading(body, level=2)
    assert [s.title for s in out] == ["Chapter One", "Chapter Two"]
    assert "### Section A" in out[0].content
    assert "### Section B" in out[0].content
    assert "Overview..." not in out[1].content


# ─── Section dataclass ────────────────────────────────────────────────


def test_section_is_dataclass():
    """Downstream code assumes field-based (not dict-based) access —
    verify the dataclass contract holds."""
    body = "## a\ncontent\n"
    s = split_by_heading(body, level=2)[0]
    assert isinstance(s, Section)
    # All documented fields present:
    for f in ("level", "title", "header_line", "start", "end", "content"):
        assert hasattr(s, f)


def test_duplicate_chapter_titles_are_preserved():
    body = (
        "# Book One\n"
        "## Chapter One\n"
        "Body a\n"
        "## Chapter Two\n"
        "Body b\n"
        "# Book Two\n"
        "## Chapter One\n"
        "Body c\n"
    )
    out = split_by_heading(body, level=2)
    first_chapters = [s for s in out if s.title == "Chapter One"]
    assert len(first_chapters) == 2
