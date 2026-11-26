"""Live end-to-end check of the ETL path through the real scheduler queue and worker.

    docker compose exec api python -m scripts.e2e_check

For each demo source (PostgreSQL, and MySQL when configured) it saves a pipeline
(Extract -> Pandas transform -> append Load to csv://), creates a schedule, enqueues runs
the same way APScheduler does, and waits for the worker container to process them:

  1. first run loads the full table and stores a checkpoint
     (PostgreSQL: integer primary key; MySQL: timestamp column),
  2. new source rows are inserted, and the second run must load only those rows,
  3. a pipeline reading a missing table must be logged as a failure with a retry scheduled,
  4. a runaway query (triple self-join, ~5.6e10 rows) must be stopped by the statement timeout
     applied to every source connection (E2E_TIMEOUT_SECONDS, default 3).

Every run is checked in the persisted run log (status, attempts, rows, duration, error).
Rows inserted into the demo source are removed again at the end.
"""
from __future__ import annotations

import csv
import json
import os
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

from api.connection_profiles import profile_uri
from api.database import (ConnectionProfile, PipelineSchedule, SavedPipeline, ScheduleRunLog, SessionLocal, User,
                          app_now)
from api.pipeline_storage import save_index_pipeline
from api.scheduler_service import enqueue_schedule_run
from src.config import LOCAL_CSV_OUTPUT_DIR

NEW_IDS = list(range(900001, 900006))
SOURCES = {
    "postgresql": {
        "connection": "Demo retail (PostgreSQL)",
        "admin_url": lambda: "postgresql+psycopg://demo_admin:{}@{}:5432/{}".format(
            os.getenv("DEMO_DB_ADMIN_PASSWORD", "demo-admin-local"), os.getenv("DEMO_SOURCE_HOST", "demo-db"),
            os.getenv("DEMO_SOURCE_DB", "retail")),
        "extract": {"source_mode": "table", "table_name": "orders", "query": "",
                    "incremental_mode": "primary_key", "checkpoint_column": "id"},
    },
    "mysql": {
        "connection": "Demo retail (MySQL)",
        "admin_url": lambda: os.getenv("DEMO_MYSQL_ADMIN_URL", ""),
        "extract": {"source_mode": "query",
                    "query": "SELECT id, customer_id, status, updated_at FROM orders",
                    "incremental_mode": "timestamp", "checkpoint_column": "updated_at"},
    },
}


def _pipeline(name: str, profile: ConnectionProfile, extract: dict, sink: str) -> dict:
    return {
        "report_name": name,
        "credential": {"index": 1, "out": [2], "connection_id": profile.id, "connection_name": profile.name,
                       "host": profile.host, "database": profile.database_name, "username": profile.username,
                       "connectionStatus": "connected"},
        "extract": {"queries": [{"index": 2, "name": "Orders", "out": [3], "expected_columns": ["id", "status"],
                                 **extract}]},
        "transform": [{"index": 3, "name": "Keep reporting columns", "in": [2], "out": [4],
                       "operations": [{"type": "select_columns",
                                       "columns": ["id", "customer_id", "status", "updated_at"]}]}],
        "load": [{"index": 4, "name": "Orders CSV", "in": [3], "google_sheet_id": f"csv://{sink}",
                  "write_mode": "append", "sheets": [{"name": "orders"}]}],
    }


def _schedule(db, pipeline_name: str, user: User) -> int:
    pipeline = db.query(SavedPipeline).filter_by(slug=pipeline_name).one()
    now = app_now()
    schedule = PipelineSchedule(pipeline_id=pipeline.id, pipeline_version_id=pipeline.versions[-1].id,
                                created_by_user_id=user.id, name=f"{pipeline.name} (e2e)", status="active",
                                trigger_type="cron", day_of_week="sun", hour=3, minute=0, timezone="UTC",
                                apscheduler_job_id="e2e", created_at=now, updated_at=now)
    db.add(schedule)
    db.flush()
    schedule.apscheduler_job_id = f"pipeline_schedule_{schedule.id}"
    db.commit()
    return schedule.id


def _run(schedule_id: int, slot: int, until=("success", "failed", "retry_wait"), timeout=120) -> ScheduleRunLog:
    when = (app_now().replace(second=0, microsecond=0) + timedelta(minutes=slot)).isoformat()
    enqueue_schedule_run(schedule_id, scheduled_for=when)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            log = (db.query(ScheduleRunLog).filter_by(schedule_id=schedule_id)
                   .order_by(ScheduleRunLog.id.desc()).first())
            if log and log.status in until:
                db.expunge(log)
                return log
        time.sleep(1)
    raise SystemExit(f"Run for schedule {schedule_id} did not finish in {timeout}s (is the worker running?)")


def _csv_rows(sink: str) -> int:
    files = sorted((Path(LOCAL_CSV_OUTPUT_DIR) / sink).glob("*.csv"))
    if not files:
        return 0
    with files[0].open() as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def _describe(log: ScheduleRunLog) -> dict:
    duration = (log.finished_at - log.started_at).total_seconds() if log.finished_at and log.started_at else None
    return {"status": log.status, "attempt": f"{log.attempt_count}/{log.max_attempts}", "rows": log.rows_written,
            "duration_s": round(duration, 3) if duration is not None else None, "worker": log.worker_id,
            "error": (log.error_message or "")[:120] or None,
            "next_attempt_at": log.next_attempt_at.isoformat() if log.next_attempt_at else None}


