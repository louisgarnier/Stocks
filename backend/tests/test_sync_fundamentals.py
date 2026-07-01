import sqlite3
import backend.scripts.fundamentals_fetch as ff
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


class _FakeTicker:
    def __init__(self, s):
        self.info = {"longName": f"{s} Inc", "grossMargins": 0.65, "returnOnEquity": 0.30,
                     "freeCashflow": 300.0, "totalRevenue": 1000.0}
        self.income_stmt = {"EBIT": 400.0, "Diluted EPS": [1.0, 1.8]}
        self.balance_sheet = {"Total Debt": 200.0, "Stockholders Equity": 800.0}
        self.earnings_history = []


def test_sync_fundamentals_endpoint(temp_db, monkeypatch):
    from datetime import datetime
    conn = sqlite3.connect(str(temp_db))
    now = datetime.now().isoformat()
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled, added_at) VALUES (?, ?, ?)",
                 ('AAPL', 1, now))
    conn.commit(); conn.close()
    monkeypatch.setattr(ff, "_yf_ticker", lambda s: _FakeTicker(s))
    resp = client.post("/api/sync/fundamentals")
    assert resp.status_code == 200
    assert resp.json()["rows_written"] == 1
    # a sync_runs row was recorded
    conn = sqlite3.connect(str(temp_db))
    n = conn.execute("SELECT COUNT(*) FROM sync_runs WHERE action='fundamentals'").fetchone()[0]
    conn.close()
    assert n == 1


def test_fundamentals_status_overdue_when_never_run(temp_db):
    resp = client.get("/api/sync/fundamentals/status")
    assert resp.status_code == 200
    assert resp.json()["overdue"] is True


def test_sync_fundamentals_auto_rescores(temp_db, monkeypatch):
    """After fetching fundamentals, scoring must re-run so score_fund is fresh."""
    from datetime import datetime
    conn = sqlite3.connect(str(temp_db))
    now = datetime.now().isoformat()
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled, added_at) VALUES (?, ?, ?)",
                 ('AAPL', 1, now))
    # scoring only runs for symbols that have a screen_signals row
    conn.execute("INSERT INTO screen_signals (symbol, date, momentum_60d, above_ma50) "
                 "VALUES ('AAPL','2026-07-01', 10.0, 1)")
    conn.commit(); conn.close()
    monkeypatch.setattr(ff, "_yf_ticker", lambda s: _FakeTicker(s))
    resp = client.post("/api/sync/fundamentals")
    assert resp.status_code == 200
    assert resp.json()["rescored"] >= 1
    conn = sqlite3.connect(str(temp_db))
    n = conn.execute("SELECT COUNT(*) FROM screen_scores WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert n == 1
