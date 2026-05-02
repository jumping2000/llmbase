"""Background worker — autonomous learning, compilation, and maintenance.

Runs alongside the web server. Periodically:
1. Ingests new content from configured sources
2. Compiles unprocessed raw documents into wiki
3. Rebuilds index
4. Runs health checks

Configure via config.yaml ``worker:`` section.

Customization contract
======================
Downstream projects can register custom learn sources and background jobs
without forking this module:

  LEARN_SOURCES   – dict of source_name → callable(batch_size, base_dir)
  CUSTOM_JOBS     – list of {"id", "interval_hours", "handler"} dicts

Example::

    import llmwiki.worker as w

    def my_corpus_learn(batch_size, base_dir):
        ...  # ingest from custom source
        return ["ingested-1", "ingested-2"]

    w.register_learn_source("my_corpus", my_corpus_learn)
    w.register_job("my_sync", interval_hours=2, handler=my_sync_fn)
"""

import logging
import time
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config, ensure_dirs

logger = logging.getLogger("llmbase.worker")

# Global job lock — prevents concurrent auto_fix, compile, worker tasks
# from stepping on each other's file operations
job_lock = threading.Lock()
_worker_started = False
_worker_start_lock = threading.Lock()

# ─── Pluggable learn sources ─────────────────────────────────────
# Built-in sources are registered at module load time below.
# Downstream calls register_learn_source() to add custom ones.
LEARN_SOURCES: dict[str, callable] = {}


def register_learn_source(name: str, handler) -> None:
    """Register a learn source handler.

    handler is called as ``handler(batch_size=N, base_dir=path)``.
    It MUST accept these two keyword arguments (use **kwargs to be
    forward-compatible if your handler has extra params)::

        def my_learn(batch_size, base_dir, **kwargs):
            ...
            return ["ingested-1"]

    Extra keyword arguments may be passed in future versions.
    """
    LEARN_SOURCES[name] = handler


# ─── Custom background jobs ──────────────────────────────────────
CUSTOM_JOBS: list[dict] = []


def register_job(job_id: str, interval_hours: float, handler) -> None:
    """Register a custom background job.

    handler signature: (base_dir: Path) -> None
    """
    CUSTOM_JOBS.append({
        "id": job_id,
        "interval_hours": interval_hours,
        "handler": handler,
    })


def run_worker(base_dir: Path | None = None):
    """Main worker loop — runs forever, executing scheduled tasks."""
    base = Path(base_dir) if base_dir else Path.cwd()
    cfg = load_config(base)
    ensure_dirs(cfg)

    worker_cfg = cfg.get("worker", {})
    if not worker_cfg.get("enabled", False):
        logger.info("Worker disabled in config. Set worker.enabled: true to activate.")
        return

    learn_interval = worker_cfg.get("learn_interval_hours", 6) * 3600
    compile_interval = worker_cfg.get("compile_interval_hours", 1) * 3600
    learn_batch = worker_cfg.get("learn_batch_size", 10)
    learn_source = worker_cfg.get("learn_source", "url")

    taxonomy_interval = worker_cfg.get("taxonomy_interval_hours", 12) * 3600
    health_interval = worker_cfg.get("health_check_interval_hours", 24) * 3600

    logger.info(
        f"Worker started: learn every {learn_interval/3600:.0f}h, "
        f"compile every {compile_interval/3600:.0f}h, "
        f"health every {health_interval/3600:.0f}h"
    )

    last_learn = 0
    last_compile = 0
    last_taxonomy = 0
    last_health = 0
    custom_job_times = {}

    while True:
        now = time.time()

        # Learn from sources
        if now - last_learn >= learn_interval and job_lock.acquire(blocking=False):
            try:
                _task_learn(base, learn_source, learn_batch)
            finally:
                job_lock.release()
            last_learn = now

        # Compile new documents
        if now - last_compile >= compile_interval and job_lock.acquire(blocking=False):
            try:
                _task_compile(base)
            finally:
                job_lock.release()
            last_compile = now

        # Regenerate taxonomy periodically
        if now - last_taxonomy >= taxonomy_interval and job_lock.acquire(blocking=False):
            try:
                _task_taxonomy(base)
            finally:
                job_lock.release()
            last_taxonomy = now

        # Health checks and auto-repair
        if now - last_health >= health_interval and job_lock.acquire(blocking=False):
            try:
                _task_health_check(base)
            finally:
                job_lock.release()
            last_health = now

        # Custom jobs registered via register_job()
        for job in CUSTOM_JOBS:
            job_id = job["id"]
            try:
                interval = float(job["interval_hours"]) * 3600
            except (TypeError, ValueError):
                continue
            if interval <= 0:
                continue
            last_key = f"_last_{job_id}"
            last_run = custom_job_times.get(last_key, 0)
            if now - last_run >= interval and job_lock.acquire(blocking=False):
                try:
                    logger.info(f"[custom:{job_id}] Running...")
                    job["handler"](base)
                    logger.info(f"[custom:{job_id}] Done")
                except Exception as e:
                    logger.error(f"[custom:{job_id}] Error: {e}")
                finally:
                    job_lock.release()
                custom_job_times[last_key] = now

        time.sleep(60)  # Check every minute


