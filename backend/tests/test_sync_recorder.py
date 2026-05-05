"""Tests for the sync_recorder context manager."""
import json
import sqlite3

import pytest

from backend.utils.sync_recorder import record_run


def _rows(temp_db):
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT id, action, status, summary, details_json, duration_ms FROM sync_runs ORDER BY id"
    ).fetchall()
    conn.close()
    return rows


def test_record_run_writes_success_row(temp_db):
    with record_run("market_data") as run:
        run.summary("552 OK")
        run.details({"rows_inserted": 1234})

    rows = _rows(temp_db)
    assert len(rows) == 1
    _, action, status, summary, details_json, duration_ms = rows[0]
    assert action == "market_data"
    assert status == "success"
    assert summary == "552 OK"
    assert json.loads(details_json) == {"rows_inserted": 1234}
    assert duration_ms is not None and duration_ms >= 0


def test_record_run_explicit_partial_status(temp_db):
    with record_run("analytics") as run:
        run.summary("3 of 4 steps ok")
        run.status("partial")

    rows = _rows(temp_db)
    assert len(rows) == 1
    assert rows[0][2] == "partial"


def test_record_run_captures_exception(temp_db):
    with pytest.raises(RuntimeError):
        with record_run("ibkr") as run:
            run.summary("about to fail")
            raise RuntimeError("Flex 1001")

    rows = _rows(temp_db)
    assert len(rows) == 1
    _, action, status, summary, details_json, _ = rows[0]
    assert action == "ibkr"
    assert status == "error"
    assert summary == "about to fail"
    details = json.loads(details_json)
    assert "RuntimeError: Flex 1001" in details["error"]


def test_record_run_minimal_call(temp_db):
    """No summary, no details — should still write a row with sensible defaults."""
    with record_run("manual_add"):
        pass

    rows = _rows(temp_db)
    assert len(rows) == 1
    assert rows[0][1] == "manual_add"
    assert rows[0][2] == "success"
    assert rows[0][3] is None  # summary
    assert rows[0][4] is None  # details_json


def test_record_run_invalid_status_raises(temp_db):
    with pytest.raises(ValueError):
        with record_run("ibkr") as run:
            run.status("bogus")
