import json
from datetime import datetime, timezone
from unittest.mock import patch

from llmwiki.web import create_web_app
from llmwiki.llm import chat_with_meta
from llmwiki.llm_usage import append_usage_record, recent_requests, summarize_usage, usage_log_path


FIXED_NOW = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)


def test_usage_summary_rolls_up_global_model_feature_and_stage_totals(tmp_kb):
    append_usage_record(tmp_kb, {
        "feature": "compile",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "reasoning_tokens": 4,
        "total_tokens": 30,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
    })
    append_usage_record(tmp_kb, {
        "feature": "ask",
        "stage": "selector",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o-mini",
        "prompt_tokens": 5,
        "completion_tokens": 6,
        "reasoning_tokens": 0,
        "total_tokens": 11,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 2,
        "retry": False,
        "fallback": True,
        "success": True,
        "error_type": None,
        "error_message": None,
    })
    append_usage_record(tmp_kb, {
        "feature": "ask",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "reasoning_tokens": 0,
        "total_tokens": 3,
        "finish_reason": None,
        "truncated": False,
        "attempt_index": 2,
        "attempts_total_so_far": 3,
        "retry": True,
        "fallback": False,
        "success": False,
        "error_type": "empty_response",
        "error_message": None,
    })

    summary = summarize_usage(tmp_kb)

    assert summary["record_count"] == 3
    assert summary["malformed_record_count"] == 0
    assert summary["missing_usage_count"] == 0
    assert summary["totals"]["total_tokens"] == 44
    assert summary["successful_totals"]["total_tokens"] == 41
    assert summary["retry_fallback_totals"]["total_tokens"] == 14

    assert summary["by_model"][0]["model"] == "gpt-4o"
    assert summary["by_model"][0]["total_tokens"] == 33
    assert summary["by_model"][1]["model"] == "gpt-4o-mini"
    assert summary["by_model"][1]["fallback_count"] == 1

    compile_feature = next(item for item in summary["by_feature"] if item["feature"] == "compile")
    ask_feature = next(item for item in summary["by_feature"] if item["feature"] == "ask")
    assert compile_feature["total_tokens"] == 30
    assert ask_feature["attempt_count"] == 2
    assert ask_feature["retry_count"] == 1
    assert ask_feature["fallback_count"] == 1
    selector_stage = next(item for item in ask_feature["by_stage"] if item["stage"] == "selector")
    answer_stage = next(item for item in ask_feature["by_stage"] if item["stage"] == "answer")
    assert selector_stage["total_tokens"] == 11
    assert answer_stage["total_tokens"] == 3


def test_usage_summary_skips_malformed_lines_and_counts_missing_usage(tmp_kb):
    append_usage_record(tmp_kb, {
        "feature": "xici",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": None,
        "completion_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
        "finish_reason": None,
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": False,
        "error_type": "exception",
        "error_message": "boom",
    })
    path = usage_log_path(tmp_kb)
    with open(path, "ab") as f:
        f.write(b"{not-json}\n")
        f.write(json.dumps(["wrong-shape"]).encode("utf-8") + b"\n")

    summary = summarize_usage(tmp_kb)

    assert summary["record_count"] == 1
    assert summary["malformed_record_count"] == 2
    assert summary["missing_usage_count"] == 1
    assert summary["totals"]["total_tokens"] == 0
    assert summary["by_feature"][0]["feature"] == "xici"
    assert summary["by_feature"][0]["by_stage"][0]["stage"] == "answer"


