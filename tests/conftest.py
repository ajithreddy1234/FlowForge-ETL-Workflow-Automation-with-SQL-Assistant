"""Hermetic test configuration; never load a developer's credentials."""
import os
from pathlib import Path
from dotenv import dotenv_values
for key, value in dotenv_values(Path(__file__).resolve().parents[1] / ".env.example").items():
    if value is not None:
        os.environ.setdefault(key, value)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["PASSWORD_PEPPER"] = "test-only-pepper"
os.environ["APP_SECRET_KEY"] = "test-only-key"
os.environ["FLOWFORGE_DEMO"] = "false"
