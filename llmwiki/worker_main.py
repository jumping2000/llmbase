"""Dedicated worker entry point for containerized/background execution."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .config import load_config
from .worker import run_worker


def main(*, poll_interval_seconds: int = 60) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    base = Path(__file__).resolve().parent.parent
    logger = logging.getLogger("llmbase.worker")

    while True:
        cfg = load_config(base)
        if cfg.get("worker", {}).get("enabled", False):
            run_worker(base)
            return

        logger.info(
            "Worker container idle. Set worker.enabled: true in config.yaml to start background jobs."
        )
        time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    main()