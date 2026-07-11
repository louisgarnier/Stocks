import json
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
                 "VALUES ('TEST', 10, 100.0, 'USD')")
    conn.execute("INSERT INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
                 "VALUES ('TEST','Test Corp','USD',?,1,datetime('now'))", (json.dumps(["test"]),))
    for d, px, fx in (("2026-07-08", 110.0, 1.10), ("2026-07-09", 121.0, 1.10)):
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('TEST',?,?,?,?,?,1000)", (d, px, px, px, px))
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('EURUSD=X',?,?,?,?,?,0)", (d, fx, fx, fx, fx))
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('^GSPC',?,?,?,?,?,0)", (d, 7500.0, 7500.0, 7500.0, 7500.0))
        conn.execute("INSERT INTO portfolio_value_history (date, value_eur) VALUES (?, ?)",
                     (d, 10 * px / fx))
    conn.execute("INSERT INTO fundamentals (symbol, sector) VALUES ('TEST', 'Technology')")
    conn.execute("INSERT INTO holding_signals (symbol, signal_type, fired, last_evaluated_at) "
                 "VALUES ('TEST','stop_loss',1,datetime('now'))")
    conn.commit(); conn.close()


def test_dashboard_net_worth_and_day_change(temp_db):
    _seed(temp_db)
    r = client.get("/api/dashboard")
    assert r.status_code == 200, r.text
    b = r.json()
    assert abs(b["net_worth"]["value_eur"] - 1100.0) < 0.1          # 10*121/1.10
    assert abs(b["net_worth"]["day_change_eur"] - 100.0) < 0.1      # vs 10*110/1.10
    assert b["net_worth"]["positions"] == 1


def test_dashboard_allocation_and_actions(temp_db):
    _seed(temp_db)
    b = client.get("/api/dashboard").json()
    assert b["allocation"]["sector"][0]["label"] == "Technology"
    assert abs(b["allocation"]["sector"][0]["pct"] - 100.0) < 0.1
    sell = b["actions"]["sell"]
    assert sell and sell[0]["symbol"] == "TEST" and "stop_loss" in sell[0]["fired"]


def test_dashboard_performance_normalized(temp_db):
    _seed(temp_db)
    b = client.get("/api/dashboard?window=MAX").json()
    assert b["performance"]["portfolio"][0]["value"] == 100.0
    assert b["performance"]["benchmark"][0]["value"] == 100.0
    assert abs(b["performance"]["portfolio"][-1]["value"] - 110.0) < 0.1  # 1100/1000
