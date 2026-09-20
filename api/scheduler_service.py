import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor as FuturesThreadPoolExecutor
from zoneinfo import ZoneInfo

from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.exc import IntegrityError

from api.database import PipelineSchedule, ScheduleRunLog, SessionLocal, app_now
from api.scheduled_runner import run_scheduled_pipeline_log
from src.config import (
    APP_TIMEZONE,
    SCHEDULE_JOB_MAX_INSTANCES,
    SCHEDULE_MISFIRE_GRACE_SECONDS,
    SCHEDULE_STALE_RUNNING_MINUTES,
    SCHEDULE_RUN_MAX_ATTEMPTS,
    SCHEDULER_RUN_WORKERS,
    SCHEDULER_TRIGGER_WORKERS,
)

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
_worker_pool: FuturesThreadPoolExecutor | None = None


def start_scheduler(run_workers: bool = True):
    global _scheduler, _worker_pool
    if _scheduler and _scheduler.running:
        return

    _worker_pool = (
        FuturesThreadPoolExecutor(max_workers=SCHEDULER_RUN_WORKERS)
        if run_workers
        else None
    )
    _scheduler = BackgroundScheduler(
        timezone=ZoneInfo(APP_TIMEZONE),
        executors={"default": ThreadPoolExecutor(max_workers=SCHEDULER_TRIGGER_WORKERS)},
    )
    _scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    _scheduler.start()
    recover_stale_running_logs()
    if run_workers:
        enqueue_existing_queued_runs()
    register_all_active_schedules()
    logger.info(
        "APScheduler started with trigger_workers=%s embedded_run_workers=%s",
        SCHEDULER_TRIGGER_WORKERS,
        SCHEDULER_RUN_WORKERS if run_workers else 0,
    )


def shutdown_scheduler():
    global _scheduler, _worker_pool
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
    if _worker_pool:
        _worker_pool.shutdown(wait=False, cancel_futures=False)
    _worker_pool = None


def register_all_active_schedules():
    db = SessionLocal()
    try:
        for schedule in db.query(PipelineSchedule).filter(PipelineSchedule.status == "active").all():
            _register_schedule_obj(schedule)
        db.commit()
        logger.info("Registered active schedules")
    finally:
        db.close()


def register_schedule(schedule_id: int):
    db = SessionLocal()
    try:
        schedule = db.query(PipelineSchedule).filter(PipelineSchedule.id == schedule_id).first()
        if not schedule:
            return
        _register_schedule_obj(schedule)
        db.commit()
        logger.info("Registered schedule id=%s", schedule.id)
    finally:
        db.close()


def enqueue_existing_queued_runs():
    db = SessionLocal()
    try:
        queued = (
            db.query(ScheduleRunLog)
            .filter(ScheduleRunLog.status == "queued")
            .order_by(ScheduleRunLog.queued_at.asc(), ScheduleRunLog.id.asc())
            .all()
        )
        for log in queued:
            _submit_run_log(log.id)
        logger.info("Submitted existing queued schedule runs count=%s", len(queued))
    finally:
        db.close()


def recover_stale_running_logs():
    if SCHEDULE_STALE_RUNNING_MINUTES <= 0:
        return
    db = SessionLocal()
    try:
        now = app_now()
        cutoff = now - timedelta(minutes=SCHEDULE_STALE_RUNNING_MINUTES)
        stale_logs = (
            db.query(ScheduleRunLog)
            .filter(ScheduleRunLog.status == "running")
            .filter(ScheduleRunLog.finished_at.is_(None))
            .filter(ScheduleRunLog.started_at < cutoff)
            .all()
        )
        for log in stale_logs:
            log.status = "failed"
            log.finished_at = now
            log.error_message = (
                "Run was marked failed because the backend stopped before it completed."
            )
            if log.schedule:
                log.schedule.last_run_at = now
                log.schedule.last_status = "failed"
                log.schedule.last_error = log.error_message
                log.schedule.updated_at = now
        db.commit()
        logger.info("Recovered stale running schedule logs count=%s", len(stale_logs))
    finally:
        db.close()


