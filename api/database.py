import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    UniqueConstraint,
)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from src.config import APP_TIMEZONE as APP_TIMEZONE_NAME
from src.config import DATABASE_URL, PASSWORD_PEPPER, PROJECT_ROOT, SESSION_TTL_DAYS

APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    parsed_url = make_url(DATABASE_URL)
    sqlite_database = parsed_url.database
    if sqlite_database and sqlite_database != ":memory:":
        sqlite_path = Path(sqlite_database)
        if not sqlite_path.is_absolute():
            sqlite_path = PROJECT_ROOT / sqlite_path
        if not sqlite_path.exists() and os.getenv("ALLOW_MISSING_DATABASE") != "true":
            raise RuntimeError(
                f"SQLite app DB does not exist: {sqlite_path}. "
                "Provide an existing application database before starting the backend."
            )
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, future=True, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=2)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    login_id = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(120), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: app_now(), nullable=False
    )


class ConnectionProfile(Base):
    """Server-side source connection.

    The browser only receives non-secret connection metadata. Passwords are
    encrypted with APP_SECRET_KEY and are decrypted only inside a worker or a
    bounded preview request.
    """

    __tablename__ = "connection_profiles"
    __table_args__ = (
        UniqueConstraint(
            "created_by_user_id",
            "name",
            name="uq_connection_profiles_owner_name",
        ),
    )

    id = Column(Integer, primary_key=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    db_type = Column(String(20), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(String(12), nullable=True)
    database_name = Column(String(120), nullable=False)
    username = Column(String(120), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    allowed_schemas_json = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="active", index=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)

    created_by = relationship("User")
    catalog_snapshots = relationship(
        "CatalogSnapshot", cascade="all, delete-orphan", back_populates="connection"
    )


class CatalogSnapshot(Base):
    __tablename__ = "catalog_snapshots"

    id = Column(Integer, primary_key=True)
    connection_id = Column(
        Integer, ForeignKey("connection_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(String(20), nullable=False, default="ready", index=True)
    dialect = Column(String(20), nullable=False)
    table_count = Column(Integer, nullable=False, default=0)
    column_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)

    connection = relationship("ConnectionProfile", back_populates="catalog_snapshots")
    tables = relationship(
        "CatalogTable", cascade="all, delete-orphan", back_populates="snapshot"
    )
    relationships = relationship(
        "CatalogRelationship", cascade="all, delete-orphan", back_populates="snapshot"
    )


class CatalogTable(Base):
    __tablename__ = "catalog_tables"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "schema_name", "table_name", name="uq_catalog_table_identity"
        ),
    )

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(
        Integer, ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schema_name = Column(String(160), nullable=False)
    table_name = Column(String(200), nullable=False)
    table_type = Column(String(40), nullable=False, default="table")
    table_comment = Column(Text, nullable=True)

    snapshot = relationship("CatalogSnapshot", back_populates="tables")
    columns = relationship(
        "CatalogColumn", cascade="all, delete-orphan", back_populates="table"
    )


class CatalogColumn(Base):
    __tablename__ = "catalog_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "column_name", name="uq_catalog_column_identity"),
    )

    id = Column(Integer, primary_key=True)
    table_id = Column(
        Integer, ForeignKey("catalog_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_name = Column(String(200), nullable=False)
    data_type = Column(String(160), nullable=False)
    is_nullable = Column(Boolean, nullable=False, default=True)
    ordinal_position = Column(Integer, nullable=False, default=0)
    is_primary_key = Column(Boolean, nullable=False, default=False)
    column_comment = Column(Text, nullable=True)

    table = relationship("CatalogTable", back_populates="columns")


class CatalogRelationship(Base):
    __tablename__ = "catalog_relationships"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(
        Integer, ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_schema = Column(String(160), nullable=False)
    source_table = Column(String(200), nullable=False)
    source_column = Column(String(200), nullable=False)
    target_schema = Column(String(160), nullable=False)
    target_table = Column(String(200), nullable=False)
    target_column = Column(String(200), nullable=False)
    constraint_name = Column(String(200), nullable=True)

    snapshot = relationship("CatalogSnapshot", back_populates="relationships")


class SqlAssistantCandidate(Base):
    __tablename__ = "sql_assistant_candidates"

    id = Column(Integer, primary_key=True)
    connection_id = Column(Integer, ForeignKey("connection_profiles.id"), nullable=False, index=True)
    catalog_snapshot_id = Column(Integer, ForeignKey("catalog_snapshots.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    requirement = Column(Text, nullable=False)
    generated_sql = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    referenced_tables_json = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="draft", index=True)
    validation_error = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)

    connection = relationship("ConnectionProfile")
    catalog_snapshot = relationship("CatalogSnapshot")
    user = relationship("User")


class ExtractCheckpoint(Base):
    """Last successfully loaded high-water value for a scheduled extract."""

    __tablename__ = "extract_checkpoints"
    __table_args__ = (
        UniqueConstraint("schedule_id", "extract_node_id", name="uq_extract_checkpoint_scope"),
    )

    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("pipeline_schedules.id", ondelete="CASCADE"), nullable=False, index=True)
    extract_node_id = Column(String(120), nullable=False)
    value_json = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: app_now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    login_id = Column(String(80), nullable=False, index=True)
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String(160), nullable=True)
    ip_address = Column(String(80), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: app_now(), nullable=False
    )


class SavedPipeline(Base):
    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True)
    slug = Column(String(160), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    pipeline_json = Column(Text, nullable=False)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    last_edited_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: app_now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), default=lambda: app_now(), nullable=False
    )

    created_by = relationship("User", foreign_keys=[created_by_user_id])
    last_edited_by = relationship("User", foreign_keys=[last_edited_by_user_id])
    versions = relationship(
        "PipelineVersion", cascade="all, delete-orphan", back_populates="pipeline"
    )


