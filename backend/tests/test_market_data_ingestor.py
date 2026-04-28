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
