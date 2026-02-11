"""
Updated Transactions API Routes - IBKR Portfolio Tracker

Handles CRUD operations for split/spinoff adjusted transactions.

⚠️ Before making changes, read: ../../../docs/workflow/BEST_PRACTICES.md
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import sqlite3
import logging
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)

# Database path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = PROJECT_ROOT / "output" / "database" / "finance.db"


def get_db_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@router.get("")
async def get_updated_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    symbol: Optional[str] = None,
    sort_by: str = Query("trade_date", regex="^(trade_date|symbol|updated_quantity|split_ratio)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    Get updated transactions with pagination and filtering.
    
    Query Parameters:
    - page: Page number (default: 1)
    - limit: Items per page (default: 25, max: 100)
    - symbol: Filter by symbol (optional)
    - sort_by: Sort column (default: trade_date)
    - sort_order: Sort order asc/desc (default: desc)
    
    Returns:
    - data: List of updated transactions
    - page: Current page
    - limit: Items per page
    - total: Total count
    - pages: Total pages
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build WHERE clause
        where_clause = ""
        params = []
        if symbol:
            where_clause = "WHERE symbol = ?"
            params.append(symbol)
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM updated_transactions {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Calculate pagination
        offset = (page - 1) * limit
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        
        # Get data
        query = f"""
            SELECT 
                id, transaction_id, symbol, trade_date,
                original_quantity, original_price,
                updated_quantity, updated_price,
                split_ratio, ca_id, ca_type, ca_date,
                created_at
            FROM updated_transactions
            {where_clause}
            ORDER BY {sort_by} {sort_order.upper()}
            LIMIT ? OFFSET ?
        """
        cursor.execute(query, params + [limit, offset])
        
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
        
        conn.close()
        
        logger.info(f"📊 Retrieved {len(data)} updated transactions (page {page}/{total_pages})")
        
        return {
            "data": data,
            "page": page,
            "limit": limit,
            "total": total,
            "pages": total_pages
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to get updated transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def delete_all_updated_transactions():
    """
    Delete all updated transactions.
    
    Returns:
    - message: Success message
    - deleted: Number of deleted records
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get count before delete
        cursor.execute("SELECT COUNT(*) FROM updated_transactions")
        count = cursor.fetchone()[0]
        
        # Delete all
        cursor.execute("DELETE FROM updated_transactions")
        conn.commit()
        conn.close()
        
        logger.info(f"🗑️  Deleted {count} updated transactions")
        
        return {
            "message": f"Successfully deleted {count} updated transactions",
            "deleted": count
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to delete updated transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{id}")
async def delete_updated_transaction(id: int):
    """
    Delete a specific updated transaction by ID.
    
    Path Parameters:
    - id: Updated transaction ID
    
    Returns:
    - message: Success message
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM updated_transactions WHERE id = ?", (id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail=f"Updated transaction {id} not found")
        
        # Delete
        cursor.execute("DELETE FROM updated_transactions WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        
        logger.info(f"🗑️  Deleted updated transaction {id}")
        
        return {
            "message": f"Successfully deleted updated transaction {id}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to delete updated transaction {id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete-batch")
async def delete_batch_updated_transactions(ids: list[int]):
    """
    Delete multiple updated transactions by IDs.
    
    Request Body:
    - ids: List of updated transaction IDs
    
    Returns:
    - message: Success message
    - deleted: Number of deleted records
    """
    if not ids:
        raise HTTPException(status_code=400, detail="No IDs provided")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete batch
        placeholders = ','.join(['?'] * len(ids))
        cursor.execute(f"DELETE FROM updated_transactions WHERE id IN ({placeholders})", ids)
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"🗑️  Deleted {deleted} updated transactions")
        
        return {
            "message": f"Successfully deleted {deleted} updated transactions",
            "deleted": deleted
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to delete batch updated transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
