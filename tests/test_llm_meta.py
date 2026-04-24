"""Tests for v0.7.8 — `chat_with_meta` + `LLMMeta` + `reasoning_budget` (议 5-甲/乙).

Rationale: siwen's 2026-04-21 post-mortem of an 11-hour wenguan failure
traced root cause to the absence of ``finish_reason='length'`` detection.
``chat_with_meta`` surfaces finish_reason / usage / attempts to the
caller; ``reasoning_budget`` is the arithmetic helper downstream uses
to size chunks safely against the model's output budget.

Tests mock ``tools.llm._call_llm`` at its new (content, finish_reason,
usage) tuple return shape and exercise:
- happy path + finish_reason propagation
- ``finish_reason="length"`` → ``meta.truncated=True`` without raising
- reasoning_tokens flattening from OpenAI's nested response
- fallback bookkeeping (``meta.model`` and ``meta.attempts``)
- empty-exhaustion preserves chat()'s silent-empty contract + meta
- ``reasoning_budget`` formula, boundary conditions, ValueError on bad input
- ``chat()`` unchanged externally (regression guard for v0.7.x callers)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


# ─── LLMMeta: happy path + truncation + reasoning tokens ────────────


def _usage(prompt=10, completion=20, reasoning=None, total=None):
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "reasoning_tokens": reasoning,
        "total_tokens": total if total is not None else prompt + completion,
    }


def test_chat_with_meta_happy_path():
    """Clean first-try returns content + meta describing that call."""
    def fake_call(messages, model, max_tokens, api_key=None):
        return ("hello", "stop", _usage(prompt=5, completion=3))

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        text, meta = chat_with_meta("hi", model="m1")

    assert text == "hello"
    assert meta.model == "m1"
    assert meta.finish_reason == "stop"
    assert meta.truncated is False
    assert meta.attempts == 1
    assert meta.usage["prompt_tokens"] == 5
    assert meta.usage["completion_tokens"] == 3


def test_chat_with_meta_length_cut_returns_truncated_true():
    """finish_reason='length' must set meta.truncated=True without raising.

    This is the field whose absence caused the 11-hour wenguan loss —
    ratio check did not distinguish length-cut from stop."""
    def fake_call(messages, model, max_tokens, api_key=None):
        return ("partial output...", "length", _usage(completion=16384))

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        text, meta = chat_with_meta("hi", model="m1", max_tokens=16384)

    assert text == "partial output..."
    assert meta.finish_reason == "length"
    assert meta.truncated is True


def test_chat_with_meta_unknown_finish_reason_not_truncated():
    """Anything other than 'length' → truncated=False (including None)."""
    def fake_call(messages, model, max_tokens, api_key=None):
        return ("x", None, _usage())

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        _, meta = chat_with_meta("hi", model="m")

    assert meta.finish_reason is None
    assert meta.truncated is False


def test_chat_with_meta_reasoning_tokens_flattened_from_openai_nested():
    """OpenAI SDK returns reasoning_tokens nested in
    completion_tokens_details — `_extract_usage` must flatten it into
    the top-level usage dict so callers don't walk nested objects."""
    from llmwiki.llm import _extract_usage

    class FakeDetails:
        reasoning_tokens = 512

    class FakeUsage:
        prompt_tokens = 100
        completion_tokens = 1500
        total_tokens = 1600
        completion_tokens_details = FakeDetails()

    usage = _extract_usage(FakeUsage())
    assert usage["prompt_tokens"] == 100
    assert usage["completion_tokens"] == 1500
    assert usage["reasoning_tokens"] == 512
    assert usage["total_tokens"] == 1600


def test_extract_usage_missing_details_leaves_reasoning_none():
    """Providers that don't return reasoning_tokens → None (not KeyError)."""
    from llmwiki.llm import _extract_usage

    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 20
        total_tokens = 30
        # No completion_tokens_details attribute at all.

    usage = _extract_usage(FakeUsage())
    assert usage["reasoning_tokens"] is None


