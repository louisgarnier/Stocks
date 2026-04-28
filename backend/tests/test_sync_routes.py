"""Tests for sync pipeline routes."""
import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_positions_returns_raw_ibkr_only(temp_db):
    """GET /api/positions returns positions_ibkr rows without any recon fields."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_money, "
        "cost_basis_price, mark_price, position_value, unrealized_pnl, "
        "currency, asset_category) VALUES "
        "('AAPL', 100, 15000, 150, 200, 20000, 5000, 'USD', 'STK')"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/positions")
    assert resp.status_code == 200
    body = resp.json()

    assert body["success"] is True
    assert len(body["positions"]) == 1
    pos = body["positions"][0]

    # raw IBKR fields present
    assert pos["symbol"] == "AAPL"
    assert pos["quantity"] == 100
    assert pos["cost_basis_money"] == 15000

    # recon fields removed
    assert "qty_calculated" not in pos
    assert "qty_diff" not in pos
    assert "qty_diff_pct" not in pos
    assert "rec_status" not in pos
    assert "transaction_count" not in pos

    # summary no longer carries recon counters
    assert "matched" not in body["summary"]
    assert "warnings" not in body["summary"]
    assert "errors" not in body["summary"]
    assert body["summary"]["total_positions"] == 1


def test_fetch_flex_response_returns_xml(monkeypatch, flex_xml_minimal):
    """fetch_flex_response wraps request + fetch and returns the XML string."""
    import backend.scripts.fetch_flex_trades as flex

    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    xml = flex.fetch_flex_response("last_month")
    assert "<FlexQueryResponse" in xml
    assert "TEST" in xml


def test_fetch_flex_response_raises_on_missing_token(monkeypatch):
    """Helper raises a clear error when IBKR_FLEX_TOKEN is unset."""
    import backend.scripts.fetch_flex_trades as flex
    monkeypatch.delenv("IBKR_FLEX_TOKEN", raising=False)
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    with pytest.raises(RuntimeError, match="IBKR_FLEX_TOKEN"):
        flex.fetch_flex_response("last_month")


def test_fetch_flex_response_falls_back_to_unified_for_positions(monkeypatch, flex_xml_minimal):
    """When IBKR_QUERY_ID_positions is unset, helper falls back to IBKR_QUERY_ID_last_month."""
    import backend.scripts.fetch_flex_trades as flex

    used_query_id = []
    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: used_query_id.append(qid) or "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.delenv("IBKR_QUERY_ID_positions", raising=False)
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    flex.fetch_flex_response("positions")
    assert used_query_id == ["9999"]


def test_sync_positions_writes_only_positions_table(temp_db, stub_flex_http, monkeypatch):
    """POST /api/sync/positions populates positions_ibkr and leaves transactions empty."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/positions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["positions_inserted"] == 1

    conn = sqlite3.connect(str(temp_db))
    pos_count = conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0]
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    assert pos_count == 1
    assert tx_count == 0


def test_sync_transactions_writes_only_transactions_table(temp_db, stub_flex_http, monkeypatch):
    """POST /api/sync/transactions populates transactions and leaves positions_ibkr empty."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/transactions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["inserted"] >= 1

    conn = sqlite3.connect(str(temp_db))
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    pos_count = conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0]
    ca_status = conn.execute(
        "SELECT status FROM corporate_actions_status WHERE sec_id='TEST'"
    ).fetchone()
    conn.close()
    assert tx_count == 1
    assert pos_count == 0
    assert ca_status is not None and ca_status[0] == "orange"


def test_sync_transactions_writes_import_log(temp_db, stub_flex_http, monkeypatch):
    """Each transactions sync should append a row to import_logs so the UI history shows it."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/transactions")
    assert resp.status_code == 200, resp.text

    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT filename, inserted, status FROM import_logs ORDER BY id DESC LIMIT 1"
    ).fetchall()
    conn.close()
    assert rows and rows[0][0] == "api_sync_transactions"
    assert rows[0][2] == "success"


def test_sync_corporate_actions_returns_success(temp_db, monkeypatch):
    """POST /api/sync/corporate-actions wraps the existing CA refresh logic."""
    import backend.scripts.fetch_corporate_actions as ca
    monkeypatch.setattr(
        ca, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    resp = client.post("/api/sync/corporate-actions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "parsed" in body


def test_sync_splits_returns_success(temp_db, monkeypatch):
    """POST /api/sync/splits wraps the existing apply-splits logic."""
    import backend.scripts.apply_splits as aps
    monkeypatch.setattr(
        aps, "apply_all_splits",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )
    resp = client.post("/api/sync/splits")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True


def test_sync_full_runs_all_four_steps(temp_db, stub_flex_http, monkeypatch):
    """POST /api/sync/full runs positions, transactions, CAs, splits — in that order, with one Flex pull."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    import backend.scripts.fetch_corporate_actions as ca_mod
    import backend.scripts.apply_splits as aps_mod
    monkeypatch.setattr(
        ca_mod, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    monkeypatch.setattr(
        aps_mod, "apply_all_splits",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )

    # Track Flex HTTP calls to confirm shared pull (one call, not two)
    call_log = []
    import backend.scripts.fetch_flex_trades as flex
    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: call_log.append(qid) or "REF123")

    resp = client.post("/api/sync/full")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert [s["name"] for s in body["steps"]] == ["positions", "transactions", "corporate_actions", "splits"]
    for s in body["steps"]:
        assert s["status"] == "ok", s

    assert len(call_log) == 1  # single shared Flex call

    conn = sqlite3.connect(str(temp_db))
    assert conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
    conn.close()


def test_sync_positions_adds_held_symbols_to_universe(temp_db, stub_flex_http, monkeypatch):
    """After /api/sync/positions, every symbol in positions_ibkr is also in tracked_universe with source 'ibkr_position'."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/positions")
    assert resp.status_code == 200

    import json as _json
    conn = sqlite3.connect(str(temp_db))
    row = conn.execute(
        "SELECT sources FROM tracked_universe WHERE symbol = 'TEST'"
    ).fetchone()
    conn.close()
    assert row is not None, "TEST symbol should be auto-added to tracked_universe"
    assert "ibkr_position" in _json.loads(row[0])


def test_sold_position_removes_ibkr_source(temp_db):
    """If a symbol previously had source 'ibkr_position' but is no longer in positions_ibkr, the source is removed."""
    import json as _json
    from backend.api.routes.sync import _sync_positions_to_universe

    conn = sqlite3.connect(str(temp_db))
    # Universe has FOO from a prior sync, but it's no longer in positions_ibkr
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('FOO', '[\"ibkr_position\"]', 1, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('BAR', '[\"sp500\", \"ibkr_position\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    _sync_positions_to_universe()

    conn = sqlite3.connect(str(temp_db))
    foo = conn.execute("SELECT sources FROM tracked_universe WHERE symbol = 'FOO'").fetchone()
    bar = conn.execute("SELECT sources FROM tracked_universe WHERE symbol = 'BAR'").fetchone()
    conn.close()
    assert foo is None, "FOO had only ibkr_position; should be deleted now that no longer held"
    assert bar is not None and _json.loads(bar[0]) == ["sp500"], "BAR retains sp500 source"
