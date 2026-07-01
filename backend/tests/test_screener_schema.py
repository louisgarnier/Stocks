import sqlite3
from backend.database.connection import get_db_connection

EXPECTED_TABLES = [
    "fundamentals", "screen_signals", "consolidation_patterns",
    "breakout_signals", "support_resistance", "screen_scores", "screener_settings",
]

def _tables(temp_db):
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    return {r[0] for r in rows}

def test_phase1_tables_exist(temp_db):
    tables = _tables(temp_db)
    for t in EXPECTED_TABLES:
        assert t in tables, f"missing table {t}"

def test_screener_settings_seeded(temp_db):
    conn = sqlite3.connect(str(temp_db))
    keys = {r[0] for r in conn.execute("SELECT key FROM screener_settings").fetchall()}
    conn.close()
    for k in ("quality_gates", "consolidation_params", "scoring_weights", "retention", "account"):
        assert k in keys, f"missing setting {k}"

def test_breakout_signals_pk_is_symbol_date(temp_db):
    conn = sqlite3.connect(str(temp_db))
    pk = [r[1] for r in conn.execute("PRAGMA table_info(breakout_signals)").fetchall() if r[5] > 0]
    conn.close()
    assert set(pk) == {"symbol", "date"}
