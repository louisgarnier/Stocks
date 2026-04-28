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
