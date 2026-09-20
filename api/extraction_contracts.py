"""Validation and high-water query helpers for Extract nodes."""

import re
from datetime import date, datetime
from decimal import Decimal

import pandas as pd

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(value: str, dialect: str) -> str:
    if not IDENTIFIER.fullmatch(value or ""):
        raise ValueError(f"Invalid SQL identifier: {value!r}")
    marker = "`" if dialect == "mysql" else '"'
    return f"{marker}{value}{marker}"


def table_query(table_name: str, dialect: str) -> str:
    parts = (table_name or "").strip().split(".")
    if len(parts) not in (1, 2):
        raise ValueError("Select a table as table or schema.table")
    return "SELECT * FROM " + ".".join(quote_identifier(part, dialect) for part in parts)


def incremental_query(sql: str, column: str, checkpoint, dialect: str) -> str:
    key = quote_identifier(column, dialect)
    condition = "1 = 1" if checkpoint is None else f"{key} > :__flowforge_checkpoint"
    return f"SELECT * FROM (\n{sql.strip().rstrip(';')}\n) AS incremental_source WHERE {condition} ORDER BY {key}"


def validate_schema(frame: pd.DataFrame, expected_columns) -> None:
    expected = [item.strip() for item in expected_columns or [] if isinstance(item, str) and item.strip()]
    if len(expected) != len(set(expected)):
        raise ValueError("Expected column names must be unique")
    missing = [name for name in expected if name not in frame.columns]
    if missing:
        raise ValueError("Schema validation failed; missing columns: " + ", ".join(missing))


def checkpoint_value(frame: pd.DataFrame, column: str, kind: str):
    if column not in frame.columns:
        raise ValueError(f"Checkpoint column {column!r} is missing from query results")
    if frame[column].isna().any():
        raise ValueError("Checkpoint column contains null values")
    values = frame[column].dropna()
    if values.empty:
        return None
    if kind == "primary_key":
        if values.duplicated().any():
            raise ValueError("Primary-key checkpoint column has duplicate values")
        if not pd.api.types.is_integer_dtype(values.dtype):
            raise ValueError("Primary-key checkpoint must use an integer column")
        return int(values.max())
    if kind == "timestamp":
        parsed = pd.to_datetime(values, errors="raise", utc=True)
        if parsed.duplicated().any():
            raise ValueError("Timestamp checkpoint values must be unique; use an integer primary key for tied timestamps")
        return parsed.max().to_pydatetime()
    raise ValueError("Incremental mode must be primary_key or timestamp")


def encode_checkpoint(value):
    if isinstance(value, datetime):
        return {"type": "timestamp", "value": value.isoformat()}
    if isinstance(value, date):
        return {"type": "timestamp", "value": value.isoformat()}
    if isinstance(value, (int, float, Decimal)):
        return {"type": "number", "value": str(value)}
    raise ValueError("Unsupported checkpoint value type")


def decode_checkpoint(value):
    if value["type"] == "timestamp":
        return datetime.fromisoformat(value["value"])
    if value["type"] == "number":
        return int(value["value"])
    raise ValueError("Unsupported stored checkpoint type")
