import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def test_default_config_uses_seed_urls(tmp_path):
    from llmwiki.config import load_config

    cfg = load_config(tmp_path)
    assert cfg["worker"]["learn_source"] == "seed_urls"


def test_seed_urls_source_is_registered():
    from llmwiki.worker import LEARN_SOURCES

    assert "seed_urls" in LEARN_SOURCES


def test_seed_urls_ingests_pending_urls_and_persists_state(tmp_kb, monkeypatch):
    from llmwiki import worker_sources

    meta_dir = Path(tmp_kb) / "wiki" / "_meta"
    seed_path = meta_dir / worker_sources.SEED_FILE_NAME
    seed_path.write_text(
        json.dumps({
            "urls": [
                "https://example.com/a",
                "https://example.com/b",
                "https://example.com/c",
            ]
        }),
        encoding="utf-8",
    )

    calls = []

    def fake_ingest(url, base_dir):
        calls.append(url)
        slug = url.rsplit("/", 1)[-1]
        return Path(base_dir) / "raw" / slug / "index.md"

    monkeypatch.setattr(worker_sources, "_ingest_seed_url", fake_ingest)

    first = worker_sources.learn_from_seed_urls(batch_size=2, base_dir=tmp_kb)
    second = worker_sources.learn_from_seed_urls(batch_size=10, base_dir=tmp_kb)

    assert first == [
        str(Path(tmp_kb) / "raw" / "a" / "index.md"),
        str(Path(tmp_kb) / "raw" / "b" / "index.md"),
    ]
    assert second == [str(Path(tmp_kb) / "raw" / "c" / "index.md")]
    assert calls == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]

    state_path = meta_dir / worker_sources.STATE_FILE_NAME
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert sorted(state["done"].keys()) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
    assert state["failed"] == {}


def test_seed_urls_backoff_skips_recent_failures_and_retries_elapsed(tmp_kb, monkeypatch):
    from llmwiki import worker_sources

    meta_dir = Path(tmp_kb) / "wiki" / "_meta"
    seed_path = meta_dir / worker_sources.SEED_FILE_NAME
    seed_path.write_text(json.dumps(["https://example.com/retry-me"]), encoding="utf-8")

    attempts = []

    def always_fail(url, base_dir):
        attempts.append(url)
        raise RuntimeError("temporary failure")

    monkeypatch.setattr(worker_sources, "_ingest_seed_url", always_fail)

    assert worker_sources.learn_from_seed_urls(batch_size=1, base_dir=tmp_kb) == []
    assert attempts == ["https://example.com/retry-me"]

    assert worker_sources.learn_from_seed_urls(batch_size=1, base_dir=tmp_kb) == []
    assert attempts == ["https://example.com/retry-me"]

    state_path = meta_dir / worker_sources.STATE_FILE_NAME
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["failed"]["https://example.com/retry-me"]["last_attempt_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=2)
    ).isoformat()
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def succeed(url, base_dir):
        attempts.append(url)
        return Path(base_dir) / "raw" / "retry-me" / "index.md"

    monkeypatch.setattr(worker_sources, "_ingest_seed_url", succeed)

    retried = worker_sources.learn_from_seed_urls(batch_size=1, base_dir=tmp_kb)

    assert retried == [str(Path(tmp_kb) / "raw" / "retry-me" / "index.md")]
    assert attempts == [
        "https://example.com/retry-me",
        "https://example.com/retry-me",
    ]

    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert final_state["failed"] == {}
    assert "https://example.com/retry-me" in final_state["done"]