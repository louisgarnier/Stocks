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
        MRSI  = ((RS / RS_MA) - 1) * 100

    MRSI is positive when stock outperforms benchmark over 252 trading days,
    negative when underperforming, ~0 when matching.
    """
    merged = stock_df[["time", "adj_close"]].merge(
        bench_df[["time", "adj_close"]],
        on="time", suffixes=("_stock", "_bench"),
    ).sort_values("time").reset_index(drop=True)

    rs = merged["adj_close_stock"] / merged["adj_close_bench"].where(merged["adj_close_bench"] != 0)
    rs_ma = rs.rolling(252).mean()
    mrsi = ((rs / rs_ma.where(rs_ma != 0)) - 1) * 100
    return pd.Series(mrsi.values, index=merged["time"].values)
