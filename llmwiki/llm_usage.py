"""LLM token usage logging and aggregation."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import ensure_dirs, load_config

try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - Windows path
    fcntl = None

try:
    import msvcrt  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - POSIX path
    msvcrt = None


_TOKEN_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "total_tokens",
)

_WINDOW_DELTAS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "365d": timedelta(days=365),
}


def usage_log_path(base_dir: Path | None = None) -> Path:
    cfg = load_config(base_dir)
    ensure_dirs(cfg)
    return Path(cfg["paths"]["meta"]) / "llm-usage.jsonl"


def append_usage_record(base_dir: Path | None, record: dict) -> Path:
    path = usage_log_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = dict(record)
    payload["ts"] = payload.get("ts") or _now_iso()
    line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

    with _locked_file(path):
        with open(path, "ab+") as f:
            f.seek(0, 2)
            if f.tell() > 0:
                f.seek(-1, 2)
                if f.read(1) != b"\n":
                    f.write(b"\n")
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
    return path


def summarize_usage(
    base_dir: Path | None = None,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    last: str | None = None,
) -> dict:
    path = usage_log_path(base_dir)
    window = _resolve_time_window(from_ts=from_ts, to_ts=to_ts, last=last)
    summary = {
        "generated_at": _now_iso(),
        "source_path": str(path),
        "applied_window": window["applied_window"],
        "from_ts": _dt_to_iso(window["from_dt"]),
        "to_ts": _dt_to_iso(window["to_dt"]),
        "record_count": 0,
        "malformed_record_count": 0,
        "missing_usage_count": 0,
        "skipped_timestamp_count": 0,
        "totals": _empty_totals(),
        "successful_totals": _empty_totals(),
        "retry_fallback_totals": _empty_totals(),
        "by_model": [],
        "by_feature": [],
    }

    if not path.exists():
        return summary

    by_model: dict[str, dict] = {}
    by_feature: dict[str, dict] = {}

    for record in _filtered_usage_records(path, summary, window):
        summary["record_count"] += 1
        if record.get("total_tokens") is None:
            summary["missing_usage_count"] += 1

        _add_tokens(summary["totals"], record)
        if record.get("success") is True:
            _add_tokens(summary["successful_totals"], record)
        if record.get("retry") or record.get("fallback"):
            _add_tokens(summary["retry_fallback_totals"], record)

        model = str(record.get("actual_model") or record.get("requested_model") or "unknown")
        feature = str(record.get("feature") or "unknown")
        stage = record.get("stage")

        model_bucket = by_model.setdefault(model, _group_bucket(model_key="model", value=model))
        _update_group_bucket(model_bucket, record)

        feature_bucket = by_feature.setdefault(feature, _feature_bucket(feature))
        _update_group_bucket(feature_bucket, record)
        stage_key = stage if stage not in ("", None) else None
        stage_bucket = feature_bucket["_stage_map"].setdefault(
            stage_key,
            _group_bucket(model_key="stage", value=stage_key),
        )
        _update_group_bucket(stage_bucket, record)

    summary["by_model"] = _sorted_group_list(by_model.values(), label_key="model")
    summary["by_feature"] = _sorted_feature_list(by_feature.values())
    return summary


def recent_requests(
    base_dir: Path | None = None,
    limit: int = 10,
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    last: str | None = None,
) -> dict:
    path = usage_log_path(base_dir)
    window = _resolve_time_window(from_ts=from_ts, to_ts=to_ts, last=last)
    out = {
        "source_path": str(path),
        "applied_window": window["applied_window"],
        "from_ts": _dt_to_iso(window["from_dt"]),
        "to_ts": _dt_to_iso(window["to_dt"]),
        "skipped_timestamp_count": 0,
        "requests": [],
    }
    if not path.exists() or limit <= 0:
        return out

    groups: dict[str, dict] = {}
    order_index = 0
    for record in _filtered_usage_records(path, out, window):
        request_id = record.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            request_id = f"legacy-{order_index + 1}"
        order_index += 1

        group = groups.get(request_id)
        if group is None:
            group = {
                "request_id": request_id,
                "ts": record.get("ts"),
                "feature": record.get("feature") or "unknown",
                "stage": record.get("stage"),
                "requested_model": record.get("requested_model"),
                "actual_models": [],
                "attempt_count": 0,
                "success": False,
                "retry_count": 0,
                "fallback_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "reasoning_tokens": 0,
                "total_tokens": 0,
                "last_finish_reason": None,
                "last_error_type": None,
                "last_error_message": None,
                "truncated": False,
                "_last_index": -1,
                "_sort_dt": None,
                "_actual_model_set": set(),
            }
            groups[request_id] = group

        actual_model = record.get("actual_model")
        if isinstance(actual_model, str) and actual_model and actual_model not in group["_actual_model_set"]:
            group["_actual_model_set"].add(actual_model)
            group["actual_models"].append(actual_model)

        group["attempt_count"] += 1
        if record.get("success") is True:
            group["success"] = True
        if record.get("retry"):
            group["retry_count"] += 1
        if record.get("fallback"):
            group["fallback_count"] += 1
        for key in _TOKEN_KEYS:
            group[key] += _coerce_token(record.get(key))

        group["ts"] = record.get("ts") or group["ts"]
        group["feature"] = record.get("feature") or group["feature"]
        group["stage"] = record.get("stage") if record.get("stage") not in ("", None) else group["stage"]
        group["requested_model"] = record.get("requested_model") or group["requested_model"]
        group["last_finish_reason"] = record.get("finish_reason")
        group["last_error_type"] = record.get("error_type")
        group["last_error_message"] = record.get("error_message")
        group["truncated"] = bool(record.get("truncated"))
        group["_last_index"] = order_index
        record_dt = _parse_record_ts(record.get("ts"))
        if record_dt is not None and (group["_sort_dt"] is None or record_dt >= group["_sort_dt"]):
            group["_sort_dt"] = record_dt

    requests = sorted(
        groups.values(),
        key=lambda item: (
            item["_sort_dt"] or datetime.min.replace(tzinfo=timezone.utc),
            item["_last_index"],
        ),
        reverse=True,
    )
    out["requests"] = [
        {k: v for k, v in item.items() if not k.startswith("_")}
        for item in requests[:limit]
    ]
    return out


def _resolve_time_window(
    *,
    from_ts: str | None = None,
    to_ts: str | None = None,
    last: str | None = None,
) -> dict:
    if last:
        normalized_last = str(last).strip().lower()
        delta = _WINDOW_DELTAS.get(normalized_last)
        if delta is None:
            raise ValueError(f"Invalid last window: {last!r}")
        to_dt = _now_dt()
        from_dt = to_dt - delta
        return {
            "applied_window": normalized_last,
            "from_dt": from_dt,
            "to_dt": to_dt,
        }

    from_dt = _parse_filter_ts(from_ts) if from_ts else None
    to_dt = _parse_filter_ts(to_ts) if to_ts else None
    if from_dt and to_dt and from_dt > to_dt:
        raise ValueError("from_ts must be <= to_ts")
    return {
        "applied_window": "custom" if from_dt or to_dt else "all",
        "from_dt": from_dt,
        "to_dt": to_dt,
    }


def _feature_bucket(feature: str) -> dict:
    bucket = _group_bucket(model_key="feature", value=feature)
    bucket["_stage_map"] = {}
    return bucket


def _group_bucket(*, model_key: str, value) -> dict:
    return {
        model_key: value,
        "attempt_count": 0,
        "success_count": 0,
        "retry_count": 0,
        "fallback_count": 0,
        **_empty_totals(),
    }


def _update_group_bucket(bucket: dict, record: dict) -> None:
    bucket["attempt_count"] += 1
    if record.get("success") is True:
        bucket["success_count"] += 1
    if record.get("retry"):
        bucket["retry_count"] += 1
    if record.get("fallback"):
        bucket["fallback_count"] += 1
    _add_tokens(bucket, record)


def _add_tokens(target: dict, record: dict) -> None:
    for key in _TOKEN_KEYS:
        target[key] += _coerce_token(record.get(key))


def _coerce_token(value) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _empty_totals() -> dict:
    return {key: 0 for key in _TOKEN_KEYS}


def _sorted_group_list(groups, *, label_key: str) -> list[dict]:
    return [
        {k: v for k, v in group.items() if not k.startswith("_")}
        for group in sorted(
            groups,
            key=lambda item: (-item["total_tokens"], str(item[label_key])),
        )
    ]


def _sorted_feature_list(groups) -> list[dict]:
    out = []
    for group in sorted(groups, key=lambda item: (-item["total_tokens"], str(item["feature"]))):
        public = {k: v for k, v in group.items() if not k.startswith("_")}
        public["by_stage"] = _sorted_group_list(group["_stage_map"].values(), label_key="stage")
        out.append(public)
    return out


def _filtered_usage_records(path: Path, counters: dict, window: dict):
    from_dt = window["from_dt"]
    to_dt = window["to_dt"]
    for record in _iter_usage_records(path, counters):
        if from_dt is None and to_dt is None:
            yield record
            continue
        record_dt = _parse_record_ts(record.get("ts"))
        if record_dt is None:
            counters["skipped_timestamp_count"] = counters.get("skipped_timestamp_count", 0) + 1
            continue
        if _record_in_time_window(record_dt, from_dt=from_dt, to_dt=to_dt):
            yield record


def _record_in_time_window(
    record_dt: datetime,
    *,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> bool:
    if from_dt is not None and record_dt < from_dt:
        return False
    if to_dt is not None and record_dt > to_dt:
        return False
    return True


def _parse_filter_ts(value: str) -> datetime:
    dt = _parse_record_ts(value)
    if dt is None:
        raise ValueError(f"Invalid timestamp: {value!r}")
    return dt


def _parse_record_ts(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _iter_usage_records(path: Path, summary: dict | None = None):
    with open(path, "rb") as f:
        for raw_line in f:
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                if summary is not None:
                    summary["malformed_record_count"] += 1
                continue
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                if summary is not None:
                    summary["malformed_record_count"] += 1
                continue
            if not isinstance(record, dict):
                if summary is not None:
                    summary["malformed_record_count"] += 1
                continue
            yield record


@contextmanager
def _locked_file(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as lockf:
        _acquire_lock(lockf)
        try:
            yield
        finally:
            _release_lock(lockf)


def _acquire_lock(f) -> None:
    if fcntl is not None:  # pragma: no branch
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        return
    if msvcrt is not None:  # pragma: no cover - exercised on Windows
        f.seek(0)
        if not f.read(1):
            f.write(b"0")
            f.flush()
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        return


def _release_lock(f) -> None:
    if fcntl is not None:  # pragma: no branch
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return
    if msvcrt is not None:  # pragma: no cover - exercised on Windows
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def _now_iso() -> str:
    return _now_dt().isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)