def test_chat_with_meta_logs_attempts_to_usage_jsonl(tmp_kb, monkeypatch):
    monkeypatch.setenv("LLMBASE_PRIMARY_RETRIES", "2")
    monkeypatch.setenv("LLMBASE_FALLBACK_MODELS", "")

    responses = iter([
        ("", "stop", {"prompt_tokens": 4, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 4}),
        ("ok", "stop", {"prompt_tokens": 5, "completion_tokens": 7, "reasoning_tokens": 1, "total_tokens": 12}),
    ])

    with patch("llmwiki.llm._call_llm", side_effect=lambda *args, **kwargs: next(responses)):
        text, meta = chat_with_meta(
            "hello",
            model="gpt-4o",
            feature="ask",
            stage="answer",
            base_dir=tmp_kb,
        )

    assert text == "ok"
    assert meta.attempts == 2
    summary = summarize_usage(tmp_kb)
    assert summary["record_count"] == 2
    assert summary["totals"]["total_tokens"] == 16
    assert summary["successful_totals"]["total_tokens"] == 12
    assert summary["retry_fallback_totals"]["total_tokens"] == 12
    ask_feature = next(item for item in summary["by_feature"] if item["feature"] == "ask")
    assert ask_feature["attempt_count"] == 2
    assert ask_feature["retry_count"] == 1
    recent = recent_requests(tmp_kb, limit=1)
    assert len(recent["requests"]) == 1
    assert recent["requests"][0]["attempt_count"] == 2
    assert recent["requests"][0]["total_tokens"] == 16
    assert recent["requests"][0]["success"] is True


def test_recent_requests_groups_attempts_by_request_id(tmp_kb):
    append_usage_record(tmp_kb, {
        "request_id": "req-1",
        "feature": "ask",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 2,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 2,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": False,
        "error_type": "empty_response",
        "error_message": None,
        "ts": "2026-05-08T10:00:00+00:00",
    })
    append_usage_record(tmp_kb, {
        "request_id": "req-1",
        "feature": "ask",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o-mini",
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "reasoning_tokens": 1,
        "total_tokens": 8,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 2,
        "retry": False,
        "fallback": True,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "2026-05-08T10:00:01+00:00",
    })
    append_usage_record(tmp_kb, {
        "request_id": "req-2",
        "feature": "compile",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "reasoning_tokens": 0,
        "total_tokens": 20,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "2026-05-08T10:00:02+00:00",
    })

    recent = recent_requests(tmp_kb, limit=2)

    assert len(recent["requests"]) == 2
    assert recent["requests"][0]["request_id"] == "req-2"
    assert recent["requests"][1]["request_id"] == "req-1"
    assert recent["requests"][1]["attempt_count"] == 2
    assert recent["requests"][1]["success"] is True
    assert recent["requests"][1]["fallback_count"] == 1
    assert recent["requests"][1]["total_tokens"] == 10
    assert recent["requests"][1]["actual_models"] == ["gpt-4o", "gpt-4o-mini"]


