import json
import re
import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from api.crypto import encrypt_secret
from api.database import (
    ExtractCheckpoint,
    PipelineLog,
    PipelineSchedule,
    PipelineVersion,
    SavedPipeline,
    ScheduleRunLog,
    User,
    app_now,
    is_admin,
)
from api.executor import extract_sheet_id, topo_sort
from api.models import PipelineGraph


def slug_name(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower())
    return slug.strip("_") or "untitled_pipeline"


def list_saved_pipelines(db: Session) -> list[dict]:
    out = []
    for pipeline in (
        db.query(SavedPipeline).order_by(SavedPipeline.updated_at.desc()).all()
    ):
        try:
            payload = json.loads(pipeline.pipeline_json)
            out.append(
                {
                    "name": pipeline.slug,
                    "pipeline_name": pipeline.name,
                    "nodes": _count_nodes(payload),
                    "edges": _count_links(payload),
                    "created_by": (
                        pipeline.created_by.display_name if pipeline.created_by else ""
                    ),
                    "created_by_login_id": (
                        pipeline.created_by.login_id if pipeline.created_by else ""
                    ),
                    "created_by_user_id": pipeline.created_by_user_id,
                    "last_edited_by": (
                        pipeline.last_edited_by.display_name
                        if pipeline.last_edited_by
                        else ""
                    ),
                    "last_edited_by_login_id": (
                        pipeline.last_edited_by.login_id
                        if pipeline.last_edited_by
                        else ""
                    ),
                    "last_edited_by_user_id": pipeline.last_edited_by_user_id,
                    "created_at": _iso(pipeline.created_at),
                    "updated_at": _iso(pipeline.updated_at),
                    "version": _latest_version_number(db, pipeline.id),
                }
            )
        except Exception as exc:
            out.append(
                {
                    "name": pipeline.slug,
                    "pipeline_name": pipeline.name,
                    "nodes": 0,
                    "edges": 0,
                    "created_by": (
                        pipeline.created_by.display_name if pipeline.created_by else ""
                    ),
                    "created_by_login_id": (
                        pipeline.created_by.login_id if pipeline.created_by else ""
                    ),
                    "created_by_user_id": pipeline.created_by_user_id,
                    "last_edited_by": (
                        pipeline.last_edited_by.display_name
                        if pipeline.last_edited_by
                        else ""
                    ),
                    "last_edited_by_login_id": (
                        pipeline.last_edited_by.login_id
                        if pipeline.last_edited_by
                        else ""
                    ),
                    "last_edited_by_user_id": pipeline.last_edited_by_user_id,
                    "created_at": _iso(pipeline.created_at),
                    "updated_at": _iso(pipeline.updated_at),
                    "error": f"Saved pipeline JSON is invalid: {exc}",
                }
            )
    return out


def load_saved_pipeline(db: Session, name: str) -> dict:
    pipeline = _get_pipeline(db, name)
    if not pipeline:
        raise FileNotFoundError(f"Saved pipeline not found: {name}")
    return json.loads(pipeline.pipeline_json)


def clear_saved_pipelines(db: Session) -> dict:
    count = db.query(SavedPipeline).count()
    db.query(ExtractCheckpoint).delete(synchronize_session=False)
    db.query(ScheduleRunLog).delete(synchronize_session=False)
    db.query(PipelineSchedule).delete(synchronize_session=False)
    db.query(PipelineVersion).delete(synchronize_session=False)
    db.query(PipelineLog).delete()
    db.query(SavedPipeline).delete()
    db.commit()
    return {"deleted": count}


def save_pipeline_graph(
    db: Session, graph: PipelineGraph, user: User, existing_name: str | None = None
) -> dict:
    return save_index_pipeline(
        db, graph_to_index_flow(graph), user, existing_name=existing_name
    )


