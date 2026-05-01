"""Tests for tools.anchor — span anchoring + normalize."""

import pytest

from llmwiki.anchor import Anchor, locate_span, normalize_text


# ─── normalize_text ───────────────────────────────────────────────────


def test_normalize_none_is_identity():
    s = "Introduzione  , sezione"
    assert normalize_text(s, "none") == s


def test_normalize_punct_strips_configured_punctuation():
    assert normalize_text("Introduzione, sezione!", "punct") == "Introduzione sezione"
    assert normalize_text("Title — with [brackets]!", "punct") == "Title  with brackets"


def test_normalize_punct_keeps_whitespace():
    # punct level must preserve spaces (that is the whole reason levels exist).
    assert normalize_text("Intro duzione", "punct") == "Intro duzione"


def test_normalize_punct_spaces_strips_all_whitespace_incl_ideographic():
    assert normalize_text("Intro du\u3000zione\tuno", "punct_spaces") == "Introduzioneuno"


def test_normalize_punct_spaces_combines_punct_and_spaces():
    assert normalize_text("Introduzione,\u3000 sezione!", "punct_spaces") == "Introduzionesezione"


def test_normalize_unknown_level_raises():
    with pytest.raises(ValueError):
        normalize_text("x", "bogus")  # type: ignore[arg-type]


# ─── locate_span: exact matches ───────────────────────────────────────


def test_head_tail_exact():
    c = "La teoria della vacuita chiarisce la natura dei fenomeni. La conclusione ribadisce il punto centrale."
    a = locate_span(c, "teoria della vacuita", "punto centrale")
    assert a is not None
    assert a.strategy == "exact"
    assert c[a.start : a.end].startswith("teoria della vacuita")
    assert c[a.start : a.end].endswith("punto centrale")


def test_head_tail_exact_without_normalize():
    c = "abc_DEF_xyz"
    a = locate_span(c, "abc", "xyz", normalize="none")
    assert a is not None
    assert a.strategy == "exact"
    assert c[a.start : a.end] == "abc_DEF_xyz"


# ─── locate_span: normalization across punctuation ────────────────────


def test_punct_differ_matches_through_comma():
    c = "Introduzione al tema, con un passaggio chiave."
    a = locate_span(c, "Introduzione al tema con un passaggio chiave", normalize="punct")
    assert a is not None


def test_punct_spaces_bridges_spaces_and_punct():
    c = "Introduzione al tema, con un passaggio chiave."
    a = locate_span(c, "Introduzione al tema con un passaggio chiave", normalize="punct_spaces")
    assert a is not None
    assert a.strategy == "head_only"  # no tail → head_only


def test_offsets_are_original_not_normalized():
    """Critical invariant: offsets must index into original content so a
    caller can DOM-slice, highlight, or scroll without reversing normalize."""
    c = '"Introduzione", sezione.'
    a = locate_span(c, "Introduzione")
    assert a is not None
    # Span must start at the 觀 char, not at the opening 「.
    assert c[a.start] == "I"
    # Original-index span should cover exactly 觀自在菩薩 at the head boundary.
    assert c[a.start : a.start + 12] == "Introduzione"


def test_offsets_exclude_trailing_dropped_chars():
    # Head "觀自在菩薩" followed immediately by 。— end should stop at 薩, not include 。.
    c = "Introduzione. Altra parte."
    a = locate_span(c, "Introduzione", "Altra parte")
    assert a is not None
    assert a.strategy == "exact"
    assert c[a.start : a.end] == "Introduzione. Altra parte"


# ─── locate_span: fallback strategies ─────────────────────────────────


def test_head_only_when_tail_missing():
    c = "Introduzione al tema. Testo successivo."
    a = locate_span(c, "Introduzione", "coda mancante")
    assert a is not None
    assert a.strategy == "head_only"
    assert a.start < a.end
    assert a.end == len(c)


def test_empty_tail_yields_head_only():
    c = "Introduzione al tema."
    a = locate_span(c, "Introduzione")
    assert a is not None
    assert a.strategy == "head_only"
    assert a.end == len(c)


def test_empty_tail_explicit_empty_string():
    c = "Introduzione al tema."
    a = locate_span(c, "Introduzione", tail="")
    assert a is not None
    assert a.strategy == "head_only"


def test_tail_all_punct_treated_as_empty():
    # tail normalizes to empty → head_only (rather than spurious match).
    c = "Introduzione al tema."
    a = locate_span(c, "Introduzione", tail=",.!?")
    assert a is not None
    assert a.strategy == "head_only"


def test_tail_before_head_does_not_match():
    # Tail text appears before head in content. Must NOT count as exact.
    c = "Conclusione. Testo iniziale. Introduzione al tema."
    a = locate_span(c, "Introduzione", "Conclusione")
    assert a is not None
    assert a.strategy == "head_only"


# ─── locate_span: no match / boundary cases ───────────────────────────


def test_no_match_returns_none():
    assert locate_span("Testo non correlato.", "Introduzione", "punto centrale") is None


def test_empty_content_returns_none():
    assert locate_span("", "Introduzione") is None


def test_empty_head_raises():
    with pytest.raises(ValueError):
        locate_span("some content", "")


def test_head_all_punct_normalizes_to_empty_returns_none():
    # Head is all punctuation → normalizes to empty → cannot anchor.
    a = locate_span("Introduzione.", ",.!?")
    assert a is None


def test_head_longer_than_content_returns_none():
    assert locate_span("short", "very very long heading") is None


# ─── locate_span: invariants ──────────────────────────────────────────


def test_anchor_invariant_start_lt_end():
    c = "Introduzione al tema."
    a = locate_span(c, "Introduzione", "tema")
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

    padding = "a" * 500_000
    c = padding + "introduzione al tema" + padding
    t0 = time.perf_counter()
    a = locate_span(c, "introduzione", "tema")
    elapsed = time.perf_counter() - t0
    assert a is not None
    assert a.strategy == "exact"
    assert elapsed < 1.0, f"locate_span too slow on 1MB content: {elapsed:.2f}s"
