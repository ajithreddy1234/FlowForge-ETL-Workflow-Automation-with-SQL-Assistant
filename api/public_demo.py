"""Safe synthetic adapters for the real executor and scheduler, never external accounts."""
import json
import os
import secrets
import sqlite3
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic

import pandas as pd
from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response, JSONResponse

DEMO_MODE = os.getenv("FLOWFORGE_DEMO", "false") == "true"
RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
SOURCE = RUNTIME / "synthetic.db"
ALLOWED_OPS = {"rename", "select_columns", "drop_columns", "sort", "filter", "fillna", "replace", "map", "abs", "astype", "drop_duplicates", "groupby", "pivot", "format_date", "date_extract", "rank", "cumsum", "pct_of_total", "add_total_column", "add_total_row"}
RUN_LOCK = threading.BoundedSemaphore(2)


def seed_demo():
    from api.database import SessionLocal, User, ConnectionProfile, PipelineSchedule, SavedPipeline, app_now, hash_password
    from api.crypto import encrypt_secret
    from api.pipeline_storage import save_index_pipeline
    RUNTIME.mkdir(exist_ok=True)
    with sqlite3.connect(SOURCE) as db:
        db.execute("CREATE TABLE IF NOT EXISTS orders (order_id INTEGER PRIMARY KEY, order_date TEXT, region TEXT, category TEXT, amount REAL, status TEXT)")
        if not db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]:
            rows = [(i, (datetime(2026, 11, 1) + timedelta(days=i % 17)).date().isoformat(), ["North", "South", "East", "West"][i % 4], ["Home", "Apparel", "Electronics"][i % 3], round(199 + (i * 83.27) % 4800, 2), "returned" if i % 9 == 0 else "completed") for i in range(1, 241)]
            db.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", rows)
        db.execute("CREATE TABLE IF NOT EXISTS outputs (name TEXT PRIMARY KEY, csv TEXT, rows INTEGER, updated_at TEXT)")
    with SessionLocal() as db:
        user = db.query(User).filter_by(login_id="public_sandbox").first()
        if not user:
            user = User(login_id="public_sandbox", display_name="Public sandbox", role="user", password_hash=hash_password(secrets.token_urlsafe(48)))
            db.add(user)
            db.flush()
        connection = db.query(ConnectionProfile).filter_by(created_by_user_id=user.id, name="Synthetic orders").first()
        if not connection:
            connection = ConnectionProfile(created_by_user_id=user.id, name="Synthetic orders", db_type="sqlite", host="sandbox", database_name="synthetic_orders", username="demo", encrypted_password=encrypt_secret(""))
            db.add(connection)
            db.flush()
        db.commit()
        template = {
            "report_name": "Regional revenue", "credential": {"index": 1, "out": [2], "connection_id": connection.id, "connection_name": "Synthetic orders", "host": "sandbox", "database": "synthetic_orders", "username": "demo", "connectionStatus": "connected"},
            "extract": {"queries": [{"index": 2, "name": "Completed orders", "out": [3], "query": "SELECT order_id, region, category, amount, order_date FROM orders WHERE status = 'completed'"}]},
            "transform": [{"index": 3, "name": "Revenue by region", "in": [2], "out": [4], "operations": [{"type": "groupby", "group_by": ["region"], "aggregations": {"amount": "sum"}}]}],
            "load": [{"index": 4, "name": "Regional revenue CSV", "in": [3], "google_sheet_id": "sandbox://csv", "write_mode": "overwrite", "sheets": [{"name": "regional_revenue"}]}],
        }
        pipeline = db.query(SavedPipeline).filter_by(slug="regional_revenue").first()
        if not pipeline:
            saved = save_index_pipeline(db, template, user)
            pipeline = db.query(SavedPipeline).filter_by(slug=saved["name"]).one()
        if not db.query(PipelineSchedule).filter_by(pipeline_id=pipeline.id).first():
            now = app_now()
            later = now + timedelta(minutes=2)
            schedule = PipelineSchedule(pipeline_id=pipeline.id, pipeline_version_id=pipeline.versions[-1].id, created_by_user_id=user.id, name="Daily regional revenue", status="active", trigger_type="cron", day_of_week="mon,tue,wed,thu,fri,sat,sun", hour=later.hour, minute=later.minute, timezone="Asia/Kolkata", apscheduler_job_id="initial", created_at=now, updated_at=now)
            db.add(schedule)
            db.flush()
            schedule.apscheduler_job_id = f"pipeline_schedule_{schedule.id}"
            db.commit()


def validate_graph(graph):
    if not 1 <= len(graph.nodes) <= 12 or len(graph.edges) > 20:
        raise ValueError("The public sandbox supports up to 12 nodes and 20 connections.")
    for node in graph.nodes:
        if len(node.id) > 100:
            raise ValueError("Node ID is too long.")
        if node.type == "transform":
            op = node.data.get("operation") or {}
            if op and op.get("type") not in ALLOWED_OPS:
                raise ValueError("This operation is available in a private deployment. Choose a listed sandbox operation.")
            if op.get("type") == "astype" and any(v not in {"str", "int", "float", "bool"} for v in (op.get("mapping") or {}).values()):
                raise ValueError("Use a supported data type.")