def save_index_pipeline(
    db: Session, payload: dict, user: User, existing_name: str | None = None
) -> dict:
    old_name = slug_name(existing_name) if existing_name else None
    report_name = (
        payload.get("report_name")
        or payload.get("pipeline_name")
        or "Untitled Pipeline"
    )
    payload = dict(payload)
    payload["report_name"] = report_name
    payload.pop("pipeline_name", None)
    payload = _encrypt_credentials(payload)

    name = slug_name(report_name)
    now = app_now()
    pipeline = (
        _get_pipeline(db, old_name)
        if old_name
        else db.query(SavedPipeline).filter(SavedPipeline.slug == name).first()
    )
    if old_name and not pipeline:
        raise FileNotFoundError(f"Saved pipeline not found: {existing_name}")
    if pipeline and not old_name and not is_admin(user):
        report_name, name = _unique_copy_name(db, report_name)
        payload["report_name"] = report_name
        pipeline = None
    action = "updated" if pipeline else "created"
    old_display_name = pipeline.name if pipeline else None

    if old_name and old_name != name:
        conflict = db.query(SavedPipeline).filter(SavedPipeline.slug == name).first()
        if conflict and conflict.id != pipeline.id:
            raise HTTPException(
                status_code=409,
                detail=f"A saved pipeline named '{report_name}' already exists.",
            )

    if not pipeline:
        pipeline = SavedPipeline(
            slug=name,
            name=report_name,
            pipeline_json="{}",
            created_by_user_id=user.id,
            last_edited_by_user_id=user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(pipeline)
        db.flush()

    pipeline.slug = name
    pipeline.name = report_name
    pipeline.pipeline_json = json.dumps(payload, indent=4, ensure_ascii=False)
    pipeline.last_edited_by_user_id = user.id
    pipeline.updated_at = now
    db.flush()
    version = _create_pipeline_version(db, pipeline, user, now)
    _add_pipeline_log(db, pipeline.id, user.id, action, old_display_name, report_name)
    db.commit()
    db.refresh(pipeline)

    return {
        "name": name,
        "pipeline_name": report_name,
        "nodes": _count_nodes(payload),
        "edges": _count_links(payload),
        "created_by": pipeline.created_by.display_name if pipeline.created_by else "",
        "created_by_login_id": (
            pipeline.created_by.login_id if pipeline.created_by else ""
        ),
        "created_by_user_id": pipeline.created_by_user_id,
        "last_edited_by": (
            pipeline.last_edited_by.display_name if pipeline.last_edited_by else ""
        ),
        "last_edited_by_login_id": (
            pipeline.last_edited_by.login_id if pipeline.last_edited_by else ""
        ),
        "last_edited_by_user_id": pipeline.last_edited_by_user_id,
        "created_at": _iso(pipeline.created_at),
        "updated_at": _iso(pipeline.updated_at),
        "version": version.version_number,
    }


def delete_saved_pipeline(db: Session, name: str, user: User) -> dict:
    pipeline = _get_pipeline(db, name)
    if not pipeline:
        raise FileNotFoundError(f"Saved pipeline not found: {name}")
    deleted = pipeline.slug
    schedule_ids = [row.id for row in db.query(PipelineSchedule.id).filter(PipelineSchedule.pipeline_id == pipeline.id)]
    if schedule_ids:
        db.query(ExtractCheckpoint).filter(ExtractCheckpoint.schedule_id.in_(schedule_ids)).delete(synchronize_session=False)
    db.query(ScheduleRunLog).filter(
        ScheduleRunLog.pipeline_id == pipeline.id
    ).delete(synchronize_session=False)
    db.query(PipelineSchedule).filter(
        PipelineSchedule.pipeline_id == pipeline.id
    ).delete(synchronize_session=False)
    db.query(PipelineLog).filter(PipelineLog.pipeline_id == pipeline.id).update(
        {PipelineLog.pipeline_id: None}, synchronize_session=False
    )
    _add_pipeline_log(db, None, user.id, "deleted", pipeline.name, None)
    db.delete(pipeline)
    db.commit()
    return {"deleted": deleted}


def rename_saved_pipeline(
    db: Session, name: str, new_report_name: str, user: User
) -> dict:
    old_name = slug_name(name)
    new_name = slug_name(new_report_name)
    pipeline = _get_pipeline(db, old_name)
    if not pipeline:
        raise FileNotFoundError(f"Saved pipeline not found: {name}")

    payload = json.loads(pipeline.pipeline_json)
    payload["report_name"] = new_report_name
    payload = _encrypt_credentials(payload)
    old_display_name = pipeline.name
    conflict = db.query(SavedPipeline).filter(SavedPipeline.slug == new_name).first()
    if conflict and conflict.id != pipeline.id:
        raise HTTPException(
            status_code=409,
            detail=f"A saved pipeline named '{new_report_name}' already exists.",
        )
    pipeline.slug = new_name
    pipeline.name = new_report_name
    pipeline.pipeline_json = json.dumps(payload, indent=4, ensure_ascii=False)
    pipeline.last_edited_by_user_id = user.id
    pipeline.updated_at = app_now()
    db.flush()
    version = _create_pipeline_version(db, pipeline, user, pipeline.updated_at)
    _add_pipeline_log(
        db, pipeline.id, user.id, "renamed", old_display_name, new_report_name
    )
    db.commit()
    db.refresh(pipeline)

    return {
        "name": new_name,
        "pipeline_name": new_report_name,
        "nodes": _count_nodes(payload),
        "edges": _count_links(payload),
        "created_by": pipeline.created_by.display_name if pipeline.created_by else "",
        "created_by_login_id": (
            pipeline.created_by.login_id if pipeline.created_by else ""
        ),
        "created_by_user_id": pipeline.created_by_user_id,
        "last_edited_by": (
            pipeline.last_edited_by.display_name if pipeline.last_edited_by else ""
        ),
        "last_edited_by_login_id": (
            pipeline.last_edited_by.login_id if pipeline.last_edited_by else ""
        ),
        "last_edited_by_user_id": pipeline.last_edited_by_user_id,
        "created_at": _iso(pipeline.created_at),
        "updated_at": _iso(pipeline.updated_at),
        "version": version.version_number,
    }


def log_pipeline_run(db: Session, pipeline_name: str | None, user: User):
    pipeline = _get_pipeline(db, pipeline_name) if pipeline_name else None
    _add_pipeline_log(
        db,
        pipeline.id if pipeline else None,
        user.id,
        "run",
        pipeline.name if pipeline else None,
        pipeline.name if pipeline else None,
    )
    db.commit()


def graph_to_index_flow(graph: PipelineGraph) -> dict:
    ordered = topo_sort(graph.nodes, graph.edges)
    index_by_id = {node.id: i for i, node in enumerate(ordered, start=1)}
    incoming = {node.id: [] for node in graph.nodes}
    outgoing = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        if edge.source in index_by_id and edge.target in index_by_id:
            incoming[edge.target].append(edge)
            outgoing[edge.source].append(edge)

    report = {"report_name": graph.pipeline_name}

    credential = next((node for node in ordered if node.type == "credential"), None)
    if credential:
        report["credential"] = _drop_empty(
            {
                "index": index_by_id[credential.id],
                "out": _out_indexes(credential.id, outgoing, index_by_id),
            }
        )

    extract_nodes = [node for node in ordered if node.type == "extract"]
    if extract_nodes:
        report["extract"] = {
            "queries": [
                _drop_empty(
                    {
                        "index": index_by_id[node.id],
                        "name": _label(node, node.id),
                        "out": _out_indexes(node.id, outgoing, index_by_id),
                        "query": node.data.get("sql", ""),
                        "source_mode": node.data.get("source_mode", "query"),
                        "table_name": node.data.get("table_name", ""),
                        "incremental_mode": node.data.get("incremental_mode", "none"),
                        "checkpoint_column": node.data.get("checkpoint_column", ""),
                        "expected_columns": node.data.get("expected_columns", []),
                    }
                )
                for node in extract_nodes
            ]
        }

    transform_steps = []
    for node in ordered:
        if node.type != "transform":
            continue
        in_indexes = _in_indexes(node.id, incoming, index_by_id)
        step = _drop_empty(
            {
                "index": index_by_id[node.id],
                "name": _label(node, "Transform"),
                "in": in_indexes,
                "out": _out_indexes(node.id, outgoing, index_by_id),
                "output": _slug(_label(node, node.id)),
                "operations": [_clean_operation(node.data.get("operation") or {})],
            }
        )
        transform_steps.append(step)
    if transform_steps:
        report["transform"] = transform_steps

    load_nodes = [node for node in ordered if node.type == "load"]
    if load_nodes:
        report["load"] = [
            _drop_empty(
                {
                    "index": index_by_id[node.id],
                    "name": _label(node, "Sink"),
                    "write_mode": node.data.get("write_mode", "overwrite"),
                    "google_sheet_id": extract_sheet_id(
                        node.data.get("google_sheet_url", "")
                    ),
                    "sheets": [{"name": tab} for tab in _tab_names(node.data)],
                }
            )
            for node in load_nodes
        ]

    return report


def _count_nodes(pipeline: dict) -> int:
    if "nodes" in pipeline:
        return len(pipeline.get("nodes", []))
    return (
        (1 if pipeline.get("credential") else 0)
        + len(pipeline.get("extract", {}).get("queries", []))
        + len(pipeline.get("transform", []))
        + len(
            pipeline.get("load", [])
            if isinstance(pipeline.get("load"), list)
            else ([pipeline["load"]] if pipeline.get("load") else [])
        )
    )


def _count_links(pipeline: dict) -> int:
    if "edges" in pipeline:
        return len(pipeline.get("edges", []))
    total = 0

    def add_from(definition):
        nonlocal total
        total += len(_as_list(definition.get("out")))
        total += len(_as_list(definition.get("in")))

    if pipeline.get("credential"):
        add_from(pipeline["credential"])
    for query in pipeline.get("extract", {}).get("queries", []):
        add_from(query)
    for transform in pipeline.get("transform", []):
        add_from(transform)
    for load in (
        pipeline.get("load", []) if isinstance(pipeline.get("load"), list) else []
    ):
        add_from(load)
    return total


def _in_indexes(node_id: str, incoming: dict, index_by_id: dict) -> list[int]:
    edges = incoming.get(node_id, [])
    left = [edge for edge in edges if edge.targetHandle != "right"]
    right = [edge for edge in edges if edge.targetHandle == "right"]
    return [
        index_by_id[edge.source]
        for edge in [*left, *right]
        if edge.source in index_by_id
    ]


def _out_indexes(node_id: str, outgoing: dict, index_by_id: dict) -> list[int]:
    return [
        index_by_id[edge.target]
        for edge in outgoing.get(node_id, [])
        if edge.target in index_by_id
    ]


def _label(node, fallback: str) -> str:
    return node.data.get("label") or fallback


def _clean_operation(operation: dict) -> dict:
    cleaned = dict(operation)
    for key in ("index", "right_input", "right_input_index"):
        cleaned.pop(key, None)
    return _drop_empty(cleaned)


def _tab_names(data: dict) -> list[str]:
    names = data.get("tab_names") or [data.get("tab_name", "")]
    names = [str(name).strip() for name in names if str(name).strip()]
    return names


def _drop_empty(value):
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _drop_empty(item)) not in ("", None, [], {})
        }
    if isinstance(value, list):
        return [
            cleaned
            for item in value
            if (cleaned := _drop_empty(item)) not in ("", None, [], {})
        ]
    return value


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower())
    return slug.strip("_") or "output"


