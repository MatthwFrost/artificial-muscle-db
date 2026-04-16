"""Entry point. For v0 this is a placeholder loop; production will pull jobs from Redis
(via RQ) and dispatch them to the extractor."""

from __future__ import annotations

import time

import structlog

from .config import CONFIG

log = structlog.get_logger()


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
    log.info("worker_starting", version="0.1.0", spark_model=CONFIG.spark_model)

    # TODO: connect to Redis, pull jobs from 'muscle.extract' queue, dispatch.
    # For v0, just idle so the container stays alive for `docker compose logs -f worker`.
    while True:
        log.info("worker_idle")
        time.sleep(60)


if __name__ == "__main__":
    main()
