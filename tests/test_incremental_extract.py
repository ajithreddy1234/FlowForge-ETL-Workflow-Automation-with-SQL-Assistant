import sqlite3

import pytest

from api import executor
from api.models import Edge, Node, PipelineGraph
from api.extraction_contracts import checkpoint_value, validate_schema
from api.sql_guardrails import validate_read_only_statement
from src.config import get_connection_uri_from_fields, get_engine_kwargs


def _graph():
    return PipelineGraph(
        pipeline_name="incremental-test",
        nodes=[
            Node(id="credential_1", type="credential", data={"connection_id": 1, "connectionStatus": "connected"}),
            Node(id="extract_2", type="extract", data={
                "source_mode": "table", "table_name": "orders",
                "incremental_mode": "primary_key", "checkpoint_column": "id",
                "expected_columns": ["id", "amount"],
            }),
            Node(id="load_3", type="load", data={
                "google_sheet_url": "test-sheet", "tab_names": ["Orders"], "write_mode": "append",
            }),
        ],
        edges=[
            Edge(id="a", source="credential_1", target="extract_2"),
            Edge(id="b", source="extract_2", target="load_3"),
        ],
    )


def test_incremental_checkpoint_advances_only_after_load(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount INTEGER)")
        connection.executemany("INSERT INTO orders VALUES (?, ?)", [(1, 10), (2, 20)])

    monkeypatch.setattr(executor, "_saved_connection_uri", lambda *args, **kwargs: f"sqlite:///{source}")
    state = {}
    monkeypatch.setattr(executor, "_read_checkpoint", lambda scope, node: state.get((scope, node)))
    monkeypatch.setattr(executor, "_save_checkpoints", lambda scope, pending: state.update({(scope, node): value for node, value in pending.items()}))
    monkeypatch.setattr("src.sheets.load", lambda **kwargs: None)

    first = executor.execute_up_to(_graph(), "load_3", checkpoint_scope=7, trusted_connection=True)
    assert first["extract_2"]["id"].tolist() == [1, 2]
    assert state[(7, "extract_2")] == 2

    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO orders VALUES (3, 30)")

    def fail_load(**kwargs):
        raise RuntimeError("Sheets unavailable")

    monkeypatch.setattr("src.sheets.load", fail_load)
    with pytest.raises(RuntimeError, match="Sheets unavailable"):
        executor.execute_up_to(_graph(), "load_3", checkpoint_scope=7, trusted_connection=True)
    assert state[(7, "extract_2")] == 2

    monkeypatch.setattr("src.sheets.load", lambda **kwargs: None)
    third = executor.execute_up_to(_graph(), "load_3", checkpoint_scope=7, trusted_connection=True)
    assert third["extract_2"]["id"].tolist() == [3]
    assert state[(7, "extract_2")] == 3


def test_schema_and_checkpoint_contracts():
    import pandas as pd

    frame = pd.DataFrame({"id": [1, 2], "amount": [10, 20]})
    validate_schema(frame, ["id", "amount"])
    assert checkpoint_value(frame, "id", "primary_key") == 2
    with pytest.raises(ValueError, match="missing columns"):
        validate_schema(frame, ["updated_at"])
    with pytest.raises(ValueError, match="duplicate values"):
        checkpoint_value(pd.DataFrame({"id": [1, 1]}), "id", "primary_key")


def test_postgresql_source_and_sql_policy():
    uri = get_connection_uri_from_fields("postgresql", "localhost", "warehouse", "reader")
    assert uri.startswith("postgresql+psycopg://")
    assert ":5432/warehouse" in uri
    assert get_engine_kwargs(uri)["connect_args"]["connect_timeout"] > 0
    assert validate_read_only_statement("SELECT * FROM public.orders", "postgresql")
