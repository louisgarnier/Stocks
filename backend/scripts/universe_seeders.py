"""Wikipedia-based index list seeders for tracked_universe."""
import json
from datetime import datetime
from io import StringIO

import pandas as pd
import requests

from backend.database.connection import get_db_connection

_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CAC40_URL = "https://en.wikipedia.org/wiki/CAC_40"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Stocks/1.0"


def _read_html_with_ua(url: str) -> list[pd.DataFrame]:
    """Fetch HTML with a real User-Agent (Wikipedia rejects pandas' default UA), parse tables."""
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=30)
    resp.raise_for_status()
    return pd.read_html(StringIO(resp.text))


def _fetch_sp500_dataframe() -> pd.DataFrame:
    """Pull the S&P 500 constituents table from Wikipedia."""
    tables = _read_html_with_ua(_SP500_URL)
    df = tables[0]
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    df = df.rename(columns={col: "Symbol"})
    # Some tickers like BRK.B come with a period; yfinance prefers BRK-B
    df["Symbol"] = df["Symbol"].astype(str).str.replace(".", "-", regex=False)
    return df


def _fetch_cac40_dataframe() -> pd.DataFrame:
    """Pull the CAC 40 constituents table from Wikipedia."""
    tables = _read_html_with_ua(_CAC40_URL)
    for t in tables:
        if "Ticker" in t.columns:
            return t
    raise RuntimeError("Could not find CAC 40 ticker table on Wikipedia")


_INDEX_CONFIG = {
    "sp500": {
        "currency": "USD",
        "benchmark": "^GSPC",
        "fetcher": "_fetch_sp500_dataframe",
        "symbol_col": "Symbol",
        "name_col": "Security",
        "sector_col": "GICS Sector",
    },
    "cac40": {
        "currency": "EUR",
        "benchmark": "^FCHI",
        "fetcher": "_fetch_cac40_dataframe",
        "symbol_col": "Ticker",
        "name_col": "Company",
        "sector_col": "Sector",
    },
}


FX_SYMBOLS = [("EURUSD=X", "EUR/USD", "USD")]


def seed_fx_symbols(conn) -> int:
    """Seed FX rate symbols so they flow through the normal market-data ingest.

    Source tag 'fx' (like 'benchmark') — INSERT OR IGNORE keeps it idempotent.
    """
    n = 0
    for symbol, name, currency in FX_SYMBOLS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
            "VALUES (?, ?, ?, ?, 1, datetime('now'))",
            (symbol, name, currency, json.dumps(["fx"])),
        )
        n += cur.rowcount
    conn.commit()
    return n


def seed_index(index_name: str) -> dict:
    """Fetch the index member list and upsert into tracked_universe.

    For each member: if symbol already exists, append index_name to its sources
    array (idempotent). Else create a new row with sources=[index_name].

    Returns: {"index": str, "inserted": int, "updated": int, "count": int}
    """
    import backend.scripts.universe_seeders as _self
    if index_name not in _INDEX_CONFIG:
        raise ValueError(f"unknown index: {index_name}")
    cfg = _INDEX_CONFIG[index_name]
    fetcher = getattr(_self, cfg["fetcher"])
    df = fetcher()

    conn = get_db_connection()
    inserted = 0
    updated = 0
    now = datetime.now().astimezone().isoformat()

    for _, row in df.iterrows():
        sym = str(row[cfg["symbol_col"]]).strip().upper()
        if not sym or sym == "NAN":
            continue
        name = None
        if cfg["name_col"] in row and not pd.isna(row[cfg["name_col"]]):
            name = str(row[cfg["name_col"]])
        sector = None
        if cfg["sector_col"] in row and not pd.isna(row[cfg["sector_col"]]):
            sector = str(row[cfg["sector_col"]])

        existing = conn.execute(
            "SELECT sources FROM tracked_universe WHERE symbol = ?", (sym,)
        ).fetchone()
        if existing:
            sources = json.loads(existing[0] or "[]")
            if index_name not in sources:
                sources.append(index_name)
                conn.execute(
                    "UPDATE tracked_universe SET sources = ?, sector = COALESCE(sector, ?), "
                    "name = COALESCE(name, ?) WHERE symbol = ?",
                    (json.dumps(sources), sector, name, sym),
                )
                updated += 1
        else:
            conn.execute(
                "INSERT INTO tracked_universe "
                "(symbol, name, sector, currency, benchmark, sources, enabled, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (sym, name, sector, cfg["currency"], cfg["benchmark"],
                 json.dumps([index_name]), now),
            )
            inserted += 1

    cnt = conn.execute(
        "SELECT COUNT(*) FROM tracked_universe WHERE sources LIKE ?",
        (f'%"{index_name}"%',),
    ).fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO tracked_indices (name, enabled, last_refreshed_at, symbol_count) "
        "VALUES (?, COALESCE((SELECT enabled FROM tracked_indices WHERE name=?), 1), ?, ?)",
        (index_name, index_name, now, cnt),
    )
    conn.commit()
    conn.close()
    return {"index": index_name, "inserted": inserted, "updated": updated, "count": cnt}