class PipelineVersion(Base):
    __tablename__ = "pipeline_versions"
    __table_args__ = (
        UniqueConstraint(
            "pipeline_id", "version_number", name="uq_pipeline_version_number"
        ),
    )

    id = Column(Integer, primary_key=True)
    pipeline_id = Column(
        Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number = Column(Integer, nullable=False)
    pipeline_json = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="published", index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)

    pipeline = relationship("SavedPipeline", back_populates="versions")
    created_by = relationship("User")


class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id = Column(Integer, primary_key=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String(40), nullable=False)
    old_name = Column(String(200), nullable=True)
    new_name = Column(String(200), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: app_now(), nullable=False
    )


class PipelineSchedule(Base):
    __tablename__ = "pipeline_schedules"

    id = Column(Integer, primary_key=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id"), nullable=False, index=True)
    pipeline_version_id = Column(
        Integer, ForeignKey("pipeline_versions.id"), nullable=True, index=True
    )
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    status = Column(String(20), default="active", nullable=False, index=True)
    trigger_type = Column(String(20), default="cron", nullable=False)
    day_of_week = Column(String(80), nullable=False)
    hour = Column(Integer, nullable=False)
    minute = Column(Integer, nullable=False)
    timezone = Column(String(80), nullable=False)
    apscheduler_job_id = Column(String(160), unique=True, nullable=False, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(20), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)

    pipeline = relationship("SavedPipeline")
    pipeline_version = relationship("PipelineVersion")
    created_by = relationship("User")


class ScheduleRunLog(Base):
    __tablename__ = "schedule_run_logs"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "scheduled_for",
            name="uq_schedule_run_logs_schedule_scheduled_for",
        ),
    )

    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey("pipeline_schedules.id"), nullable=False, index=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    queued_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    worker_id = Column(String(160), nullable=True, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    rows_written = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: app_now(), nullable=False)

    schedule = relationship("PipelineSchedule")
    pipeline = relationship("SavedPipeline")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def app_now() -> datetime:
    return datetime.now(APP_TIMEZONE)


def cleanup_expired_sessions(db: Session):
    now = app_now()
    db.query(UserSession).filter(UserSession.expires_at < now).delete()
    db.query(UserSession).filter(UserSession.revoked_at.isnot(None)).delete()
    db.commit()


def hash_password(password: str) -> str:
    value = f"{PASSWORD_PEPPER}:{password}"
    return f"argon2id${PASSWORD_HASHER.hash(value)}"


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("argon2id$"):
        encoded_hash = stored_hash.split("$", 1)[1]
        try:
            return PASSWORD_HASHER.verify(
                encoded_hash,
                f"{PASSWORD_PEPPER}:{password}",
            )
        except (VerifyMismatchError, InvalidHashError):
            return False

    # Existing users can sign in once with a legacy hash. The login route then
    # transparently upgrades their password to Argon2id.
    try:
        method, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if method != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        f"{PASSWORD_PEPPER}:{password}".encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return hmac.compare_digest(digest, expected)


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=app_now() + timedelta(days=SESSION_TTL_DAYS),
        )
    )
    db.commit()
    return token


def revoke_session(db: Session, token: str):
    session = (
        db.query(UserSession)
        .filter(UserSession.token_hash == hash_token(token))
        .first()
    )
    if session and not session.revoked_at:
        session.revoked_at = app_now()
        db.commit()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "login_id": user.login_id,
        "display_name": user.display_name,
        "role": user.role,
    }


def is_admin(user: User) -> bool:
    return (user.role or "").lower() == "admin"


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    return get_user_from_token(db, token)


def get_user_from_token(db: Session, token: str) -> User:
    session = (
        db.query(UserSession)
        .filter(UserSession.token_hash == hash_token(token))
        .first()
    )
    now = app_now()
    if not session or session.revoked_at:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = _as_aware(session.expires_at)
    if expires_at < now:
        raise HTTPException(status_code=401, detail="Session expired")
    if not session.user or not session.user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return session.user


def get_token_from_request(request: Request) -> str | None:
    return _extract_bearer_token(request.headers.get("Authorization"))


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
