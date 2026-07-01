import json
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
from backend.scripts.screen_signals_compute import compute_signals, _ma_cross_status


def test_momentum_and_flags_exact():
    # 70 ascending closes so momentum is positive; volume flat except last day spike
    closes = [100 + i for i in range(70)]
    vols = [1_000_000] * 69 + [3_000_000]
    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=70).astype(str),
        "high": [c + 1 for c in closes], "low": [c - 1 for c in closes],
        "close": closes, "volume": vols,
    })
    ind = {"ma_50": 150.0, "ma_100": 140.0, "ma_150": 130.0, "ma_200": 120.0}
    r = compute_signals(df, ind)
    c = closes[-1]
    assert round(r["momentum_5d"], 2) == round((c - closes[-6]) / closes[-6] * 100, 2)
    assert round(r["multi_factor_momentum"], 2) == round(
        0.4*r["momentum_5d"] + 0.3*r["momentum_20d"] + 0.3*r["momentum_60d"], 2)
    assert r["volume_spike"] == 1               # 3M > 1.5 * ~1M
    assert r["above_ma50"] == 1                 # close 169 > 150
    assert r["ma_cross_status"] == "All Bullish"  # 150>140>130
    assert r["near_52w_high"] == 1              # last close is the high


def test_ma_cross_status_first_match_mostly_bullish():
    """ma150 < ma50 < ma100 must resolve to 'Mostly Bullish' (SQL first-match: ma50>ma150 matches
    before the dead 'Short-term Bullish' branch is ever reached)."""
    assert _ma_cross_status(105, 110, 100) == "Mostly Bullish"


def test_ma_cross_status_first_match_mostly_bearish():
    """ma100 < ma50 < ma150 must resolve to 'Mostly Bearish' (SQL first-match: ma50<ma150 matches
    before the dead 'Short-term Bearish' branch is ever reached)."""
    assert _ma_cross_status(95, 90, 100) == "Mostly Bearish"


def _seed_market_data(conn, symbol: str, days: int, start_close: float = 100.0, currency: str = "USD"):
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


def _seed_indicators(conn, symbol: str, ma_50, ma_100, ma_150, ma_200, mrsi=None):
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_100, ma_150, ma_200, mrsi) "
        "VALUES (?, datetime('now'), ?, ?, ?, ?, ?)",
        (symbol, ma_50, ma_100, ma_150, ma_200, mrsi),
    )
    conn.commit()


def test_compute_for_symbol_writes_and_upserts_single_row(temp_db):
    """compute_for_symbol writes exactly one screen_signals row per symbol, and re-running it
    replaces (upserts) rather than duplicating — screen_signals is latest-only (PK: symbol)."""
    from backend.scripts.screen_signals_compute import compute_for_symbol
    from backend.database.connection import get_db_connection

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "AAPL", days=60)
    _seed_indicators(conn, "AAPL", ma_50=105.0, ma_100=110.0, ma_150=100.0, ma_200=95.0, mrsi=1.5)
    conn.close()

    conn = get_db_connection()
    written = compute_for_symbol(conn, "AAPL")
    conn.close()
    assert written == 1

    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute("SELECT ma_cross_status, above_ma50 FROM screen_signals WHERE symbol='AAPL'").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "Mostly Bullish"
    assert rows[0][1] == 1

    # Run again — must still be exactly one row (upsert, not insert).
    conn = get_db_connection()
    compute_for_symbol(conn, "AAPL")
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM screen_signals WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert cnt == 1
