"""Validated runtime configuration loaded from the Job_Scheduler .env file."""

import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set in .env or the process environment")
    return value


def _integer(name: str, minimum: int = 0) -> int:
    raw = _required(name)
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


def _boolean(name: str) -> bool:
    raw = _required(name).lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false")


def _optional_boolean(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false")


def _optional_integer(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


def _csv(name: str) -> list[str]:
    values = [item.strip() for item in _required(name).split(",") if item.strip()]
    if not values:
        raise RuntimeError(f"{name} must contain at least one value")
    return values


DATABASE_URL = _required("DATABASE_URL")
APP_TIMEZONE = _required("APP_TIMEZONE")
PASSWORD_PEPPER = _required("PASSWORD_PEPPER")
APP_SECRET_KEY = _required("APP_SECRET_KEY")
SESSION_TTL_DAYS = _integer("SESSION_TTL_DAYS", 1)
LOGIN_MAX_FAILURES = _optional_integer("LOGIN_MAX_FAILURES", 10, 1)
LOGIN_FAILURE_WINDOW_MINUTES = _optional_integer(
    "LOGIN_FAILURE_WINDOW_MINUTES", 15, 1
)

APP_CORS_ORIGINS = _csv("APP_CORS_ORIGINS")
APP_CORS_METHODS = _csv("APP_CORS_METHODS")
APP_CORS_HEADERS = _csv("APP_CORS_HEADERS")

SCHEDULER_TRIGGER_WORKERS = _integer("SCHEDULER_TRIGGER_WORKERS", 1)
SCHEDULER_RUN_WORKERS = _integer("SCHEDULER_RUN_WORKERS", 1)
SCHEDULE_JOB_MAX_INSTANCES = _integer("SCHEDULE_JOB_MAX_INSTANCES", 1)
SCHEDULE_MISFIRE_GRACE_SECONDS = _integer("SCHEDULE_MISFIRE_GRACE_SECONDS", 1)
SCHEDULE_STALE_RUNNING_MINUTES = _integer("SCHEDULE_STALE_RUNNING_MINUTES", 0)
SCHEDULE_RUN_MAX_ATTEMPTS = _optional_integer("SCHEDULE_RUN_MAX_ATTEMPTS", 3, 1)

LOG_LEVEL = _required("LOG_LEVEL").upper()
SOURCE_DB_CONNECT_TIMEOUT_SECONDS = _integer("SOURCE_DB_CONNECT_TIMEOUT_SECONDS", 1)
SOURCE_DB_QUERY_TIMEOUT_SECONDS = _integer("SOURCE_DB_QUERY_TIMEOUT_SECONDS", 1)
PREVIEW_SQL_LIMIT = _integer("PREVIEW_SQL_LIMIT", 1)
ALLOW_UNSAFE_SQL = _boolean("ALLOW_UNSAFE_SQL")
REDSHIFT_SSL = _boolean("REDSHIFT_SSL")
REDSHIFT_SSLMODE = _required("REDSHIFT_SSLMODE")

GOOGLE_SERVICE_ACCOUNT_FILE = PROJECT_ROOT / _required("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_SHEETS_MAX_RETRIES = _optional_integer("GOOGLE_SHEETS_MAX_RETRIES", 3, 0)

# Production services are optional so existing local .env files remain valid.
# In Docker/production the scheduler and worker run as separate processes.
RUN_EMBEDDED_SCHEDULER = _optional_boolean("RUN_EMBEDDED_SCHEDULER", True)
SQL_ASSISTANT_PROVIDER = os.getenv("SQL_ASSISTANT_PROVIDER", "ollama").strip().lower()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
OLLAMA_SQL_MODEL = os.getenv("OLLAMA_SQL_MODEL", "sqlcoder:7b").strip()
SQL_ASSISTANT_TIMEOUT_SECONDS = _optional_integer(
    "SQL_ASSISTANT_TIMEOUT_SECONDS", 180, 1
)
# Hosted LLM provider (any OpenAI-compatible endpoint; OpenRouter by default)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
LLM_API_KEY = (os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini").strip()
SQL_ASSISTANT_MAX_ATTEMPTS = _optional_integer("SQL_ASSISTANT_MAX_ATTEMPTS", 3, 1)
# Local development sink: a Load node whose sheet is "csv://<name>" writes CSV files here
LOCAL_CSV_OUTPUT_DIR = os.getenv("LOCAL_CSV_OUTPUT_DIR", "").strip()
CATALOG_MAX_TABLES = _optional_integer("CATALOG_MAX_TABLES", 250, 1)
CATALOG_MAX_COLUMNS_PER_TABLE = _optional_integer(
    "CATALOG_MAX_COLUMNS_PER_TABLE", 250, 1
)
SQL_ASSISTANT_SCHEMA_TABLE_LIMIT = _optional_integer(
    "SQL_ASSISTANT_SCHEMA_TABLE_LIMIT", 12, 1
)
SCHEDULE_WORKER_POLL_SECONDS = _optional_integer(
    "SCHEDULE_WORKER_POLL_SECONDS", 2, 1
)


def build_connection_uri(profile: dict) -> str:
    driver = profile["driver"]
    user = quote_plus(str(profile.get("user", "")))
    password = quote_plus(str(profile.get("password", "")))
    host = profile.get("host", "")
    port = profile.get("port", "")
    database = quote_plus(str(profile.get("database", "")))
    auth = f"{user}:{password}" if password else user
    uri = f"{driver}://{auth}@{host}:{port}/{database}"

    query = profile.get("query") or {}
    if query:
        params = "&".join(
            f"{quote_plus(str(k))}={quote_plus(str(v))}" for k, v in query.items()
        )
        uri = f"{uri}?{params}"
    return uri


def get_engine_kwargs(uri: str) -> dict:
    """Return SQLAlchemy create_engine kwargs required by a DB driver."""
    if uri.startswith("redshift+redshift_connector://"):
        connect_args = {
            "timeout": SOURCE_DB_CONNECT_TIMEOUT_SECONDS,
        }
        if not REDSHIFT_SSL:
            connect_args.update({"ssl": False, "sslmode": "disable"})
            return {"connect_args": connect_args}

        connect_args.update({
            "ssl": True,
            "sslmode": REDSHIFT_SSLMODE,
        })
        return {"connect_args": connect_args}

    if uri.startswith("mysql+pymysql://"):
        return {
            "connect_args": {
                "connect_timeout": SOURCE_DB_CONNECT_TIMEOUT_SECONDS,
                # Server-side max_execution_time cancels the query first; the socket
                # timeouts are only a backstop so a dropped client never hides a live query.
                "read_timeout": SOURCE_DB_QUERY_TIMEOUT_SECONDS + 10,
                "write_timeout": SOURCE_DB_QUERY_TIMEOUT_SECONDS + 10,
            }
        }

    if uri.startswith("postgresql+psycopg://"):
        return {
            "connect_args": {
                "connect_timeout": SOURCE_DB_CONNECT_TIMEOUT_SECONDS,
                "options": f"-c statement_timeout={SOURCE_DB_QUERY_TIMEOUT_SECONDS * 1000}",
            }
        }

    return {}


def get_connection_uri_from_fields(
    db_type: str,
    host: str,
    database: str,
    user: str,
    password: str = "",
    port: str | int | None = None,
) -> str:
    db_type = (db_type or "mysql").lower()
    drivers = {
        "mysql": ("mysql+pymysql", "3306", {"charset": "utf8mb4"}),
        "postgresql": ("postgresql+psycopg", "5432", {}),
        "redshift": ("redshift+redshift_connector", "5439", {}),
    }
    if db_type not in drivers:
        raise ValueError(
            f"Unsupported database type '{db_type}'. Use postgresql, mysql or redshift."
        )

    driver, default_port, query = drivers[db_type]
    return build_connection_uri(
        {
            "driver": driver,
            "host": host,
            "port": str(port or default_port),
            "database": database,
            "user": user,
            "password": password,
            "query": query,
        }
    )
