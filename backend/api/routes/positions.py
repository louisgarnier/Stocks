"""
API routes for portfolio positions.
Returns IBKR positions (source of truth) with reconciliation against calculated positions.
"""

from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
async def get_positions():
    """
    Get IBKR positions with reconciliation against calculated positions.
    Returns positions with qty reconciliation status.
    """
    logger.info("📊 Fetching positions with reconciliation...")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get IBKR positions (source of truth)
        cursor.execute("""
            SELECT symbol, quantity, cost_basis_money, cost_basis_price,
                   mark_price, position_value, unrealized_pnl,
                   currency, asset_category, last_updated
            FROM positions_ibkr
            ORDER BY symbol
        """)
        ibkr_rows = cursor.fetchall()
        
        # Get calculated positions (for reconciliation)
        cursor.execute("""
            SELECT symbol, quantity, transaction_count
            FROM positions_calculated
        """)
        calc_map = {}
        for row in cursor.fetchall():
            calc_map[row[0]] = {"quantity": row[1], "transaction_count": row[2]}
        
        conn.close()
        
        # Build positions with reconciliation
        positions = []
        matched = 0
        warnings = 0
        errors = 0
        
        for row in ibkr_rows:
            symbol = row[0]
            qty_ibkr = row[1]
            
            # Reconciliation
            calc_data = calc_map.get(symbol, {})
            qty_calc = calc_data.get("quantity", 0)
            tx_count = calc_data.get("transaction_count", 0)
            qty_diff = qty_ibkr - qty_calc
            qty_diff_pct = (qty_diff / qty_ibkr * 100) if qty_ibkr != 0 else 0
            
            if abs(qty_diff_pct) < 1:
                rec_status = "match"
                matched += 1
            elif abs(qty_diff_pct) < 5:
                rec_status = "warning"
                warnings += 1
            else:
                rec_status = "error"
                errors += 1
            
            positions.append({
                "symbol": symbol,
                "quantity": qty_ibkr,
                "cost_basis_money": row[2],
                "cost_basis_price": row[3],
                "mark_price": row[4],
                "position_value": row[5],
                "unrealized_pnl": row[6],
                "currency": row[7],
                "asset_category": row[8],
                "last_updated": row[9],
                "qty_calculated": qty_calc,
                "transaction_count": tx_count,
                "qty_diff": round(qty_diff, 4),
                "qty_diff_pct": round(qty_diff_pct, 2),
                "rec_status": rec_status
            })
        
        # Sort by position value descending
        positions.sort(key=lambda x: abs(x.get("position_value") or 0), reverse=True)
        
        logger.info(f"✅ Positions: {len(positions)} total, {matched} matched, {warnings} warnings, {errors} errors")
        
        return {
            "success": True,
            "positions": positions,
            "summary": {
                "total_positions": len(positions),
                "matched": matched,
                "warnings": warnings,
                "errors": errors,
                "last_updated": ibkr_rows[0][9] if ibkr_rows else None
            }
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_positions():
    """
    Recalculate positions from transactions (for reconciliation).
    """
    logger.info("🔄 Refreshing calculated positions...")
    
    try:
        from backend.scripts.calculate_and_save_positions import calculate_and_save_positions
        
        result = calculate_and_save_positions()
        
        logger.info(f"✅ Calculated positions refreshed: {result['open_positions']} open, {result['closed_positions']} closed")
        
        return result
    except Exception as e:
        logger.error(f"❌ Failed to refresh positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
