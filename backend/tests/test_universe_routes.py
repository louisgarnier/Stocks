"""Tests for universe + market_data tables and routes."""
import sqlite3


def test_universe_schema_has_tracked_universe(temp_db):
    """The schema must create a tracked_universe table with required columns."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_universe'")
    assert cur.fetchone() is not None, "tracked_universe table missing"

    cur.execute("PRAGMA table_info(tracked_universe)")
    cols = {r[1] for r in cur.fetchall()}
    expected = {"symbol", "name", "sector", "currency", "exchange", "benchmark",
                "sources", "enabled", "added_at", "last_synced_at"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"
    conn.close()


def test_universe_schema_has_tracked_indices(temp_db):
    """tracked_indices table must exist."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_indices'")
    assert cur.fetchone() is not None
    cur.execute("PRAGMA table_info(tracked_indices)")
    cols = {r[1] for r in cur.fetchall()}
    expected = {"name", "enabled", "last_refreshed_at", "symbol_count"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"
    conn.close()


def test_market_data_schema(temp_db):
    """market_data table must exist with PK (symbol, time)."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_data'")
    assert cur.fetchone() is not None
    cur.execute("PRAGMA table_info(market_data)")
    rows = cur.fetchall()
    cols = {r[1] for r in rows}
    expected = {"symbol", "time", "open", "high", "low", "close", "adj_close", "volume"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"
    pk_cols = sorted([r[1] for r in rows if r[5] > 0])
    assert pk_cols == ["symbol", "time"], f"expected composite PK (symbol, time), got {pk_cols}"
    conn.close()


import json
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_universe_empty(temp_db):
    """GET /api/universe returns an empty list when nothing is tracked."""
    resp = client.get("/api/universe")
    assert resp.status_code == 200
    assert resp.json() == {"symbols": [], "count": 0}


def test_add_manual_symbol(temp_db):
    """POST /api/universe/manual creates a manual entry."""
    resp = client.post("/api/universe/manual", json={"symbol": "TSLA"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["symbol"]["symbol"] == "TSLA"
    assert "manual" in body["symbol"]["sources"]


def test_add_manual_symbol_uppercases(temp_db):
    """Manual symbols are normalized to uppercase."""
    resp = client.post("/api/universe/manual", json={"symbol": "tsla"})
    assert resp.status_code == 200
    assert resp.json()["symbol"]["symbol"] == "TSLA"


def test_add_manual_symbol_idempotent(temp_db):
    """Adding the same manual symbol twice is a no-op."""
    client.post("/api/universe/manual", json={"symbol": "TSLA"})
    resp = client.post("/api/universe/manual", json={"symbol": "TSLA"})
    assert resp.status_code == 200
    list_resp = client.get("/api/universe")
    syms = [s["symbol"] for s in list_resp.json()["symbols"]]
    assert syms.count("TSLA") == 1


def test_remove_manual_symbol(temp_db):
    """DELETE /api/universe/manual/{symbol} removes manual contribution.
    If symbol came only from 'manual', the row is deleted.
    """
    client.post("/api/universe/manual", json={"symbol": "TSLA"})
    resp = client.delete("/api/universe/manual/TSLA")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    list_resp = client.get("/api/universe")
    assert list_resp.json()["count"] == 0


def test_remove_manual_keeps_row_if_other_sources(temp_db):
    """If symbol exists from sp500 AND manual, removing 'manual' leaves the row with just sp500."""
    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('TSLA', '[\"sp500\", \"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    resp = client.delete("/api/universe/manual/TSLA")
    assert resp.status_code == 200
    list_resp = client.get("/api/universe")
    body = list_resp.json()
    assert body["count"] == 1
    assert body["symbols"][0]["sources"] == ["sp500"]


def test_list_indices(temp_db):
    """GET /api/universe/indices returns the seeded index list."""
    resp = client.get("/api/universe/indices")
    assert resp.status_code == 200
    body = resp.json()
    names = {idx["name"] for idx in body["indices"]}
    assert "sp500" in names
    assert "cac40" in names


def test_toggle_index(temp_db):
    """POST /api/universe/indices/{name}/toggle flips the enabled flag."""
    resp = client.post("/api/universe/indices/sp500/toggle")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    resp = client.post("/api/universe/indices/sp500/toggle")
    assert resp.json()["enabled"] is False


def test_benchmarks_auto_seeded(temp_db):
    """The 4 benchmark symbols (^GSPC, ^FCHI, ^GDAXI, ^FTSE) get auto-seeded into tracked_universe."""
    resp = client.get("/api/universe/indices")
    assert resp.status_code == 200

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT symbol, currency, sources FROM tracked_universe "
        "WHERE symbol IN ('^GSPC', '^FCHI', '^GDAXI', '^FTSE') ORDER BY symbol"
    ).fetchall()
    conn.close()
    syms = {r[0] for r in rows}
    assert syms == {"^FCHI", "^FTSE", "^GDAXI", "^GSPC"}
    for r in rows:
        assert "benchmark" in r[2]