def enqueue_schedule_run(schedule_id: int, scheduled_for: str | None = None):
    db = SessionLocal()
    try:
        schedule = db.query(PipelineSchedule).filter(PipelineSchedule.id == schedule_id).first()
        if not schedule or schedule.status != "active":
            logger.info("Skipping enqueue for inactive/missing schedule id=%s", schedule_id)
            return
        queued_at = app_now()
        scheduled_at = _scheduled_slot(schedule, queued_at, scheduled_for)
        existing = (
            db.query(ScheduleRunLog)
            .filter(ScheduleRunLog.schedule_id == schedule.id)
            .filter(ScheduleRunLog.scheduled_for == scheduled_at)
            .first()
        )
        if existing:
            logger.info(
                "Schedule run already queued schedule_id=%s scheduled_for=%s log_id=%s",
                schedule.id,
                scheduled_at,
                existing.id,
            )
            return
        log = ScheduleRunLog(
            schedule_id=schedule.id,
            pipeline_id=schedule.pipeline_id,
            status="queued",
            scheduled_for=scheduled_at,
            queued_at=queued_at,
            attempt_count=0,
            max_attempts=SCHEDULE_RUN_MAX_ATTEMPTS,
            rows_written=0,
        )
        db.add(log)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.info(
                "Duplicate schedule run ignored schedule_id=%s scheduled_for=%s",
                schedule.id,
                scheduled_at,
            )
            return
        db.refresh(log)
        logger.info("Queued schedule run log_id=%s schedule_id=%s", log.id, schedule.id)
        _submit_run_log(log.id)
    finally:
        db.close()


def _scheduled_slot(
    schedule: PipelineSchedule,
    queued_at: datetime,
    scheduled_for: str | None,
) -> datetime:
    if scheduled_for:
        return datetime.fromisoformat(scheduled_for)
    if schedule.next_run_at:
        return schedule.next_run_at
    return queued_at.replace(second=0, microsecond=0)


def _submit_run_log(log_id: int):
    if not _worker_pool:
        logger.warning("Schedule run worker pool is not available; log_id=%s remains queued", log_id)
        return
    _worker_pool.submit(run_scheduled_pipeline_log, log_id)


def pause_schedule_job(schedule: PipelineSchedule):
    if _scheduler:
        try:
            _scheduler.pause_job(schedule.apscheduler_job_id)
        except Exception:
            logger.exception("Failed to pause scheduler job id=%s", schedule.apscheduler_job_id)
    schedule.status = "paused"
    schedule.next_run_at = None
    schedule.updated_at = app_now()


def resume_schedule_job(schedule: PipelineSchedule):
    schedule.status = "active"
    schedule.updated_at = app_now()
    _register_schedule_obj(schedule)


def delete_schedule_job(schedule: PipelineSchedule):
    if _scheduler:
        try:
            _scheduler.remove_job(schedule.apscheduler_job_id)
        except Exception:
            logger.exception("Failed to delete scheduler job id=%s", schedule.apscheduler_job_id)


def _register_schedule_obj(schedule: PipelineSchedule):
    if not _scheduler:
        return
    tz = ZoneInfo(schedule.timezone)
    if schedule.trigger_type == "date":
        run_date = datetime.fromisoformat(schedule.day_of_week).replace(
            hour=schedule.hour,
            minute=schedule.minute,
            second=0,
            microsecond=0,
            tzinfo=tz,
        )
        if run_date <= datetime.now(tz):
            schedule.status = "completed"
            schedule.next_run_at = None
            schedule.updated_at = app_now()
            logger.info("One-time schedule id=%s is in the past and was marked completed", schedule.id)
            return
        trigger = DateTrigger(run_date=run_date, timezone=tz)
    else:
        trigger = CronTrigger(
            day_of_week=schedule.day_of_week,
            hour=schedule.hour,
            minute=schedule.minute,
            timezone=tz,
        )
    job = _scheduler.add_job(
        enqueue_schedule_run,
        trigger=trigger,
        args=[schedule.id],
        id=schedule.apscheduler_job_id,
        replace_existing=True,
        max_instances=SCHEDULE_JOB_MAX_INSTANCES,
        coalesce=False,
        misfire_grace_time=SCHEDULE_MISFIRE_GRACE_SECONDS,
    )
    schedule.next_run_at = job.next_run_time
    logger.info(
        "Schedule job registered id=%s trigger=%s next_run_at=%s",
        schedule.id,
        schedule.trigger_type,
        schedule.next_run_at,
    )


def _job_listener(event):
    db = SessionLocal()
    try:
        schedule = (
            db.query(PipelineSchedule)
            .filter(PipelineSchedule.apscheduler_job_id == event.job_id)
            .first()
        )
        if not schedule:
            return
        job = _scheduler.get_job(event.job_id) if _scheduler else None
        next_run_at = job.next_run_time if job else None
        schedule.next_run_at = next_run_at
        if (
            schedule.trigger_type == "date"
            and not event.exception
            and next_run_at is None
        ):
            schedule.status = "completed"
        schedule.updated_at = app_now()
        db.commit()
        if event.exception:
            logger.error("Scheduled job failed job_id=%s", event.job_id)
        else:
            logger.info("Scheduled job completed job_id=%s", event.job_id)
    finally:
        db.close()
