"""Tests for index list seeders."""
import json

import pandas as pd
import pytest

from backend.scripts.universe_seeders import seed_index


def _fake_sp500_table():
    """Mimic what pd.read_html returns for the S&P 500 Wikipedia page."""
    return pd.DataFrame({
        "Symbol": ["AAPL", "MSFT", "NVDA"],
        "Security": ["Apple Inc.", "Microsoft Corp.", "NVIDIA Corp."],
        "GICS Sector": ["Information Technology", "Information Technology", "Information Technology"],
    })


def _fake_cac40_table():
    return pd.DataFrame({
        "Ticker": ["MC.PA", "AIR.PA"],
        "Company": ["LVMH", "Airbus"],
        "Sector": ["Consumer", "Industrials"],
    })


def test_seed_sp500_inserts_rows(temp_db, monkeypatch):
    """seed_index('sp500') populates tracked_universe with sources=['sp500']."""
    import backend.scripts.universe_seeders as seeders
    monkeypatch.setattr(seeders, "_fetch_sp500_dataframe", lambda: _fake_sp500_table())

    result = seed_index("sp500")
    assert result["inserted"] == 3
    assert result["count"] == 3

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT symbol, name, sector, currency, sources FROM tracked_universe ORDER BY symbol"
    ).fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["AAPL", "MSFT", "NVDA"]
    assert rows[0][1] == "Apple Inc."
    assert rows[0][2] == "Information Technology"
    assert rows[0][3] == "USD"
    assert json.loads(rows[0][4]) == ["sp500"]


def test_seed_sp500_idempotent_merges_sources(temp_db, monkeypatch):
    """If a symbol is already in tracked_universe with another source, seeding adds 'sp500' to sources."""
    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    import backend.scripts.universe_seeders as seeders
    monkeypatch.setattr(seeders, "_fetch_sp500_dataframe", lambda: _fake_sp500_table())
    seed_index("sp500")

    conn = sqlite3.connect(str(temp_db))
    sources = conn.execute("SELECT sources FROM tracked_universe WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert set(json.loads(sources)) == {"manual", "sp500"}


def test_seed_cac40(temp_db, monkeypatch):
    import backend.scripts.universe_seeders as seeders
    monkeypatch.setattr(seeders, "_fetch_cac40_dataframe", lambda: _fake_cac40_table())

    result = seed_index("cac40")
    assert result["inserted"] == 2

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    row = conn.execute("SELECT currency, benchmark FROM tracked_universe WHERE symbol='MC.PA'").fetchone()
    conn.close()
    assert row[0] == "EUR"
    assert row[1] == "^FCHI"


def test_seed_unknown_index_raises(temp_db):
    with pytest.raises(ValueError, match="unknown index"):
        seed_index("ftse101")
