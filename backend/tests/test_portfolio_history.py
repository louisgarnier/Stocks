import json
import sqlite3


def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    # one USD stock bought 2026-01-05 (10 sh @100), one fx series, 3 trading days
    conn.execute("INSERT INTO tracked_universe (symbol, currency, sources, enabled, added_at) "
                 "VALUES ('TEST', 'USD', ?, 1, datetime('now'))", (json.dumps(["test"]),))
    conn.execute(
        "INSERT INTO transactions (transaction_id, asset_category, currency, symbol, trade_date, quantity, t_price) "
        "VALUES ('t1', 'STK', 'USD', 'TEST', '2026-01-05', 10, 100.0)")
    for d, px, fx in (("2026-01-05", 100.0, 1.10), ("2026-01-06", 110.0, 1.10), ("2026-01-07", 120.0, 1.20)):
        conn.execute("INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES ('TEST', ?, ?, ?, ?, ?, 1000)", (d, px, px, px, px))
        conn.execute("INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES ('EURUSD=X', ?, ?, ?, ?, ?, 0)", (d, fx, fx, fx, fx))
    conn.commit(); conn.close()


def test_compute_history_values_and_fx(temp_db):
    from backend.scripts.portfolio_history_compute import compute_history
    from backend.database.connection import get_db_connection

    _seed(temp_db)
    conn = get_db_connection()
    result = compute_history(conn)
    conn.close()
    assert result["days_written"] == 3

    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT date, value_eur, fx_rate FROM portfolio_value_history ORDER BY date").fetchall()
    conn.close()
    # day1: 10*100/1.10 ≈ 909.09 ; day3: 10*120/1.20 = 1000.0
    assert abs(rows[0][1] - 909.09) < 0.1
    assert abs(rows[2][1] - 1000.0) < 0.01
    assert rows[2][2] == 1.20


def test_forex_and_cash_transactions_excluded(temp_db):
    from backend.scripts.portfolio_history_compute import compute_history
    from backend.database.connection import get_db_connection

    _seed(temp_db)
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO transactions (transaction_id, asset_category, currency, symbol, trade_date, quantity, t_price) "
        "VALUES ('fx1', 'CASH', 'USD', 'EUR.USD', '2026-01-05', 1773.76, 1.18)")
    conn.commit(); conn.close()

    conn = get_db_connection()
    compute_history(conn)
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    v = conn.execute("SELECT value_eur FROM portfolio_value_history WHERE date='2026-01-05'").fetchone()[0]
    conn.close()
    assert abs(v - 909.09) < 0.1  # CASH row must not change the valuation


def test_get_fx_rate_latest_and_dated(temp_db):
    from backend.scripts.portfolio_history_compute import get_fx_rate
    from backend.database.connection import get_db_connection

    _seed(temp_db)
    conn = get_db_connection()
    assert get_fx_rate(conn) == 1.20
    assert get_fx_rate(conn, on_date="2026-01-06") == 1.10
    conn.close()
