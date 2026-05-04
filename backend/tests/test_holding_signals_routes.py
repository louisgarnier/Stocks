"""Tests for /api/sync/holding-signals + /api/holding-signals reads + settings."""
import sqlite3

from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
        "VALUES ('NVDA', 10, 100, 'USD')"
    )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_150, rsi_14, mrsi) "
        "VALUES ('NVDA', '2026-04-27', 110, 109, 55, 0.05)"
    )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_150, rsi_14, mrsi) "
        "VALUES ('NVDA', '2026-04-28', 100, 110, 48, -0.02)"
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, close, volume) "
        "VALUES ('NVDA', '2026-04-28', 85, 1500000)"
    )
    conn.commit()
    conn.close()


def test_sync_endpoint_runs_compute(temp_db):
    _seed(temp_db)
    r = client.post("/api/sync/holding-signals")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["symbols_processed"] == 1


def test_get_all_signals_filters_fired(temp_db):
    _seed(temp_db)
    client.post("/api/sync/holding-signals")
    r = client.get("/api/holding-signals?fired=true")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    assert all(it["fired"] is True for it in items)


def test_get_signals_for_one_symbol(temp_db):
    _seed(temp_db)
    client.post("/api/sync/holding-signals")
    r = client.get("/api/holding-signals/NVDA")
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "NVDA"
    assert any(s["signal_type"] == "stop_loss" and s["fired"] for s in data["signals"])


def test_get_settings_returns_11(temp_db):
    r = client.get("/api/holding-signals/settings")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 11


def test_settings_post_updates_threshold(temp_db):
    r = client.post(
        "/api/holding-signals/settings",
        json={"signal_type": "stop_loss", "enabled": True, "threshold": 0.05},
    )
    assert r.status_code == 200
    conn = sqlite3.connect(str(temp_db))
    row = conn.execute(
        "SELECT enabled, threshold FROM signal_settings WHERE signal_type='stop_loss'"
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] == 0.05


def test_settings_post_unknown_signal_type_returns_404(temp_db):
    r = client.post(
        "/api/holding-signals/settings",
        json={"signal_type": "made_up_signal", "enabled": True},
    )
    assert r.status_code == 404
