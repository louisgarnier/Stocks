"""Tests for fundamentals route."""
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_fundamentals(temp_db):
    """GET /api/fundamentals/{symbol} returns row dict or 404."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO fundamentals (symbol, long_name, gates_passed, gates_total, roic) "
                 "VALUES ('AAPL','Apple Inc',6,7,0.55)")
    conn.commit()
    conn.close()
    resp = client.get("/api/fundamentals/aapl")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["gates_passed"] == 6
    assert client.get("/api/fundamentals/NOPE").status_code == 404
