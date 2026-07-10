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
    # two indicator rows; the view must surface the LATEST one
    conn.execute("INSERT INTO indicators (symbol, time, ma_50, rsi_14, atr_14) VALUES ('AAPL','2026-06-01', 100.0, 40.0, 2.0)")
    conn.execute("INSERT INTO indicators (symbol, time, ma_50, rsi_14, atr_14) VALUES ('AAPL','2026-06-30', 141.2, 62.5, 3.4)")
    # market_data for latest-close (price) — latest is 2026-06-30 @ 145.5
    conn.execute("INSERT INTO market_data (symbol, time, open, high, low, close, volume) VALUES ('AAPL','2026-06-01', 1,1,1, 130.0, 10)")
    conn.execute("INSERT INTO market_data (symbol, time, open, high, low, close, volume) VALUES ('AAPL','2026-06-30', 1,1,1, 145.5, 10)")
    conn.commit()
    conn.close()


def test_research_view_joins_latest_indicators(temp_db):
    _seed(temp_db)
    conn = sqlite3.connect(str(temp_db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM research_overview WHERE symbol='AAPL'").fetchone()
    conn.close()
    # signals + fundamentals still present
    assert row["momentum_60d"] == 12.0
    assert row["gates_passed"] == 6
    # latest indicator values joined (2026-06-30, not 2026-06-01)
    assert row["ma_50"] == 141.2
    assert row["rsi_14"] == 62.5
    assert row["atr_14"] == 3.4
    # latest close price
    assert row["price"] == 145.5


def test_research_overview_json(temp_db):
    _seed(temp_db)
    resp = client.get("/api/research/overview")
    assert resp.status_code == 200
    aapl = next(r for r in resp.json()["rows"] if r["symbol"] == "AAPL")
    assert aapl["rsi_14"] == 62.5 and aapl["momentum_60d"] == 12.0


def test_research_overview_csv(temp_db):
    _seed(temp_db)
    resp = client.get("/api/research/overview?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    header = resp.text.splitlines()[0]
    assert "rsi_14" in header and "symbol" in header


def test_breakout_rows_carry_their_own_consolidation_bounds(temp_db):
    """breakout_signals embeds its own consolidation detector (independent of the
    consolidation_patterns ZigZag detector). A breakout row must expose the bounds
    that produced it — previously the view only showed consolidation_patterns
    columns, so 'breakout_detected' rows displayed empty consolidation data."""
    _seed(temp_db)
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO breakout_signals (symbol, date, breakout_status, breakout_direction, "
        "consolidation_bottom, consolidation_top, consolidation_range_pct, consolidation_duration_days) "
        "VALUES ('AAPL','2026-06-30','breakout_detected','bullish', 130.0, 142.0, 9.2, 35)"
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM research_overview WHERE symbol='AAPL'").fetchone()
    conn.close()
    assert row["breakout_status"] == "breakout_detected"
    assert row["breakout_support"] == 130.0
    assert row["breakout_resistance"] == 142.0
    assert row["breakout_range_pct"] == 9.2
    assert row["breakout_duration_days"] == 35


def test_screener_overview_alias_still_works(temp_db):
    _seed(temp_db)
    resp = client.get("/api/screener/overview")
    assert resp.status_code == 200
    aapl = next(r for r in resp.json()["rows"] if r["symbol"] == "AAPL")
    assert aapl["gates_passed"] == 6
