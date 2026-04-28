"""Market data query routes (read access to OHLCV table)."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


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
