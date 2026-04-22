"""Tests for tools.anchor — span anchoring + normalize."""

import pytest

from tools.anchor import Anchor, locate_span, normalize_text


# ─── normalize_text ───────────────────────────────────────────────────


def test_normalize_none_is_identity():
    s = "觀自在菩薩　，行深"
    assert normalize_text(s, "none") == s


def test_normalize_punct_strips_cjk_and_ascii():
    assert normalize_text("觀自在菩薩，行深！", "punct") == "觀自在菩薩行深"
    assert normalize_text("Title — with [brackets]!", "punct") == "Title  with brackets"


def test_normalize_punct_keeps_whitespace():
    # punct level must preserve spaces (that is the whole reason levels exist).
    assert normalize_text("觀 自 在", "punct") == "觀 自 在"


def test_normalize_punct_spaces_strips_all_whitespace_incl_ideographic():
    assert normalize_text("觀 自　在\t菩薩", "punct_spaces") == "觀自在菩薩"


def test_normalize_punct_spaces_combines_punct_and_spaces():
    assert normalize_text("觀自在菩薩，　行深！", "punct_spaces") == "觀自在菩薩行深"


def test_normalize_unknown_level_raises():
    with pytest.raises(ValueError):
        normalize_text("x", "bogus")  # type: ignore[arg-type]


# ─── locate_span: exact matches ───────────────────────────────────────


def test_head_tail_exact():
    c = "觀自在菩薩行深般若波羅蜜多時，照見五蘊皆空，度一切苦厄。舍利子！色不異空。"
    a = locate_span(c, "觀自在菩薩", "度一切苦厄")
    assert a is not None
    assert a.strategy == "exact"
    assert c[a.start : a.end].startswith("觀自在菩薩")
    assert c[a.start : a.end].endswith("度一切苦厄")


def test_head_tail_exact_without_normalize():
    c = "abc_DEF_xyz"
    a = locate_span(c, "abc", "xyz", normalize="none")
    assert a is not None
    assert a.strategy == "exact"
    assert c[a.start : a.end] == "abc_DEF_xyz"


# ─── locate_span: normalization across punctuation ────────────────────


def test_punct_differ_matches_through_comma():
    # Content has 「，」, head key provided without it — punct normalize must bridge.
    c = "觀自在菩薩行深般若波羅蜜多時，照見五蘊皆空。"
    a = locate_span(c, "觀自在菩薩行深般若波羅蜜多時照見", normalize="punct")
    assert a is not None


def test_punct_spaces_bridges_spaces_and_punct():
    c = "觀自在菩薩行深般若波羅蜜多時，照見五蘊皆空。"
    a = locate_span(c, "觀自在菩薩行深般若波羅蜜多時 照見", normalize="punct_spaces")
    assert a is not None
    assert a.strategy == "head_only"  # no tail → head_only


def test_offsets_are_original_not_normalized():
    """Critical invariant: offsets must index into original content so a
    caller can DOM-slice, highlight, or scroll without reversing normalize."""
    c = "「觀自在菩薩」，行深。"
    a = locate_span(c, "觀自在菩薩")
    assert a is not None
    # Span must start at the 觀 char, not at the opening 「.
    assert c[a.start] == "觀"
    # Original-index span should cover exactly 觀自在菩薩 at the head boundary.
    assert c[a.start : a.start + 5] == "觀自在菩薩"


def test_offsets_exclude_trailing_dropped_chars():
    # Head "觀自在菩薩" followed immediately by 。— end should stop at 薩, not include 。.
    c = "觀自在菩薩。餘文。"
    a = locate_span(c, "觀自在菩薩", "餘文")
    assert a is not None
    assert a.strategy == "exact"
    assert c[a.start : a.end] == "觀自在菩薩。餘文"  # dropped chars inside span kept, trailing 。excluded


# ─── locate_span: fallback strategies ─────────────────────────────────


def test_head_only_when_tail_missing():
    c = "觀自在菩薩行深般若。餘文後省。"
    a = locate_span(c, "觀自在菩薩", "不存之尾")
    assert a is not None
    assert a.strategy == "head_only"
    assert a.start < a.end
    assert a.end == len(c)


def test_empty_tail_yields_head_only():
    c = "觀自在菩薩行深。"
    a = locate_span(c, "觀自在菩薩")
    assert a is not None
    assert a.strategy == "head_only"
    assert a.end == len(c)


def test_empty_tail_explicit_empty_string():
    c = "觀自在菩薩行深。"
    a = locate_span(c, "觀自在菩薩", tail="")
    assert a is not None
    assert a.strategy == "head_only"


def test_tail_all_punct_treated_as_empty():
    # tail normalizes to empty → head_only (rather than spurious match).
    c = "觀自在菩薩行深。"
    a = locate_span(c, "觀自在菩薩", tail="，。！")
    assert a is not None
    assert a.strategy == "head_only"


def test_tail_before_head_does_not_match():
    # Tail text appears before head in content. Must NOT count as exact.
    c = "度一切苦厄。前文。觀自在菩薩行深。"
    a = locate_span(c, "觀自在菩薩", "度一切苦厄")
    assert a is not None
    assert a.strategy == "head_only"


# ─── locate_span: no match / boundary cases ───────────────────────────


def test_no_match_returns_none():
    assert locate_span("無關之文。", "觀自在菩薩", "度一切苦厄") is None


def test_empty_content_returns_none():
    assert locate_span("", "觀自在菩薩") is None


def test_empty_head_raises():
    with pytest.raises(ValueError):
        locate_span("some content", "")


def test_head_all_punct_normalizes_to_empty_returns_none():
    # Head is all punctuation → normalizes to empty → cannot anchor.
    a = locate_span("觀自在菩薩。", "，。！")
    assert a is None


def test_head_longer_than_content_returns_none():
    assert locate_span("短", "很長很長很長的頭") is None


# ─── locate_span: invariants ──────────────────────────────────────────


def test_anchor_invariant_start_lt_end():
    c = "觀自在菩薩行深。"
    a = locate_span(c, "觀自在菩薩", "行深")
    assert a is not None
    assert a.start < a.end
    assert 0 <= a.start
    assert a.end <= len(c)


def test_anchor_frozen_dataclass():
    a = Anchor(0, 5, "exact")
    with pytest.raises(Exception):
        a.start = 99  # type: ignore[misc]


# ─── locate_span: performance (linear scan) ───────────────────────────


def test_large_content_performance():
    """head search must be O(n), not O(n^2). 1 MB content in <1s."""
    import time

    padding = "無" * 500_000
    c = padding + "觀自在菩薩行深般若" + padding
    t0 = time.perf_counter()
    a = locate_span(c, "觀自在菩薩", "行深般若")
    elapsed = time.perf_counter() - t0
    assert a is not None
    assert a.strategy == "exact"
    assert elapsed < 1.0, f"locate_span too slow on 1MB content: {elapsed:.2f}s"
