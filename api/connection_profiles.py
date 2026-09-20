import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.connection_checker import check_database_connection
from api.crypto import decrypt_secret
from api.database import ConnectionProfile, User, app_now, is_admin
from api.models import DBConnectionRequest
from src.config import get_connection_uri_from_fields


def get_connection_allowed(
    db: Session, connection_id: int, user: User
) -> ConnectionProfile:
    profile = (
        db.query(ConnectionProfile)
        .filter(ConnectionProfile.id == connection_id)
        .first()
    )
    if not profile or profile.status == "deleted":
        raise HTTPException(status_code=404, detail="Connection not found")
    if profile.created_by_user_id != user.id and not is_admin(user):
        raise HTTPException(status_code=403, detail="You cannot use this connection")
    return profile


def profile_password(profile: ConnectionProfile) -> str:
    return decrypt_secret(profile.encrypted_password)


def profile_uri(profile: ConnectionProfile) -> str:
    return get_connection_uri_from_fields(
        db_type=profile.db_type,
        host=profile.host,
        port=profile.port,
        database=profile.database_name,
        user=profile.username,
        password=profile_password(profile),
    )


def check_profile(profile: ConnectionProfile) -> dict:
    result = check_database_connection(
        DBConnectionRequest(
            db_type=profile.db_type,
            host=profile.host,
            port=profile.port,
            database=profile.database_name,
            username=profile.username,
            password=profile_password(profile),
        )
    )
    profile.last_checked_at = app_now()
    profile.updated_at = app_now()
    return result


def allowed_schemas(profile: ConnectionProfile) -> list[str]:
    try:
        values = json.loads(profile.allowed_schemas_json or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in values if str(item).strip()]


def connection_to_dict(profile: ConnectionProfile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "db_type": profile.db_type,
        "host": profile.host,
        "port": profile.port,
        "database": profile.database_name,
        "username": profile.username,
        "allowed_schemas": allowed_schemas(profile),
        "status": profile.status,
        "last_checked_at": _iso(profile.last_checked_at),
        "created_at": _iso(profile.created_at),
        "updated_at": _iso(profile.updated_at),
        "created_by_user_id": profile.created_by_user_id,
        "created_by": profile.created_by.display_name if profile.created_by else "",
    }


def _iso(value):
    return value.isoformat() if value else None
