import pandas as pd
import pytest

from src import sheets


class Worksheet:
    row_count = 100
    col_count = 26

    def get_all_values(self):
        return [["old_name"], ["1"]]

    def update(self, *args, **kwargs):
        raise AssertionError("mismatched header must stop before writing")


def test_append_rejects_existing_header_mismatch(monkeypatch):
    monkeypatch.setattr(sheets, "_get_or_create_worksheet", lambda **kwargs: Worksheet())
    with pytest.raises(ValueError, match="different header"):
        sheets._write_tab(object(), pd.DataFrame({"new_name": [2]}), "Output", "append")
