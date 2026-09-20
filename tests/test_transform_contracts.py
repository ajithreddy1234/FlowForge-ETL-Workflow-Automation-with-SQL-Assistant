import pandas as pd

from src.transform import transform


def apply(frame, operation, extra=None):
    context = {"input": frame, **(extra or {})}
    return transform(
        context,
        [
            {
                "name": "test",
                "input": "input",
                "output": "output",
                "operations": [operation],
            }
        ],
    )["output"]


def test_fillna_uses_columns_contract():
    frame = pd.DataFrame({"amount": [1, None], "label": [None, None]})
    result = apply(frame, {"type": "fillna", "columns": ["amount"], "value": 0})
    assert result["amount"].tolist() == [1, 0]
    assert result["label"].isna().all()


def test_replace_uses_to_replace_and_value_contract():
    result = apply(
        pd.DataFrame({"status": ["old", "ok"]}),
        {"type": "replace", "column": "status", "to_replace": "old", "value": "new"},
    )
    assert result["status"].tolist() == ["new", "ok"]


def test_rank_uses_rank_by_and_output_column_contract():
    result = apply(
        pd.DataFrame({"revenue": [10, 30, 20]}),
        {
            "type": "rank",
            "rank_by": "revenue",
            "output_column": "position",
            "ascending": False,
        },
    )
    assert result["position"].tolist() == [3, 1, 2]


def test_date_extract_uses_array_contract():
    result = apply(
        pd.DataFrame({"created_at": ["2026-08-21"]}),
        {
            "type": "date_extract",
            "column": "created_at",
            "parts": ["year", "month"],
            "output_columns": ["year", "month"],
        },
    )
    assert result.loc[0, "year"] == 2026
    assert result.loc[0, "month"] == 8


def test_concat_axis_one_stacks_columns():
    result = apply(
        pd.DataFrame({"left": [1, 2]}),
        {"type": "concat", "right_input": "right", "axis": 1},
        {"right": pd.DataFrame({"right": [3, 4]})},
    )
    assert result.to_dict(orient="list") == {"left": [1, 2], "right": [3, 4]}
