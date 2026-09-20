import logging
import os
import signal
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from sqlalchemy import or_

from api.database import ScheduleRunLog, SessionLocal, app_now
from api.logging_config import configure_logging
from api.scheduled_runner import run_scheduled_pipeline_log
from src.config import SCHEDULER_RUN_WORKERS, SCHEDULE_WORKER_POLL_SECONDS

logger = logging.getLogger(__name__)
CLAIM_STALE_MINUTES = 10


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _recover_stale_claims():
    db = SessionLocal()
    try:
        cutoff = app_now() - timedelta(minutes=CLAIM_STALE_MINUTES)
        count = (
            db.query(ScheduleRunLog)
            .filter(ScheduleRunLog.status == "claimed")
            .filter(ScheduleRunLog.claimed_at < cutoff)
            .update(
                {
                    ScheduleRunLog.status: "queued",
                    ScheduleRunLog.claimed_at: None,
                    ScheduleRunLog.worker_id: None,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        if count:
            logger.warning("Recovered stale claimed runs count=%s", count)
    finally:
        db.close()


def _claim_one(worker_id: str) -> int | None:
    db = SessionLocal()
    try:
        candidate = (
            db.query(ScheduleRunLog.id)
            .filter(ScheduleRunLog.status.in_(("queued", "retry_wait")))
            .filter(
                or_(
                    ScheduleRunLog.next_attempt_at.is_(None),
                    ScheduleRunLog.next_attempt_at <= app_now(),
                )
            )
            .order_by(ScheduleRunLog.queued_at.asc(), ScheduleRunLog.id.asc())
            .first()
        )
        if not candidate:
            return None
        claimed_at = app_now()
        updated = (
            db.query(ScheduleRunLog)
            .filter(ScheduleRunLog.id == candidate.id)
            .filter(ScheduleRunLog.status.in_(("queued", "retry_wait")))
            .update(
                {
                    ScheduleRunLog.status: "claimed",
                    ScheduleRunLog.claimed_at: claimed_at,
                    ScheduleRunLog.worker_id: worker_id,
                    ScheduleRunLog.attempt_count: ScheduleRunLog.attempt_count + 1,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return candidate.id if updated == 1 else None
    finally:
        db.close()


def main():
    configure_logging()
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    worker_id = _worker_id()
    _recover_stale_claims()
    logger.info("ETL worker started worker_id=%s concurrency=%s", worker_id, SCHEDULER_RUN_WORKERS)

    with ThreadPoolExecutor(max_workers=SCHEDULER_RUN_WORKERS) as pool:
        active = set()
        while not stopped.is_set():
            active = {future for future in active if not future.done()}
            while len(active) < SCHEDULER_RUN_WORKERS:
                log_id = _claim_one(worker_id)
                if not log_id:
                    break
                active.add(pool.submit(run_scheduled_pipeline_log, log_id))
            stopped.wait(SCHEDULE_WORKER_POLL_SECONDS)


if __name__ == "__main__":
    main()
