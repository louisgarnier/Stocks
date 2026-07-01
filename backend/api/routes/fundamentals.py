from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}")
async def get_fundamentals(symbol: str):
    sym = symbol.upper()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM fundamentals WHERE symbol = ?", (sym,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"no fundamentals for {sym}")
    logger.info(f"🏦 Returned fundamentals for {sym}")
    return {k: row[k] for k in row.keys()}
