import json
import logging
from pathlib import Path

import pytest

from api.sql_guardrails import SqlPolicyError, validate_read_only_sql, validate_read_only_statement

logging.getLogger("sqlglot").setLevel(logging.ERROR)
EVAL = Path(__file__).resolve().parents[1] / "eval"
SUITES = json.loads((EVAL / "adversarial.json").read_text())
WRITE_DDL = SUITES["write_ddl"]
ATTACKS = WRITE_DDL + SUITES["side_effect_exfiltration"]
GOLD = [q["gold"] for q in json.loads((EVAL / "questions.json").read_text())]
DIALECTS = ["postgresql", "mysql", "redshift"]
ALLOWED = {("public", t) for t in ("orders", "customers", "products", "order_items")}


def test_write_ddl_suite_size():
    assert len(WRITE_DDL) == 40
    assert len(set(ATTACKS)) == len(ATTACKS)


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("sql", ATTACKS)
def test_manual_queries_block_attacks(sql, dialect):
    with pytest.raises(SqlPolicyError):
        validate_read_only_statement(sql, dialect)


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("sql", ATTACKS)
def test_assistant_queries_block_attacks(sql, dialect):
    with pytest.raises(SqlPolicyError):
        validate_read_only_sql(sql, dialect, ALLOWED)


@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("sql", GOLD)
def test_gold_analytics_queries_allowed(sql, dialect):
    assert validate_read_only_sql(sql, dialect, ALLOWED).referenced_tables
