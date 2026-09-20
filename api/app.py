"""
app.py - FastAPI backend for the ETL Pipeline Builder.

Routes:
  POST /api/preview          - run up to a node, return 10 rows + columns
  WS   /ws/run               - execute full pipeline, stream per-node progress
"""

import asyncio
import json
import logging
import math
import threading
from datetime import timedelta
from decimal import Decimal
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from api.database import (
    LoginLog,
    SessionLocal,
    User,
    app_now,
    cleanup_expired_sessions,
    create_session,
    get_current_user,
    get_db,
    get_token_from_request,
    get_user_from_token,
    hash_password,
    is_admin,
    revoke_session,
    user_to_dict,
    verify_password,
)
from api.logging_config import configure_logging
from api.executor import execute_up_to, topo_sort
from api.models import LoginRequest, PipelineGraph, PreviewRequest
from api.pipeline_storage import (
    clear_saved_pipelines,
    delete_saved_pipeline,
    log_pipeline_run,
    list_saved_pipelines,
    list_pipeline_versions,
    load_saved_pipeline,
    load_pipeline_version,
    rename_saved_pipeline,
    save_index_pipeline,
    save_pipeline_graph,
    graph_to_index_flow,
)
from api.dashboard_routes import router as dashboard_router
from api.catalog_routes import router as catalog_router
from api.scheduler_routes import router as scheduler_router
from api.scheduler_service import shutdown_scheduler, start_scheduler
from src.config import (
    APP_CORS_HEADERS,
    APP_CORS_METHODS,
    APP_CORS_ORIGINS,
    LOGIN_FAILURE_WINDOW_MINUTES,
    LOGIN_MAX_FAILURES,
    RUN_EMBEDDED_SCHEDULER,
)

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="ETL Pipeline Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CORS_ORIGINS,
    allow_methods=APP_CORS_METHODS,
    allow_headers=APP_CORS_HEADERS,
)

app.include_router(scheduler_router)
app.include_router(dashboard_router)
app.include_router(catalog_router)


@app.on_event("startup")
def startup():
    db = None
    try:
        db = SessionLocal()
        cleanup_expired_sessions(db)
        logger.info("Expired sessions cleaned up")
    except Exception:
        logger.exception("Session cleanup failed")
    finally:
        if db is not None:
            db.close()
    if RUN_EMBEDDED_SCHEDULER:
        threading.Thread(target=start_scheduler, daemon=True).start()
    else:
        logger.info("Embedded scheduler disabled; expecting dedicated scheduler and worker processes")


@app.on_event("shutdown")
def shutdown():
    if RUN_EMBEDDED_SCHEDULER:
        shutdown_scheduler()


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)):
    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Application database unavailable") from exc
    return {"status": "ready"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    login_id = payload.login_id.strip()
    password = payload.password
    if not login_id or not password.strip():
        raise HTTPException(
            status_code=400,
            detail="Login ID and password are required",
        )

    client_ip = request.client.host if request.client else None
    failure_cutoff = app_now() - timedelta(minutes=LOGIN_FAILURE_WINDOW_MINUTES)
    latest_success = db.query(LoginLog).filter(
        LoginLog.login_id == login_id,
        LoginLog.success.is_(True),
        LoginLog.created_at >= failure_cutoff,
    )
    if client_ip:
        latest_success = latest_success.filter(LoginLog.ip_address == client_ip)
    latest_success = latest_success.order_by(LoginLog.created_at.desc()).first()
    if latest_success:
        # A valid login resets the failure streak without deleting its audit log.
        failure_cutoff = latest_success.created_at

    recent_failures = db.query(LoginLog).filter(
        LoginLog.login_id == login_id,
        LoginLog.success.is_(False),
        LoginLog.created_at >= failure_cutoff,
    )
    if client_ip:
        recent_failures = recent_failures.filter(LoginLog.ip_address == client_ip)
    if recent_failures.count() >= LOGIN_MAX_FAILURES:
        _log_login(db, None, login_id, False, "rate_limited", request)
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(LOGIN_FAILURE_WINDOW_MINUTES * 60)},
        )

    user = db.query(User).filter(User.login_id == login_id).first()

    if not user:
        _log_login(db, None, login_id, False, "login_id_not_found", request)
        logger.warning("Login failed: login_id_not_found login_id=%s", login_id)
        raise HTTPException(status_code=401, detail="Invalid login ID or password")

    if not user.is_active or not verify_password(password, user.password_hash):
        _log_login(db, user.id, login_id, False, "invalid_password", request)
        logger.warning("Login failed: invalid_password login_id=%s", login_id)
        raise HTTPException(status_code=401, detail="Invalid login ID or password")

    if user.password_hash.startswith("pbkdf2_sha256$"):
        user.password_hash = hash_password(password)
        db.commit()

    token = create_session(db, user)
    _log_login(db, user.id, login_id, True, None, request)
    logger.info("Login success login_id=%s user_id=%s", login_id, user.id)
    return {"token": token, "user": user_to_dict(user)}


@app.post("/api/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = get_token_from_request(request)
    if token:
        revoke_session(db, token)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_to_dict(user)}


