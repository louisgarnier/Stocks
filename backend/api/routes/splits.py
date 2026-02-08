"""
Stock Splits API Routes

Endpoints for fetching and managing stock splits.
"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import api_logger as logger

router = APIRouter(prefix="/api/splits", tags=["splits"])


class Split(BaseModel):
    id: int
    symbol: str
    split_date: str
    split_ratio: float
    fetched_at: Optional[str]
    applied_at: Optional[str]


class SplitsResponse(BaseModel):
    data: List[Split]
    total: int


class SplitsStatusResponse(BaseModel):
    total_splits: int
    splits_applied: int
    last_fetch_at: Optional[str]
    transactions_adjusted: int


class FetchResponse(BaseModel):
    success: bool
    message: str
    splits_found: int = 0
    splits_stored: int = 0
    transactions_adjusted: int = 0


def run_fetch_and_apply():
    """Run the fetch and apply in background."""
    try:
        from backend.scripts.c_stock_splits import fetch_and_apply
        
        logger.info("🚀 Starting background splits fetch and apply...")
        result = fetch_and_apply()
        logger.info(f"✅ Splits fetch and apply complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Splits fetch failed: {e}")
        return {"success": False, "message": str(e)}


@router.get("", response_model=SplitsResponse)
async def list_splits():
    """
    List all stock splits in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, symbol, split_date, split_ratio, fetched_at, applied_at
        FROM stock_splits
        ORDER BY split_date DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    splits = [
        Split(
            id=row["id"],
            symbol=row["symbol"],
            split_date=row["split_date"],
            split_ratio=row["split_ratio"],
            fetched_at=row["fetched_at"],
            applied_at=row["applied_at"]
        )
        for row in rows
    ]
    
    logger.info(f"📊 Listed {len(splits)} stock splits")
    
    return SplitsResponse(data=splits, total=len(splits))


@router.get("/status", response_model=SplitsStatusResponse)
async def get_splits_status():
    """
    Get the status of stock splits.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total splits
    cursor.execute("SELECT COUNT(*) FROM stock_splits")
    total_splits = cursor.fetchone()[0]
    
    # Splits applied
    cursor.execute("SELECT COUNT(*) FROM stock_splits WHERE applied_at IS NOT NULL")
    splits_applied = cursor.fetchone()[0]
    
    # Last fetch
    cursor.execute("SELECT MAX(fetched_at) FROM stock_splits")
    last_fetch = cursor.fetchone()[0]
    
    # Transactions adjusted
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE stock_splits_applied IS NOT NULL AND stock_splits_applied != 'no split'")
    transactions_adjusted = cursor.fetchone()[0]
    
    conn.close()
    
    return SplitsStatusResponse(
        total_splits=total_splits,
        splits_applied=splits_applied,
        last_fetch_at=last_fetch,
        transactions_adjusted=transactions_adjusted
    )


@router.post("/fetch", response_model=FetchResponse)
async def fetch_splits(background_tasks: BackgroundTasks):
    """
    Fetch stock splits from Yahoo Finance and apply to transactions.
    
    This runs in the background as it may take a while for many symbols.
    """
    logger.info("📡 Splits fetch requested")
    
    # Run in background
    background_tasks.add_task(run_fetch_and_apply)
    
    return FetchResponse(
        success=True,
        message="Fetch started. Splits will be fetched and applied automatically.",
        splits_found=0,
        splits_stored=0,
        transactions_adjusted=0
    )
