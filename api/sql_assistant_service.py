import json
import logging
import math
import re
import time
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
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    OLLAMA_BASE_URL,
    SQL_ASSISTANT_MAX_ATTEMPTS,
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
    """Draft SQL from catalog metadata, then validate it.

    With a hosted model, guardrail rejections and EXPLAIN errors are sent back to the
    model so it can correct itself (up to SQL_ASSISTANT_MAX_ATTEMPTS drafts).
    """
    ranked_tables = _rank_tables(snapshot, requirement)
    schema_context = _schema_context(snapshot, ranked_tables)
    allowed = {(table.schema_name, table.table_name) for table in snapshot.tables}
    attempts = SQL_ASSISTANT_MAX_ATTEMPTS if SQL_ASSISTANT_PROVIDER in HOSTED_PROVIDERS else 1
    feedback: list[str] = []
    last_error = None
    raw_sql = ""

    for attempt in range(1, attempts + 1):
        raw_sql = _generate_sql(requirement, profile.db_type, schema_context, ranked_tables, feedback)
        try:
            validation = validate_read_only_sql(raw_sql, profile.db_type, allowed)
        except SqlPolicyError as exc:
            last_error = f"Rejected by the SQL policy engine: {exc}"
            feedback.append(f"Your SQL:\n{_extract_sql(raw_sql)}\nwas rejected: {exc}")
            continue
        if SQL_ASSISTANT_PROVIDER in HOSTED_PROVIDERS:
            explain_error = _explain_error(profile, validation.sql)
            if explain_error:
                last_error = f"The database rejected the query: {explain_error}"
                feedback.append(f"Your SQL:\n{validation.sql}\nfailed with: {explain_error}")
                continue
        tries = f" after {attempt} drafts" if attempt > 1 else ""
        explanation = (
            f"Generated from catalog metadata{tries}. It reads only from: "
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

    candidate = SqlAssistantCandidate(
        connection_id=profile.id,
        catalog_snapshot_id=snapshot.id,
        user_id=user.id,
        requirement=requirement,
        generated_sql=_extract_sql(raw_sql),
        explanation=f"No safe, valid query after {attempts} draft(s).",
        referenced_tables_json="[]",
        status="rejected",
        validation_error=last_error,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    raise SqlPolicyError(last_error or "The SQL assistant could not produce a valid query")


def _explain_error(profile: ConnectionProfile, sql: str) -> str | None:
    """Return the database's error for EXPLAIN <sql>, or None when the plan is valid."""
    uri = profile_uri(profile)
    engine = create_engine(uri, pool_pre_ping=True, **get_engine_kwargs(uri))
    try:
        with engine.connect() as connection:
            _apply_statement_timeout(connection, uri)
            connection.execute(text(f"EXPLAIN {sql}"))
        return None
    except Exception as exc:  # noqa: BLE001 - surfaced to the model as feedback
        return _database_error_message(exc)[:400]
    finally:
        engine.dispose()


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
        + f"\n) AS sql_assistant_preview LIMIT {int(limit) + 1}"
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

    limited = len(frame) > limit  # one extra row fetched to detect truncation exactly
    frame = frame.head(int(limit))
    return {
        "columns": frame.columns.tolist(),
        "rows": _safe_rows(frame),
        "total_rows": len(frame),
        "limited": limited,
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


HOSTED_PROVIDERS = {"openrouter", "openai"}

SYSTEM_PROMPT = """You are a careful analytics engineer who writes {dialect} SQL.
Rules:
- Return exactly one read-only SELECT (CTEs allowed) inside a ```sql code block, nothing else.
- Use only tables and columns from the supplied schema and qualify every table with its schema.
- Join on the listed foreign keys. Use ORDER BY ... LIMIT N for "top N" questions.
- Round money/averages to 2 decimals. Never use INSERT, UPDATE, DELETE, DDL, locks or functions with side effects."""


def _generate_sql(
    requirement: str,
    dialect: str,
    schema_context: str,
    ranked_tables: list,
    feedback: list[str] | None = None,
) -> str:
    if SQL_ASSISTANT_PROVIDER == "heuristic":
        return _heuristic_sql(requirement, ranked_tables)
    if SQL_ASSISTANT_PROVIDER in HOSTED_PROVIDERS:
        return _hosted_sql(requirement, dialect, schema_context, feedback or [])
    if SQL_ASSISTANT_PROVIDER != "ollama":
        raise SqlAssistantUnavailable(
            "SQL assistant is disabled. Set SQL_ASSISTANT_PROVIDER=openrouter, ollama or heuristic."
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
            f"`ollama pull {OLLAMA_SQL_MODEL}`, or set SQL_ASSISTANT_PROVIDER=openrouter."
        ) from exc
    return _extract_sql(generated)


def _hosted_sql(requirement: str, dialect: str, schema_context: str, feedback: list[str]) -> str:
    if not LLM_API_KEY:
        raise SqlAssistantUnavailable("Set OPENROUTER_API_KEY to use the hosted SQL assistant.")
    user = f"Schema:\n{schema_context}\n\nRequirement: {requirement.strip()}"
    for note in feedback:
        user += f"\n\n{note}\nWrite a corrected query."
    body = {
        "model": LLM_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(dialect=dialect)},
            {"role": "user", "content": user},
        ],
    }
    for attempt in range(LLM_RATE_LIMIT_RETRIES + 1):
        try:
            response = httpx.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json=body,
                timeout=SQL_ASSISTANT_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise SqlAssistantUnavailable(f"Could not reach the LLM provider at {LLM_BASE_URL}: {exc}") from exc
        retryable = response.status_code == 429 or response.status_code >= 500
        if not retryable:
            break
        if response.status_code == 429 and "per-day" in response.text:
            raise SqlAssistantUnavailable(
                "The free-model daily request limit is used up; it resets at 00:00 UTC."
            )
        if attempt < LLM_RATE_LIMIT_RETRIES:
            delay = _retry_after_seconds(response, attempt)
            logger.warning("LLM provider returned %s; retrying in %ss", response.status_code, delay)
            time.sleep(delay)
    if response.status_code == 429:
        raise SqlAssistantUnavailable("The LLM provider is rate limiting requests; try again shortly.")
    if response.status_code in (401, 403):
        raise SqlAssistantUnavailable("The LLM provider rejected OPENROUTER_API_KEY (invalid key or no credit).")
    if response.status_code >= 400:
        raise SqlAssistantUnavailable(f"LLM provider error {response.status_code}: {response.text[:200]}")
    try:
        content = response.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as exc:
        raise SqlAssistantUnavailable("The LLM provider returned an unexpected response") from exc
    return _extract_sql(content)


LLM_RATE_LIMIT_RETRIES = 4


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """Honour Retry-After when the provider sends it; otherwise back off 5s, 10s, 20s, 40s."""
    try:
        return min(max(float(response.headers.get("retry-after", "")), 1.0), 60.0)
    except ValueError:
        return float(min(5 * 2 ** attempt, 60))


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