def test_extract_usage_none_returns_none_filled_dict():
    """Some providers omit usage entirely — must not crash."""
    from llmwiki.llm import _extract_usage

    usage = _extract_usage(None)
    assert usage["prompt_tokens"] is None
    assert usage["reasoning_tokens"] is None


def test_extract_usage_accepts_dict_shaped_payload():
    """Some aggregators / older clients hand back usage as a plain dict.

    Regression for Codex v0.7.8 finding: strict `getattr` silently
    coerced every usage field to ``None`` on dict-shaped input, which
    would make downstream `tokens_per_char` calibration noisy."""
    from llmwiki.llm import _extract_usage

    usage_dict = {
        "prompt_tokens": 42,
        "completion_tokens": 99,
        "total_tokens": 141,
        "completion_tokens_details": {"reasoning_tokens": 33},
    }
    usage = _extract_usage(usage_dict)
    assert usage["prompt_tokens"] == 42
    assert usage["completion_tokens"] == 99
    assert usage["total_tokens"] == 141
    assert usage["reasoning_tokens"] == 33


def test_extract_usage_dict_without_reasoning_details():
    """Dict-shaped usage missing the nested reasoning details → None."""
    from llmwiki.llm import _extract_usage

    usage = _extract_usage({"prompt_tokens": 1, "completion_tokens": 2,
                             "total_tokens": 3})
    assert usage["prompt_tokens"] == 1
    assert usage["reasoning_tokens"] is None


# ─── Fallback accounting ────────────────────────────────────────────


def test_chat_with_meta_fallback_records_fallback_model_and_attempts(monkeypatch):
    """Primary fails, fallback succeeds → meta reflects fallback model
    and total attempts across both."""
    monkeypatch.setenv("LLMBASE_PRIMARY_RETRIES", "2")
    monkeypatch.setenv("LLMBASE_FALLBACK_RETRIES", "1")
    monkeypatch.setenv("LLMBASE_FALLBACK_MODELS", "fallback-m")

    calls = {"n": 0}

    def fake_call(messages, model, max_tokens, api_key=None):
        calls["n"] += 1
        if model == "primary":
            raise RuntimeError("primary down")
        return ("hello from fallback", "stop", _usage())

    # monkeypatch time.sleep so the 2**attempt backoff doesn't wall-clock.
    import llmwiki.llm as llm_mod
    monkeypatch.setattr(llm_mod, "time", type("T", (), {"sleep": lambda *_: None}))

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        text, meta = chat_with_meta("hi", model="primary")

    assert text == "hello from fallback"
    assert meta.model == "fallback-m"
    # primary retries exhaust (2) + fallback first try (1) = 3
    assert meta.attempts == 3
    assert calls["n"] == 3


def test_chat_with_meta_attempts_one_on_clean_first_try(monkeypatch):
    monkeypatch.setenv("LLMBASE_FALLBACK_MODELS", "")
    monkeypatch.setenv("LLMBASE_PRIMARY_RETRIES", "3")

    def fake_call(messages, model, max_tokens, api_key=None):
        return ("ok", "stop", _usage())

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        _, meta = chat_with_meta("hi", model="m")

    assert meta.attempts == 1


# ─── Empty-exhaustion path preserves silent-empty contract ──────────


def test_chat_with_meta_empty_exhausted_returns_empty_plus_last_meta(monkeypatch):
    """Matching chat()'s v0.7.x silent-empty contract: when every
    retry returns empty content, we return ('', meta) — not raise —
    and meta reflects the LAST observed response shape."""
    monkeypatch.setenv("LLMBASE_PRIMARY_RETRIES", "2")
    monkeypatch.setenv("LLMBASE_FALLBACK_MODELS", "")

    def fake_call(messages, model, max_tokens, api_key=None):
        return ("", "stop", _usage(completion=0))

    import llmwiki.llm as llm_mod
    monkeypatch.setattr(llm_mod, "time", type("T", (), {"sleep": lambda *_: None}))

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        text, meta = chat_with_meta("hi", model="m")

    assert text == ""
    assert meta.finish_reason == "stop"
    assert meta.attempts == 2