@app.get("/api/pipelines")
def get_saved_pipelines(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return saved editable canvas pipelines from saved_pipeline/."""
    return list_saved_pipelines(db)


@app.get("/api/pipelines/{name}")
def get_saved_pipeline(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Load one saved editable canvas pipeline."""
    try:
        return load_saved_pipeline(db, name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/pipelines/{name}/versions")
def get_pipeline_versions(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return list_pipeline_versions(db, name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/pipelines/{name}/versions/{version_number}")
def get_pipeline_version(
    name: str,
    version_number: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return load_pipeline_version(db, name, version_number)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/pipelines")
async def save_saved_pipeline(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save the editable pipeline into saved_pipeline/."""
    if "nodes" in payload and "edges" in payload:
        return save_pipeline_graph(db, PipelineGraph(**payload), user)

    return save_index_pipeline(db, payload, user)


@app.put("/api/pipelines/{name}")
async def update_saved_pipeline(
    name: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update an existing saved editable pipeline, preserving its identity."""
    if not is_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Only admins can save changes to an existing pipeline. Save as a new pipeline instead.",
        )
    if "nodes" in payload and "edges" in payload:
        graph = PipelineGraph(**payload)
        return save_index_pipeline(
            db, graph_to_index_flow(graph), user, existing_name=name
        )
    return save_index_pipeline(db, payload, user, existing_name=name)


@app.delete("/api/pipelines")
def delete_saved_pipelines(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete saved editable canvas pipelines from saved_pipeline/."""
    if not is_admin(user):
        raise HTTPException(
            status_code=403, detail="Only admins can delete all pipelines"
        )
    return clear_saved_pipelines(db)


@app.patch("/api/pipelines/{name}")
async def rename_pipeline(
    name: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not is_admin(user):
        raise HTTPException(
            status_code=403, detail="Only admins can rename saved pipelines"
        )
    try:
        return rename_saved_pipeline(
            db,
            name,
            payload.get("report_name") or payload.get("pipeline_name") or name,
            user,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/pipelines/{name}")
def delete_saved_pipeline_route(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not is_admin(user):
        raise HTTPException(
            status_code=403, detail="Only admins can delete saved pipelines"
        )
    try:
        return delete_saved_pipeline(db, name, user)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# Preview


@app.post("/api/preview")
def preview_node(req: PreviewRequest, user: User = Depends(get_current_user)):
    """
    Execute all nodes up to (and including) req.node_id.
    Returns first 10 rows, column names, and total row count.
    """
    try:
        ctx = execute_up_to(
            req.graph,
            req.node_id,
            dry_run=True,
            actor_user_id=user.id,
            actor_is_admin=is_admin(user),
        )
        import pandas as pd

        df = ctx.get(req.node_id)

        if df is None or df.empty:
            return {"columns": [], "rows": [], "total_rows": 0, "error": None}

        cols = df.columns.tolist()
        rows = _safe_rows(df.head(10))
        return {"columns": cols, "rows": rows, "total_rows": len(df), "error": None}

    except Exception as exc:
        return {"columns": [], "rows": [], "total_rows": 0, "error": str(exc)}


def _safe_rows(df) -> list[dict]:
    """Convert DataFrame rows to JSON-safe dicts."""
    import pandas as pd

    rows = []
    for _, row in df.iterrows():
        clean = {}
        for k, v in row.items():
            if pd.isna(v):
                clean[k] = ""
            elif isinstance(v, Decimal):
                clean[k] = float(v)
            elif isinstance(v, bytes):
                clean[k] = v.decode("utf-8", errors="replace")
            elif isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean[k] = ""
            elif hasattr(v, "isoformat"):
                clean[k] = v.isoformat()
            elif hasattr(v, "item"):  # numpy scalar
                clean[k] = v.item()
            else:
                clean[k] = v
        rows.append(clean)
    return rows


# WebSocket run


@app.websocket("/ws/run")
async def run_websocket(ws: WebSocket):
    """
    Stream per-node execution progress.
    Client sends:  {"token": "...", "graph": PipelineGraph}
    Server sends:  { type: "progress", node_id, status, rows, error? }
                   { type: "complete" }
                   { type: "error", message }
    """
    await ws.accept()
    db = None

    try:
        raw = await ws.receive_text()
        payload = json.loads(raw)
        token = payload.get("token")
        if not token:
            await ws.send_json({"type": "error", "message": "Login required"})
            return
        db = next(get_db())
        user = get_user_from_token(db, token)

        graph = PipelineGraph(**payload.get("graph", {}))
        log_pipeline_run(db, graph.pipeline_name, user)

        # Find last node in topo order (skip credential)
        ordered = topo_sort(graph.nodes, graph.edges)
        exec_nodes = [n for n in ordered if n.type != "credential"]
        if not exec_nodes:
            await ws.send_json({"type": "complete"})
            return

        last_id = exec_nodes[-1].id

        # Thread-safe progress queue
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def on_progress(node_id, status, rows=0, error=None):
            msg = {
                "type": "progress",
                "node_id": node_id,
                "status": status,
                "rows": rows,
            }
            if error:
                msg["error"] = error
            asyncio.run_coroutine_threadsafe(queue.put(msg), loop)

        error_holder = {}

        def run():
            try:
                execute_up_to(
                    graph,
                    last_id,
                    on_progress=on_progress,
                    actor_user_id=user.id,
                    actor_is_admin=is_admin(user),
                )
            except Exception as exc:
                error_holder["msg"] = str(exc)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        # Stream messages until sentinel
        while True:
            msg = await queue.get()
            if msg is None:
                break
            await ws.send_json(msg)

        if "msg" in error_holder:
            await ws.send_json({"type": "error", "message": error_holder["msg"]})
        else:
            await ws.send_json({"type": "complete"})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        if db is not None:
            db.close()


def _log_login(
    db: Session,
    user_id: int | None,
    login_id: str,
    success: bool,
    failure_reason: str | None,
    request: Request,
):
    db.add(
        LoginLog(
            user_id=user_id,
            login_id=login_id,
            success=success,
            failure_reason=failure_reason,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
