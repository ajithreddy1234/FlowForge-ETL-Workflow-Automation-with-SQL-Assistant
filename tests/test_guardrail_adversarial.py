import json
import logging
from pathlib import Path

import pytest

from api.sql_guardrails import SqlPolicyError, validate_read_only_sql, validate_read_only_statement

logging.getLogger("sqlglot").setLevel(logging.ERROR)
ATTACKS = json.loads((Path(__file__).resolve().parents[1] / "eval" / "adversarial.json").read_text())
SAFE = [
    "SELECT o.id, c.city FROM public.orders o JOIN public.customers c ON c.id = o.customer_id",
    "WITH t AS (SELECT customer_id, COUNT(*) AS n FROM public.orders GROUP BY 1) SELECT * FROM t",
    "SELECT ROUND(AVG(price), 2) AS avg_price, DATE_TRUNC('month', order_date) FROM public.orders GROUP BY 2",
    "SELECT COALESCE(city, 'x'), LOWER(name), EXTRACT(YEAR FROM signup_date) FROM public.customers",
]


@pytest.mark.parametrize("dialect", ["postgresql", "mysql"])
@pytest.mark.parametrize("sql", ATTACKS)
def test_manual_queries_block_attacks(sql, dialect):
    with pytest.raises(SqlPolicyError):
        validate_read_only_statement(sql, dialect)


@pytest.mark.parametrize("sql", ATTACKS)
def test_assistant_queries_block_attacks(sql):
    allowed = {("public", "orders"), ("public", "customers")}
    with pytest.raises(SqlPolicyError):
        validate_read_only_sql(sql, "postgresql", allowed)


@pytest.mark.parametrize("sql", SAFE)
def test_normal_analytics_allowed(sql):
    allowed = {("public", "orders"), ("public", "customers")}
    assert validate_read_only_sql(sql, "postgresql", allowed).referenced_tables
