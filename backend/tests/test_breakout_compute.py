import sqlite3
import pandas as pd
from backend.scripts.breakout_compute import compute_for_symbol
from backend.database.connection import get_db_connection


def _seed(temp_db, symbol, df):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled) VALUES (?, 1)", (symbol,))
    for _, r in df.iterrows():
        conn.execute("INSERT OR IGNORE INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (symbol, str(r["time"]), r["open"], r["high"], r["low"], r["close"], r["volume"]))
    conn.commit(); conn.close()


def _base_then_breakout(n=43):
    rows = []
    for i in range(n - 1):
        p = 100 + (3 if i % 6 < 3 else -3)   # ~6% base
        rows.append({"time": pd.date_range("2026-01-01", periods=n)[i], "open": p,
                     "high": p + 0.5, "low": p - 0.5, "close": p, "volume": 1_000_000})
    # breakout day: gap above resistance on 3x volume
    d = pd.date_range("2026-01-01", periods=n)[n - 1]
    rows.append({"time": d, "open": 112, "high": 116, "low": 111, "close": 115, "volume": 3_000_000})
    return pd.DataFrame(rows)


def test_breakout_row_written(temp_db):
    _seed(temp_db, "BRK", _base_then_breakout())
    conn = get_db_connection()
    compute_for_symbol(conn, "BRK")
    row = conn.execute("SELECT breakout_status, breakout_direction FROM breakout_signals WHERE symbol='BRK'").fetchone()
    conn.close()
    assert row is not None                      # a status row is always written
    assert row[0] in ("breakout_detected", "consolidation_found_no_breakout", "no_consolidation_patterns")


def _tight_consolidation_then_gap_up(n=43, support=100.0, resistance=112.0):
    """Build a ~40-day tight, well-touched consolidation channel (bouncing between
    a fixed support and resistance level every 3 bars, each swing >= 6% away from
    the prior extreme so the zigzag_deviation threshold fires) followed by a
    final-day gap ABOVE resistance on high volume - designed to trip the strict
    validations in detect_strict_consolidation_patterns and check_breakout_for_day,
    proving the ported breakout path actually fires bullish."""
    rows = []
    dates = pd.date_range("2026-01-01", periods=n)
    for i in range(n - 1):
        if i % 6 < 3:
            close, high, low = resistance - 0.3, resistance, resistance - 0.6
        else:
            close, high, low = support + 0.3, support + 0.6, support
        rows.append({"time": dates[i], "open": close, "high": high, "low": low,
                     "close": close, "volume": 1_000_000})
    # Final day: gap above resistance, high volume (well above 20d avg, so ratio > 1)
    rows.append({"time": dates[n - 1], "open": resistance + 3, "high": resistance + 5,
                 "low": resistance + 2, "close": resistance + 4, "volume": 5_000_000})
    return pd.DataFrame(rows)


def test_breakout_detected_bullish_on_gap_above_resistance(temp_db):
    _seed(temp_db, "GAPUP", _tight_consolidation_then_gap_up())
    conn = get_db_connection()
    compute_for_symbol(conn, "GAPUP")
    row = conn.execute(
        "SELECT breakout_status, breakout_direction FROM breakout_signals WHERE symbol='GAPUP'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "breakout_detected"
    assert row[1] == "bullish"


def _tight_consolidation_still_inside(n=43, support=100.0, resistance=112.0):
    """Same tight channel as _tight_consolidation_then_gap_up but the final day
    stays INSIDE the channel — consolidation found, no breakout."""
    df = _tight_consolidation_then_gap_up(n, support, resistance)
    mid = (support + resistance) / 2
    df.loc[df.index[-1], ["open", "high", "low", "close", "volume"]] = [
        mid, mid + 0.6, mid - 0.6, mid, 1_000_000]
    return df


def test_consolidation_without_breakout_still_stores_bounds(temp_db):
    """A 'consolidation_found_no_breakout' row must carry the bounds of the
    consolidation it found (regression: bounds were only extracted when a
    breakout FIRED, so 60/561 prod rows claimed a consolidation with no levels)."""
    _seed(temp_db, "INSIDE", _tight_consolidation_still_inside())
    conn = get_db_connection()
    compute_for_symbol(conn, "INSIDE")
    row = conn.execute(
        "SELECT breakout_status, consolidation_bottom, consolidation_top, "
        "consolidation_range_pct, consolidation_duration_days "
        "FROM breakout_signals WHERE symbol='INSIDE'").fetchone()
    sr = conn.execute(
        "SELECT COUNT(*) FROM support_resistance WHERE symbol='INSIDE'").fetchone()[0]
    conn.close()
    assert row is not None
    assert row[0] == "consolidation_found_no_breakout"
    assert row[1] is not None and abs(row[1] - 100.0) < 2.0   # support ~100
    assert row[2] is not None and abs(row[2] - 112.0) < 2.0   # resistance ~112
    assert row[3] is not None and row[4] is not None
    assert sr == 2  # support + resistance zones persisted too
