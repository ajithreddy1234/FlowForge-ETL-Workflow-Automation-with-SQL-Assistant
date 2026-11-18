"""Single-service entry point for the synthetic, public portfolio sandbox."""
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault("FLOWFORGE_DEMO", "true")
if os.environ["FLOWFORGE_DEMO"] == "true":
    defaults = {
        "DATABASE_URL": "sqlite:///./runtime/app.db", "ALLOW_MISSING_DATABASE": "true",
        "APP_TIMEZONE": "Asia/Kolkata", "SESSION_TTL_DAYS": "1",
        "APP_CORS_ORIGINS": "http://localhost:8000", "APP_CORS_METHODS": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
        "APP_CORS_HEADERS": "Authorization,Content-Type", "SCHEDULER_TRIGGER_WORKERS": "1",
        "SCHEDULER_RUN_WORKERS": "1", "SCHEDULE_JOB_MAX_INSTANCES": "1",
        "SCHEDULE_MISFIRE_GRACE_SECONDS": "300", "SCHEDULE_STALE_RUNNING_MINUTES": "5",
        "LOG_LEVEL": "INFO", "SOURCE_DB_CONNECT_TIMEOUT_SECONDS": "5",
        "SOURCE_DB_QUERY_TIMEOUT_SECONDS": "5", "PREVIEW_SQL_LIMIT": "100",
        "ALLOW_UNSAFE_SQL": "false", "REDSHIFT_SSL": "true", "REDSHIFT_SSLMODE": "verify-full",
        "GOOGLE_SERVICE_ACCOUNT_FILE": "unused-in-public-demo.json", "RUN_EMBEDDED_SCHEDULER": "true",
    }
    Path("runtime").mkdir(exist_ok=True)
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    # Persist across restarts when a persistent volume is mounted; never commit keys.
    for key in ("PASSWORD_PEPPER", "APP_SECRET_KEY"):
        path = Path("runtime") / key.lower()
        if not path.exists():
            path.write_text(secrets.token_urlsafe(48))
            path.chmod(0o600)
        os.environ.setdefault(key, path.read_text().strip())

from alembic.config import Config
from alembic import command
command.upgrade(Config(str(ROOT / "alembic.ini")), "head")

if os.environ["FLOWFORGE_DEMO"] == "true":
    from api.public_demo import seed_demo
    seed_demo()

import uvicorn
uvicorn.run("api.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), ws_max_size=65536)
