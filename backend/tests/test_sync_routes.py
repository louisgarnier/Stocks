"""Tests for sync pipeline routes."""
import sqlite3
import pytest
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


def test_fetch_flex_response_returns_xml(monkeypatch, flex_xml_minimal):
    """fetch_flex_response wraps request + fetch and returns the XML string."""
    import backend.scripts.fetch_flex_trades as flex

    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    xml = flex.fetch_flex_response("last_month")
    assert "<FlexQueryResponse" in xml
    assert "TEST" in xml


def test_fetch_flex_response_raises_on_missing_token(monkeypatch):
    """Helper raises a clear error when IBKR_FLEX_TOKEN is unset."""
    import backend.scripts.fetch_flex_trades as flex
    monkeypatch.delenv("IBKR_FLEX_TOKEN", raising=False)
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    with pytest.raises(RuntimeError, match="IBKR_FLEX_TOKEN"):
        flex.fetch_flex_response("last_month")


def test_fetch_flex_response_falls_back_to_unified_for_positions(monkeypatch, flex_xml_minimal):
    """When IBKR_QUERY_ID_positions is unset, helper falls back to IBKR_QUERY_ID_last_month."""
    import backend.scripts.fetch_flex_trades as flex

    used_query_id = []
    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: used_query_id.append(qid) or "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.delenv("IBKR_QUERY_ID_positions", raising=False)
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    flex.fetch_flex_response("positions")
    assert used_query_id == ["9999"]
