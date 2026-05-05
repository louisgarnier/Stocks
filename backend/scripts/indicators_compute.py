"""Pure pandas-based indicator computation functions.

Inputs are DataFrames with OHLCV columns; outputs are the same frames with
indicator columns added. No DB I/O — see compute_for_symbol() in Story D-4
for the per-symbol orchestrator that does the SQL.

Indicator definitions:
- MA 50/100/150/200: simple rolling mean of adj_close
- BB(20, 2): MA20 of adj_close ± 2 stddev; bb_width = (upper - lower) / MA20
- RSI(14): standard 14-period RSI using Wilder's smoothing (EWM with alpha=1/14)
- ATR(14): Wilder's true range smoothed over 14 periods (uses raw OHLC)
- Volume MA(20): simple rolling mean of volume
- MRSI (Mansfield Relative Strength): ((stock_close / bench_close) /
  MA(stock/bench, 252) - 1) * 100; centered at 0
"""
from typing import Optional

import pandas as pd


def compute_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute MA / BB / RSI / ATR / Volume MA on a DataFrame.

    Input df must have columns: time (sorted ascending), open, high, low,
    close, adj_close, volume. Returns the same df with indicator columns
    appended (does not mutate the input).
    """
    out = df.copy()
    close = out["adj_close"]

    # Moving averages on adjusted close
    out["ma_50"] = close.rolling(50).mean()
    out["ma_100"] = close.rolling(100).mean()
    out["ma_150"] = close.rolling(150).mean()
    out["ma_200"] = close.rolling(200).mean()

    # Bollinger Bands (20, 2)
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    out["bb_upper_20"] = ma20 + 2 * std20
    out["bb_lower_20"] = ma20 - 2 * std20
    width_denom = ma20.where(ma20 != 0)
    out["bb_width"] = (out["bb_upper_20"] - out["bb_lower_20"]) / width_denom

    # RSI(14) using Wilder's smoothing (EWM with alpha = 1/14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.where(avg_loss != 0)
    out["rsi_14"] = 100 - (100 / (1 + rs))
    out["rsi_14"] = out["rsi_14"].where(avg_loss != 0, 100.0)  # all gains → RSI = 100

    # ATR(14) — uses raw OHLC (volatility metric, not split-adjusted)
    hl = out["high"] - out["low"]
    hc = (out["high"] - out["close"].shift()).abs()
    lc = (out["low"] - out["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    out["atr_14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    # Volume MA(20)
    out["volume_ma_20"] = out["volume"].rolling(20).mean()

    return out


def compute_mrsi(stock_df: pd.DataFrame, bench_df: pd.DataFrame) -> pd.Series:
    """Compute Mansfield Relative Strength.

    Inputs: stock_df + bench_df both with columns 'time' + 'adj_close'.
    Returns: pd.Series of MRSI values indexed by the merged 'time' values.

    Formula:
        RS    = stock_close / bench_close
        RS_MA = MA(RS, 252)
        MRSI  = (RS / RS_MA) - 1

    Centered at 0, natural ratio scale (positive ≈ outperforming, negative ≈
    underperforming). Typical magnitudes ~0.3 for active stocks; not strictly
    bounded but rarely exceeds ±0.5.
    """
    merged = stock_df[["time", "adj_close"]].merge(
        bench_df[["time", "adj_close"]],
        on="time", suffixes=("_stock", "_bench"),
    ).sort_values("time").reset_index(drop=True)

    rs = merged["adj_close_stock"] / merged["adj_close_bench"].where(merged["adj_close_bench"] != 0)
    rs_ma = rs.rolling(252).mean()
    mrsi = (rs / rs_ma.where(rs_ma != 0)) - 1
    return pd.Series(mrsi.values, index=merged["time"].values)


# ---------------------------------------------------------------------------
# DB-backed orchestrator (Story D-4)
# ---------------------------------------------------------------------------

from backend.api.utils.logger import logger  # noqa: E402 — after pure functions

_BENCHMARK_BY_CURRENCY = {
    "USD": "^GSPC",
    "EUR": "^FCHI",
    "GBP": "^FTSE",
}


def _resolve_benchmark(currency: Optional[str], stored_benchmark: Optional[str]) -> Optional[str]:
    """Pick the benchmark symbol for a given symbol's currency.

    Priority: stored_benchmark column (set at seed time) → currency mapping → fallback ^GSPC.
    """
    if stored_benchmark:
        return stored_benchmark
    return _BENCHMARK_BY_CURRENCY.get(currency or "USD", "^GSPC")


def _read_market_data(conn, symbol: str) -> pd.DataFrame:
    """Pull market_data rows for a symbol as a DataFrame."""
    df = pd.read_sql_query(
        "SELECT time, open, high, low, close, adj_close, volume FROM market_data "
        "WHERE symbol = ? ORDER BY time ASC",
        conn,
        params=[symbol],
    )
    return df


def _none_if_nan(v):
    """Coerce NaN / None / non-floats to None for SQLite parameter binding."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_for_symbol(conn, symbol: str) -> int:
    """Compute indicators for one symbol. Returns rows written.

    Reads market_data for `symbol`, resolves its benchmark, computes all
    indicators (including MRSI vs benchmark when available), and UPSERTs
    into the indicators table. Idempotent via ON CONFLICT (symbol, time)
    DO UPDATE SET (every indicator column gets refreshed).
    """
    cur = conn.cursor()
    row = cur.execute(
        "SELECT currency, benchmark FROM tracked_universe WHERE symbol = ?", (symbol,)
    ).fetchone()
    if not row:
        return 0
    benchmark = _resolve_benchmark(row[0], row[1])

    df = _read_market_data(conn, symbol)
    if df.empty:
        return 0

    out = compute_basic_indicators(df)

    # MRSI: needs the benchmark's market_data with overlapping dates
    bench_df = (
        _read_market_data(conn, benchmark)
        if benchmark and benchmark != symbol
        else pd.DataFrame()
    )
    if not bench_df.empty:
        mrsi_series = compute_mrsi(df, bench_df)
        out = out.assign(mrsi=out["time"].map(lambda t: mrsi_series.get(t)))
    else:
        out = out.assign(mrsi=None)

    written = 0
    for _, r in out.iterrows():
        cur.execute(
            "INSERT INTO indicators "
            "(symbol, time, ma_50, ma_100, ma_150, ma_200, "
            " bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (symbol, time) DO UPDATE SET "
            " ma_50 = excluded.ma_50, "
            " ma_100 = excluded.ma_100, "
            " ma_150 = excluded.ma_150, "
            " ma_200 = excluded.ma_200, "
            " bb_upper_20 = excluded.bb_upper_20, "
            " bb_lower_20 = excluded.bb_lower_20, "
            " bb_width = excluded.bb_width, "
            " rsi_14 = excluded.rsi_14, "
            " mrsi = excluded.mrsi, "
            " atr_14 = excluded.atr_14, "
            " volume_ma_20 = excluded.volume_ma_20",
            (
                symbol, r["time"],
                _none_if_nan(r.get("ma_50")), _none_if_nan(r.get("ma_100")),
                _none_if_nan(r.get("ma_150")), _none_if_nan(r.get("ma_200")),
                _none_if_nan(r.get("bb_upper_20")), _none_if_nan(r.get("bb_lower_20")),
                _none_if_nan(r.get("bb_width")),
                _none_if_nan(r.get("rsi_14")),
                _none_if_nan(r.get("mrsi")),
                _none_if_nan(r.get("atr_14")),
                _none_if_nan(r.get("volume_ma_20")),
            ),
        )
        written += 1
    conn.commit()
    return written


def compute_all(conn) -> dict:
    """Compute indicators for every enabled symbol in tracked_universe.

    Returns: {
        "symbols_processed": list[str],
        "rows_written": int,
        "errors": int,
        "failures": list[{"symbol": str, "reason": str}],
    }

    "failures" only captures real exceptions (compute crashed for this symbol).
    Symbols with no market_data return 0 rows silently — that's an upstream
    ingest concern, already surfaced by /sync/market-data.
    """
    rows = conn.execute(
        "SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol"
    ).fetchall()
    symbols_processed = []
    rows_written = 0
    errors = 0
    failures: list[dict] = []
    for (sym,) in rows:
        try:
            n = compute_for_symbol(conn, sym)
            if n > 0:
                symbols_processed.append(sym)
                rows_written += n
        except Exception as e:
            logger.error(f"❌ indicators compute failed for {sym}: {e}")
            errors += 1
            failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    logger.info(
        f"✅ Indicators: {len(symbols_processed)} symbols processed, "
        f"{rows_written} rows written, {errors} errors"
    )
    return {
        "symbols_processed": symbols_processed,
        "rows_written": rows_written,
        "errors": errors,
        "failures": failures,
    }
