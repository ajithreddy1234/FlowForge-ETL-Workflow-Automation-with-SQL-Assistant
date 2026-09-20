import json
import logging
import threading
from datetime import timedelta
from api.crypto import decrypt_secret
from api.database import (
    PipelineSchedule,
    ScheduleRunLog,
    SessionLocal,
    app_now,
)
from api.executor import execute_up_to, topo_sort
from api.models import Edge, Node, PipelineGraph

logger = logging.getLogger(__name__)


def run_scheduled_pipeline_log(log_id: int):
    db = SessionLocal()
    log = None
    schedule = None
    try:
        log = db.query(ScheduleRunLog).filter(ScheduleRunLog.id == log_id).first()
        if not log:
            logger.info("Queued schedule run log missing log_id=%s", log_id)
            return
        if log.status not in {"queued", "claimed"}:
            logger.info("Queued schedule run already handled log_id=%s status=%s", log.id, log.status)
            return

        embedded_attempt = log.status == "queued" and not log.worker_id
        if embedded_attempt:
            log.attempt_count += 1

        schedule = db.query(PipelineSchedule).filter(PipelineSchedule.id == log.schedule_id).first()
        if not schedule or schedule.status not in {"active", "completed"}:
            log.status = "skipped"
            log.finished_at = app_now()
            log.error_message = "Schedule is not active"
            db.commit()
            return
        if not schedule.pipeline:
            raise RuntimeError("Scheduled pipeline no longer exists")

        started = app_now()
        log.status = "running"
        log.started_at = started
        db.commit()

        logger.info("Queued scheduled pipeline started log_id=%s schedule_id=%s", log.id, schedule.id)
        payload = json.loads(
            schedule.pipeline_version.pipeline_json
            if schedule.pipeline_version
            else schedule.pipeline.pipeline_json
        )
        graph = scheduled_payload_to_graph(payload, schedule)
        ordered = topo_sort(graph.nodes, graph.edges)
        exec_nodes = [node for node in ordered if node.type != "credential"]
        if not exec_nodes:
            raise RuntimeError("Pipeline has no executable nodes")

        ctx = execute_up_to(
            graph,
            exec_nodes[-1].id,
            trusted_connection=True,
            checkpoint_scope=schedule.id,
        )
        rows_written = len(ctx.get(exec_nodes[-1].id, []))

        finished = app_now()
        log.status = "success"
        log.finished_at = finished
        log.rows_written = rows_written
        log.next_attempt_at = None
        schedule.last_run_at = finished
        schedule.last_status = "success"
        schedule.last_error = None
        schedule.updated_at = finished
        db.commit()
        logger.info("Queued scheduled pipeline succeeded log_id=%s rows_written=%s", log.id, rows_written)
    except Exception as exc:
        finished = app_now()
        will_retry = bool(log and log.attempt_count < log.max_attempts)
        embedded_retry = bool(will_retry and log and not log.worker_id)
        retry_delay_seconds = None
        if log:
            log.error_message = str(exc)
            log.claimed_at = None
            log.worker_id = None
            if will_retry:
                retry_delay_seconds = min(60 * (2 ** max(log.attempt_count - 1, 0)), 900)
                log.status = "queued" if embedded_retry else "retry_wait"
                log.next_attempt_at = finished + timedelta(seconds=retry_delay_seconds)
                log.started_at = None
                log.finished_at = None
            else:
                log.status = "failed"
                log.finished_at = finished
        if schedule:
            schedule.last_run_at = finished
            schedule.last_status = "retrying" if will_retry else "failed"
            schedule.last_error = str(exc)
            schedule.updated_at = finished
        db.commit()
        if embedded_retry and retry_delay_seconds is not None:
            timer = threading.Timer(
                retry_delay_seconds,
                run_scheduled_pipeline_log,
                args=[log_id],
            )
            timer.daemon = True
            timer.start()
        logger.exception("Queued scheduled pipeline failed log_id=%s", log_id)
    finally:
        db.close()


