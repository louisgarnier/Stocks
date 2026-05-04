"""Tests for the yfinance-backed market data ingestor."""
import sqlite3
from datetime import datetime, timedelta

import pandas as pd

from backend.scripts.market_data_ingestor import ingest_market_data


def _fake_ohlcv_df(symbol: str, days: int = 5) -> pd.DataFrame:
    """Build a tiny DataFrame in the shape yf.download returns for one symbol."""
    end = datetime(2026, 4, 27)
    dates = pd.date_range(end - timedelta(days=days - 1), end, freq="D")
    return pd.DataFrame({
        "Open": [100.0 + i for i in range(days)],
        "High": [102.0 + i for i in range(days)],
        "Low": [99.0 + i for i in range(days)],
        "Close": [101.0 + i for i in range(days)],
        "Adj Close": [101.0 + i for i in range(days)],
        "Volume": [1_000_000 + i * 1000 for i in range(days)],
    }, index=dates)


def test_ingest_writes_rows(temp_db, monkeypatch):
    """ingest_market_data writes one row per (symbol, date) to market_data."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    fake = _fake_ohlcv_df("AAPL", days=5)
    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(
        ingestor, "_yf_download",
        lambda symbols, start=None, end=None, **k: {"AAPL": fake},
    )

    result = ingest_market_data()
    assert result["symbols_processed"] == 1
    assert result["rows_inserted"] == 5

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM market_data WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert cnt == 5


def test_ingest_idempotent(temp_db, monkeypatch):
    """Running ingest twice doesn't duplicate rows (PK conflict resolved)."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(
        ingestor, "_yf_download",
        lambda *a, **k: {"AAPL": _fake_ohlcv_df("AAPL", days=5)},
    )

    ingest_market_data()
    ingest_market_data()

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM market_data WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert cnt == 5  # not 10


def test_ingest_skips_disabled_symbols(temp_db, monkeypatch):
    """Symbols with enabled=0 are skipped."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 0, datetime('now'))"
    )
    conn.commit()
    conn.close()

    import backend.scripts.market_data_ingestor as ingestor
    called = []
    monkeypatch.setattr(
        ingestor, "_yf_download",
        lambda symbols, **k: called.append(symbols) or {},
    )

    result = ingest_market_data()
    assert result["symbols_processed"] == 0
    assert called == []


def test_ingest_only_fetches_since_last_bar(temp_db, monkeypatch):
    """For each symbol, yfinance is asked for bars starting after the latest stored bar."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
        "VALUES ('AAPL', '2026-04-20', 100, 102, 99, 101, 101, 1000000)"
    )
    conn.commit()
    conn.close()

    import backend.scripts.market_data_ingestor as ingestor
    captured = {}

    def fake_download(symbols, start=None, end=None, **k):
        captured["start"] = start
        captured["symbols"] = symbols
        return {}

    monkeypatch.setattr(ingestor, "_yf_download", fake_download)

    ingest_market_data()
    assert captured["start"] >= "2026-04-21"


def test_ingest_skips_today_intraday_bar(temp_db, monkeypatch):
    """yfinance returns an intraday snapshot dated today when called mid-session.

    The ingestor must drop that row so we never write partial-day data into
    market_data (signals + indicators would otherwise fire against incomplete
    closes). Bars dated yesterday and earlier go in normally.
    """
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('TSLA', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    df = pd.DataFrame({
        "Open":      [380.0, 385.0, 390.0],
        "High":      [382.0, 388.0, 394.0],
        "Low":       [378.0, 384.0, 385.0],
        "Close":     [381.0, 387.0, 386.99],   # today's close = intraday snapshot — must be dropped
        "Adj Close": [381.0, 387.0, 386.99],
        "Volume":    [10_000_000, 12_000_000, 23_686_053],
    }, index=pd.to_datetime([two_days_ago, yesterday, today]))

    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: {"TSLA": df})

    result = ingest_market_data()
    assert result["rows_inserted"] == 2  # not 3

    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT time FROM market_data WHERE symbol='TSLA' ORDER BY time"
    ).fetchall()
    conn.close()
    assert [r[0] for r in rows] == [two_days_ago.isoformat(), yesterday.isoformat()]
