"""API routes for portfolio positions.

Returns raw IBKR positions (source of truth). No reconciliation —
positions and transactions both come from the same Flex Query, so they
are inherently consistent at sync time.
"""

from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
async def get_positions():
    """Return all positions stored in positions_ibkr (the IBKR snapshot)."""
    logger.info("📊 Fetching positions from positions_ibkr...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT symbol, quantity, cost_basis_money, cost_basis_price,
                   mark_price, position_value, unrealized_pnl,
                   currency, asset_category, last_updated
            FROM positions_ibkr
            ORDER BY ABS(COALESCE(position_value, 0)) DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()

        positions = [
            {
                "symbol": r[0],
                "quantity": r[1],
                "cost_basis_money": r[2],
                "cost_basis_price": r[3],
                "mark_price": r[4],
                "position_value": r[5],
                "unrealized_pnl": r[6],
                "currency": r[7],
                "asset_category": r[8],
                "last_updated": r[9],
            }
            for r in rows
        ]

        logger.info(f"✅ Returned {len(positions)} positions")
        return {
            "success": True,
            "positions": positions,
            "summary": {
                "total_positions": len(positions),
                "last_updated": rows[0][9] if rows else None,
            },
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