def _unique_copy_name(db: Session, report_name: str) -> tuple[str, str]:
    base = f"{report_name} Copy"
    candidate = base
    index = 2
    while (
        db.query(SavedPipeline)
        .filter(SavedPipeline.slug == slug_name(candidate))
        .first()
    ):
        candidate = f"{base} {index}"
        index += 1
    return candidate, slug_name(candidate)


def _encrypt_credentials(payload: dict) -> dict:
    cleaned = dict(payload)
    credential = cleaned.get("credential")
    if isinstance(credential, dict):
        allowed = {
            "index",
            "in",
            "out",
            "connection_id",
            "connection_name",
            "db_type",
            "host",
            "port",
            "database",
            "username",
            "connectionStatus",
        }
        next_credential = {
            key: value for key, value in credential.items() if key in allowed
        }
        password = credential.get("password")
        encrypted_password = credential.get("encrypted_password")
        if credential.get("connection_id"):
            # A saved connection is resolved server-side at execution time. Do
            # not duplicate its secret in the pipeline document.
            next_credential.pop("host", None)
            next_credential.pop("port", None)
            next_credential.pop("database", None)
            next_credential.pop("username", None)
        elif password:
            next_credential["encrypted_password"] = encrypt_secret(str(password))
        elif encrypted_password:
            next_credential["encrypted_password"] = encrypted_password
        cleaned["credential"] = next_credential
    return cleaned


