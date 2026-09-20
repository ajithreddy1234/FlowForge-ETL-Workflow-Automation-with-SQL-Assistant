import json
import logging
import math
import re
from decimal import Decimal

import httpx
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from api.connection_profiles import profile_uri
from api.database import (
    CatalogSnapshot,
    ConnectionProfile,
    SqlAssistantCandidate,
    User,
    app_now,
)
from api.executor import _apply_statement_timeout, _database_error_message
from api.sql_guardrails import SqlPolicyError, validate_read_only_sql
from src.config import (
    OLLAMA_BASE_URL,
    OLLAMA_SQL_MODEL,
    SQL_ASSISTANT_PROVIDER,
    SQL_ASSISTANT_SCHEMA_TABLE_LIMIT,
    SQL_ASSISTANT_TIMEOUT_SECONDS,
    get_engine_kwargs,
)

logger = logging.getLogger(__name__)


class SqlAssistantUnavailable(RuntimeError):
    pass


def generate_candidate(
    db: Session,
    user: User,
    profile: ConnectionProfile,
    snapshot: CatalogSnapshot,
    requirement: str,
) -> SqlAssistantCandidate:
    ranked_tables = _rank_tables(snapshot, requirement)
    schema_context = _schema_context(snapshot, ranked_tables)
    raw_sql = _generate_sql(requirement, profile.db_type, schema_context, ranked_tables)
    allowed = {(table.schema_name, table.table_name) for table in snapshot.tables}

    try:
        validation = validate_read_only_sql(raw_sql, profile.db_type, allowed)
    except SqlPolicyError as exc:
        candidate = SqlAssistantCandidate(
            connection_id=profile.id,
            catalog_snapshot_id=snapshot.id,
            user_id=user.id,
            requirement=requirement,
            generated_sql=_extract_sql(raw_sql),
            explanation="The generated query was rejected by the SQL policy engine.",
            referenced_tables_json="[]",
            status="rejected",
            validation_error=str(exc),
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        raise SqlPolicyError(str(exc)) from exc

    explanation = (
        "Generated from catalog metadata. It reads only from: "
        + ", ".join(validation.referenced_tables)
        + ". Review the filters, joins, and aggregations before approving it."
    )
    candidate = SqlAssistantCandidate(
        connection_id=profile.id,
        catalog_snapshot_id=snapshot.id,
        user_id=user.id,
        requirement=requirement.strip(),
        generated_sql=validation.sql,
        explanation=explanation,
        referenced_tables_json=json.dumps(validation.referenced_tables),
        status="draft",
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def preview_candidate(
    candidate: SqlAssistantCandidate,
    profile: ConnectionProfile,
    limit: int,
) -> dict:
    snapshot = candidate.catalog_snapshot
    allowed = {(table.schema_name, table.table_name) for table in snapshot.tables}
    validation = validate_read_only_sql(candidate.generated_sql, profile.db_type, allowed)
    preview_sql = (
        "SELECT * FROM (\n"
        + validation.sql.rstrip(";")
        + f"\n) AS sql_assistant_preview LIMIT {int(limit)}"
    )

    uri = profile_uri(profile)
    engine = create_engine(uri, pool_pre_ping=True, **get_engine_kwargs(uri))
    try:
        with engine.connect() as connection:
            _apply_statement_timeout(connection, uri)
            # EXPLAIN catches most semantic and permission errors without reading rows.
            connection.execute(text(f"EXPLAIN {validation.sql}"))
            frame = pd.read_sql(text(preview_sql), connection)
    except Exception as exc:
        raise RuntimeError(_database_error_message(exc)) from exc
    finally:
        engine.dispose()

    return {
        "columns": frame.columns.tolist(),
        "rows": _safe_rows(frame),
        "total_rows": len(frame),
        "limited": len(frame) >= limit,
    }


def approve_candidate(candidate: SqlAssistantCandidate) -> SqlAssistantCandidate:
    candidate.status = "approved"
    candidate.approved_at = app_now()
    return candidate


def candidate_to_dict(candidate: SqlAssistantCandidate) -> dict:
    try:
        tables = json.loads(candidate.referenced_tables_json or "[]")
    except json.JSONDecodeError:
        tables = []
    return {
        "id": candidate.id,
        "connection_id": candidate.connection_id,
        "catalog_snapshot_id": candidate.catalog_snapshot_id,
        "requirement": candidate.requirement,
        "sql": candidate.generated_sql,
        "explanation": candidate.explanation,
        "referenced_tables": tables,
        "status": candidate.status,
        "validation_error": candidate.validation_error,
        "approved_at": candidate.approved_at.isoformat() if candidate.approved_at else None,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


def _generate_sql(
    requirement: str,
    dialect: str,
    schema_context: str,
    ranked_tables: list,
) -> str:
    if SQL_ASSISTANT_PROVIDER == "heuristic":
        return _heuristic_sql(requirement, ranked_tables)
    if SQL_ASSISTANT_PROVIDER != "ollama":
        raise SqlAssistantUnavailable(
            "SQL assistant is disabled. Set SQL_ASSISTANT_PROVIDER=ollama or heuristic."
        )

    prompt = f"""### Task
Generate one read-only {dialect} SQL query that answers the user's requirement.
Use only tables and columns from the supplied schema. Never invent identifiers.
Return SQL only. Do not use INSERT, UPDATE, DELETE, DDL, procedures, temp tables,
file exports, or more than one statement. Qualify every table with its schema.

[QUESTION]
{requirement.strip()}
[/QUESTION]

### Database Schema
{schema_context}

### Answer
[SQL]
"""
    try:
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_SQL_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 900},
            },
            timeout=SQL_ASSISTANT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        generated = response.json().get("response", "")
    except (httpx.HTTPError, ValueError) as exc:
        raise SqlAssistantUnavailable(
            "The local SQL model is unavailable. Start Ollama and run "
            f"`ollama pull {OLLAMA_SQL_MODEL}`. No paid API key is required."
        ) from exc
    return _extract_sql(generated)


def _rank_tables(snapshot: CatalogSnapshot, requirement: str) -> list:
    terms = set(_tokens(requirement))
    scored = []
    for table in snapshot.tables:
        table_terms = set(_tokens(f"{table.schema_name} {table.table_name} {table.table_comment or ''}"))
        column_terms = set()
        for column in table.columns:
            column_terms.update(_tokens(f"{column.column_name} {column.column_comment or ''}"))
        score = len(terms & table_terms) * 6 + len(terms & column_terms) * 2
        for term in terms:
            if term and term in table.table_name.lower():
                score += 3
        scored.append((score, table.schema_name, table.table_name, table))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    selected = [item[3] for item in scored[:SQL_ASSISTANT_SCHEMA_TABLE_LIMIT]]
    return selected


def _schema_context(snapshot: CatalogSnapshot, tables: list) -> str:
    selected = {(table.schema_name, table.table_name) for table in tables}
    lines = []
    for table in tables:
        column_lines = []
        for column in sorted(table.columns, key=lambda item: item.ordinal_position):
            flags = []
            if column.is_primary_key:
                flags.append("PRIMARY KEY")
            if not column.is_nullable:
                flags.append("NOT NULL")
            suffix = f" {' '.join(flags)}" if flags else ""
            comment = f" -- {column.column_comment}" if column.column_comment else ""
            column_lines.append(
                f"  {column.column_name} {column.data_type}{suffix}{comment}"
            )
        lines.append(
            f"TABLE {table.schema_name}.{table.table_name} (\n"
            + ",\n".join(column_lines)
            + "\n);"
        )
    relationships = []
    for relation in snapshot.relationships:
        source = (relation.source_schema, relation.source_table)
        target = (relation.target_schema, relation.target_table)
        if source in selected or target in selected:
            relationships.append(
                f"FOREIGN KEY {relation.source_schema}.{relation.source_table}.{relation.source_column} "
                f"REFERENCES {relation.target_schema}.{relation.target_table}.{relation.target_column}"
            )
    if relationships:
        lines.append("RELATIONSHIPS:\n" + "\n".join(relationships))
    return "\n\n".join(lines)


def _heuristic_sql(requirement: str, tables: list) -> str:
    if not tables:
        raise SqlAssistantUnavailable("The metadata catalog contains no usable tables")
    table = tables[0]
    qualified = f"{table.schema_name}.{table.table_name}"
    lowered = requirement.lower()
    if any(word in lowered for word in ("count", "how many", "number of")):
        return f"SELECT COUNT(*) AS row_count\nFROM {qualified}"
    columns = [column.column_name for column in table.columns[:8]]
    projection = ",\n  ".join(columns) if columns else "*"
    return f"SELECT\n  {projection}\nFROM {qualified}"


def _extract_sql(value: str) -> str:
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", value or "", flags=re.I | re.S)
    clean = fenced.group(1) if fenced else (value or "")
    clean = clean.replace("[SQL]", "").replace("[/SQL]", "").strip()
    select_match = re.search(r"\b(SELECT|WITH)\b", clean, flags=re.I)
    if select_match:
        clean = clean[select_match.start() :]
    return clean.strip().rstrip(";")


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", (value or "").lower())
        if len(token) > 2
    ]


def _safe_rows(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in frame.iterrows():
        clean = {}
        for key, value in row.items():
            if pd.isna(value):
                clean[key] = None
            elif isinstance(value, Decimal):
                clean[key] = float(value)
            elif isinstance(value, bytes):
                clean[key] = value.decode("utf-8", errors="replace")
            elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                clean[key] = None
            elif hasattr(value, "isoformat"):
                clean[key] = value.isoformat()
            elif hasattr(value, "item"):
                clean[key] = value.item()
            else:
                clean[key] = value
        rows.append(clean)
    return rows
