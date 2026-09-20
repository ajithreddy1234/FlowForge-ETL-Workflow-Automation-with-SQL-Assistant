from sqlalchemy import create_engine, text

from src.config import get_connection_uri_from_fields, get_engine_kwargs


def check_database_connection(config) -> dict:
    db_type = config.db_type
    host = config.host.strip()
    database = config.database.strip()
    username = config.username.strip()
    password = config.password or ""
    port = config.port

    uri = get_connection_uri_from_fields(
        db_type=db_type,
        host=host,
        port=port,
        database=database,
        user=username,
        password=password,
    )
    engine = create_engine(uri, pool_pre_ping=True, **get_engine_kwargs(uri))
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(_database_error_message(exc)) from exc
    finally:
        engine.dispose()

    return {"ok": True, "message": "Database connection successful"}


def _database_error_message(exc: Exception) -> str:
    raw = str(exc)
    lowered = raw.lower()
    if "access denied for user" in lowered or "(1045" in lowered:
        return (
            "Database login failed. Check the DB username/password and confirm "
            "the database user can connect from this machine/IP."
        )
    if "could not translate host name" in lowered or "name or service not known" in lowered:
        return "Database host could not be resolved. Check the host name."
    if "connection refused" in lowered or "timed out" in lowered:
        return "Database server is not reachable. Check host, port, VPN/firewall, and database availability."
    return raw
