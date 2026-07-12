"""Security Detail endpoint — combined per-symbol data for the Sheet modal."""
import json
import pandas as pd
from fastapi import APIRouter, HTTPException

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection
from backend.scripts.consolidation_core import calculate_zigzag, load_params

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/{symbol}/detail")
async def get_security_detail(symbol: str):
    """Return everything we know about a symbol in one response."""
    sym = symbol.upper()
    conn = get_db_connection()

    universe_row = conn.execute(
        "SELECT symbol, name, sector, currency, exchange, benchmark, sources, "
        "enabled, added_at, last_synced_at FROM tracked_universe WHERE symbol = ?",
        (sym,),
    ).fetchone()
    if not universe_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"{sym} not in universe")

    universe = {
        "symbol": universe_row[0],
        "name": universe_row[1],
        "sector": universe_row[2],
        "currency": universe_row[3],
        "exchange": universe_row[4],
        "benchmark": universe_row[5],
        "sources": json.loads(universe_row[6] or "[]"),
        "enabled": bool(universe_row[7]),
        "added_at": universe_row[8],
        "last_synced_at": universe_row[9],
    }

    position_row = conn.execute(
        "SELECT symbol, quantity, cost_basis_money, cost_basis_price, mark_price, "
        "position_value, unrealized_pnl, currency, asset_category, last_updated "
        "FROM positions_ibkr WHERE symbol = ?",
        (sym,),
    ).fetchone()
    is_held = position_row is not None
    position = None
    if position_row:
        position = {
            "symbol": position_row[0],
            "quantity": position_row[1],
            "cost_basis_money": position_row[2],
            "cost_basis_price": position_row[3],
            "mark_price": position_row[4],
            "position_value": position_row[5],
            "unrealized_pnl": position_row[6],
            "currency": position_row[7],
            "asset_category": position_row[8],
            "last_updated": position_row[9],
        }

    transactions = []
    if is_held:
        tx_rows = conn.execute(
            "SELECT transaction_id, trade_date, quantity, t_price, proceeds, comm_fee, "
            "currency, asset_category FROM transactions WHERE symbol = ? ORDER BY trade_date DESC",
            (sym,),
        ).fetchall()
        transactions = [
            {
                "transaction_id": r[0],
                "trade_date": r[1],
                "quantity": r[2],
                "t_price": r[3],
                "proceeds": r[4],
                "comm_fee": r[5],
                "currency": r[6],
                "asset_category": r[7],
            }
            for r in tx_rows
        ]

    ind_row = conn.execute(
        "SELECT time, ma_50, ma_100, ma_150, ma_200, bb_upper_20, bb_lower_20, "
        "bb_width, rsi_14, mrsi, atr_14, volume_ma_20 FROM indicators "
        "WHERE symbol = ? ORDER BY time DESC LIMIT 1",
        (sym,),
    ).fetchone()
    indicators = None
    if ind_row:
        indicators = {
            "time": ind_row[0],
            "ma_50": ind_row[1], "ma_100": ind_row[2], "ma_150": ind_row[3], "ma_200": ind_row[4],
            "bb_upper_20": ind_row[5], "bb_lower_20": ind_row[6], "bb_width": ind_row[7],
            "rsi_14": ind_row[8], "mrsi": ind_row[9], "atr_14": ind_row[10],
            "volume_ma_20": ind_row[11],
        }

    bar_rows = conn.execute(
        "SELECT time, open, high, low, close, adj_close, volume FROM market_data "
        "WHERE symbol = ? ORDER BY time DESC LIMIT 30",
        (sym,),
    ).fetchall()
    bars = [
        {
            "time": r[0], "open": r[1], "high": r[2], "low": r[3],
            "close": r[4], "adj_close": r[5], "volume": r[6],
        }
        for r in bar_rows
    ]

    fund_cols = ["gross_margin", "roe", "roic", "levered_fcf_margin", "interest_cover",
                 "eps_5y_growth", "gates_passed", "gates_total", "market_cap", "trailing_pe"]
    frow = conn.execute(
        f"SELECT {', '.join(fund_cols)} FROM fundamentals WHERE symbol = ?", (sym,)
    ).fetchone()
    fundamentals = {c: frow[i] for i, c in enumerate(fund_cols)} if frow else None

    sig_row = conn.execute(
        "SELECT momentum_5d, momentum_20d, momentum_60d, multi_factor_momentum, "
        "ma_cross_status, trend_aligned, volume_spike, near_52w_high, "
        "dist_from_52w_high, vs_benchmark AS mrsi, date FROM screen_signals "
        "WHERE symbol = ?",
        (sym,),
    ).fetchone()
    technical = None
    if sig_row:
        technical = {
            "momentum_5d": sig_row[0],
            "momentum_20d": sig_row[1],
            "momentum_60d": sig_row[2],
            "multi_factor_momentum": sig_row[3],
            "ma_cross_status": sig_row[4],
            "trend_aligned": sig_row[5],
            "volume_spike": sig_row[6],
            "near_52w_high": sig_row[7],
            "dist_from_52w_high": sig_row[8],
            "mrsi": sig_row[9],
            "signal_date": sig_row[10],
        }

    brk_row = conn.execute(
        "SELECT breakout_status, breakout_direction, breakout_strength, "
        "breakout_volume_ratio, consolidation_bottom, consolidation_top, "
        "consolidation_range_pct, consolidation_duration_days, date "
        "FROM breakout_signals WHERE symbol = ? ORDER BY date DESC LIMIT 1",
        (sym,),
    ).fetchone()
    if brk_row:
        breakout = {
            "status": brk_row[0],
            "direction": brk_row[1],
            "strength": brk_row[2],
            "volume_ratio": brk_row[3],
            "support": brk_row[4],
            "resistance": brk_row[5],
            "range_pct": brk_row[6],
            "duration_days": brk_row[7],
            "date": brk_row[8],
        }
    else:
        breakout = {
            "status": "no_consolidation_patterns",
            "direction": "none",
            "strength": None,
            "volume_ratio": None,
            "support": None,
            "resistance": None,
            "range_pct": None,
            "duration_days": None,
            "date": None,
        }

    params = load_params(conn)
    df = pd.read_sql_query(
        "SELECT time, high, low, close FROM market_data WHERE symbol = ? ORDER BY time ASC",
        conn, params=[sym],
    )
    swings = []
    if len(df) >= 20:
        df["time"] = pd.to_datetime(df["time"])
        pts = calculate_zigzag(df.tail(41).iloc[:-1].copy(), params) or []
        swings = [
            {"date": str(p["date"].date()), "price": round(float(p["price"]), 2), "type": p["type"]}
            for p in pts
        ]
    zigzag = {
        "deviation_pct": params["zigzag_deviation"],
        "window_days": params["lookback_days"],
        "swings": swings,
    }

    conn.close()
    logger.info(f"📂 Security detail for {sym}: held={is_held}, tx={len(transactions)}, bars={len(bars)}")

    return {
        "symbol": sym,
        "is_held": is_held,
        "universe": universe,
        "position": position,
        "transactions": transactions,
        "indicators": indicators,
        "fundamentals": fundamentals,
        "bars": bars,
        "technical": technical,
        "breakout": breakout,
        "zigzag": zigzag,
    }
