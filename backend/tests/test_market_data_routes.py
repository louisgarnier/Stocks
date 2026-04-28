"""Tests for /api/market-data and /api/sync/market-data routes."""
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_market_data_for_symbol(temp_db):
    """GET /api/market-data/{symbol} returns OHLCV rows."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
        "VALUES ('AAPL', '2026-04-27', 100, 102, 99, 101, 101, 1500000)"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/market-data/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert len(body["bars"]) == 1
    bar = body["bars"][0]
    assert bar["close"] == 101


def test_market_data_404_for_unknown_symbol(temp_db):
    resp = client.get("/api/market-data/NOPE")
    assert resp.status_code == 404


def test_sync_market_data_endpoint(temp_db, monkeypatch):
    """POST /api/sync/market-data runs the ingestor."""
    import backend.scripts.market_data_ingestor as ing
    monkeypatch.setattr(
        ing, "ingest_market_data",
        lambda **kw: {"symbols_processed": 3, "rows_inserted": 12, "errors": 0},
    )
    resp = client.post("/api/sync/market-data")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["symbols_processed"] == 3
    assert body["rows_inserted"] == 12
