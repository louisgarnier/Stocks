import json
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.routes.sync import _prune_retention
client = TestClient(app)

def test_prune_drops_old_breakouts(temp_db):
    conn = sqlite3.connect(str(temp_db))
    old = (datetime.now(timezone.utc) - timedelta(days=40)).date().isoformat()
    new = datetime.now(timezone.utc).date().isoformat()
    for d in (old, new):
        conn.execute("INSERT INTO breakout_signals (symbol, date, breakout_status) VALUES ('X', ?, 'x')", (d,))
    conn.commit(); conn.close()
    resp = client.post("/api/sync/screen")
    assert resp.status_code == 200
    conn = sqlite3.connect(str(temp_db))
    dates = {r[0] for r in conn.execute("SELECT date FROM breakout_signals WHERE symbol='X'").fetchall()}
    conn.close()
    assert new in dates and old not in dates   # 40d-old pruned by 30d retention

def test_prune_drops_old_screen_scores(temp_db):
    conn = sqlite3.connect(str(temp_db))
    old = (datetime.now(timezone.utc) - timedelta(days=70)).date().isoformat()
    new = datetime.now(timezone.utc).date().isoformat()
    for d in (old, new):
        conn.execute("INSERT INTO screen_scores (symbol, date) VALUES ('Y', ?)", (d,))
    conn.commit(); conn.close()
    resp = client.post("/api/sync/screen")
    assert resp.status_code == 200
    conn = sqlite3.connect(str(temp_db))
    dates = {r[0] for r in conn.execute("SELECT date FROM screen_scores WHERE symbol='Y'").fetchall()}
    conn.close()
    assert new in dates and old not in dates   # 70d-old pruned by 60d retention

def test_prune_keeps_row_at_retention_boundary(temp_db):
    conn = sqlite3.connect(str(temp_db))
    boundary = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    conn.execute("INSERT INTO breakout_signals (symbol, date, breakout_status) VALUES ('Z', ?, 'x')", (boundary,))
    conn.commit(); conn.close()
    resp = client.post("/api/sync/screen")
    assert resp.status_code == 200
    conn = sqlite3.connect(str(temp_db))
    dates = {r[0] for r in conn.execute("SELECT date FROM breakout_signals WHERE symbol='Z'").fetchall()}
    conn.close()
    assert boundary in dates   # exactly at 30d boundary is kept (delete uses < not <=)


def test_prune_retention_missing_row_does_not_crash(temp_db):
    """Regression: a missing `retention` row previously crashed `.fetchone()[0]` on None."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("DELETE FROM screener_settings WHERE key='retention'")
    conn.commit()
    result = _prune_retention(conn)  # must not raise
    conn.close()
    assert result == {"breakout_signals_pruned": 0, "screen_scores_pruned": 0}


def test_prune_retention_partial_row_fills_defaults_and_keeps_overrides(temp_db):
    conn = sqlite3.connect(str(temp_db))
    old_brk = (datetime.now(timezone.utc) - timedelta(days=40)).date().isoformat()
    old_sc = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
    conn.execute("INSERT INTO breakout_signals (symbol, date, breakout_status) VALUES ('X', ?, 'x')", (old_brk,))
    conn.execute("INSERT INTO screen_scores (symbol, date) VALUES ('Y', ?)", (old_sc,))
    # Only override screen_scores_retention_days to 5; breakout_retention_days must fall back to default (30).
    conn.execute("UPDATE screener_settings SET value_json=? WHERE key='retention'",
                 (json.dumps({"screen_scores_retention_days": 5}),))
    conn.commit()

    result = _prune_retention(conn)

    brk_dates = {r[0] for r in conn.execute("SELECT date FROM breakout_signals WHERE symbol='X'").fetchall()}
    sc_dates = {r[0] for r in conn.execute("SELECT date FROM screen_scores WHERE symbol='Y'").fetchall()}
    conn.close()
    assert old_brk not in brk_dates   # 40d-old still pruned by default 30d retention
    assert old_sc not in sc_dates     # 10d-old pruned by overridden 5d retention
    assert result["breakout_signals_pruned"] == 1
    assert result["screen_scores_pruned"] == 1
