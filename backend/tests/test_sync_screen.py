import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend.api.main import app
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
