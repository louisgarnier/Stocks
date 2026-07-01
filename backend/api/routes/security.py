"""Security Detail endpoint — combined per-symbol data for the Sheet modal."""
import json
from fastapi import APIRouter, HTTPException

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

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
    }
