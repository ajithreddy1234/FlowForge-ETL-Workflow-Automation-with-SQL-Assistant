import pandas as pd
import pytest

import api.executor as ex


def test_csv_target_parsing(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.LOCAL_CSV_OUTPUT_DIR", str(tmp_path))
    assert ex._local_csv_target("https://docs.google.com/spreadsheets/d/abc") is None
    assert ex._local_csv_target("csv://daily_report") == "daily_report"
    with pytest.raises(ValueError):
        ex._local_csv_target("csv://../../etc")


def test_csv_disabled_without_output_dir(monkeypatch):
    monkeypatch.setattr("src.config.LOCAL_CSV_OUTPUT_DIR", "")
    with pytest.raises(ValueError, match="disabled"):
        ex._local_csv_target("csv://x")


def test_overwrite_and_append(monkeypatch, tmp_path):
    monkeypatch.setattr("src.config.LOCAL_CSV_OUTPUT_DIR", str(tmp_path))
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    ex._write_local_csv("r", {"tab_names": ["t"], "write_mode": "overwrite"}, df)
    ex._write_local_csv("r", {"tab_names": ["t"], "write_mode": "overwrite"}, df)
    assert len(pd.read_csv(tmp_path / "r" / "t.csv")) == 2
    ex._write_local_csv("r", {"tab_names": ["t"], "write_mode": "append"}, df)
    assert len(pd.read_csv(tmp_path / "r" / "t.csv")) == 4
    with pytest.raises(ValueError, match="different header"):
        ex._write_local_csv("r", {"tab_names": ["t"], "write_mode": "append"}, df.rename(columns={"a": "z"}))
