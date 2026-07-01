import json
import sqlite3
import pandas as pd
from backend.scripts.consolidation_compute import compute_for_symbol, analyze_symbol
from backend.database.connection import get_db_connection


def _seed(temp_db, symbol, df):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled) VALUES (?, 1)", (symbol,))
    for _, r in df.iterrows():
        conn.execute("INSERT OR IGNORE INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (symbol, str(r["time"]), r["open"], r["high"], r["low"], r["close"], r["volume"]))
    conn.commit(); conn.close()


def _tight_base(n=70):
    rows = []
    for i in range(n):
        p = 100 + (2 if i % 6 < 3 else -2)  # ~4% band
        rows.append({"time": pd.date_range("2026-01-01", periods=n)[i], "open": p,
                     "high": p + 0.5, "low": p - 0.5, "close": p, "volume": 1_000_000})
    return pd.DataFrame(rows)


def test_consolidation_writes_when_present(temp_db):
    _seed(temp_db, "COIL", _tight_base())
    conn = get_db_connection()
    n = compute_for_symbol(conn, "COIL")
    row = conn.execute("SELECT quality_score, range_pct FROM consolidation_patterns WHERE symbol='COIL'").fetchone()
    conn.close()
    # Sparse: a row exists only if a pattern was detected
    assert (n == 1 and row is not None) or (n == 0 and row is None)


def _bouncing_channel(n=70, support=100.0, resistance=104.5):
    """Build a synthetic series that bounces between a tight support/resistance
    channel, with periodic overshoots large enough to clear the default
    zigzag_deviation (6.0%) and generate boundary touches, so the hybrid
    channel+zigzag detector actually fires (proves the ported path works,
    rather than only exercising the sparse-write no-op case)."""
    rows = []
    dates = pd.date_range("2026-01-01", periods=n)
    for i in range(n):
        cycle = i % 6
        if cycle in (0, 1, 2):
            close, high, low = resistance - 0.2, resistance, resistance - 0.6
        else:
            close, high, low = support + 0.2, support + 0.6, support
        if i % 12 == 0:
            high = resistance * 1.02
            close = high - 0.1
            low = resistance - 0.6
        if i % 12 == 6:
            low = support * 0.98
            close = low + 0.1
            high = support + 0.6
        volume = max(2_000_000 - i * 10_000, 100_000)  # declining volume trend
        rows.append({"time": dates[i], "open": close, "high": high, "low": low,
                     "close": close, "volume": volume})
    return pd.DataFrame(rows)


def test_analyze_symbol_detects_bouncing_channel(temp_db):
    conn = sqlite3.connect(str(temp_db))
    params = json.loads(
        conn.execute("SELECT value_json FROM screener_settings WHERE key='consolidation_params'").fetchone()[0]
    )
    conn.close()
    df = _bouncing_channel()
    best = analyze_symbol(df, params)
    assert best is not None
    assert best["quality_score"] is not None
