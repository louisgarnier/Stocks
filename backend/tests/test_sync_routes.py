"""Tests for sync pipeline routes."""
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_positions_returns_raw_ibkr_only(temp_db):
    """GET /api/positions returns positions_ibkr rows without any recon fields."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_money, "
        "cost_basis_price, mark_price, position_value, unrealized_pnl, "
        "currency, asset_category) VALUES "
        "('AAPL', 100, 15000, 150, 200, 20000, 5000, 'USD', 'STK')"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/positions")
    assert resp.status_code == 200
    body = resp.json()

    assert body["success"] is True
    assert len(body["positions"]) == 1
    pos = body["positions"][0]

    # raw IBKR fields present
    assert pos["symbol"] == "AAPL"
    assert pos["quantity"] == 100
    assert pos["cost_basis_money"] == 15000

    # recon fields removed
    assert "qty_calculated" not in pos
    assert "qty_diff" not in pos
    assert "qty_diff_pct" not in pos
    assert "rec_status" not in pos
    assert "transaction_count" not in pos

    # summary no longer carries recon counters
    assert "matched" not in body["summary"]
    assert "warnings" not in body["summary"]
    assert "errors" not in body["summary"]
    assert body["summary"]["total_positions"] == 1
