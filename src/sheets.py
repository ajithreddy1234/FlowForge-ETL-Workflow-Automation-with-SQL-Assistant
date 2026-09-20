"""
sheets.py — LOAD layer.
Writes each output DataFrame to its own worksheet tab in a Google Sheet.
"""

import logging
import time
import gspread
import pandas as pd
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials
from src.config import GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SHEETS_MAX_RETRIES

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(str(GOOGLE_SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    return gspread.authorize(creds)


def load(context: dict[str, pd.DataFrame], sheets_config: list[dict], google_sheet_id: str) -> list[dict]:
    """
    Write each entry in sheets_config to its own worksheet tab.
    sheets_config: [{"name": "Tab Name", "input": "context_key"}, ...]
    """
    client = _get_client()
    spreadsheet = _retry_api(client.open_by_key, google_sheet_id)
    results = []

    for sheet_cfg in sheets_config:
        df       = context[sheet_cfg["input"]]
        tab_name = sheet_cfg["name"]
        result   = _write_tab(
            spreadsheet,
            df,
            tab_name,
            mode=sheet_cfg.get("write_mode", "overwrite"),
        )
        results.append(result)
        logger.info("  Wrote '%s': %d rows × %d columns", tab_name, result["rows_written"], result["columns"])

    return results


def _write_tab(spreadsheet, df: pd.DataFrame, tab_name: str, mode: str = "overwrite") -> dict:
    if mode not in {"overwrite", "append"}:
        raise ValueError("Google Sheets write mode must be overwrite or append")
    required_rows = max(len(df) + 1, 1)
    required_cols = max(len(df.columns), 1)

    ws = _get_or_create_worksheet(
        spreadsheet=spreadsheet,
        tab_name=tab_name,
        rows=max(required_rows, 100),
        cols=max(required_cols, 26),
    )

    start_row = 1
    include_header = True
    if mode == "append":
        existing_values = _retry_api(ws.get_all_values)
        existing_rows = len(existing_values)
        if existing_rows and existing_values[0] != [str(column) for column in df.columns]:
            raise ValueError(f"Google Sheet tab {tab_name!r} has a different header; append was stopped")
        start_row = existing_rows + 1
        include_header = existing_rows == 0
        required_rows = max(start_row + len(df) + (1 if include_header else 0) - 1, 1)
    else:
        # Clear values first so shorter later runs cannot leave stale rows from
        # a previous larger result.
        _retry_api(ws.clear)

    _retry_api(ws.resize,
        rows=max(required_rows, ws.row_count, 100),
        cols=max(required_cols, ws.col_count, 26),
    )

    rows = [df.columns.tolist()] if include_header else []
    for _, row in df.iterrows():
        rows.append([_serialize(v) for v in row.tolist()])

    if rows:
        end_row = start_row + len(rows) - 1
        cell_range = f"A{start_row}:{gspread.utils.rowcol_to_a1(end_row, len(rows[0]))}"
        _retry_api(ws.update, cell_range, rows)

    return {
        "tab":          tab_name,
        "rows_written": len(df),
        "columns":      len(df.columns),
        "write_mode":   mode,
        "sheet_url":    f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}",
    }


def _get_or_create_worksheet(spreadsheet, tab_name: str, rows: int, cols: int):
    ws = _find_worksheet(spreadsheet, tab_name)
    if ws:
        return ws

    try:
        ws = _retry_api(spreadsheet.add_worksheet, title=tab_name, rows=rows, cols=cols)
        logger.info("  Created new tab '%s'.", tab_name)
        return ws
    except APIError as exc:
        if "already exists" not in str(exc).lower():
            raise

        _retry_api(spreadsheet.fetch_sheet_metadata)
        ws = _find_worksheet(spreadsheet, tab_name)
        if ws:
            logger.info("  Reusing existing tab '%s' after duplicate-title response.", tab_name)
            return ws
        raise


def _find_worksheet(spreadsheet, tab_name: str):
    try:
        return _retry_api(spreadsheet.worksheet, tab_name)
    except gspread.WorksheetNotFound:
        pass

    normalized = tab_name.strip().casefold()
    for ws in _retry_api(spreadsheet.worksheets):
        if ws.title.strip().casefold() == normalized:
            return ws

    metadata = _retry_api(spreadsheet.fetch_sheet_metadata)
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        title = props.get("title", "")
        if title.strip().casefold() == normalized:
            return spreadsheet.get_worksheet_by_id(props["sheetId"])
    return None


def _retry_api(action, *args, **kwargs):
    """Retry only transient Google API responses with bounded backoff."""
    for attempt in range(GOOGLE_SHEETS_MAX_RETRIES + 1):
        try:
            return action(*args, **kwargs)
        except APIError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status not in {429, 500, 502, 503, 504} or attempt >= GOOGLE_SHEETS_MAX_RETRIES:
                raise
            delay = min(2 ** attempt, 8)
            logger.warning("Google Sheets API returned %s; retrying in %ss", status, delay)
            time.sleep(delay)


def _serialize(value) -> str | int | float | None:
    if pd.isna(value):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)