def test_chat_with_meta_empty_then_length_cut_last_round_wins(monkeypatch):
    """Last-seen semantics: if retries go empty-stop then empty-length,
    meta.finish_reason == 'length' (last observed), truncated=True."""
    monkeypatch.setenv("LLMBASE_PRIMARY_RETRIES", "2")
    monkeypatch.setenv("LLMBASE_FALLBACK_MODELS", "")

    responses = iter([
        ("", "stop", _usage()),
        ("", "length", _usage()),
    ])

    def fake_call(messages, model, max_tokens, api_key=None):
        return next(responses)

    import llmwiki.llm as llm_mod
    monkeypatch.setattr(llm_mod, "time", type("T", (), {"sleep": lambda *_: None}))

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        text, meta = chat_with_meta("hi", model="m")

    assert text == ""
    assert meta.finish_reason == "length"
    assert meta.truncated is True


# ─── api_key plumbing + no leak into meta ───────────────────────────


def test_chat_with_meta_forwards_api_key():
    captured = {}

    def fake_call(messages, model, max_tokens, api_key=None):
        captured["api_key"] = api_key
        return ("ok", "stop", _usage())

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        chat_with_meta("hi", model="m", api_key="sk-user-abc")

    assert captured["api_key"] == "sk-user-abc"


def test_chat_with_meta_does_not_leak_api_key_into_meta():
    """Regression guard: meta must not carry the api_key anywhere —
    neither as a field nor inside usage / model / finish_reason."""
    def fake_call(messages, model, max_tokens, api_key=None):
        return ("ok", "stop", _usage())

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat_with_meta
        _, meta = chat_with_meta("hi", model="m", api_key="sk-secret-XYZ")

    # Fields' string reprs must not echo the key.
    dumped = repr(meta)
    assert "sk-secret-XYZ" not in dumped


# ─── chat() unchanged externally (v0.7.x regression) ────────────────


def test_chat_returns_bare_string_not_tuple():
    """chat() signature must still return ``str`` — v0.7.x callers rely on it."""
    def fake_call(messages, model, max_tokens, api_key=None):
        return ("bare-string", "stop", _usage())

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat
        result = chat("hi", model="m")

    assert isinstance(result, str)
    assert result == "bare-string"


def test_chat_empty_exhausted_returns_empty_string(monkeypatch):
    """chat() must still silently return '' when retries exhaust empty —
    that's the v0.7.x contract."""
    monkeypatch.setenv("LLMBASE_PRIMARY_RETRIES", "2")
    monkeypatch.setenv("LLMBASE_FALLBACK_MODELS", "")

    def fake_call(messages, model, max_tokens, api_key=None):
        return ("", "stop", _usage())

    import llmwiki.llm as llm_mod
    monkeypatch.setattr(llm_mod, "time", type("T", (), {"sleep": lambda *_: None}))

    with patch("llmwiki.llm._call_llm", side_effect=fake_call):
        from llmwiki.llm import chat
        assert chat("hi", model="m") == ""


# ─── reasoning_budget (议 5-乙) ──────────────────────────────────────


def test_reasoning_budget_siwen_postmortem_numbers():
    """siwen's 2026-04-21 post-mortem: max_tokens=32000, ratio=17 → 1500 chars.

    Exact formula: 32000 * 0.8 / 17 = 1505.88 → int() truncates to 1505.
    siwen rounded to 1500 in their config; 1505 is the precise answer."""
    from llmwiki.llm import reasoning_budget
    assert reasoning_budget(max_tokens=32000, tokens_per_char=17) == 1505


def test_reasoning_budget_tight_safety():
    """Lower safety fraction → smaller chunk (more headroom)."""
    from llmwiki.llm import reasoning_budget
    assert reasoning_budget(32000, 17, safety=0.6) == 1129  # 32000*0.6/17


def test_reasoning_budget_ascii_summarization_ratio():
    """Low ratio (summarization: ~2 tokens/input-char) → much larger chunks."""
    from llmwiki.llm import reasoning_budget
    result = reasoning_budget(max_tokens=8000, tokens_per_char=2.0)
    assert result == 3200  # 8000 * 0.8 / 2


