import sqlite3
import pandas as pd
import backend.scripts.fundamentals_fetch as ff
from backend.database.connection import get_db_connection


class _FakeTicker:
    def __init__(self, symbol):
        self.info = {"longName": f"{symbol} Inc", "sector": "Technology", "currency": "USD",
                     "grossMargins": 0.65, "returnOnEquity": 0.30, "freeCashflow": 300.0,
                     "totalRevenue": 1000.0, "marketCap": 2.0e12, "trailingPE": 30.0}
        self.income_stmt = {"EBIT": 400.0, "Tax Provision": 80.0, "Pretax Income": 400.0,
                            "Interest Expense": 20.0, "Diluted EPS": [1.0, 1.2, 1.5, 1.8]}
        self.balance_sheet = {"Total Debt": 200.0, "Stockholders Equity": 800.0,
                              "Cash And Cash Equivalents": 100.0}
        self.earnings_history = [{"epsActual": 1.8, "epsEstimate": 1.6},
                                 {"epsActual": 1.5, "epsEstimate": 1.5}]


def _seed_universe(temp_db, symbols):
    from datetime import datetime
    conn = sqlite3.connect(str(temp_db))
    now = datetime.now().isoformat()
    for s in symbols:
        conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled, added_at) VALUES (?, 1, ?)", (s, now))
    # Seed quality gates
    import json
    gates = {"gross_margin":0.60,"roe":0.15,"roic":0.10,"levered_fcf_margin":0.20,
             "interest_cover":3.0,"eps_5y_growth":0.10,"free_cashflow":0}
    conn.execute("INSERT OR IGNORE INTO screener_settings (key, value_json) VALUES (?, ?)",
                 ("quality_gates", json.dumps(gates)))
    conn.commit(); conn.close()


def test_fetch_all_writes_rows(temp_db, monkeypatch):
    _seed_universe(temp_db, ["AAPL", "MSFT"])
    monkeypatch.setattr(ff, "_yf_ticker", lambda s: _FakeTicker(s))
    conn = get_db_connection()
    result = ff.fetch_all(conn)
    row = conn.execute("SELECT gates_passed, roic_method, gross_margin, long_name FROM fundamentals WHERE symbol='AAPL'").fetchone()
    conn.close()
    assert result["rows_written"] == 2
    assert row[0] == 7           # gates_passed
    assert row[1] == "nopat"     # roic_method
    assert row[2] == 0.65        # gross_margin
    assert row[3] == "AAPL Inc"


def test_fetch_records_error_not_crash(temp_db, monkeypatch):
    _seed_universe(temp_db, ["BAD"])
    def _boom(s): raise RuntimeError("yf down")
    monkeypatch.setattr(ff, "_yf_ticker", _boom)
    conn = get_db_connection()
    result = ff.fetch_all(conn)
    conn.close()
    assert result["errors"] == 1
    assert result["failures"][0]["symbol"] == "BAD"


def test_as_dict_dataframe_reverses_newest_first_columns_to_oldest_first():
    # yfinance shape: index = line items, columns = period timestamps, NEWEST first.
    df = pd.DataFrame(
        {
            pd.Timestamp("2025-12-31"): [500, 2.0],
            pd.Timestamp("2024-12-31"): [400, 1.0],
        },
        index=["EBIT", "Diluted EPS"],
    )
    out = ff._as_dict(df)
    assert out["EBIT"] == [400, 500]
    assert out["Diluted EPS"] == [1.0, 2.0]


def test_as_dict_dataframe_failure_logs_and_returns_empty(monkeypatch, caplog):
    class _BrokenDF:
        @property
        def columns(self):
            raise RuntimeError("shape changed")

    with caplog.at_level("WARNING"):
        out = ff._as_dict(_BrokenDF())
    assert out == {}
    assert "_as_dict" in caplog.text


def test_earnings_list_dataframe_yields_row_dicts():
    hist = pd.DataFrame(
        {"epsActual": [1.5, 1.8], "epsEstimate": [1.5, 1.6]},
        index=pd.to_datetime(["2025-06-30", "2025-09-30"]),
    )
    out = ff._earnings_list(hist)
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0]["epsActual"] == 1.5
    assert out[1]["epsEstimate"] == 1.6


def test_earnings_list_failure_logs_and_returns_empty(caplog):
    class _BrokenHist:
        def reset_index(self):
            raise RuntimeError("shape changed")

    with caplog.at_level("WARNING"):
        out = ff._earnings_list(_BrokenHist())
    assert out == []
    assert "_earnings_list" in caplog.text
