import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apscheduler.triggers.cron import CronTrigger

from api.connection_checker import check_database_connection
from api.database import (
    ExtractCheckpoint,
    ConnectionProfile,
    PipelineSchedule,
    PipelineVersion,
    SavedPipeline,
    ScheduleRunLog,
    User,
    app_now,
    get_current_user,
    get_db,
    is_admin,
)
from api.models import CreateSchedulesRequest, DBConnectionRequest
from api.pipeline_storage import slug_name
from api.scheduler_service import (
    delete_schedule_job,
    pause_schedule_job,
    register_schedule,
    resume_schedule_job,
)
from src.config import APP_TIMEZONE

router = APIRouter()
logger = logging.getLogger(__name__)
DEFAULT_TIMEZONE = APP_TIMEZONE


@router.post("/api/db/check-connection")
def check_db_connection(
    payload: DBConnectionRequest,
    user: User = Depends(get_current_user),
):
    try:
        return check_database_connection(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/pipelines/{pipeline_name}/schedules")
def list_pipeline_schedules(
    pipeline_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pipeline = _get_pipeline_or_404(db, pipeline_name)
    query = db.query(PipelineSchedule).filter(PipelineSchedule.pipeline_id == pipeline.id)
    if not is_admin(user):
        query = query.filter(PipelineSchedule.created_by_user_id == user.id)
    schedules = query.order_by(PipelineSchedule.created_at.desc()).all()
    return [_schedule_to_dict(item, include_pipeline=True) for item in schedules]


@router.post("/api/pipelines/{pipeline_name}/schedules")
def create_pipeline_schedules(
    pipeline_name: str,
    payload: CreateSchedulesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pipeline = _get_pipeline_or_404(db, pipeline_name)
    _require_saved_credentials(db, pipeline, user)
    pinned_version = (
        db.query(PipelineVersion)
        .filter(PipelineVersion.pipeline_id == pipeline.id)
        .order_by(PipelineVersion.version_number.desc())
        .first()
    )

    created = []
    now = app_now()
    for rule in payload.rules:
        schedule = PipelineSchedule(
            pipeline_id=pipeline.id,
            pipeline_version_id=pinned_version.id if pinned_version else None,
            created_by_user_id=user.id,
            name="pending",
            status="active",
            trigger_type=rule.trigger_type,
            day_of_week=_normalize_schedule_value(rule.trigger_type, rule.day_of_week),
            hour=rule.hour,
            minute=rule.minute,
            timezone=rule.timezone or DEFAULT_TIMEZONE,
            apscheduler_job_id="pending",
            created_at=now,
            updated_at=now,
        )
        db.add(schedule)
        db.flush()
        schedule.name = f"pipeline_{schedule.id}"
        schedule.apscheduler_job_id = f"pipeline_schedule_{schedule.id}"
        created.append(schedule)
    db.commit()

    for schedule in created:
        register_schedule(schedule.id)

    for schedule in created:
        db.refresh(schedule)
    logger.info(
        "Schedules created pipeline_id=%s user_id=%s count=%s",
        pipeline.id,
        user.id,
        len(created),
    )
    return [_schedule_to_dict(item, include_pipeline=True) for item in created]


@router.get("/api/schedules")
def list_schedules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(PipelineSchedule)
    if not is_admin(user):
        query = query.filter(PipelineSchedule.created_by_user_id == user.id)
    schedules = query.order_by(PipelineSchedule.created_at.desc()).all()
    return [_schedule_to_dict(item, include_pipeline=True) for item in schedules]


@router.get("/api/pipelines/{pipeline_name}/schedules/upcoming")
def list_pipeline_upcoming_schedules(
    pipeline_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pipeline = _get_pipeline_or_404(db, pipeline_name)
    query = (
        db.query(PipelineSchedule)
        .filter(PipelineSchedule.pipeline_id == pipeline.id)
        .filter(PipelineSchedule.status == "active")
    )
    if not is_admin(user):
        query = query.filter(PipelineSchedule.created_by_user_id == user.id)
    schedules = query.all()
    return _upcoming_schedule_events(schedules, limit=5)


@router.post("/api/schedules/{schedule_id}/pause")
def pause_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = _get_schedule_allowed(db, schedule_id, user)
    pause_schedule_job(schedule)
    db.commit()
    db.refresh(schedule)
    logger.info("Schedule paused schedule_id=%s user_id=%s", schedule.id, user.id)
    return _schedule_to_dict(schedule, include_pipeline=True)


@router.post("/api/schedules/{schedule_id}/start")
def start_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = _get_schedule_allowed(db, schedule_id, user)
    resume_schedule_job(schedule)
    db.commit()
    db.refresh(schedule)
    logger.info("Schedule started schedule_id=%s user_id=%s", schedule.id, user.id)
    return _schedule_to_dict(schedule, include_pipeline=True)


@router.delete("/api/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Only admins can delete schedules")
    schedule = db.query(PipelineSchedule).filter(PipelineSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    delete_schedule_job(schedule)
    db.query(ExtractCheckpoint).filter(ExtractCheckpoint.schedule_id == schedule_id).delete(synchronize_session=False)
    db.delete(schedule)
    db.commit()
    logger.info("Schedule deleted schedule_id=%s user_id=%s", schedule_id, user.id)
    return {"deleted": schedule_id}


@router.get("/api/schedules/upcoming")
def list_upcoming_schedules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        db.query(PipelineSchedule)
        .filter(PipelineSchedule.status == "active")
    )
    if not is_admin(user):
        query = query.filter(PipelineSchedule.created_by_user_id == user.id)
    schedules = query.all()
    return _upcoming_schedule_events(schedules, limit=5)


@router.get("/api/schedules/{schedule_id}/logs")
def get_schedule_logs(
    schedule_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    schedule = _get_schedule_allowed(db, schedule_id, user)
    logs = (
        db.query(ScheduleRunLog)
        .filter(ScheduleRunLog.schedule_id == schedule.id)
        .order_by(
            ScheduleRunLog.created_at.desc(),
            ScheduleRunLog.queued_at.desc(),
            ScheduleRunLog.started_at.desc(),
        )
        .limit(50)
        .all()
    )
    return [_log_to_dict(log) for log in logs]


def _get_pipeline_or_404(db: Session, name: str) -> SavedPipeline:
    pipeline = db.query(SavedPipeline).filter(SavedPipeline.slug == slug_name(name)).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Saved pipeline not found: {name}")
    return pipeline


def _require_saved_credentials(db: Session, pipeline: SavedPipeline, user: User):
    import json

    try:
        credential = json.loads(pipeline.pipeline_json).get("credential") or {}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Saved pipeline JSON is invalid: {exc}") from exc
    legacy_required = ["host", "database", "username", "encrypted_password"]
    has_saved_connection = bool(credential.get("connection_id"))
    has_legacy_credentials = all(credential.get(key) for key in legacy_required)
    if not has_saved_connection and not has_legacy_credentials:
        raise HTTPException(
            status_code=400,
            detail="Save the pipeline with a checked Credential node before creating a schedule.",
        )
    if has_saved_connection:
        connection = (
            db.query(ConnectionProfile)
            .filter(ConnectionProfile.id == int(credential["connection_id"]))
            .filter(ConnectionProfile.status == "active")
            .first()
        )
        if not connection:
            raise HTTPException(status_code=400, detail="Saved database connection is unavailable")
        if connection.created_by_user_id != user.id and not is_admin(user):
            raise HTTPException(
                status_code=403,
                detail="You cannot schedule a pipeline that uses another user's database connection.",
            )


def _get_schedule_allowed(db: Session, schedule_id: int, user: User) -> PipelineSchedule:
    schedule = db.query(PipelineSchedule).filter(PipelineSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule.created_by_user_id != user.id and not is_admin(user):
        raise HTTPException(status_code=403, detail="You can manage only schedules you created")
    return schedule


def _normalize_schedule_value(trigger_type: str, value: str) -> str:
    if trigger_type == "date":
        return _normalize_date(value)
    return _normalize_days(value)


def _normalize_date(value: str) -> str:
    from datetime import date

    raw = (value or "").strip()
    try:
        date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid schedule date") from exc
    return raw


def _normalize_days(value: str) -> str:
    raw = (value or "").strip().lower()
    if raw in {"*", "daily", "everyday", "every day"}:
        return "mon,tue,wed,thu,fri,sat,sun"
    allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    days = [day.strip()[:3] for day in raw.split(",") if day.strip()]
    if not days or any(day not in allowed for day in days):
        raise HTTPException(status_code=400, detail="Invalid schedule days")
    return ",".join(dict.fromkeys(days))


def _schedule_to_dict(schedule: PipelineSchedule, include_pipeline: bool = False) -> dict:
    data = {
        "id": schedule.id,
        "name": schedule.name,
        "status": schedule.status,
        "trigger_type": schedule.trigger_type,
        "day_of_week": schedule.day_of_week,
        "hour": schedule.hour,
        "minute": schedule.minute,
        "timezone": schedule.timezone,
        "last_run_at": _iso(schedule.last_run_at),
        "next_run_at": _iso(schedule.next_run_at),
        "last_status": schedule.last_status,
        "last_error": schedule.last_error,
        "created_at": _iso(schedule.created_at),
        "updated_at": _iso(schedule.updated_at),
        "created_by": schedule.created_by.display_name if schedule.created_by else "",
        "created_by_login_id": schedule.created_by.login_id if schedule.created_by else "",
    }
    if include_pipeline:
        data["pipeline_name"] = schedule.pipeline.name if schedule.pipeline else ""
        data["pipeline_slug"] = schedule.pipeline.slug if schedule.pipeline else ""
        data["pipeline_version"] = (
            schedule.pipeline_version.version_number if schedule.pipeline_version else None
        )
    return data


def _upcoming_schedule_events(schedules: list[PipelineSchedule], limit: int = 5) -> list[dict]:
    events = []
    now_by_tz: dict[str, datetime] = {}
    for schedule in schedules:
        tz = ZoneInfo(schedule.timezone or DEFAULT_TIMEZONE)
        now = now_by_tz.setdefault(str(tz), datetime.now(tz))
        for run_at in _next_run_times(schedule, now, limit):
            item = _schedule_to_dict(schedule, include_pipeline=True)
            item["next_run_at"] = _iso(run_at)
            item["upcoming_id"] = f"{schedule.id}_{run_at.isoformat()}"
            events.append((run_at, item))
    events.sort(key=lambda pair: pair[0])
    return [item for _, item in events[:limit]]


def _next_run_times(schedule: PipelineSchedule, now: datetime, limit: int) -> list[datetime]:
    if schedule.trigger_type == "date":
        run_at = datetime.fromisoformat(schedule.day_of_week).replace(
            hour=schedule.hour,
            minute=schedule.minute,
            second=0,
            microsecond=0,
            tzinfo=now.tzinfo,
        )
        return [run_at] if run_at > now else []

    trigger = CronTrigger(
        day_of_week=schedule.day_of_week,
        hour=schedule.hour,
        minute=schedule.minute,
        timezone=now.tzinfo,
    )
    runs = []
    previous = None
    cursor = now
    for _ in range(limit):
        next_run = trigger.get_next_fire_time(previous, cursor)
        if not next_run:
            break
        runs.append(next_run)
        previous = next_run
        cursor = next_run
    return runs


def _log_to_dict(log: ScheduleRunLog) -> dict:
    return {
        "id": log.id,
        "schedule_id": log.schedule_id,
        "pipeline_id": log.pipeline_id,
        "status": log.status,
        "scheduled_for": _iso(log.scheduled_for),
        "queued_at": _iso(log.queued_at),
        "claimed_at": _iso(log.claimed_at),
        "attempt_count": log.attempt_count,
        "max_attempts": log.max_attempts,
        "next_attempt_at": _iso(log.next_attempt_at),
        "started_at": _iso(log.started_at),
        "finished_at": _iso(log.finished_at),
        "error_message": log.error_message,
        "rows_written": log.rows_written,
        "created_at": _iso(log.created_at),
    }


def _iso(value):
    return value.isoformat() if value else None
