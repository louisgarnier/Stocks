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
