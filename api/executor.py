"""
executor.py — Converts a node-based pipeline graph into execution steps
and runs them using the existing src/ ETL code.
"""

import re
import logging
import json
from collections import defaultdict, deque
from datetime import date, timedelta
from typing import Callable, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from src.config import (
    ALLOW_UNSAFE_SQL,
    PREVIEW_SQL_LIMIT,
    SOURCE_DB_QUERY_TIMEOUT_SECONDS,
    get_connection_uri_from_fields,
    get_engine_kwargs,
)
from src.transform import transform as apply_transform
from api.sql_guardrails import SqlPolicyError, validate_read_only_statement
from api.extraction_contracts import (
    checkpoint_value,
    decode_checkpoint,
    encode_checkpoint,
    incremental_query,
    table_query,
    validate_schema,
)

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────


def resolve_date(mode: str, custom: str = "") -> str:
    today = date.today()
    if mode == "today":
        return str(today)
    if mode == "yesterday":
        return str(today - timedelta(days=1))
    return custom or str(today)


def extract_sheet_id(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else url


def topo_sort(nodes: list, edges: list) -> list:
    """Return nodes in dependency order (Kahn's algorithm)."""
    node_ids = {n.id for n in nodes}
    by_id = {n.id: n for n in nodes}
    in_deg = {n.id: 0 for n in nodes}
    adj = defaultdict(list)

    for e in edges:
        if e.source in node_ids and e.target in node_ids:
            adj[e.source].append(e.target)
            in_deg[e.target] += 1

    queue = deque([n for n in nodes if in_deg[n.id] == 0])
    result = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for nid in adj[node.id]:
            in_deg[nid] -= 1
            if in_deg[nid] == 0:
                queue.append(by_id[nid])
    if len(result) != len(nodes):
        raise ValueError("Pipeline graph contains a cycle. Remove the circular connection and try again.")
    return result


def incoming_edges(node_id: str, edges: list) -> list:
    return [e for e in edges if e.target == node_id]


# ── Main executor ─────────────────────────────────────────────────────────────


def execute_up_to(
    graph,
    target_node_id: str,
    on_progress: Optional[Callable] = None,
    dry_run: bool = False,
    actor_user_id: int | None = None,
    actor_is_admin: bool = False,
    trusted_connection: bool = False,
    checkpoint_scope: int | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Execute all nodes up to and including target_node_id (in topological order).
    Returns context dict {node_id: DataFrame}.
    on_progress(node_id, status, rows, error) is called for each node.
    When dry_run=True, Load nodes are executed but skip the actual sheet write.
    """
    all_ordered = topo_sort(graph.nodes, graph.edges)

    if not any(node.id == target_node_id for node in all_ordered):
        raise ValueError(f"Target node not found: {target_node_id}")
    # Execute the target's dependency closure only. A topological prefix can
    # contain unrelated branches and previously caused expensive queries to run
    # during previews for a different branch.
    required_ids = _ancestor_ids(target_node_id, graph.edges)
    ordered = [node for node in all_ordered if node.id in required_ids]
    incremental_nodes = [
        node for node in ordered
        if node.type == "extract" and node.data.get("incremental_mode", "none") != "none"
    ]
    if incremental_nodes and not dry_run:
        if checkpoint_scope is None:
            raise ValueError("Incremental extracts must run through a saved schedule")
        if not any(node.type == "load" for node in ordered):
            raise ValueError("An incremental extract requires a Google Sheets Load node")
        if any(node.type == "load" and node.data.get("write_mode", "overwrite") != "append" for node in ordered):
            raise ValueError("Incremental extracts require append-mode Google Sheets Load nodes")

    # Credential node — prefer a server-side profile so the browser never needs
    # to retain or resend a saved password. Inline fields remain supported for
    # unsaved/legacy pipelines.
    cred = next((n for n in graph.nodes if n.type == "credential"), None)
    if not cred:
        raise ValueError("A Credential node is required.")
    if cred.data.get("connectionStatus") != "connected":
        raise ValueError("Check DB connection in the Credential node before previewing or running the pipeline.")

    d = cred.data
    if d.get("connection_id"):
        db_uri = _saved_connection_uri(
            int(d["connection_id"]),
            actor_user_id=actor_user_id,
            actor_is_admin=actor_is_admin,
            trusted=trusted_connection,
        )
    else:
        if not (d.get("host") and d.get("database") and d.get("username")):
            raise ValueError(
                "Credential node must use a saved connection or include Host, Database, and Username."
            )
        db_uri = get_connection_uri_from_fields(
            db_type=d.get("db_type", "mysql"),
            host=d["host"],
            port=d.get("port"),
            database=d["database"],
            user=d["username"],
            password=d.get("password", ""),
        )

    context: dict[str, pd.DataFrame] = {}
    pending_checkpoints = {}

    for node in ordered:
        if on_progress:
            on_progress(node.id, "running", 0, None)

        try:
            _execute_node(
                node, graph.edges, context, db_uri, dry_run=dry_run,
                checkpoint_scope=checkpoint_scope,
                pending_checkpoints=pending_checkpoints,
            )
        except Exception as exc:
            if on_progress:
                on_progress(node.id, "error", 0, str(exc))
            raise

        rows = len(context.get(node.id, pd.DataFrame()))
        if on_progress:
            on_progress(node.id, "done", rows, None)

    if pending_checkpoints:
        _save_checkpoints(checkpoint_scope, pending_checkpoints)
    return context


def _ancestor_ids(target_node_id: str, edges: list) -> set[str]:
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        incoming[edge.target].append(edge.source)
    required = {target_node_id}
    stack = [target_node_id]
    while stack:
        current = stack.pop()
        for source in incoming.get(current, []):
            if source not in required:
                required.add(source)
                stack.append(source)
    return required


def _saved_connection_uri(
    connection_id: int,
    actor_user_id: int | None,
    actor_is_admin: bool,
    trusted: bool,
) -> str:
    from api.connection_profiles import profile_uri
    from api.database import ConnectionProfile, SessionLocal

    db = SessionLocal()
    try:
        profile = (
            db.query(ConnectionProfile)
            .filter(ConnectionProfile.id == connection_id)
            .filter(ConnectionProfile.status == "active")
            .first()
        )
        if not profile:
            raise ValueError("Saved database connection was not found or is inactive.")
        if not trusted and not actor_is_admin and profile.created_by_user_id != actor_user_id:
            raise ValueError("You are not allowed to use this saved database connection.")
        return profile_uri(profile)
    finally:
        db.close()


def _execute_node(
    node, edges: list, context: dict, db_uri: str, dry_run: bool = False,
    checkpoint_scope: int | None = None, pending_checkpoints: dict | None = None,
):
    """Execute a single node and store result in context."""

    if node.type == "credential":
        return  # no-op

    elif node.type == "extract":
        d = node.data
        dialect = _dialect_from_uri(db_uri)
        ref = resolve_date(
            d.get("reference_date_mode", "custom"), d.get("reference_date", "")
        )
        query_date = d.get("query_date") or ref
        base_sql = (
            (table_query(d.get("table_name", ""), dialect) if d.get("source_mode") == "table" else d.get("sql", ""))
            .replace("{reference_date}", ref)
            .replace("{date}", query_date)
        )
        if not base_sql.strip():
            raise ValueError("SQL query is required for the Extract node.")
        _validate_safe_sql(base_sql, dialect)
        mode = d.get("incremental_mode", "none")
        checkpoint = None
        if mode != "none":
            if mode not in {"primary_key", "timestamp"}:
                raise ValueError("Incremental mode must be primary_key or timestamp")
            if not dry_run:
                checkpoint = _read_checkpoint(checkpoint_scope, node.id)
            sql = incremental_query(base_sql, d.get("checkpoint_column", ""), checkpoint, dialect)
        else:
            sql = base_sql
        if dry_run:
            sql = _preview_sql(sql)
        params = {"date": query_date, "reference_date": ref}
        if checkpoint is not None:
            params["__flowforge_checkpoint"] = checkpoint
        engine = create_engine(db_uri, pool_pre_ping=True, **get_engine_kwargs(db_uri))
        try:
            with engine.connect() as conn:
                _apply_statement_timeout(conn, db_uri)
                df = pd.read_sql(text(sql), conn, params=params)
        except Exception as exc:
            raise RuntimeError(_database_error_message(exc)) from exc
        finally:
            engine.dispose()
        validate_schema(df, d.get("expected_columns"))
        if mode != "none":
            value = checkpoint_value(df, d.get("checkpoint_column", ""), mode)
            if value is not None and not dry_run:
                pending_checkpoints[node.id] = value
        context[node.id] = df

    elif node.type == "transform":
        in_edges = incoming_edges(node.id, edges)
        if not in_edges:
            raise ValueError("Transform node requires an input connection.")

        d = node.data
        operation = dict(d.get("operation") or {})
        op_type = operation.get("type", "")

        if len(in_edges) >= 2 and op_type in ("merge", "concat"):
            # Split into left / right by targetHandle
            left_key = next(
                (e.source for e in in_edges if e.targetHandle != "right"),
                in_edges[0].source,
            )
            right_key = next(
                (e.source for e in in_edges if e.targetHandle == "right"),
                in_edges[-1].source,
            )
            _require_context(context, left_key, "Transform")
            _require_context(context, right_key, "Transform")
            df = context[left_key].copy()
            operation["right_input"] = right_key
        else:
            left_key = in_edges[0].source
            _require_context(context, left_key, "Transform")
            df = context[left_key].copy()

        if not operation:
            context[node.id] = df
            return

        # Apply through existing transform layer
        mini = dict(context)
        mini["__in__"] = df
        step = {
            "name": d.get("label", "transform"),
            "input": "__in__",
            "output": node.id,
            "operations": [operation],
        }
        result = apply_transform(mini, [step])
        context[node.id] = result[node.id]

    elif node.type == "load":
        in_edges = incoming_edges(node.id, edges)
        if not in_edges:
            raise ValueError("Load node requires an input connection.")
        input_key = in_edges[0].source
        _require_context(context, input_key, "Load")
        df = context[input_key]
        d = node.data
        sheet_id = extract_sheet_id(d.get("google_sheet_url", ""))
        if not sheet_id.strip():
            raise ValueError("Google Sheet URL or ID is required for the Load node.")
        tab_names = d.get("tab_names") or []
        tab_names = [str(t).strip() for t in tab_names if str(t).strip()]
        if not tab_names:
            tab_name = str(d.get("tab_name", "")).strip()
            if tab_name:
                tab_names = [tab_name]
        if not tab_names:
            raise ValueError("At least one Google Sheet tab name is required for the Load node.")

        if not dry_run:
            from src.sheets import load as write_sheets

            write_sheets(
                context={input_key: df},
                sheets_config=[
                    {
                        "name": tab,
                        "input": input_key,
                        "write_mode": d.get("write_mode", "overwrite"),
                    }
                    for tab in tab_names
                ],
                google_sheet_id=sheet_id,
            )
        context[node.id] = df  # always keep for preview

    else:
        raise ValueError(f"Unsupported node type: {node.type}")


def _require_context(context: dict, input_key: str, node_type: str):
    if input_key not in context:
        raise ValueError(f"{node_type} input is not available: {input_key}")


def _preview_sql(sql: str) -> str:
    clean = sql.strip().rstrip(";")
    if not clean:
        return clean
    if PREVIEW_SQL_LIMIT <= 0:
        return clean
    return f"SELECT * FROM (\n{clean}\n) AS preview_source LIMIT {PREVIEW_SQL_LIMIT}"


def _validate_safe_sql(sql: str, dialect: str = "mysql"):
    if ALLOW_UNSAFE_SQL:
        return
    try:
        validate_read_only_statement(sql, dialect)
    except SqlPolicyError as exc:
        raise ValueError(str(exc)) from exc


def _dialect_from_uri(db_uri: str) -> str:
    if db_uri.startswith("redshift+"):
        return "redshift"
    if db_uri.startswith("postgresql+"):
        return "postgres"
    return "mysql"


def _read_checkpoint(schedule_id: int, extract_node_id: str):
    from api.database import ExtractCheckpoint, SessionLocal

    with SessionLocal() as db:
        row = (
            db.query(ExtractCheckpoint)
            .filter_by(schedule_id=schedule_id, extract_node_id=extract_node_id)
            .first()
        )
        return decode_checkpoint(json.loads(row.value_json)) if row else None


def _save_checkpoints(schedule_id: int, pending: dict):
    from api.database import ExtractCheckpoint, SessionLocal, app_now

    with SessionLocal() as db:
        for node_id, value in pending.items():
            row = (
                db.query(ExtractCheckpoint)
                .filter_by(schedule_id=schedule_id, extract_node_id=node_id)
                .first()
            )
            if row is None:
                row = ExtractCheckpoint(schedule_id=schedule_id, extract_node_id=node_id)
                db.add(row)
            elif decode_checkpoint(json.loads(row.value_json)) >= value:
                continue
            row.value_json = json.dumps(encode_checkpoint(value))
            row.updated_at = app_now()
        db.commit()


def _strip_sql_comments(sql: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"(?m)--.*$", " ", without_block)


def _apply_statement_timeout(conn, db_uri: str):
    timeout_ms = max(SOURCE_DB_QUERY_TIMEOUT_SECONDS, 1) * 1000
    try:
        if db_uri.startswith("mysql+pymysql://"):
            conn.execute(text("SET SESSION max_execution_time = :timeout_ms"), {"timeout_ms": timeout_ms})
        elif db_uri.startswith("redshift+redshift_connector://"):
            conn.execute(text(f"SET statement_timeout TO {timeout_ms}"))
    except Exception:
        logger.warning("Database did not accept statement timeout configuration", exc_info=True)


def _database_error_message(exc: Exception) -> str:
    raw = str(exc)
    lowered = raw.lower()
    if "access denied for user" in lowered or "(1045" in lowered:
        return (
            "Database login failed. Check the source DB username/password, encode special "
            "characters if needed, and confirm the database user is allowed to connect "
            "from this machine/IP."
        )
    return raw