def test_reasoning_budget_never_returns_zero_for_valid_input():
    """Tiny budget × large ratio still returns ``>= 1`` — caller can't
    slice at 0 and should know the model is too cramped for the prompt."""
    from llmwiki.llm import reasoning_budget
    # 10 * 0.8 / 100 = 0.08 → int() = 0 → clamp to 1.
    assert reasoning_budget(max_tokens=10, tokens_per_char=100.0) == 1


def test_reasoning_budget_rejects_nonpositive_max_tokens():
    from llmwiki.llm import reasoning_budget
    with pytest.raises(ValueError, match="max_tokens"):
        reasoning_budget(max_tokens=0, tokens_per_char=17)
    with pytest.raises(ValueError, match="max_tokens"):
        reasoning_budget(max_tokens=-1, tokens_per_char=17)


def test_reasoning_budget_rejects_nonpositive_ratio():
    from llmwiki.llm import reasoning_budget
    with pytest.raises(ValueError, match="tokens_per_char"):
        reasoning_budget(32000, tokens_per_char=0)
    with pytest.raises(ValueError, match="tokens_per_char"):
        reasoning_budget(32000, tokens_per_char=-5.0)


def test_reasoning_budget_rejects_safety_out_of_range():
    from llmwiki.llm import reasoning_budget
    with pytest.raises(ValueError, match="safety"):
        reasoning_budget(32000, 17, safety=0)
    with pytest.raises(ValueError, match="safety"):
        reasoning_budget(32000, 17, safety=1.5)
    with pytest.raises(ValueError, match="safety"):
        reasoning_budget(32000, 17, safety=-0.1)


def test_reasoning_budget_safety_one_is_valid():
    """safety=1.0 is the no-headroom upper bound — valid but aggressive."""
    from llmwiki.llm import reasoning_budget
    assert reasoning_budget(32000, 17, safety=1.0) == int(32000 / 17)


def test_reasoning_budget_is_pure():
    """No env reads, no global state — same inputs always yield same output."""
    from llmwiki.llm import reasoning_budget
    a = reasoning_budget(10000, 5.5, safety=0.75)
    b = reasoning_budget(10000, 5.5, safety=0.75)
    assert a == b


def test_reasoning_budget_rejects_inf_overflow_as_valueerror():
    """Pathological large inputs that overflow to inf during float math
    surface as ValueError, not OverflowError — preserves the docstring's
    uniform bad-input contract (Codex v0.7.8 finding)."""
    from llmwiki.llm import reasoning_budget
    # max_tokens huge × safety 1.0 / tiny-positive ratio → multiplication
    # that overflows float64 to inf; int(inf) would otherwise raise
    # OverflowError.
    with pytest.raises(ValueError, match="non-finite"):
        reasoning_budget(
            max_tokens=10**308,
            tokens_per_char=1e-308,
            safety=1.0,
        )


def test_reasoning_budget_rejects_nan_ratio():
    """NaN tokens_per_char (bogus float) hits the finiteness guard too."""
    from llmwiki.llm import reasoning_budget
    with pytest.raises(ValueError):
        # NaN compares False against any threshold, so this slips past
        # the `<= 0` check — must be caught by the isfinite guard.
        reasoning_budget(32000, float("nan"))


def test_reasoning_budget_rejects_int_too_large_for_float():
    """An int larger than ``float('inf').__int__`` can't survive the
    first ``int * float`` and would raise OverflowError before the
    isfinite guard runs. Codex v0.7.8 round-2 flagged this edge;
    reason_budget now catches OverflowError and re-raises ValueError."""
    from llmwiki.llm import reasoning_budget
    with pytest.raises(ValueError, match="arithmetic failed"):
        # 10**309 > sys.float_info.max (~1.8e308); `int * float`
        # conversion raises OverflowError on the multiplication itself.
        reasoning_budget(max_tokens=10**309, tokens_per_char=1.0)
