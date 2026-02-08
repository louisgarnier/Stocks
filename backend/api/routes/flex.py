"""
Flex API Routes - IBKR Flex Web Service Integration

Endpoints for fetching data from IBKR Flex Web Service API.
"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import api_logger as logger

router = APIRouter(prefix="/api/flex", tags=["flex"])


class FlexFetchResponse(BaseModel):
    success: bool
    message: str
    records: int = 0
    file: Optional[str] = None


class FlexStatusResponse(BaseModel):
    last_fetch_at: Optional[str]
    last_fetch_status: str
    last_fetch_message: Optional[str]
    records_fetched: int


def update_sync_status(status: str, message: str = None, records: int = 0):
    """Update the sync_status table with fetch results."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE sync_status 
        SET last_fetch_at = ?,
            last_fetch_status = ?,
            last_fetch_message = ?,
            records_fetched = ?
        WHERE id = 1
    """, (datetime.now().isoformat(), status, message, records))
    
    conn.commit()
    conn.close()


def run_flex_fetch():
    """Run the flex fetch in background."""
    try:
        from backend.scripts.a_flex_fetch import fetch_flex_report
        
        logger.info("🚀 Starting background Flex fetch...")
        result = fetch_flex_report()
        
        update_sync_status(
            status="success" if result["success"] else "error",
            message=result["message"],
            records=result["records"]
        )
        
        logger.info(f"✅ Background Flex fetch complete: {result['message']}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Background Flex fetch failed: {e}")
        update_sync_status(status="error", message=str(e), records=0)
        return {"success": False, "message": str(e), "records": 0}


@router.post("/fetch", response_model=FlexFetchResponse)
async def fetch_from_ibkr(background_tasks: BackgroundTasks):
    """
    Trigger a fetch from IBKR Flex Web Service.
    
    Fetches last 365 days of transactions and automatically skips duplicates.
    This runs in the background as it takes ~20 seconds.
    Check /api/flex/status for results.
    """
    logger.info("📡 Flex fetch requested")
    
    # Update status to "fetching"
    update_sync_status(status="fetching", message="Fetch in progress...")
    
    # Run in background
    background_tasks.add_task(run_flex_fetch)
    
    return FlexFetchResponse(
        success=True,
        message="Fetch started. Check /api/flex/status for results.",
        records=0
    )


@router.get("/status", response_model=FlexStatusResponse)
async def get_flex_status():
    """
    Get the status of the last Flex fetch.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT last_fetch_at, last_fetch_status, last_fetch_message, records_fetched
        FROM sync_status
        WHERE id = 1
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return FlexStatusResponse(
            last_fetch_at=row["last_fetch_at"],
            last_fetch_status=row["last_fetch_status"],
            last_fetch_message=row["last_fetch_message"],
            records_fetched=row["records_fetched"]
        )
    else:
        return FlexStatusResponse(
            last_fetch_at=None,
            last_fetch_status="never",
            last_fetch_message=None,
            records_fetched=0
        )
