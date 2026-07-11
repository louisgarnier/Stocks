"""Daily portfolio valuation from split-adjusted transactions × closes × FX.

Rebuild-from-scratch each run (dataset is small: ~550 trading days × 1 row).
CASH / forex-pair transactions are excluded — only stock legs are valued.
"""
import logging
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)

FX_SYMBOL = "EURUSD=X"


def get_fx_rate(conn, on_date: str | None = None):
    """Latest EURUSD close at-or-before on_date (or overall latest). None if absent."""
    if on_date:
        row = conn.execute(
            "SELECT close FROM market_data WHERE symbol=? AND time<=? ORDER BY time DESC LIMIT 1",
            (FX_SYMBOL, on_date)).fetchone()
    else:
        row = conn.execute(
            "SELECT close FROM market_data WHERE symbol=? ORDER BY time DESC LIMIT 1",
            (FX_SYMBOL,)).fetchone()
    return float(row[0]) if row else None


def compute_history(conn, start: str | None = None) -> dict:
    tx = pd.read_sql_query(
        "SELECT symbol, currency, trade_date, COALESCE(updated_quantity, quantity) AS qty "
        "FROM transactions WHERE asset_category IN ('STK','Stocks') AND symbol NOT LIKE '%.%'",
        conn)
    if tx.empty:
        return {"days_written": 0}

    symbols = sorted(tx["symbol"].unique())
    px = pd.read_sql_query(
        "SELECT symbol, time, close FROM market_data WHERE symbol IN (%s) ORDER BY time"
        % ",".join("?" * len(symbols)), conn, params=symbols)
    if px.empty:
        return {"days_written": 0}
    closes = px.pivot(index="time", columns="symbol", values="close").ffill()

    fx = pd.read_sql_query(
        "SELECT time, close FROM market_data WHERE symbol=? ORDER BY time",
        conn, params=[FX_SYMBOL]).set_index("time")["close"]

    # cumulative shares held per symbol per day
    qty = (tx.pivot_table(index="trade_date", columns="symbol", values="qty", aggfunc="sum")
             .reindex(closes.index).fillna(0.0).cumsum())

    ccy = dict(tx.drop_duplicates("symbol")[["symbol", "currency"]].values)
    values = closes * qty
    usd_cols = [s for s in values.columns if (ccy.get(s) or "USD") == "USD"]
    eur_cols = [s for s in values.columns if ccy.get(s) == "EUR"]

    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for day, row in values.iterrows():
        if start and day < start:
            continue
        usd_leg = float(row[usd_cols].sum()) if usd_cols else 0.0
        eur_leg = float(row[eur_cols].sum()) if eur_cols else 0.0
        sub = fx.loc[:day]
        rate = float(sub.iloc[-1]) if len(sub) else None
        if rate is None:
            continue  # no FX yet for this day — skip rather than guess
        conn.execute(
            "INSERT INTO portfolio_value_history (date, value_eur, value_usd_leg, value_eur_leg, fx_rate, computed_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(date) DO UPDATE SET value_eur=excluded.value_eur, "
            "value_usd_leg=excluded.value_usd_leg, value_eur_leg=excluded.value_eur_leg, "
            "fx_rate=excluded.fx_rate, computed_at=excluded.computed_at",
            (day, usd_leg / rate + eur_leg, usd_leg, eur_leg, rate, now))
        written += 1
    conn.commit()
    logger.info(f"✅ [PortfolioHistory] wrote {written} days")
    return {"days_written": written}
