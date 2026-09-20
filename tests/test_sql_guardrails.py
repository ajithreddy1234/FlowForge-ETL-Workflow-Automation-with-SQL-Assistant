import pytest

from api.sql_guardrails import (
    SqlPolicyError,
    validate_read_only_sql,
    validate_read_only_statement,
)


ALLOWED = {
    ("analytics", "orders"),
    ("analytics", "customers"),
}


def test_accepts_catalog_scoped_select():
    result = validate_read_only_sql(
        "SELECT o.customer_id, SUM(o.total) AS revenue "
        "FROM analytics.orders o GROUP BY o.customer_id",
        "mysql",
        ALLOWED,
    )
    assert result.referenced_tables == ["analytics.orders"]


def test_accepts_read_only_cte():
    result = validate_read_only_sql(
        "WITH recent AS (SELECT * FROM analytics.orders) SELECT * FROM recent",
        "redshift",
        ALLOWED,
    )
    assert result.referenced_tables == ["analytics.orders"]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM analytics.orders",
        "UPDATE analytics.orders SET total = 0",
        "DROP TABLE analytics.orders",
        "SELECT * FROM analytics.orders; SELECT * FROM analytics.customers",
        "SELECT SLEEP(30) FROM analytics.orders",
        "SELECT * FROM analytics.orders FOR UPDATE",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(SqlPolicyError):
        validate_read_only_sql(sql, "mysql", ALLOWED)


def test_rejects_table_outside_catalog():
    with pytest.raises(SqlPolicyError, match="outside the approved catalog"):
        validate_read_only_sql("SELECT * FROM payroll.salaries", "mysql", ALLOWED)


def test_requires_schema_for_ambiguous_table_name():
    with pytest.raises(SqlPolicyError, match="ambiguous"):
        validate_read_only_sql(
            "SELECT * FROM orders",
            "mysql",
            ALLOWED | {("archive", "orders")},
        )


def test_manual_query_policy_supports_bound_parameters():
    sql = validate_read_only_statement(
        "SELECT * FROM orders WHERE created_at >= :date", "mysql"
    )
    assert ":date" in sql
