"""Tests for /api/security/{symbol}/detail."""
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def _seed_security(temp_db, symbol: str, held: bool, days: int = 30):
    """Insert tracked_universe row + market_data + 1 indicators row + optionally positions_ibkr + transactions."""
    import json as _json
    conn = sqlite3.connect(str(temp_db))
    sources = ["sp500", "ibkr_position"] if held else ["sp500"]
    conn.execute(
        "INSERT INTO tracked_universe (symbol, name, sector, currency, sources, enabled, added_at) "
        "VALUES (?, ?, ?, ?, ?, 1, datetime('now'))",
        (symbol, f"{symbol} Inc.", "Tech", "USD", _json.dumps(sources)),
    )
    if held:
        conn.execute(
            "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_money, cost_basis_price, "
            "mark_price, position_value, unrealized_pnl, currency, asset_category) "
            "VALUES (?, 100, 15000, 150, 200, 20000, 5000, 'USD', 'STK')",
            (symbol,),
        )
        conn.execute(
            "INSERT INTO transactions (transaction_id, symbol, trade_date, quantity, t_price, currency) "
            "VALUES (?, ?, '2025-12-15', 100, 150, 'USD')",
            (f"T-{symbol}-001", symbol),
        )
    for i in range(days):
        ts = f"2026-04-{i + 1:02d}"
        c = 100.0 + i * 0.5
        conn.execute(
            "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1000000)",
            (symbol, ts, c, c + 1, c - 1, c, c),
        )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_100, ma_150, ma_200, "
        "bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20) "
        "VALUES (?, '2026-04-30', 110, 108, 105, 100, 115, 105, 0.09, 62, 0.05, 2.5, 1500000)",
        (symbol,),
    )
    conn.commit()
    conn.close()


def test_security_detail_held(temp_db):
    """Held symbol returns is_held=true + position + transactions + indicators + bars."""
    _seed_security(temp_db, "AAPL", held=True)

    resp = client.get("/api/security/AAPL/detail")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["symbol"] == "AAPL"
    assert body["is_held"] is True
    assert body["universe"]["name"] == "AAPL Inc."
    assert body["universe"]["sector"] == "Tech"
    assert "ibkr_position" in body["universe"]["sources"]

    assert body["position"]["quantity"] == 100
    assert body["position"]["cost_basis_price"] == 150

    assert len(body["transactions"]) == 1
    assert body["transactions"][0]["transaction_id"] == "T-AAPL-001"

    assert body["indicators"]["mrsi"] == 0.05
    assert body["indicators"]["rsi_14"] == 62

    assert len(body["bars"]) == 30
    assert body["bars"][0]["time"] >= body["bars"][-1]["time"]  # newest first


def test_security_detail_not_held(temp_db):
    """Non-held symbol returns is_held=false, position=None, transactions=[]."""
    _seed_security(temp_db, "MSFT", held=False)

    resp = client.get("/api/security/MSFT/detail")
    assert resp.status_code == 200
    body = resp.json()

    assert body["is_held"] is False
    assert body["position"] is None
    assert body["transactions"] == []
    assert body["indicators"]["mrsi"] == 0.05
    assert len(body["bars"]) == 30


def test_security_detail_404_unknown(temp_db):
    resp = client.get("/api/security/NOPE/detail")
    assert resp.status_code == 404


def test_security_detail_uppercases_symbol(temp_db):
    _seed_security(temp_db, "AAPL", held=False)
    resp = client.get("/api/security/aapl/detail")
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "AAPL"


def test_security_detail_includes_fundamentals(temp_db):
    _seed_security(temp_db, "AAPL", held=False)
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO fundamentals (symbol, roe, roic, gates_passed, gates_total, "
                 "market_cap, trailing_pe) VALUES ('AAPL', 0.4, 0.3, 6, 7, 3.0e12, 35.5)")
    conn.commit(); conn.close()
    resp = client.get("/api/security/AAPL/detail")
    assert resp.status_code == 200
    f = resp.json()["fundamentals"]
    assert f["gates_passed"] == 6 and f["roe"] == 0.4 and f["trailing_pe"] == 35.5


def test_security_detail_fundamentals_null_when_absent(temp_db):
    _seed_security(temp_db, "MSFT", held=False)
    resp = client.get("/api/security/MSFT/detail")
    assert resp.status_code == 200
    assert resp.json()["fundamentals"] is None
