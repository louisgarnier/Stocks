import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app
client = TestClient(app)

def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT OR IGNORE INTO tracked_universe (symbol, name, sector, enabled, added_at) "
        "VALUES ('AAPL','Apple','Tech',1,'2026-07-01T00:00:00')"
    )
    conn.execute("INSERT INTO screen_signals (symbol, date, momentum_60d, above_ma50) VALUES ('AAPL','2026-07-01', 12.0, 1)")
    conn.execute("INSERT INTO fundamentals (symbol, gates_passed, gates_total, roic) VALUES ('AAPL', 6, 7, 0.55)")
    conn.commit(); conn.close()

def test_overview_json(temp_db):
    _seed(temp_db)
    resp = client.get("/api/screener/overview")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["gates_passed"] == 6 and aapl["momentum_60d"] == 12.0

def test_overview_csv(temp_db):
    _seed(temp_db)
    resp = client.get("/api/screener/overview?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "symbol" in resp.text.splitlines()[0]
