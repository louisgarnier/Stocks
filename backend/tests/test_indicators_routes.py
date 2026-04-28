"""Tests for indicators schema, compute, and routes."""
import sqlite3


def test_indicators_schema(temp_db):
    """indicators table must exist with composite PK (symbol, time) and all 11 indicator cols."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='indicators'")
    assert cur.fetchone() is not None, "indicators table missing"

    cur.execute("PRAGMA table_info(indicators)")
    rows = cur.fetchall()
    cols = {r[1] for r in rows}
    expected = {"symbol", "time", "ma_50", "ma_100", "ma_150", "ma_200",
                "bb_upper_20", "bb_lower_20", "bb_width", "rsi_14", "mrsi",
                "atr_14", "volume_ma_20"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"

    pk_cols = sorted([r[1] for r in rows if r[5] > 0])
    assert pk_cols == ["symbol", "time"], f"expected composite PK (symbol, time), got {pk_cols}"
    conn.close()


import json
from datetime import datetime, timedelta


def _seed_market_data(conn, symbol: str, days: int, start_close: float = 100.0, currency: str = "USD"):
    """Insert `days` of synthetic market_data rows for `symbol` and ensure it's in tracked_universe."""
    conn.execute(
        "INSERT OR IGNORE INTO tracked_universe (symbol, currency, sources, enabled, added_at) "
        "VALUES (?, ?, ?, 1, datetime('now'))",
        (symbol, currency, json.dumps(["test"])),
    )
    end = datetime(2026, 4, 1)
    for i in range(days):
        ts = (end - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        c = start_close + i * 0.1
        conn.execute(
            "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1000000)",
            (symbol, ts, c, c + 0.5, c - 0.5, c, c),
        )
    conn.commit()


def test_compute_for_symbol_writes_rows(temp_db):
    """compute_for_symbol writes one indicators row per market_data bar (after warm-up periods)."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_for_symbol

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "AAPL", days=60)
    conn.close()

    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    inserted = compute_for_symbol(conn, "AAPL")
    conn.close()
    assert inserted == 60

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM indicators WHERE symbol='AAPL'").fetchone()[0]
    last = conn.execute(
        "SELECT ma_50, ma_100, rsi_14, atr_14, volume_ma_20 FROM indicators "
        "WHERE symbol='AAPL' ORDER BY time DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert cnt == 60
    assert last[0] is not None  # ma_50 populated after 50 bars
    assert last[2] is not None  # rsi populated
    assert last[3] is not None  # atr populated
    assert last[4] is not None  # volume_ma populated


def test_compute_for_symbol_idempotent(temp_db):
    """Re-running compute_for_symbol on the same data doesn't duplicate rows."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_for_symbol
    from backend.database.connection import get_db_connection

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "AAPL", days=60)
    conn.close()

    conn = get_db_connection()
    compute_for_symbol(conn, "AAPL")
    compute_for_symbol(conn, "AAPL")
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM indicators WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert cnt == 60


def test_compute_for_symbol_resolves_benchmark(temp_db):
    """compute_for_symbol picks ^GSPC for USD symbols and computes MRSI when both have ≥252 days."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_for_symbol
    from backend.database.connection import get_db_connection

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "^GSPC", days=300, start_close=4500.0, currency="USD")
    _seed_market_data(conn, "AAPL", days=300, start_close=150.0, currency="USD")
    conn.close()

    conn = get_db_connection()
    compute_for_symbol(conn, "AAPL")
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    last_mrsi = conn.execute(
        "SELECT mrsi FROM indicators WHERE symbol='AAPL' ORDER BY time DESC LIMIT 1"
    ).fetchone()[0]
    conn.close()
    assert last_mrsi is not None  # MRSI populated when benchmark + ≥252 days available


def test_compute_all_processes_enabled_symbols(temp_db):
    """compute_all skips disabled symbols and processes enabled ones."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_all
    from backend.database.connection import get_db_connection

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "ENABLED", days=60)
    _seed_market_data(conn, "DISABLED", days=60)
    conn.execute("UPDATE tracked_universe SET enabled = 0 WHERE symbol = 'DISABLED'")
    conn.commit()
    conn.close()

    conn = get_db_connection()
    result = compute_all(conn)
    conn.close()

    assert "ENABLED" in result["symbols_processed"]
    assert "DISABLED" not in result["symbols_processed"]
