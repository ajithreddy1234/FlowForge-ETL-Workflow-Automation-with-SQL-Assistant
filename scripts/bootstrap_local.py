"""Idempotent local setup: demo retail source data, a read-only role, an admin user and a
ready-to-use connection profile with a scanned catalog.

    python -m scripts.bootstrap_local

Environment:
    LOCAL_ADMIN_LOGIN / LOCAL_ADMIN_PASSWORD  admin account to create (password >= 12 chars)
    DEMO_SOURCE_ADMIN_URL   superuser URL of the demo source DB (used to seed + create the role)
    DEMO_SOURCE_HOST/PORT/DB  how the app reaches the demo DB
    DEMO_READONLY_USER / DEMO_READONLY_PASSWORD  least-privilege account the app connects with
    DEMO_MYSQL_ADMIN_URL    optional: also seed a MySQL demo source
"""
from __future__ import annotations

import os
import re
import time

from sqlalchemy import create_engine, inspect, text

from api.catalog_service import sync_catalog
from api.crypto import encrypt_secret
from api.database import ConnectionProfile, SessionLocal, User, app_now, hash_password
from scripts.demo_retail import build


def _wait(url: str, attempts: int = 30):
    for _ in range(attempts):
        try:
            with create_engine(url).connect():
                return
        except Exception:  # noqa: BLE001
            time.sleep(2)
    raise SystemExit(f"Demo database not reachable: {url.split('@')[-1]}")


_SAFE = re.compile(r"^[A-Za-z0-9_.\-]{8,64}$")


def seed_source(admin_url: str, ro_user: str, ro_password: str, dialect: str) -> None:
    # DDL cannot take bind parameters, so only allow characters that need no escaping
    if not re.fullmatch(r"[a-z_][a-z0-9_]{2,40}", ro_user) or not _SAFE.fullmatch(ro_password):
        raise SystemExit("DEMO_READONLY_USER must be lowercase letters/digits/_ and DEMO_READONLY_PASSWORD "
                         "8-64 chars of letters, digits, '.', '_' or '-'")
    _wait(admin_url)
    engine = create_engine(admin_url)
    if "customers" not in inspect(engine).get_table_names():
        build(admin_url)
    with engine.begin() as c:
        if dialect == "postgresql":
            exists = c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :u"), {"u": ro_user}).scalar()
            if not exists:
                c.execute(text(f"CREATE ROLE \"{ro_user}\" LOGIN PASSWORD '{ro_password}'"))
            c.execute(text(f'GRANT USAGE ON SCHEMA public TO "{ro_user}"'))
            c.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{ro_user}"'))
            c.execute(text(f'ALTER ROLE "{ro_user}" SET default_transaction_read_only = on'))
        else:
            c.execute(text(f"CREATE USER IF NOT EXISTS '{ro_user}'@'%' IDENTIFIED BY '{ro_password}'"))
            db = engine.url.database
            c.execute(text(f"GRANT SELECT ON `{db}`.* TO '{ro_user}'@'%'"))


def ensure_admin(db) -> User:
    login = os.getenv("LOCAL_ADMIN_LOGIN", "admin").strip()
    password = os.getenv("LOCAL_ADMIN_PASSWORD", "")
    user = db.query(User).filter_by(login_id=login).first()
    if user:
        return user
    if len(password) < 12:
        raise SystemExit("Set LOCAL_ADMIN_PASSWORD (at least 12 characters) in .env")
    user = User(login_id=login, display_name="Local admin", role="admin", is_active=True,
                password_hash=hash_password(password), created_at=app_now())
    db.add(user)
    db.commit()
    print(f"created admin user '{login}'")
    return user


def ensure_profile(db, owner: User, name: str, db_type: str, host: str, port: str, database: str,
                   username: str, password: str) -> None:
    profile = db.query(ConnectionProfile).filter_by(created_by_user_id=owner.id, name=name).first()
    if not profile:
        profile = ConnectionProfile(created_by_user_id=owner.id, name=name, db_type=db_type, host=host, port=port,
                                    database_name=database, username=username,
                                    encrypted_password=encrypt_secret(password), allowed_schemas_json="[]",
                                    status="active", created_at=app_now(), updated_at=app_now())
        db.add(profile)
        db.commit()
        print(f"created connection '{name}'")
    if not profile.catalog_snapshots:
        snapshot = sync_catalog(db, profile)
        print(f"scanned catalog for '{name}': {len(snapshot.tables)} tables")


def main():
    ro_user = os.getenv("DEMO_READONLY_USER", "flowforge_ro")
    ro_password = os.getenv("DEMO_READONLY_PASSWORD", "readonly-demo-pass")
    pg_admin = os.getenv("DEMO_SOURCE_ADMIN_URL")
    mysql_admin = os.getenv("DEMO_MYSQL_ADMIN_URL")
    with SessionLocal() as db:
        admin = ensure_admin(db)
        if pg_admin:
            seed_source(pg_admin, ro_user, ro_password, "postgresql")
            ensure_profile(db, admin, "Demo retail (PostgreSQL)", "postgresql", os.getenv("DEMO_SOURCE_HOST", "demo-db"),
                           os.getenv("DEMO_SOURCE_PORT", "5432"), os.getenv("DEMO_SOURCE_DB", "retail"), ro_user, ro_password)
        if mysql_admin:
            seed_source(mysql_admin, ro_user, ro_password, "mysql")
            ensure_profile(db, admin, "Demo retail (MySQL)", "mysql", os.getenv("DEMO_MYSQL_HOST", "demo-mysql"),
                           os.getenv("DEMO_MYSQL_PORT", "3306"), os.getenv("DEMO_MYSQL_DB", "retail"), ro_user, ro_password)
    print("local bootstrap complete")


if __name__ == "__main__":
    main()