def check(dialect: str, spec: dict, stamp: str) -> dict:
    admin = create_engine(spec["admin_url"]())
    with SessionLocal() as db:
        profile = db.query(ConnectionProfile).filter_by(name=spec["connection"]).first()
        if not profile:
            return {"skipped": f"no connection {spec['connection']!r}"}
        user = db.get(User, profile.created_by_user_id)
        source_uri = profile_uri(profile)
        sink = f"e2e_{dialect}_{stamp}"
        saved = save_index_pipeline(db, _pipeline(f"E2E {dialect} {stamp}", profile, spec["extract"], sink), user)
        schedule_id = _schedule(db, saved["name"], user)
        broken = _pipeline(f"E2E {dialect} broken {stamp}", profile,
                           {"source_mode": "table", "table_name": "missing_table", "query": "",
                            "incremental_mode": "none", "checkpoint_column": ""}, f"{sink}_broken")
        broken["load"][0]["write_mode"] = "overwrite"
        broken_id = _schedule(db, save_index_pipeline(db, broken, user)["name"], user)

    with admin.connect() as conn:
        base = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
    results: dict = {"source_rows": base}

    first = _run(schedule_id, 1)
    results["run_1_full"] = _describe(first)
    assert first.status == "success" and first.rows_written == base, results
    assert _csv_rows(sink) == base, f"CSV has {_csv_rows(sink)} rows, expected {base}"

    try:
        with admin.begin() as conn:
            for i, new_id in enumerate(NEW_IDS):
                conn.execute(text("INSERT INTO orders (id, customer_id, order_date, status, updated_at) VALUES "
                                  "(:id, 1, :d, 'placed', :u)"),
                             {"id": new_id, "d": app_now().date(), "u": app_now().replace(tzinfo=None, microsecond=0)
                              + timedelta(days=400, seconds=i)})
        second = _run(schedule_id, 2)
        results["run_2_incremental"] = _describe(second)
        assert second.status == "success" and second.rows_written == len(NEW_IDS), results
        assert _csv_rows(sink) == base + len(NEW_IDS), f"CSV has {_csv_rows(sink)} rows after append"

        third = _run(schedule_id, 3)
        results["run_3_no_new_rows"] = _describe(third)
        assert third.status == "success" and third.rows_written == 0, results
    finally:
        with admin.begin() as conn:
            conn.execute(text(f"DELETE FROM orders WHERE id IN ({', '.join(map(str, NEW_IDS))})"))
        admin.dispose()

    failed = _run(broken_id, 1)
    results["broken_pipeline"] = _describe(failed)
    assert failed.status == "retry_wait" and failed.error_message and failed.next_attempt_at, results
    with SessionLocal() as db:  # leave nothing for the real scheduler: no weekly runs, no background retries
        for sid in (schedule_id, broken_id):
            db.get(PipelineSchedule, sid).status = "paused"
        db.commit()
    results["query_timeout"] = _timeout_check(source_uri)
    time.sleep(1)
    activity = ("SELECT COUNT(*) FROM information_schema.processlist WHERE info LIKE '%quantity < 0%' "
                "AND info NOT LIKE '%processlist%'") if dialect == "mysql" else (
                "SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active' AND query LIKE '%quantity < 0%' "
                "AND query NOT LIKE '%pg_stat_activity%'")
    with create_engine(spec["admin_url"]()).connect() as conn:
        lingering = conn.execute(text(activity)).scalar()
    results["query_timeout"]["still_running_on_server"] = lingering
    assert lingering == 0, "the timed-out query is still running on the database server"
    results["csv_output"] = f"output/{sink}/"
    return results


def _timeout_check(uri: str) -> dict:
    import src.config as config
    from api import executor

    limit = int(os.getenv("E2E_TIMEOUT_SECONDS", "3"))
    config.SOURCE_DB_QUERY_TIMEOUT_SECONDS = executor.SOURCE_DB_QUERY_TIMEOUT_SECONDS = limit
    engine = create_engine(uri, **config.get_engine_kwargs(uri))
    started = time.monotonic()
    try:
        with engine.connect() as conn:
            executor._apply_statement_timeout(conn, uri)
            conn.execute(text("SELECT COUNT(*) FROM order_items a, order_items b, order_items c "
                              "WHERE a.quantity + b.quantity + c.quantity < 0")).scalar()
        stopped, error = False, None
    except Exception as exc:  # noqa: BLE001 - the timeout error is the expected outcome
        stopped, error = True, str(exc).splitlines()[0][:120]
    finally:
        engine.dispose()
    elapsed = round(time.monotonic() - started, 2)
    assert stopped and elapsed < limit + 5, f"runaway query was not stopped (elapsed {elapsed}s)"
    return {"timeout_s": limit, "stopped_after_s": elapsed, "error": error}


def main():
    stamp = app_now().strftime("%Y%m%d%H%M%S")
    report = {}
    for dialect, spec in SOURCES.items():
        if dialect == "mysql" and not spec["admin_url"]():
            report[dialect] = {"skipped": "DEMO_MYSQL_ADMIN_URL not set"}
            continue
        print(f"== {dialect}")
        report[dialect] = check(dialect, spec, stamp)
        print(json.dumps(report[dialect], indent=2, default=str))
    out = Path(__file__).resolve().parents[1] / "eval" / "results"
    out.mkdir(exist_ok=True)
    (out / "e2e.json").write_text(json.dumps({"run_at": app_now().isoformat(), **report}, indent=2, default=str))
    print("END-TO-END CHECK PASSED")


if __name__ == "__main__":
    main()