def scheduled_payload_to_graph(payload: dict, schedule: PipelineSchedule) -> PipelineGraph:
    nodes = []
    edges = []
    index_to_id = {}

    def node_id(prefix: str, index: int) -> str:
        return f"{prefix}_{index}"

    cred_def = _credential_definition(payload, schedule)
    cred_index = int(cred_def.get("index") or 1)
    cred_id = node_id("credential", cred_index)
    index_to_id[cred_index] = cred_id
    nodes.append(
        Node(
            id=cred_id,
            type="credential",
            position={"x": 80, "y": 120},
            data={
                "label": "Scheduled Credentials",
                "connection_id": cred_def.get("connection_id"),
                "connection_name": cred_def.get("connection_name") or "",
                "db_type": cred_def.get("db_type") or "mysql",
                "host": cred_def.get("host") or "",
                "port": cred_def.get("port") or "",
                "database": cred_def.get("database") or "",
                "username": cred_def.get("username") or "",
                "password": (
                    decrypt_secret(cred_def["encrypted_password"])
                    if cred_def.get("encrypted_password")
                    else ""
                ),
                "connectionStatus": "connected",
            },
        )
    )

    for query in payload.get("extract", {}).get("queries", []):
        idx = int(query.get("index"))
        nid = node_id("extract", idx)
        index_to_id[idx] = nid
        nodes.append(
            Node(
                id=nid,
                type="extract",
                position={"x": 330, "y": 120 + idx * 40},
                data={
                    "label": query.get("name") or nid,
                    "sql": query.get("query") or "",
                    "source_mode": query.get("source_mode") or "query",
                    "table_name": query.get("table_name") or "",
                    "incremental_mode": query.get("incremental_mode") or "none",
                    "checkpoint_column": query.get("checkpoint_column") or "",
                    "expected_columns": query.get("expected_columns") or [],
                },
            )
        )

    for step in payload.get("transform", []) or []:
        idx = int(step.get("index"))
        nid = node_id("transform", idx)
        index_to_id[idx] = nid
        operations = step.get("operations") or []
        nodes.append(
            Node(
                id=nid,
                type="transform",
                position={"x": 590, "y": 120 + idx * 40},
                data={
                    "label": step.get("name") or nid,
                    "operation": operations[0] if operations else {},
                },
            )
        )

    load_defs = payload.get("load") or []
    if isinstance(load_defs, dict):
        load_defs = [load_defs]
    for load_def in load_defs:
        idx = int(load_def.get("index"))
        nid = node_id("load", idx)
        index_to_id[idx] = nid
        nodes.append(
            Node(
                id=nid,
                type="load",
                position={"x": 880, "y": 120 + idx * 40},
                data={
                    "label": load_def.get("name") or "Sink",
                    "google_sheet_url": load_def.get("google_sheet_id") or "",
                    "write_mode": load_def.get("write_mode") or "overwrite",
                    "tab_names": [
                        sheet.get("name")
                        for sheet in load_def.get("sheets", [])
                        if sheet.get("name")
                    ],
                },
            )
        )

    def add_edge(source_idx, target_idx, target_handle=None):
        if source_idx not in index_to_id or target_idx not in index_to_id:
            return
        sid = index_to_id[source_idx]
        tid = index_to_id[target_idx]
        edges.append(
            Edge(
                id=f"edge_{sid}_{tid}_{len(edges) + 1}",
                source=sid,
                target=tid,
                targetHandle=target_handle,
            )
        )

    for definition in _all_index_definitions(payload):
        source_idx = definition.get("index")
        for target_idx in _as_list(definition.get("out")):
            add_edge(int(source_idx), int(target_idx))
        in_values = _as_list(definition.get("in"))
        for pos, source_idx in enumerate(in_values):
            add_edge(int(source_idx), int(definition.get("index")), "right" if pos > 0 else None)

    return PipelineGraph(
        pipeline_name=payload.get("report_name") or schedule.pipeline.name,
        nodes=nodes,
        edges=edges,
    )


def _credential_definition(payload: dict, schedule: PipelineSchedule) -> dict:
    cred_def = dict(payload.get("credential") or {"index": 1})
    if cred_def.get("connection_id") or cred_def.get("encrypted_password"):
        return cred_def

    raise RuntimeError(
        "Saved pipeline credentials are missing. Re-save the pipeline after checking the Credential node."
    )


def _all_index_definitions(payload: dict) -> list[dict]:
    items = []
    if payload.get("credential"):
        items.append(payload["credential"])
    items.extend(payload.get("extract", {}).get("queries", []))
    items.extend(payload.get("transform", []) or [])
    load_defs = payload.get("load") or []
    items.extend(load_defs if isinstance(load_defs, list) else [load_defs])
    return [item for item in items if isinstance(item, dict) and item.get("index") is not None]


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