def test_api_llm_usage_summary_returns_aggregated_json(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    append_usage_record(tmp_kb, {
        "feature": "compile",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 8,
        "completion_tokens": 12,
        "reasoning_tokens": 0,
        "total_tokens": 20,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
    })
    app = create_web_app(tmp_kb)
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/llm/usage/summary")

    assert response.status_code == 200
    data = response.get_json()
    assert data["record_count"] == 1
    assert data["totals"]["total_tokens"] == 20
    assert data["by_model"][0]["model"] == "gpt-4o"
    assert data["by_feature"][0]["feature"] == "compile"


def test_api_llm_usage_recent_returns_grouped_logical_requests(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    append_usage_record(tmp_kb, {
        "request_id": "req-9",
        "feature": "ask",
        "stage": "selector",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 6,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 6,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": False,
        "error_type": "empty_response",
        "error_message": None,
    })
    append_usage_record(tmp_kb, {
        "request_id": "req-9",
        "feature": "ask",
        "stage": "selector",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o-mini",
        "prompt_tokens": 2,
        "completion_tokens": 3,
        "reasoning_tokens": 0,
        "total_tokens": 5,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 2,
        "retry": False,
        "fallback": True,
        "success": True,
        "error_type": None,
        "error_message": None,
    })
    app = create_web_app(tmp_kb)
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/llm/usage/recent?limit=1")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["requests"]) == 1
    assert data["requests"][0]["request_id"] == "req-9"
    assert data["requests"][0]["attempt_count"] == 2
    assert data["requests"][0]["total_tokens"] == 11
    assert data["requests"][0]["actual_models"] == ["gpt-4o", "gpt-4o-mini"]


def test_usage_summary_filters_by_last_window_and_counts_bad_timestamps(tmp_kb):
    append_usage_record(tmp_kb, {
        "request_id": "recent-1",
        "feature": "ask",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 4,
        "completion_tokens": 6,
        "reasoning_tokens": 0,
        "total_tokens": 10,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "2026-05-08T10:00:00+00:00",
    })
    append_usage_record(tmp_kb, {
        "request_id": "old-1",
        "feature": "compile",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "reasoning_tokens": 0,
        "total_tokens": 30,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "2026-05-01T10:00:00+00:00",
    })
    append_usage_record(tmp_kb, {
        "request_id": "bad-ts",
        "feature": "xici",
        "stage": "generate",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 7,
        "completion_tokens": 2,
        "reasoning_tokens": 0,
        "total_tokens": 9,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "not-a-ts",
    })

    with patch("llmwiki.llm_usage._now_dt", return_value=FIXED_NOW):
        summary = summarize_usage(tmp_kb, last="24h")

    assert summary["applied_window"] == "24h"
    assert summary["record_count"] == 1
    assert summary["totals"]["total_tokens"] == 10
    assert summary["skipped_timestamp_count"] == 1
    assert summary["from_ts"] == "2026-05-07T12:00:00+00:00"
    assert summary["to_ts"] == "2026-05-08T12:00:00+00:00"


def test_recent_requests_filters_by_explicit_range_and_last_takes_precedence(tmp_kb):
    append_usage_record(tmp_kb, {
        "request_id": "window-a",
        "feature": "ask",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 2,
        "completion_tokens": 3,
        "reasoning_tokens": 0,
        "total_tokens": 5,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "2026-05-08T11:00:00+00:00",
    })
    append_usage_record(tmp_kb, {
        "request_id": "window-b",
        "feature": "ask",
        "stage": "answer",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o-mini",
        "prompt_tokens": 4,
        "completion_tokens": 5,
        "reasoning_tokens": 0,
        "total_tokens": 9,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": True,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "2026-04-01T11:00:00+00:00",
    })

    recent = recent_requests(
        tmp_kb,
        limit=5,
        from_ts="2026-03-01T00:00:00+00:00",
        to_ts="2026-06-01T00:00:00+00:00",
    )

    assert recent["applied_window"] == "custom"
    assert [item["request_id"] for item in recent["requests"]] == ["window-a", "window-b"]

    with patch("llmwiki.llm_usage._now_dt", return_value=FIXED_NOW):
        recent_last = recent_requests(
            tmp_kb,
            limit=5,
            from_ts="2026-03-01T00:00:00+00:00",
            to_ts="2026-06-01T00:00:00+00:00",
            last="24h",
        )

    assert recent_last["applied_window"] == "24h"
    assert [item["request_id"] for item in recent_last["requests"]] == ["window-a"]


def test_api_llm_usage_summary_accepts_time_filters(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    append_usage_record(tmp_kb, {
        "request_id": "summary-filter",
        "feature": "taxonomy",
        "stage": "single-pass",
        "requested_model": "gpt-4o",
        "actual_model": "gpt-4o",
        "prompt_tokens": 8,
        "completion_tokens": 2,
        "reasoning_tokens": 0,
        "total_tokens": 10,
        "finish_reason": "stop",
        "truncated": False,
        "attempt_index": 1,
        "attempts_total_so_far": 1,
        "retry": False,
        "fallback": False,
        "success": True,
        "error_type": None,
        "error_message": None,
        "ts": "2026-05-08T09:00:00+00:00",
    })
    app = create_web_app(tmp_kb)
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/llm/usage/summary?from=2026-05-08T08:00:00%2B00:00&to=2026-05-08T10:00:00%2B00:00")

    assert response.status_code == 200
    data = response.get_json()
    assert data["applied_window"] == "custom"
    assert data["record_count"] == 1
    assert data["totals"]["total_tokens"] == 10


def test_api_llm_usage_recent_rejects_invalid_last_window(tmp_kb, monkeypatch):
    monkeypatch.delenv("LLMBASE_API_SECRET", raising=False)
    app = create_web_app(tmp_kb)
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/llm/usage/recent?last=2weeks")

    assert response.status_code == 400
    data = response.get_json()
    assert "Invalid last window" in data["error"]