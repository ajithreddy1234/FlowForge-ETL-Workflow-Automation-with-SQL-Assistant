import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.catalog_service import catalog_to_dict, latest_catalog, sync_catalog
from api.connection_checker import check_database_connection
from api.connection_profiles import (
    check_profile,
    connection_to_dict,
    get_connection_allowed,
)
from api.crypto import encrypt_secret
from api.database import (
    ConnectionProfile,
    SqlAssistantCandidate,
    User,
    app_now,
    get_current_user,
    get_db,
    is_admin,
)
from api.models import (
    ConnectionProfileRequest,
    ConnectionProfileUpdateRequest,
    SqlAssistantGenerateRequest,
    SqlAssistantPreviewRequest,
)
from api.sql_assistant_service import (
    SqlAssistantUnavailable,
    approve_candidate,
    candidate_to_dict,
    generate_candidate,
    preview_candidate,
)
from api.sql_guardrails import SqlPolicyError

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


@router.get("/connections")
def list_connections(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    query = db.query(ConnectionProfile).filter(ConnectionProfile.status != "deleted")
    if not is_admin(user):
        query = query.filter(ConnectionProfile.created_by_user_id == user.id)
    return [
        connection_to_dict(profile)
        for profile in query.order_by(ConnectionProfile.updated_at.desc()).all()
    ]


@router.post("/connections")
def create_connection(
    payload: ConnectionProfileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        check_database_connection(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile = ConnectionProfile(
        created_by_user_id=user.id,
        name=payload.name.strip(),
        db_type=payload.db_type,
        host=payload.host.strip(),
        port=(payload.port or "").strip() or None,
        database_name=payload.database.strip(),
        username=payload.username.strip(),
        encrypted_password=encrypt_secret(payload.password or ""),
        allowed_schemas_json=json.dumps(
            [item.strip() for item in payload.allowed_schemas if item.strip()]
        ),
        status="active",
        last_checked_at=app_now(),
        created_at=app_now(),
        updated_at=app_now(),
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"You already have a connection named '{payload.name.strip()}'.",
        ) from exc
    db.refresh(profile)
    logger.info("Connection created connection_id=%s user_id=%s", profile.id, user.id)
    return connection_to_dict(profile)


@router.patch("/connections/{connection_id}")
def update_connection(
    connection_id: int,
    payload: ConnectionProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_connection_allowed(db, connection_id, user)
    if payload.name is not None:
        profile.name = payload.name.strip()
    if payload.password is not None:
        profile.encrypted_password = encrypt_secret(payload.password)
    if payload.allowed_schemas is not None:
        profile.allowed_schemas_json = json.dumps(
            [item.strip() for item in payload.allowed_schemas if item.strip()]
        )
    profile.updated_at = app_now()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Connection name already exists") from exc
    db.refresh(profile)
    return connection_to_dict(profile)


@router.delete("/connections/{connection_id}")
def delete_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_connection_allowed(db, connection_id, user)
    profile.status = "deleted"
    profile.updated_at = app_now()
    db.commit()
    return {"deleted": connection_id}


@router.post("/connections/{connection_id}/check")
def check_saved_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_connection_allowed(db, connection_id, user)
    try:
        result = check_profile(profile)
        db.commit()
        return result
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connections/{connection_id}/catalog/sync")
def synchronize_catalog(
    connection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_connection_allowed(db, connection_id, user)
    try:
        snapshot = sync_catalog(db, profile)
        return catalog_to_dict(snapshot)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connections/{connection_id}/catalog")
def get_catalog(
    connection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_connection_allowed(db, connection_id, user)
    snapshot = latest_catalog(db, connection_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Metadata has not been synchronized")
    return catalog_to_dict(snapshot)


@router.post("/sql-assistant/generate")
def generate_sql(
    payload: SqlAssistantGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = get_connection_allowed(db, payload.connection_id, user)
    snapshot = latest_catalog(db, profile.id)
    if not snapshot:
        try:
            snapshot = sync_catalog(db, profile)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        candidate = generate_candidate(
            db, user, profile, snapshot, payload.requirement.strip()
        )
        return candidate_to_dict(candidate)
    except SqlAssistantUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SqlPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sql-assistant/{candidate_id}/preview")
def preview_sql(
    candidate_id: int,
    payload: SqlAssistantPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    candidate = _candidate_allowed(db, candidate_id, user)
    try:
        return preview_candidate(candidate, candidate.connection, payload.limit)
    except (RuntimeError, SqlPolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sql-assistant/{candidate_id}/approve")
def approve_sql(
    candidate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    candidate = _candidate_allowed(db, candidate_id, user)
    approve_candidate(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate_to_dict(candidate)


def _candidate_allowed(
    db: Session, candidate_id: int, user: User
) -> SqlAssistantCandidate:
    candidate = (
        db.query(SqlAssistantCandidate)
        .filter(SqlAssistantCandidate.id == candidate_id)
        .first()
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="SQL candidate not found")
    if candidate.user_id != user.id and not is_admin(user):
        raise HTTPException(status_code=403, detail="You cannot access this SQL candidate")
    return candidate
