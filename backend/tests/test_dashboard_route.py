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
    conn.execute("INSERT INTO sync_runs (started_at, finished_at, action, status) "
                 "VALUES ('2026-07-09T08:00:00+00:00','2026-07-09T08:01:00+00:00',"
                 "'market_data','success')")
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


def _seed_long_history(temp_db):
    """Seed > 182 days of portfolio history so 6M and MAX windows are distinguishable."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
                 "VALUES ('TEST', 10, 100.0, 'USD')")
    conn.execute("INSERT INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
                 "VALUES ('TEST','Test Corp','USD',?,1,datetime('now'))", (json.dumps(["test"]),))
    from datetime import date, timedelta
    start = date(2025, 1, 1)  # well over 182 days before the most recent date below
    end = date(2026, 7, 9)
    d = start
    px = 100.0
    while d <= end:
        iso = d.isoformat()
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('TEST',?,?,?,?,?,1000)", (iso, px, px, px, px))
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('EURUSD=X',?,?,?,?,?,0)", (iso, 1.10, 1.10, 1.10, 1.10))
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('^GSPC',?,?,?,?,?,0)", (iso, 7500.0, 7500.0, 7500.0, 7500.0))
        conn.execute("INSERT INTO portfolio_value_history (date, value_eur) VALUES (?, ?)",
                     (iso, 10 * px / 1.10))
        d += timedelta(days=30)
        px += 1.0
    conn.execute("INSERT INTO fundamentals (symbol, sector) VALUES ('TEST', 'Technology')")
    conn.commit(); conn.close()


def test_dashboard_window_max_mixed_case_not_treated_as_6m(temp_db):
    """Regression: frontend sends ?window=Max (mixed case). WINDOWS lookup is keyed
    uppercase ('MAX'), so a naive WINDOWS.get(window, 182) silently falls back to the
    6M default instead of resolving MAX. Assert mixed-case 'Max' behaves like 'MAX'
    and (with long history seeded) differs from the 182-day '6M' window."""
    _seed_long_history(temp_db)

    mixed = client.get("/api/dashboard?window=Max").json()
    upper = client.get("/api/dashboard?window=MAX").json()
    six_month = client.get("/api/dashboard?window=6M").json()

    assert mixed["performance"]["portfolio"] == upper["performance"]["portfolio"]
    assert len(mixed["performance"]["portfolio"]) > len(six_month["performance"]["portfolio"])


def test_dashboard_missing_fx_logs_warning_and_null_rate(temp_db, caplog):
    """Regression: when EURUSD=X has no bars, get_fx_rate returns None. The endpoint
    must NOT silently value USD at parity without signal — fx_rate in the response
    must be None and a warning must be logged (ADR-3)."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
                 "VALUES ('TEST', 10, 100.0, 'USD')")
    conn.execute("INSERT INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
                 "VALUES ('TEST','Test Corp','USD',?,1,datetime('now'))", (json.dumps(["test"]),))
    for d, px in (("2026-07-08", 110.0), ("2026-07-09", 121.0)):
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('TEST',?,?,?,?,?,1000)", (d, px, px, px, px))
        # No EURUSD=X rows inserted at all.
    conn.execute("INSERT INTO fundamentals (symbol, sector) VALUES ('TEST', 'Technology')")
    conn.commit(); conn.close()

    with caplog.at_level("WARNING"):
        r = client.get("/api/dashboard")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["fx_rate"] is None
    assert any("EURUSD=X rate unavailable" in rec.message for rec in caplog.records)


def test_dashboard_as_of_entries_are_rich_objects(temp_db):
    _seed(temp_db)
    b = client.get("/api/dashboard").json()
    prices = b["as_of"]["prices"]
    assert prices["date"] == "2026-07-09"            # newest seeded bar
    assert prices["checked_at"] == "2026-07-09T08:01:00+00:00"
    assert prices["level"] in ("fresh", "stale")     # depends on wall clock
    for key in ("signals", "fundamentals", "ibkr"):
        assert set(b["as_of"][key]) == {"date", "checked_at", "level"}


def test_dashboard_as_of_unknown_without_data(temp_db):
    _seed(temp_db)
    b = client.get("/api/dashboard").json()
    # No screen_signals / ibkr sync_runs seeded → no data date.
    assert b["as_of"]["signals"]["level"] == "unknown"
    assert b["as_of"]["ibkr"]["date"] is None


def test_dashboard_ibkr_chip_ignores_failed_syncs(temp_db):
    """Regression: a FAILED ibkr sync must not refresh the IBKR chip.

    The chip's date/checked_at must reflect the last SUCCESSFUL (or partial)
    sync, not the last attempt. Otherwise a failed sync makes the dashboard
    falsely report IBKR data as freshly updated (green) when nothing changed.
    """
    _seed(temp_db)
    conn = sqlite3.connect(str(temp_db))
    # A good sync at 12:00, then TWO failed attempts afterward at 13:00 / 14:00.
    conn.execute("INSERT INTO sync_runs (started_at, finished_at, action, status) "
                 "VALUES ('2026-07-09T11:59:00+00:00','2026-07-09T12:00:00+00:00','ibkr','partial')")
    conn.execute("INSERT INTO sync_runs (started_at, finished_at, action, status) "
                 "VALUES ('2026-07-09T13:00:00+00:00','2026-07-09T13:00:01+00:00','ibkr','error')")
    conn.execute("INSERT INTO sync_runs (started_at, finished_at, action, status) "
                 "VALUES ('2026-07-09T14:00:00+00:00','2026-07-09T14:00:01+00:00','ibkr','error')")
    conn.commit(); conn.close()

    ibkr = client.get("/api/dashboard").json()["as_of"]["ibkr"]
    # Must anchor to the 12:00 success, NOT the 14:00 failure.
    assert ibkr["date"] == "2026-07-09T12:00:00+00:00"
    assert ibkr["checked_at"] == "2026-07-09T12:00:00+00:00"


def test_dashboard_prices_checked_at_ignores_failed_syncs(temp_db):
    """A failed market_data sync must not bump the prices chip's 'checked' line."""
    _seed(temp_db)  # seeds one successful market_data run finishing 2026-07-09T08:01:00
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO sync_runs (started_at, finished_at, action, status) "
                 "VALUES ('2026-07-09T20:00:00+00:00','2026-07-09T20:00:01+00:00','market_data','error')")
    conn.commit(); conn.close()

    prices = client.get("/api/dashboard").json()["as_of"]["prices"]
    assert prices["checked_at"] == "2026-07-09T08:01:00+00:00"  # the success, not the 20:00 error
