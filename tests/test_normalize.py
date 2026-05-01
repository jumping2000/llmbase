"""Tests for tools.normalize — paragraph merge + head-level rewrite."""

import pytest

from llmwiki.normalize import (
    CLOSING_WRAPPERS,
    SENTENCE_TERMINATORS,
    HeadRule,
    normalize_heads,
    normalize_paragraphs,
)


def test_paragraphs_merges_non_terminator_line():
    src = "Intro,\ncontinues here\n"
    assert normalize_paragraphs(src) == "Intro,continues here\n"


def test_paragraphs_keeps_break_after_terminator():
    src = "First sentence.\nSecond sentence.\n"
    assert normalize_paragraphs(src) == src


def test_paragraphs_preserves_blank_line_as_boundary():
    src = "Intro,\ncontinues\n\nNew part,\ncontinues\n"
    assert normalize_paragraphs(src) == "Intro,continues\n\nNew part,continues\n"


def test_paragraphs_does_not_merge_into_heading():
    src = "Intro,\n## Heading\nBody\n"
    assert normalize_paragraphs(src) == src


def test_paragraphs_does_not_merge_empty_heading():
    for heading in ("#", "##", "### ", "###### "):
        src = f"Intro,\n{heading}\nBody\n"
        assert normalize_paragraphs(src) == src


def test_paragraphs_preserves_list_items():
    src = "Intro,\n- item one\n- item two\nBody\n"
    assert normalize_paragraphs(src) == src


def test_paragraphs_preserves_blockquote_and_fence():
    src = "> quoted\nnext\n\n```\na,\nb\n```\n"
    assert normalize_paragraphs(src) == src


def test_paragraphs_preserves_link_reference_definition():
    src = "Intro,\n[ref]: https://example.com\n"
    assert normalize_paragraphs(src) == src


def test_paragraphs_preserves_indented_code_block():
    src = "Text.\n\n    code_a\n    code_b\n"
    assert normalize_paragraphs(src) == src


def test_paragraphs_preserves_trailing_newlines_and_crlf():
    assert normalize_paragraphs("a\n\n") == "a\n\n"
    assert normalize_paragraphs("Intro,\r\nBody.\r\n") == "Intro,Body.\r\n"


def test_paragraphs_override_terminators(monkeypatch):
    monkeypatch.setattr("llmwiki.normalize.SENTENCE_TERMINATORS", ".!?;,")
    src = "Intro,\nBody.\n"
    assert normalize_paragraphs(src) == src


def test_paragraphs_default_constants_shape():
    assert "." in SENTENCE_TERMINATORS and ";" in SENTENCE_TERMINATORS
    assert ")" in CLOSING_WRAPPERS and '"' in CLOSING_WRAPPERS


GENERIC_PACK: list[HeadRule] = [
    {"pattern": r"^Chapter\s+(One|Two|Three|[0-9]+)", "level": 2},
    {"pattern": r"^Section\s+[A-Z]", "level": 3},
]


def test_heads_no_rules_is_noop():
    src = "# Book\n## Chapter One\nBody\n"
    assert normalize_heads(src, []) == src


def test_heads_rewrites_by_pattern():
    src = "### Chapter One Doctrine\nBody\n# Section A\n"
    expected = "## Chapter One Doctrine\nBody\n### Section A\n"
    assert normalize_heads(src, GENERIC_PACK) == expected


def test_heads_non_matching_heading_preserved():
    src = "## Overview\nBody\n"
    assert normalize_heads(src, GENERIC_PACK) == src


def test_heads_first_match_wins():
    rules: list[HeadRule] = [
        {"pattern": r"Chapter", "level": 2},
        {"pattern": r"Chapter", "level": 4},
    ]
    src = "###### Chapter One\n"
    assert normalize_heads(src, rules) == "## Chapter One\n"


def test_heads_preserves_indent_and_closer():
    src = "   #### Chapter One Doctrine ##\n"
    expected = "   ## Chapter One Doctrine ##\n"
    assert normalize_heads(src, GENERIC_PACK) == expected


def test_heads_skips_fenced_code_and_html_block():
    src = "# Book\n```\n## Chapter One fake\n```\n## Chapter One real\n"
    assert normalize_heads(src, GENERIC_PACK) == src

    html_src = "<div>\n# Chapter One fake\n</div>\n\n### Chapter One real\n"
    html_expected = "<div>\n# Chapter One fake\n</div>\n\n## Chapter One real\n"
    assert normalize_heads(html_src, GENERIC_PACK) == html_expected


def test_heads_rejects_invalid_level():
    with pytest.raises(ValueError):
        normalize_heads("# x\n", [{"pattern": r"x", "level": 7}])
    with pytest.raises(ValueError):
        normalize_heads("# x\n", [{"pattern": r"x", "level": 0}])


def test_heads_preserve_missing_newline_empty_input_and_crlf():
    assert normalize_heads("#### Chapter One", GENERIC_PACK) == "## Chapter One"
    assert normalize_heads("", GENERIC_PACK) == ""
    assert normalize_heads("### Chapter One\r\nBody\r\n", GENERIC_PACK) == "## Chapter One\r\nBody\r\n"


def test_paragraphs_then_heads_composes_cleanly():
    src = (
        "#### Chapter One Doctrine\n"
        "The theme starts,\n"
        "and continues here.\n"
        "\n"
        "# Section A\n"
        "Not finished,\n"
        "continued.\n"
    )
    expected = (
        "## Chapter One Doctrine\n"
        "The theme starts,and continues here.\n"
        "\n"
        "### Section A\n"
        "Not finished,continued.\n"
    )
    assert normalize_heads(normalize_paragraphs(src), GENERIC_PACK) == expected
