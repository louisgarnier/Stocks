"""Indicator query routes (read access to the indicators table)."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.get("/{symbol}")
async def get_indicators(
    symbol: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=10000),
):
    """Return indicator rows for a symbol, newest first."""
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
        "SELECT time, ma_50, ma_100, ma_150, ma_200, "
        "bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20 "
        "FROM indicators WHERE " + " AND ".join(where) +
        " ORDER BY time DESC LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"no indicator rows for {sym}")
    out = [
        {
            "time": r[0],
            "ma_50": r[1], "ma_100": r[2], "ma_150": r[3], "ma_200": r[4],
            "bb_upper_20": r[5], "bb_lower_20": r[6], "bb_width": r[7],
            "rsi_14": r[8], "mrsi": r[9], "atr_14": r[10], "volume_ma_20": r[11],
        }
        for r in rows
    ]
    logger.info(f"📐 Returned {len(out)} indicator rows for {sym}")
    return {"symbol": sym, "rows": out, "count": len(out)}
