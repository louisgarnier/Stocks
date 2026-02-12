"""
API routes for portfolio positions.
"""

from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
async def get_positions():
    """
    Get all portfolio positions from the database.
    Returns open and closed positions separately.
    """
    logger.info("📊 Fetching positions...")
    
    try:
        from backend.scripts.calculate_and_save_positions import get_positions
        
        result = get_positions()
        
        logger.info(f"✅ Positions fetched: {result['open_count']} open, {result['closed_count']} closed")
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_positions():
    """
    Recalculate and save all positions to the database.
    """
    logger.info("🔄 Refreshing positions...")
    
    try:
        from backend.scripts.calculate_and_save_positions import calculate_and_save_positions
        
        result = calculate_and_save_positions()
        
        logger.info(f"✅ Positions refreshed: {result['open_positions']} open, {result['closed_positions']} closed")
        
        return result
    except Exception as e:
        logger.error(f"❌ Failed to refresh positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
