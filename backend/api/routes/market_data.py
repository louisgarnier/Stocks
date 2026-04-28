"""Market data query routes (read access to OHLCV table)."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


@router.get("/status")
async def get_market_data_status():
    """Return summary stats about market_data coverage across the enabled universe."""
    conn = get_db_connection()
    total_symbols = conn.execute(
        "SELECT COUNT(*) FROM tracked_universe WHERE enabled = 1"
    ).fetchone()[0]
    with_data = conn.execute(
        "SELECT COUNT(DISTINCT md.symbol) FROM market_data md "
        "JOIN tracked_universe tu ON tu.symbol = md.symbol WHERE tu.enabled = 1"
    ).fetchone()[0]
    total_bars = conn.execute("SELECT COUNT(*) FROM market_data").fetchone()[0]
    latest_bar = conn.execute("SELECT MAX(time) FROM market_data").fetchone()[0]
    last_sync = conn.execute(
        "SELECT MAX(last_synced_at) FROM tracked_universe WHERE last_synced_at IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    return {
        "symbols_total": total_symbols,
        "symbols_with_data": with_data,
        "total_bars": total_bars,
        "latest_bar_date": latest_bar,
        "last_sync_at": last_sync,
    }


@router.get("/{symbol}")
async def get_market_data(
    symbol: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=10000),
):
    """Return OHLCV bars for a symbol, newest first."""
    sym = symbol.upper()
    conn = get_db_connection()
    where = ["symbol = ?"]
    params: list = [sym]
    if date_from:
        where.append("time >= ?")
        params.append(date_from)
    if date_to:
        where.append("time <= ?")
        params.append(date_to)
    sql = (
        "SELECT time, open, high, low, close, adj_close, volume "
        "FROM market_data WHERE " + " AND ".join(where) +
        " ORDER BY time DESC LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"no bars for {sym}")
    bars = [
        {
            "time": r[0], "open": r[1], "high": r[2], "low": r[3],
            "close": r[4], "adj_close": r[5], "volume": r[6],
        }
        for r in rows
    ]
    logger.info(f"📊 Returned {len(bars)} bars for {sym}")
    return {"symbol": sym, "bars": bars, "count": len(bars)}
