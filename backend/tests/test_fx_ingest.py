"""Tests for FX symbol ingest."""
import sqlite3


def test_seed_fx_symbols_inserts_eurusd(temp_db):
    from backend.scripts.universe_seeders import seed_fx_symbols
    from backend.database.connection import get_db_connection

    conn = get_db_connection()
    seed_fx_symbols(conn)
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    row = conn.execute(
        "SELECT enabled, sources, currency FROM tracked_universe WHERE symbol='EURUSD=X'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 1
    assert "fx" in row[1]


def test_seed_fx_symbols_idempotent(temp_db):
    from backend.scripts.universe_seeders import seed_fx_symbols
    from backend.database.connection import get_db_connection

    conn = get_db_connection()
    seed_fx_symbols(conn)
    seed_fx_symbols(conn)
    n = conn.execute(
        "SELECT COUNT(*) FROM tracked_universe WHERE symbol='EURUSD=X'"
    ).fetchone()[0]
    conn.close()
    assert n == 1