def read_synthetic(sql):
    if len(sql) > 4000:
        raise ValueError("Keep sandbox SQL below 4,000 characters.")
    from api.sql_guardrails import validate_read_only_statement
    validate_read_only_statement(sql, "sqlite")
    allowed_functions = {"sum", "avg", "count", "min", "max", "round", "coalesce", "ifnull", "nullif", "abs", "lower", "upper", "length", "substr", "date", "strftime", "cast", "like"}
    with sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True, timeout=3) as db:
        def authorize(action, arg1, arg2, *_):
            if action == sqlite3.SQLITE_SELECT:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ and arg1 == "orders":
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() in allowed_functions:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        db.set_authorizer(authorize)
        started = monotonic()
        calls = 0
        def progress():
            nonlocal calls
            calls += 1
            return int(calls > 500 or monotonic() - started > 3)
        db.set_progress_handler(progress, 1000)
        return pd.read_sql_query(f"SELECT * FROM ({sql.strip().rstrip(';')}) LIMIT 500", db)


def write_output(name, frame):
    if len(frame) > 2000 or len(frame.columns) > 40:
        raise ValueError("Sandbox outputs are limited to 2,000 rows and 40 columns.")
    name = str(name)[:80]
    csv = frame.to_csv(index=False)
    if len(csv) > 500_000:
        raise ValueError("Sandbox output is too large.")
    with sqlite3.connect(SOURCE, timeout=5) as db:
        db.execute("INSERT INTO outputs VALUES (?,?,?,?) ON CONFLICT(name) DO UPDATE SET csv=excluded.csv, rows=excluded.rows, updated_at=excluded.updated_at", (name, csv, len(frame), datetime.now().isoformat()))
        db.execute("DELETE FROM outputs WHERE name NOT IN (SELECT name FROM outputs ORDER BY updated_at DESC LIMIT 30)")


def install_demo_routes(app):
    from api.database import SessionLocal, User, UserSession, PipelineSchedule, SavedPipeline, create_session, user_to_dict, get_current_user, app_now
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException as StaticHTTPException
    hits = defaultdict(deque)

    @app.middleware("http")
    async def sandbox_limits(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            now = monotonic()
            ip = request.client.host if request.client else "unknown"
            queue = hits[ip]
            while queue and queue[0] < now - 60:
                queue.popleft()
            if len(queue) >= 100:
                return JSONResponse({"detail": "Sandbox request limit reached. Try again in a minute."}, status_code=429)
            queue.append(now)
            if len(hits) > 1000:
                for key in list(hits):
                    if not hits[key] or hits[key][-1] < now - 60:
                        hits.pop(key, None)
            if request.method in {"POST", "PUT", "PATCH"}:
                body = await request.body()
                if len(body) > 65536:
                    return JSONResponse({"detail": "Sandbox requests are limited to 64 KB."}, status_code=413)
            if path.startswith("/api/sql-assistant") or (path.startswith("/api/connections") and request.method != "GET"):
                return JSONResponse({"detail": "External connections and the AI SQL assistant require a private deployment. Use the synthetic orders source here."}, status_code=403)
            if path == "/api/db/check-connection":
                return JSONResponse({"detail": "The synthetic orders source is already connected."}, status_code=403)
            if request.method == "POST" and (path == "/api/pipelines" or path.endswith("/schedules")):
                with SessionLocal() as db:
                    if path.endswith("/schedules"):
                        data = await request.json()
                        if len(data.get("rules", [])) > 3 or db.query(PipelineSchedule).count() >= 20:
                            return JSONResponse({"detail": "This shared sandbox has reached its schedule limit."}, status_code=409)
                    elif db.query(SavedPipeline).count() >= 50:
                        return JSONResponse({"detail": "This shared sandbox has reached its saved pipeline limit."}, status_code=409)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.post("/api/demo/session")
    def demo_session():
        with SessionLocal() as db:
            user = db.query(User).filter_by(login_id="public_sandbox").one()
            # Keep public sessions bounded without ever reusing a bearer token.
            old = db.query(UserSession.id).order_by(UserSession.id.desc()).offset(500).all()
            if old:
                db.query(UserSession).filter(UserSession.id.in_([item[0] for item in old])).delete(synchronize_session=False)
            return {"token": create_session(db, user), "user": user_to_dict(user)}

    @app.get("/api/demo/output")
    def download_output(user=Depends(get_current_user)):
        with sqlite3.connect(SOURCE) as db:
            row = db.execute("SELECT csv FROM outputs ORDER BY updated_at DESC LIMIT 1").fetchone()
        if not row:
            raise HTTPException(404, "Run a pipeline with a CSV sink first.")
        return Response(row[0], media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="flowforge-output.csv"', "Cache-Control": "no-store"})

    @app.post("/api/demo/run-schedule/{schedule_id}")
    def run_schedule(schedule_id: int, user=Depends(get_current_user)):
        from api.scheduler_service import enqueue_schedule_run
        with SessionLocal() as db:
            if not db.query(PipelineSchedule).filter_by(id=schedule_id, created_by_user_id=user.id, status="active").first():
                raise HTTPException(404, "Schedule not found")
        enqueue_schedule_run(schedule_id, scheduled_for=app_now().replace(second=0, microsecond=0).isoformat())
        return {"status": "queued"}

    class SPAFiles(StaticFiles):
        async def get_response(self, path, scope):
            try:
                return await super().get_response(path, scope)
            except StaticHTTPException as exc:
                if exc.status_code != 404 or path.startswith(("api/", "health/")) or "." in Path(path).name:
                    raise
                return await super().get_response("index.html", scope)
    dist = Path(__file__).resolve().parents[1] / "UI" / "dist"
    if dist.exists():
        app.mount("/", SPAFiles(directory=dist, html=True), name="frontend")
