"""Read-only aggregation endpoints for the Dashboard and Runtime Logs screens.

Both endpoints reuse the same visibility rule already used by scheduler_routes:
admins see every schedule/run, other users see only runs for schedules they created.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.database import (
    PipelineSchedule,
    SavedPipeline,
    ScheduleRunLog,
    User,
    app_now,
    get_current_user,
    get_db,
    is_admin,
)

router = APIRouter()
logger = logging.getLogger(__name__)

TERMINAL_STATUSES = ("success", "failed", "skipped")


def _visible_run_query(db: Session, user: User):
    query = db.query(ScheduleRunLog)
    if not is_admin(user):
        query = query.join(
            PipelineSchedule, ScheduleRunLog.schedule_id == PipelineSchedule.id
        ).filter(PipelineSchedule.created_by_user_id == user.id)
    return query


@router.get("/api/dashboard/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = app_now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = now - timedelta(days=14)

    total_pipelines = db.query(SavedPipeline).count()

    schedule_query = db.query(PipelineSchedule.pipeline_id)
    if not is_admin(user):
        schedule_query = schedule_query.filter(
            PipelineSchedule.created_by_user_id == user.id
        )
    active_pipelines = (
        schedule_query.filter(PipelineSchedule.status == "active")
        .distinct()
        .count()
    )

    runs_today = _visible_run_query(db, user).filter(
        ScheduleRunLog.created_at >= day_start
    ).count()

    records_processed_today = (
        _visible_run_query(db, user)
        .filter(ScheduleRunLog.created_at >= day_start)
        .with_entities(func.coalesce(func.sum(ScheduleRunLog.rows_written), 0))
        .scalar()
    ) or 0

    running_jobs = (
        _visible_run_query(db, user).filter(ScheduleRunLog.status == "running").count()
    )
    failed_jobs = (
        _visible_run_query(db, user)
        .filter(ScheduleRunLog.status == "failed")
        .filter(ScheduleRunLog.created_at >= now - timedelta(hours=24))
        .count()
    )

    finished_runs = _visible_run_query(db, user).filter(
        ScheduleRunLog.status.in_(TERMINAL_STATUSES)
    ).all()
    success_count = sum(1 for run in finished_runs if run.status == "success")
    success_rate = (
        round((success_count / len(finished_runs)) * 100, 1) if finished_runs else 0
    )

    durations = [
        (run.finished_at - run.started_at).total_seconds()
        for run in finished_runs
        if run.started_at and run.finished_at
    ]
    average_duration_seconds = (
        round(sum(durations) / len(durations), 1) if durations else 0
    )

    status_breakdown = {"queued": 0, "running": 0, "success": 0, "failed": 0, "skipped": 0}
    for run in _visible_run_query(db, user).filter(
        ScheduleRunLog.created_at >= window_start
    ).all():
        status_breakdown[run.status] = status_breakdown.get(run.status, 0) + 1

    execution_series = _daily_series(db, user, day_start, days=14)

    recent_runs = (
        _visible_run_query(db, user)
        .order_by(ScheduleRunLog.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_pipelines": total_pipelines,
        "active_pipelines": active_pipelines,
        "runs_today": runs_today,
        "success_rate": success_rate,
        "records_processed_today": int(records_processed_today),
        "running_jobs": running_jobs,
        "failed_jobs": failed_jobs,
        "average_duration_seconds": average_duration_seconds,
        "execution_series": execution_series,
        "status_breakdown": status_breakdown,
        "recent_runs": [_run_to_dict(run) for run in recent_runs],
    }


@router.get("/api/logs")
def list_runtime_logs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: str | None = Query(default=None),
    pipeline: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    query = _visible_run_query(db, user)
    if status and status != "all":
        query = query.filter(ScheduleRunLog.status == status)
    if pipeline:
        query = query.join(
            SavedPipeline, ScheduleRunLog.pipeline_id == SavedPipeline.id
        ).filter(SavedPipeline.slug == pipeline)

    runs = query.order_by(ScheduleRunLog.created_at.desc()).limit(limit).all()

    if search:
        needle = search.strip().lower()
        runs = [
            run
            for run in runs
            if needle in (run.pipeline.name if run.pipeline else "").lower()
            or needle in (run.error_message or "").lower()
            or needle in str(run.id)
        ]

    return [_run_to_dict(run) for run in runs]


@router.get("/api/logs/{run_id}")
def get_runtime_log(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = _visible_run_query(db, user).filter(ScheduleRunLog.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_dict(run, detailed=True)


def _daily_series(db: Session, user: User, day_start: datetime, days: int) -> list[dict]:
    start = day_start - timedelta(days=days - 1)
    runs = _visible_run_query(db, user).filter(ScheduleRunLog.created_at >= start).all()

    buckets: dict[str, dict] = {}
    for offset in range(days):
        key = (start + timedelta(days=offset)).date().isoformat()
        buckets[key] = {"date": key, "success": 0, "failed": 0, "skipped": 0, "total": 0}

    for run in runs:
        created = run.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        key = created.date().isoformat()
        bucket = buckets.get(key)
        if not bucket:
            continue
        if run.status in ("success", "failed", "skipped"):
            bucket[run.status] += 1
        bucket["total"] += 1

    return [buckets[key] for key in sorted(buckets.keys())]


def _run_to_dict(run: ScheduleRunLog, detailed: bool = False) -> dict:
    duration_seconds = None
    if run.started_at and run.finished_at:
        duration_seconds = round((run.finished_at - run.started_at).total_seconds(), 1)

    data = {
        "id": run.id,
        "run_id": run.id,
        "schedule_id": run.schedule_id,
        "schedule_name": run.schedule.name if run.schedule else None,
        "pipeline_id": run.pipeline_id,
        "pipeline_name": run.pipeline.name if run.pipeline else None,
        "pipeline_slug": run.pipeline.slug if run.pipeline else None,
        "status": run.status,
        "scheduled_for": _iso(run.scheduled_for),
        "queued_at": _iso(run.queued_at),
        "claimed_at": _iso(run.claimed_at),
        "attempt_count": run.attempt_count,
        "max_attempts": run.max_attempts,
        "next_attempt_at": _iso(run.next_attempt_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "duration_seconds": duration_seconds,
        "rows_written": run.rows_written,
        "error_message": run.error_message,
        "created_at": _iso(run.created_at),
    }
    if detailed:
        data["created_by"] = (
            run.schedule.created_by.display_name
            if run.schedule and run.schedule.created_by
            else None
        )
    return data


def _iso(value):
    return value.isoformat() if value else None
