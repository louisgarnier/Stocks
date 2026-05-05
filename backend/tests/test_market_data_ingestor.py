"""Tests for the yfinance-backed market data ingestor."""
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pytest

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


def test_ingest_records_failure_for_invalid_ticker(temp_db, monkeypatch):
    """When yfinance returns nothing for a brand-new symbol, ingest must record a failure.

    This is the TSMC class of bug — typo / non-yfinance symbol silently dropping
    out of the batch response with no signal to the user.
    """
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('TSMC', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    # yfinance returns AAPL but drops TSMC from the response (typical 404 silent-drop)
    fake = _fake_ohlcv_df("AAPL", days=3)
    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: {"AAPL": fake})

    result = ingest_market_data()
    assert {f["symbol"] for f in result["failures"]} == {"TSMC"}
    assert "no usable bars" in result["failures"][0]["reason"]
    assert result["symbols_processed"] == 2
    assert result["rows_inserted"] == 3  # AAPL still landed


def test_ingest_records_failure_for_all_nan_close(temp_db, monkeypatch):
    """yfinance can return a df-shaped response with all-NaN Close
    (HEIA case: 'possibly delisted; no timezone found'). The previous shape-
    based check missed this because df was neither None nor empty. Detection
    must rely on actually-inserted row count.
    """
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('HEIA', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    today = datetime.now().date()
    dates = pd.date_range(today - timedelta(days=4), today - timedelta(days=1), freq="D")
    nan_df = pd.DataFrame({
        "Open": [None] * 4, "High": [None] * 4, "Low": [None] * 4,
        "Close": [None] * 4, "Adj Close": [None] * 4, "Volume": [None] * 4,
    }, index=dates)

    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: {"HEIA": nan_df})

    result = ingest_market_data()
    assert result["rows_inserted"] == 0
    assert {f["symbol"] for f in result["failures"]} == {"HEIA"}
    assert "delisted" in result["failures"][0]["reason"].lower() or "invalid" in result["failures"][0]["reason"].lower()


# ---------------------------------------------------------------------------
# yfinance response-shape coverage — locks the contract so future bugs in this
# layer fail loudly. Each shape is a real failure mode observed in production
# or in yfinance's own test suite.
# ---------------------------------------------------------------------------

def _seed_one(temp_db, symbol="X"):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES (?, '[\"manual\"]', 1, datetime('now'))",
        (symbol,),
    )
    conn.commit()
    conn.close()


def _make_dates(days=3):
    today = datetime.now().date()
    return pd.to_datetime([today - timedelta(days=days - i) for i in range(days)])


@pytest.mark.parametrize(
    "shape_name, build_response",
    [
        # 1. yfinance silently dropped the symbol from the response dict
        ("symbol_dropped", lambda: {}),

        # 2. yfinance returned an empty DataFrame for the symbol
        ("empty_df", lambda: {"X": pd.DataFrame()}),

        # 3. yfinance returned 500 rows of all-NaN Close (HEIA case)
        ("all_nan_close", lambda: {"X": pd.DataFrame({
            "Open": [None, None, None], "High": [None, None, None], "Low": [None, None, None],
            "Close": [None, None, None], "Adj Close": [None, None, None], "Volume": [None, None, None],
        }, index=_make_dates())}),

        # 4. yfinance returned a DataFrame whose Close column is missing entirely
        ("missing_close_col", lambda: {"X": pd.DataFrame({
            "Open": [10.0, 11.0, 12.0], "High": [11.0, 12.0, 13.0], "Low": [9.0, 10.0, 11.0],
        }, index=_make_dates())}),
    ],
)
def test_ingest_flags_failure_for_each_unusable_yfinance_shape(temp_db, monkeypatch, shape_name, build_response):
    """All four 'no usable data' shapes from yfinance must land as a per-symbol failure."""
    _seed_one(temp_db)
    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: build_response())

    result = ingest_market_data()
    assert result["rows_inserted"] == 0, f"{shape_name}: expected 0 inserts"
    assert {f["symbol"] for f in result["failures"]} == {"X"}, f"{shape_name}: missing X failure"


def test_ingest_handles_partial_nan_close(temp_db, monkeypatch):
    """Mixed bag: some rows have Close, some are NaN. The NaN ones get skipped,
    valid ones land. NOT a failure since some rows did insert."""
    _seed_one(temp_db, "Y")
    today = datetime.now().date()
    dates = pd.to_datetime([today - timedelta(days=4 - i) for i in range(4)])
    df = pd.DataFrame({
        "Open":  [10.0, 11.0, 12.0, 13.0],
        "High":  [11.0, 12.0, 13.0, 14.0],
        "Low":   [9.0, 10.0, 11.0, 12.0],
        "Close": [10.5, None, 12.5, None],   # 2 valid, 2 NaN
        "Adj Close": [10.5, None, 12.5, None],
        "Volume": [1000, None, 1100, None],
    }, index=dates)

    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: {"Y": df})

    result = ingest_market_data()
    assert result["rows_inserted"] == 2  # only the valid Close rows
    assert result["failures"] == []      # not a failure — partial data is data


def test_ingest_handles_multiindex_response(temp_db, monkeypatch):
    """yfinance returns a multi-index DataFrame (default for multi-symbol batch)
    with one good symbol and one missing — only the missing one fails."""
    conn = sqlite3.connect(str(temp_db))
    for sym in ("AAA", "BBB"):
        conn.execute(
            "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
            "VALUES (?, '[\"manual\"]', 1, datetime('now'))",
            (sym,),
        )
    conn.commit()
    conn.close()

    today = datetime.now().date()
    dates = pd.to_datetime([today - timedelta(days=2), today - timedelta(days=1)])
    cols = pd.MultiIndex.from_tuples(
        [("AAA", "Open"), ("AAA", "High"), ("AAA", "Low"), ("AAA", "Close"),
         ("AAA", "Adj Close"), ("AAA", "Volume"),
         ("BBB", "Open"), ("BBB", "High"), ("BBB", "Low"), ("BBB", "Close"),
         ("BBB", "Adj Close"), ("BBB", "Volume")]
    )
    df = pd.DataFrame(
        [[10, 11, 9, 10.5, 10.5, 1000, None, None, None, None, None, None],
         [11, 12, 10, 11.5, 11.5, 1100, None, None, None, None, None, None]],
        index=dates, columns=cols,
    )
    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: df)

    result = ingest_market_data()
    assert result["rows_inserted"] == 2  # AAA both bars
    assert {f["symbol"] for f in result["failures"]} == {"BBB"}


def test_ingest_does_not_flag_failure_for_already_synced_symbol(temp_db, monkeypatch):
    """If a symbol has prior bars and yfinance returns nothing this time
    (because batch_start >= batch_end after the today-skip), it's not a failure."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
        "VALUES ('AAPL', ?, 100, 102, 99, 101, 101, 1000000)",
        (yesterday.isoformat(),),
    )
    conn.commit()
    conn.close()

    # yfinance returns nothing — already up-to-date through yesterday
    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: {})

    result = ingest_market_data()
    assert result["failures"] == []  # not a failure — symbol already had data
