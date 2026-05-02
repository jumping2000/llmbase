"""Built-in worker learn sources.

The default built-in source reads a seed URL list from ``wiki/_meta`` and
persists completion/failure state alongside other worker metadata.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .atomic import atomic_write_json
from .config import load_config

SEED_FILE_NAME = "seed-urls.json"
STATE_FILE_NAME = "worker-seeds-state.json"
BASE_BACKOFF_MINUTES = 30
MAX_BACKOFF_HOURS = 24


def _meta_dir(base_dir: Path | None) -> Path:
    cfg = load_config(base_dir)
    meta_dir = Path(cfg["paths"]["meta"])
    meta_dir.mkdir(parents=True, exist_ok=True)
    return meta_dir


def _seed_file_path(base_dir: Path | None) -> Path:
    return _meta_dir(base_dir) / SEED_FILE_NAME


def _state_file_path(base_dir: Path | None) -> Path:
    return _meta_dir(base_dir) / STATE_FILE_NAME


def _load_seed_urls(base_dir: Path | None) -> list[str]:
    path = _seed_file_path(base_dir)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []

    if isinstance(payload, dict):
        payload = payload.get("urls", [])
    if not isinstance(payload, list):
        return []

    seen = set()
    urls = []
    for item in payload:
        url = str(item).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _load_state(base_dir: Path | None) -> dict:
    path = _state_file_path(base_dir)
    if not path.exists():
        return {"done": {}, "failed": {}}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"done": {}, "failed": {}}

    if not isinstance(payload, dict):
        return {"done": {}, "failed": {}}

    payload.setdefault("done", {})
    payload.setdefault("failed", {})
    return payload


def _save_state(base_dir: Path | None, state: dict) -> None:
    atomic_write_json(_state_file_path(base_dir), state, ensure_ascii=False)


def _parse_datetime(raw: str | None):
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _can_retry(meta: dict, *, now: datetime | None = None) -> bool:
    attempts = int(meta.get("attempts", 0))
    last_attempt = _parse_datetime(meta.get("last_attempt_at"))
    if last_attempt is None:
        return True

    current = now or datetime.now(timezone.utc)
    delay_minutes = BASE_BACKOFF_MINUTES * max(1, 2 ** max(0, attempts - 1))
    delay_minutes = min(delay_minutes, MAX_BACKOFF_HOURS * 60)
    retry_after = last_attempt + timedelta(minutes=delay_minutes)
    return current >= retry_after


def _pick_seed_urls(
    seed_urls: list[str],
    done: dict,
    failed: dict,
    batch_size: int,
    *,
    now: datetime | None = None,
) -> list[str]:
    if batch_size <= 0:
        return []

    picked = []
    current = now or datetime.now(timezone.utc)
    for url in seed_urls:
        if url in done:
            continue
        if url in failed and not _can_retry(failed[url], now=current):
            continue
        picked.append(url)
        if len(picked) >= batch_size:
            break
    return picked


def _ingest_seed_url(url: str, base_dir: Path | None):
    from .ingest import ingest_url

    return ingest_url(url, base_dir)


def learn_from_seed_urls(batch_size, base_dir, **kwargs):
    """Ingest unseen seed URLs from ``wiki/_meta/seed-urls.json``."""
    base = Path(base_dir) if base_dir else Path.cwd()
    state = _load_state(base)
    done = state.setdefault("done", {})
    failed = state.setdefault("failed", {})

    current = datetime.now(timezone.utc)
    current_iso = current.isoformat()
    seed_urls = _load_seed_urls(base)
    picked = _pick_seed_urls(seed_urls, done, failed, int(batch_size), now=current)

    results = []
    for url in picked:
        try:
            path = _ingest_seed_url(url, base)
            done[url] = {
                "ingested_at": current_iso,
                "path": str(path),
            }
            failed.pop(url, None)
            results.append(str(path))
        except Exception as exc:
            previous = failed.get(url, {})
            failed[url] = {
                "attempts": int(previous.get("attempts", 0)) + 1,
                "last_attempt_at": current_iso,
                "last_error": str(exc),
            }

    _save_state(base, state)
    return results