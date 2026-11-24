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
    "benchmark", "pg_sleep", "sleep", "sys_eval", "sys_exec", "load_file",
    # side effects, session changes, file/network access
    "set_config", "current_setting", "nextval", "setval", "lo_import", "lo_export",
    "lo_unlink", "dblink", "dblink_exec", "dblink_connect", "load_extension",
    "query_to_xml", "xp_cmdshell", "get_lock", "release_lock", "release_all_locks",
    "readfile", "writefile", "txid_current", "json_populate_record",
}
# Every PostgreSQL pg_* admin/introspection function (advisory locks, backend control,
# file reads, sleeps) is refused; ordinary analytics never needs them.
BLOCKED_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink")
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "mysql", "performance_schema", "sys", "pg_toast"}

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


def _function_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name or "").lower()
    return (node.sql_name() or "").lower()


def _check_functions_and_catalogs(tree: exp.Expression) -> None:
    for node in tree.find_all(exp.Func):
        name = _function_name(node)
        if name in BLOCKED_FUNCTIONS or name.startswith(BLOCKED_FUNCTION_PREFIXES):
            raise SqlPolicyError(f"Function {name} is not allowed")
    for table in tree.find_all(exp.Table):
        parts = [p.lower().strip('"`') for p in (table.catalog, table.db, table.name) if p]
        if any(part in SYSTEM_SCHEMAS or part.startswith("pg_") for part in parts):
            raise SqlPolicyError("System catalogs are not allowed: " + ".".join(parts))
        if table.catalog:
            raise SqlPolicyError("Database-qualified (catalog.schema.table) references are not allowed")


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

    _check_functions_and_catalogs(tree)

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
    _check_functions_and_catalogs(tree)
    return clean


def _strip_code_fences(value: str) -> str:
    match = re.search(r"```(?:sql)?\s*(.*?)```", value or "", flags=re.I | re.S)
    return match.group(1) if match else (value or "")
