"""Batched yfinance ingestion service for market_data table.

Reads enabled symbols from tracked_universe, asks yfinance for bars since
each symbol's latest stored bar, writes rows idempotently to market_data.
"""
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

BATCH_SIZE = 50


def _yf_download(symbols, start=None, end=None, group_by="ticker", threads=True, progress=False, auto_adjust=False):
    """Indirected so tests can monkeypatch."""
    import yfinance as yf
    return yf.download(
        tickers=symbols, start=start, end=end, group_by=group_by,
        threads=threads, progress=progress, auto_adjust=auto_adjust,
    )


def _latest_bar_date(conn, symbol: str) -> Optional[str]:
    row = conn.execute("SELECT MAX(time) FROM market_data WHERE symbol = ?", (symbol,)).fetchone()
    return row[0] if row and row[0] else None


def _enabled_symbols(conn) -> list[str]:
    rows = conn.execute(
        "SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol"
    ).fetchall()
    return [r[0] for r in rows]


def _normalize_response(resp, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """yf.download returns either a DataFrame (single symbol) or dict / multi-index DataFrame.

    Normalize to {symbol: DataFrame_with_OHLCV_cols}.
    """
    if isinstance(resp, dict):
        return {s: resp[s] for s in symbols if s in resp and resp[s] is not None}
    if isinstance(resp, pd.DataFrame):
        if isinstance(resp.columns, pd.MultiIndex):
            level0 = resp.columns.get_level_values(0).unique()
            return {s: resp[s].copy() for s in symbols if s in level0}
        else:
            if symbols:
                return {symbols[0]: resp.copy()}
    return {}


def _safe_float(v) -> Optional[float]:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> Optional[int]:
    try:
        if v is None or pd.isna(v):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _insert_bars(conn, symbol: str, df: pd.DataFrame, today: date) -> int:
    """Insert OHLCV bars idempotently. Returns number of rows actually inserted.

    Skips any bar dated `today` or later: yfinance returns an intraday snapshot
    under today's date when called during the trading session, which we don't
    want to treat as an EOD close. Real EOD bars only land tomorrow.
    """
    if df is None or df.empty:
        return 0
    today_str = today.isoformat()
    inserted = 0
    for ts, row in df.iterrows():
        if pd.isna(row.get("Close")):
            continue
        date_str = ts.strftime("%Y-%m-%d")
        if date_str >= today_str:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO market_data "
            "(symbol, time, open, high, low, close, adj_close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                symbol, date_str,
                _safe_float(row.get("Open")),
                _safe_float(row.get("High")),
                _safe_float(row.get("Low")),
                _safe_float(row.get("Close")),
                _safe_float(row.get("Adj Close", row.get("Close"))),
                _safe_int(row.get("Volume")),
            ),
        )
        if cur.rowcount > 0:
            inserted += 1
    return inserted


def ingest_market_data(default_lookback_days: int = 730) -> dict:
    """Pull market data from yfinance for all enabled symbols in tracked_universe.

    For each symbol: start = max(stored bar) + 1 day, or today - default_lookback_days
    if no bars stored yet.

    Default is 730 calendar days (~504 trading days) so the 252-day rolling MRSI
    window has at least 252 valid output points on a fresh sync. A 365-day
    lookback yields ~252 trading days, which only produces an MRSI value on the
    very last bar.

    Returns: {
        "symbols_processed": int,
        "rows_inserted": int,
        "errors": int,
        "failures": list[{"symbol": str, "reason": str}],
    }

    "failures" lists symbols where yfinance returned no usable data (the most
    common cause of "I added a ticker and nothing happened" — typically a
    typo'd or non-yfinance symbol like "TSMC" instead of "TSM").
    """
    conn = get_db_connection()
    symbols = _enabled_symbols(conn)
    if not symbols:
        conn.close()
        return {"symbols_processed": 0, "rows_inserted": 0, "errors": 0, "failures": []}

    today = datetime.now().date()
    rows_inserted = 0
    errors = 0
    processed = 0
    failures: list[dict] = []
    now_iso = datetime.now().astimezone().isoformat()

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        starts = []
        for sym in batch:
            last = _latest_bar_date(conn, sym)
            if last:
                next_day = (datetime.strptime(last, "%Y-%m-%d").date() + timedelta(days=1))
                starts.append(next_day)
            else:
                starts.append(today - timedelta(days=default_lookback_days))
        batch_start = min(starts).isoformat()
        batch_end = (today + timedelta(days=1)).isoformat()

        if batch_start >= batch_end:
            # Symbols already up to date — count them as processed, no failure.
            processed += len(batch)
            continue

        try:
            resp = _yf_download(batch, start=batch_start, end=batch_end, threads=True)
            per_symbol = _normalize_response(resp, batch)
            for sym in batch:
                df = per_symbol.get(sym)
                inserted_n = _insert_bars(conn, sym, df, today)
                rows_inserted += inserted_n
                conn.execute(
                    "UPDATE tracked_universe SET last_synced_at = ? WHERE symbol = ?",
                    (now_iso, sym),
                )
                processed += 1
                # If we wrote zero bars AND the symbol has no prior bars, the
                # symbol is effectively dead from the user's POV — surface it.
                # This catches: df=None (yfinance dropped from response),
                # df.empty (returned but empty), AND the trickier case where
                # df has 500 rows of all-NaN Close (e.g. HEIA: yfinance returns
                # the shape but logs "possibly delisted; no timezone found",
                # which silently filters out in _insert_bars' NaN check).
                if inserted_n == 0 and _latest_bar_date(conn, sym) is None:
                    failures.append({"symbol": sym, "reason": "yfinance returned no usable bars (invalid ticker or delisted?)"})
        except Exception as e:
            logger.error(f"❌ yf.download failed for batch {batch[0]}..{batch[-1]}: {e}")
            errors += len(batch)
            for sym in batch:
                failures.append({"symbol": sym, "reason": f"batch fetch error: {type(e).__name__}: {e}"})
            continue

        conn.commit()

    conn.close()
    logger.info(
        f"✅ Market data ingest: {processed} symbols, {rows_inserted} new rows, "
        f"{errors} errors, {len(failures)} per-symbol failures"
    )
    return {
        "symbols_processed": processed,
        "rows_inserted": rows_inserted,
        "errors": errors,
        "failures": failures,
    }