def _get_pipeline(db: Session, name: str | None) -> SavedPipeline | None:
    if not name:
        return None
    return db.query(SavedPipeline).filter(SavedPipeline.slug == slug_name(name)).first()


def _add_pipeline_log(
    db: Session,
    pipeline_id: int | None,
    user_id: int,
    action: str,
    old_name: str | None,
    new_name: str | None,
):
    db.add(
        PipelineLog(
            pipeline_id=pipeline_id,
            user_id=user_id,
            action=action,
            old_name=old_name,
            new_name=new_name,
        )
    )


def _iso(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def list_pipeline_versions(db: Session, name: str) -> list[dict]:
    pipeline = _get_pipeline(db, name)
    if not pipeline:
        raise FileNotFoundError(f"Saved pipeline not found: {name}")
    versions = (
        db.query(PipelineVersion)
        .filter(PipelineVersion.pipeline_id == pipeline.id)
        .order_by(PipelineVersion.version_number.desc())
        .all()
    )
    return [
        {
            "id": version.id,
            "pipeline_id": version.pipeline_id,
            "pipeline_name": pipeline.name,
            "version": version.version_number,
            "status": version.status,
            "content_hash": version.content_hash,
            "created_by": version.created_by.display_name if version.created_by else "",
            "created_at": _iso(version.created_at),
        }
        for version in versions
    ]


def load_pipeline_version(db: Session, name: str, version_number: int) -> dict:
    pipeline = _get_pipeline(db, name)
    if not pipeline:
        raise FileNotFoundError(f"Saved pipeline not found: {name}")
    version = (
        db.query(PipelineVersion)
        .filter(PipelineVersion.pipeline_id == pipeline.id)
        .filter(PipelineVersion.version_number == version_number)
        .first()
    )
    if not version:
        raise FileNotFoundError(
            f"Pipeline version not found: {name} v{version_number}"
        )
    return json.loads(version.pipeline_json)


def _create_pipeline_version(
    db: Session,
    pipeline: SavedPipeline,
    user: User,
    created_at: datetime,
) -> PipelineVersion:
    latest = (
        db.query(func.max(PipelineVersion.version_number))
        .filter(PipelineVersion.pipeline_id == pipeline.id)
        .scalar()
        or 0
    )
    content = pipeline.pipeline_json
    version = PipelineVersion(
        pipeline_id=pipeline.id,
        version_number=int(latest) + 1,
        pipeline_json=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        status="published",
        created_by_user_id=user.id,
        created_at=created_at,
    )
    db.add(version)
    db.flush()
    return version


def _latest_version_number(db: Session, pipeline_id: int) -> int:
    return int(
        db.query(func.max(PipelineVersion.version_number))
        .filter(PipelineVersion.pipeline_id == pipeline_id)
        .scalar()
        or 0
    )
