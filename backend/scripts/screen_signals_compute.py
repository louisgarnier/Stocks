"""Screening signals (f_watch, exact formulas) — momentum / MA cross / volume / 52w."""
import logging
from datetime import datetime, timezone
import pandas as pd

logger = logging.getLogger(__name__)


def _none_if_nan(v):
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _ret(closes, n):
    if len(closes) > n and closes[-(n + 1)]:
        return (closes[-1] - closes[-(n + 1)]) / closes[-(n + 1)] * 100.0
    return None


def _ma_cross_status(ma50, ma100, ma150):
    if None in (ma50, ma100, ma150):
        return None
    if ma50 > ma100 and ma100 > ma150:
        return "All Bullish"
    if ma50 > ma150:
        return "Mostly Bullish"
    if ma50 < ma100 and ma100 < ma150:
        return "All Bearish"
    if ma50 < ma150:
        return "Mostly Bearish"
    return "Mixed"


def compute_signals(df: pd.DataFrame, ind: dict) -> dict:
    df = df.sort_values("time").reset_index(drop=True)
    closes = [float(x) for x in df["close"].tolist()]
    c = closes[-1]
    ma50, ma100, ma150, ma200 = (ind.get("ma_50"), ind.get("ma_100"),
                                 ind.get("ma_150"), ind.get("ma_200"))

    m5, m20, m60 = _ret(closes, 5), _ret(closes, 20), _ret(closes, 60)
    mfm = (0.4 * m5 + 0.3 * m20 + 0.3 * m60) if None not in (m5, m20, m60) else None

    avg_vol_20 = float(df["volume"].tail(21).iloc[:-1].mean()) if len(df) >= 21 else float(df["volume"].mean())
    vol = int(df["volume"].iloc[-1])
    volume_spike = 1 if avg_vol_20 and vol > avg_vol_20 * 1.5 else 0

    # is_8d_consec: MA50 rose in >=6 of the last 8 day-over-day steps (f_watch: consecutive_increases >= 6)
    ma50_series = df["close"].rolling(50).mean().dropna()
    is_8d = 0
    if len(ma50_series) >= 9:
        last9 = ma50_series.tail(9).tolist()
        ups = sum(1 for i in range(1, len(last9)) if last9[i] > last9[i - 1])
        is_8d = 1 if ups >= 6 else 0

    high_252 = float(df["high"].tail(252).max())
    low_252 = float(df["low"].tail(252).min())
    dist_high = (c - high_252) / high_252 * 100 if high_252 else None
    dist_low = (c - low_252) / low_252 * 100 if low_252 else None

    trend_aligned = 1 if (ma50 and ma150 and c > ma50 > ma150 and ma50 * 1.01 <= c <= ma50 * 1.10) else 0

    return {
        "date": str(df["time"].iloc[-1]),
        "momentum_5d": _none_if_nan(m5), "momentum_20d": _none_if_nan(m20),
        "momentum_60d": _none_if_nan(m60), "multi_factor_momentum": _none_if_nan(mfm),
        "vs_benchmark": _none_if_nan(ind.get("mrsi")),
        "price_vs_ma50": ("Above MA50" if ma50 and c > ma50 else "Below MA50" if ma50 else None),
        "above_ma50": 1 if ma50 and c > ma50 else 0, "above_ma100": 1 if ma100 and c > ma100 else 0,
        "above_ma150": 1 if ma150 and c > ma150 else 0, "above_ma200": 1 if ma200 and c > ma200 else 0,
        "ma_cross_status": _ma_cross_status(ma50, ma100, ma150),
        "trend_aligned": trend_aligned, "is_8d_consec": is_8d,
        "volume": vol, "avg_volume_20": _none_if_nan(avg_vol_20), "volume_spike": volume_spike,
        "high_52w": _none_if_nan(high_252), "low_52w": _none_if_nan(low_252),
        "dist_from_52w_high": _none_if_nan(dist_high), "dist_from_52w_low": _none_if_nan(dist_low),
        "near_52w_high": 1 if dist_high is not None and dist_high > -5 else 0,
    }


_COLS = ["symbol","date","momentum_5d","momentum_20d","momentum_60d","multi_factor_momentum",
         "vs_benchmark","price_vs_ma50","above_ma50","above_ma100","above_ma150","above_ma200",
         "ma_cross_status","trend_aligned","is_8d_consec","volume","avg_volume_20","volume_spike",
         "high_52w","low_52w","dist_from_52w_high","dist_from_52w_low","near_52w_high","last_evaluated_at"]


# Max calendar-day gap between the last market_data bar and the indicators row it
# feeds. Covers weekends/holidays; beyond this the MAs are stale and joining them
# with fresh prices produces wrong signals (e.g. "All Bearish" on a bullish stack).
INDICATOR_FRESHNESS_DAYS = 7


def compute_for_symbol(conn, symbol: str) -> int:
    df = pd.read_sql_query(
        "SELECT time, high, low, close, volume FROM market_data WHERE symbol = ? ORDER BY time ASC",
        conn, params=[symbol])
    if len(df) < 60:
        return 0
    last_bar = str(df["time"].iloc[-1])
    ind_row = conn.execute(
        "SELECT ma_50, ma_100, ma_150, ma_200, mrsi FROM indicators WHERE symbol = ? "
        "AND date(time) <= date(?) AND date(time) >= date(?, ?) "
        "ORDER BY time DESC LIMIT 1",
        (symbol, last_bar, last_bar, f"-{INDICATOR_FRESHNESS_DAYS} days")).fetchone()
    ind = {"ma_50": ind_row[0], "ma_100": ind_row[1], "ma_150": ind_row[2],
           "ma_200": ind_row[3], "mrsi": ind_row[4]} if ind_row else {}
    sig = compute_signals(df, ind)
    sig["symbol"] = symbol
    sig["last_evaluated_at"] = datetime.now(timezone.utc).isoformat()
    updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "symbol")
    conn.execute(
        f"INSERT INTO screen_signals ({','.join(_COLS)}) VALUES ({','.join('?'*len(_COLS))}) "
        f"ON CONFLICT(symbol) DO UPDATE SET {updates}",
        tuple(sig[c] for c in _COLS))
    conn.commit()
    return 1


def compute_all(conn) -> dict:
    rows = conn.execute("SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()
    processed, written, errors, failures = [], 0, 0, []
    for (sym,) in rows:
        try:
            n = compute_for_symbol(conn, sym)
            if n:
                processed.append(sym); written += n
        except Exception as e:
            logger.error(f"❌ screen_signals failed for {sym}: {e}")
            errors += 1; failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    return {"symbols_processed": processed, "rows_written": written, "errors": errors, "failures": failures}
