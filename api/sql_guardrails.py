import re
from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError


class SqlPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class SqlValidationResult:
    sql: str
    referenced_tables: list[str]


BLOCKED_FUNCTIONS = {
    "benchmark",
    "pg_sleep",
    "sleep",
    "sys_eval",
    "sys_exec",
    "load_file",
}

BLOCKED_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Merge,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Into,
    exp.Lock,
    exp.LoadData,
    exp.Copy,
    exp.Use,
    exp.Grant,
    exp.Revoke,
    exp.Pragma,
)


def validate_read_only_sql(
    sql: str,
    dialect: str,
    allowed_tables: set[tuple[str, str]],
) -> SqlValidationResult:
    clean = _strip_code_fences(sql).strip().rstrip(";").strip()
    if not clean:
        raise SqlPolicyError("The SQL assistant returned an empty query")

    try:
        statements = [item for item in parse(clean, read="postgres" if dialect == "postgresql" else dialect) if item is not None]
    except ParseError as exc:
        raise SqlPolicyError(f"Generated SQL is not valid {dialect} SQL: {exc}") from exc

    if len(statements) != 1:
        raise SqlPolicyError("Exactly one SQL statement is allowed")

    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SqlPolicyError("Only read-only SELECT queries are allowed")
    if any(tree.find(kind) is not None for kind in BLOCKED_EXPRESSIONS):
        raise SqlPolicyError("The generated query contains a write or administrative operation")

    for function in tree.find_all(exp.Anonymous):
        if function.name.lower() in BLOCKED_FUNCTIONS:
            raise SqlPolicyError(f"Function {function.name} is not allowed")

    normalized_allowed = {
        (schema.lower(), table.lower()) for schema, table in allowed_tables
    }
    by_name: dict[str, set[str]] = {}
    for schema, table in normalized_allowed:
        by_name.setdefault(table.lower(), set()).add(schema.lower())

    referenced = []
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        table_name = table.name.lower()
        if table_name in cte_names:
            continue
        schema_name = (table.db or "").lower()
        if schema_name:
            if (schema_name, table_name) not in normalized_allowed:
                raise SqlPolicyError(
                    f"Table {schema_name}.{table_name} is outside the approved catalog"
                )
            identifier = f"{schema_name}.{table_name}"
        else:
            schemas = by_name.get(table_name, set())
            if not schemas:
                raise SqlPolicyError(f"Table {table_name} is outside the approved catalog")
            if len(schemas) > 1:
                raise SqlPolicyError(
                    f"Table {table_name} is ambiguous; qualify it with a schema"
                )
            identifier = f"{next(iter(schemas))}.{table_name}"
        if identifier not in referenced:
            referenced.append(identifier)

    if not referenced:
        raise SqlPolicyError("The generated query does not reference an approved table")

    return SqlValidationResult(sql=clean, referenced_tables=referenced)


def validate_read_only_statement(sql: str, dialect: str) -> str:
    """Validate a manual Extract query when a catalog allowlist is unavailable."""
    clean = _strip_code_fences(sql).strip().rstrip(";").strip()
    if not clean:
        raise SqlPolicyError("SQL query is required")
    try:
        statements = [item for item in parse(clean, read="postgres" if dialect == "postgresql" else dialect) if item is not None]
    except ParseError as exc:
        raise SqlPolicyError(f"SQL is not valid {dialect} SQL: {exc}") from exc
    if len(statements) != 1:
        raise SqlPolicyError("Exactly one SQL statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SqlPolicyError("Only read-only SELECT queries are allowed")
    if any(tree.find(kind) is not None for kind in BLOCKED_EXPRESSIONS):
        raise SqlPolicyError("The query contains a write, lock, or administrative operation")
    for function in tree.find_all(exp.Anonymous):
        if function.name.lower() in BLOCKED_FUNCTIONS:
            raise SqlPolicyError(f"Function {function.name} is not allowed")
    return clean


def _strip_code_fences(value: str) -> str:
    match = re.search(r"```(?:sql)?\s*(.*?)```", value or "", flags=re.I | re.S)
    return match.group(1) if match else (value or "")