def _task_learn(base: Path, source: str, batch_size: int):
    """Ingest a batch from the configured source via LEARN_SOURCES registry."""
    logger.info(f"[learn] Starting batch of {batch_size} from {source}")
    try:
        if source in LEARN_SOURCES:
            handler = LEARN_SOURCES[source]
            results = handler(batch_size=batch_size, base_dir=base)
            logger.info(f"[learn] {source}: ingested {len(results)} new works")
        else:
            logger.warning(f"[learn] Unknown source: {source} (registered: {list(LEARN_SOURCES.keys())})")
    except Exception as e:
        logger.error(f"[learn] Error: {e}")


def _task_compile(base: Path):
    """Compile any unprocessed raw documents."""
    logger.info("[compile] Checking for uncompiled documents...")
    try:
        from .compile import compile_new, rebuild_index
        articles = compile_new(base, batch_size=5)
        if articles:
            logger.info(f"[compile] Created {len(articles)} new articles")
            rebuild_index(base)
            logger.info("[compile] Index rebuilt")
        else:
            logger.debug("[compile] Nothing to compile")
    except Exception as e:
        logger.error(f"[compile] Error: {e}")


def _task_taxonomy(base: Path):
    """Regenerate taxonomy from current articles (unless locked)."""
    from .taxonomy import load_taxonomy, generate_taxonomy

    # Respect locked taxonomy — don't overwrite manually curated categories
    existing = load_taxonomy(base)
    if existing.get("locked"):
        logger.info("[taxonomy] Taxonomy is locked, skipping regeneration")
        return

    logger.info("[taxonomy] Regenerating category taxonomy...")
    try:
        taxonomy = generate_taxonomy(base)
        cats = len(taxonomy.get("categories", []))
        logger.info(f"[taxonomy] Generated {cats} categories")
    except Exception as e:
        logger.error(f"[taxonomy] Error: {e}")

    # Regenerate Xi Ci for supported languages
    logger.info("[xici] Regenerating guided introductions...")
    try:
        from .xici import generate_xici
        for lang in ("en", "it", "en-it"):
            generate_xici(base, lang)
        logger.info("[xici] Generated Xi Ci for all languages")
    except Exception as e:
        logger.error(f"[xici] Error: {e}")

    # Extract entities (if enabled)
    try:
        from .config import load_config as _load_cfg
        _cfg = _load_cfg(base)
        if _cfg.get("entities", {}).get("enabled", False):
            from .entities import extract_entities
            logger.info("[entities] Extracting entities...")
            result = extract_entities(base)
            logger.info(f"[entities] {len(result.get('people', []))} people, "
                        f"{len(result.get('events', []))} events, "
                        f"{len(result.get('places', []))} places")
    except Exception as e:
        logger.error(f"[entities] Error: {e}")


def _task_health_check(base: Path):
    """Run lint checks and auto-fix broken links."""
    logger.info("[health] Running health checks...")
    try:
        from .lint import lint, auto_fix
        import json

        # Run checks
        results = lint(base)
        total = results.get("total_issues", 0)
        logger.info(f"[health] Found {total} issues")

        # Auto-fix
        fixes = []
        if total > 0:
            fixes = auto_fix(base)
            logger.info(f"[health] Applied {len(fixes)} fixes")

        # Persist health report
        _save_health_report(base, results, fixes)

    except Exception as e:
        logger.error(f"[health] Error: {e}")


def _save_health_report(base: Path, results: dict, fixes: list[str]):
    """Save health check results to wiki/_meta/health.json."""
    import json

    cfg = load_config(base)
    meta_dir = Path(cfg["paths"]["meta"])
    meta_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "fixes_applied": fixes,
    }
    health_path = meta_dir / "health.json"
    health_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[health] Report saved to {health_path}")


def _run_worker_guarded(base_dir: Path | None):
    """Run the worker loop with a top-level crash guard.

    Without this, an unhandled exception kills the daemon thread silently
    and all background work stops with no log trail. Logging the traceback
    at error level makes the failure visible in container logs.
    """
    try:
        run_worker(base_dir)
    except Exception:
        logger.error(
            "[worker] Daemon thread crashed:\n%s",
            traceback.format_exc(),
        )
        raise


def start_worker_thread(base_dir: Path | None = None):
    """Start worker as a background daemon thread (only once per process).

    Guards against multi-thread re-entry via ``_worker_started``.
    For cross-process dedup (e.g. gunicorn ``--workers > 1``), downstream
    deployments can add their own locking before calling this function.
    """
    global _worker_started
    with _worker_start_lock:
        if _worker_started:
            logger.debug("Worker already started in this process, skipping")
            return None
        _worker_started = True

    t = threading.Thread(target=_run_worker_guarded, args=(base_dir,), daemon=True)
    t.start()
    return t


# ─── Built-in learn sources ─────────────────────────────────────
from . import worker_sources as _worker_sources

register_learn_source("seed_urls", _worker_sources.learn_from_seed_urls)
