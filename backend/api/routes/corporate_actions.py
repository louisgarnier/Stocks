"""
Corporate Actions API Routes

Handles fetching, listing, and deleting corporate actions.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import api_logger as logger

router = APIRouter(prefix="/api/corporate-actions", tags=["corporate-actions"])


@router.get("")
async def list_corporate_actions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    ca_type: Optional[str] = None,
    symbol: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = Query("ex_date", regex="^(ex_date|sec_id|ca_type|amount)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    List corporate actions with pagination and filtering.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    where_clauses = []
    params = []

    if ca_type:
        where_clauses.append("ca_type = ?")
        params.append(ca_type)
    if symbol:
        where_clauses.append("sec_id LIKE ?")
        params.append(f"{symbol.upper()}%")
    if date_from:
        where_clauses.append("ex_date >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("ex_date <= ?")
        params.append(date_to)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Get total count
    count_sql = f"SELECT COUNT(*) FROM corporate_actions {where_sql}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]
    
    # Calculate pagination
    pages = (total + limit - 1) // limit if total > 0 else 1
    offset = (page - 1) * limit
    
    # Build ORDER BY
    order_by = f"{sort_by} {sort_order.upper()}"
    
    # Get corporate actions
    sql = f"""
        SELECT id, sec_id, ca_type, ex_date, record_date, pay_date, declared_date,
               amount, currency, split_ratio, split_from, split_to, split_direction,
               dividend_type, frequency, adjusted, source, notes, created_at
        FROM corporate_actions
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """
    cursor.execute(sql, params + [limit, offset])
    rows = cursor.fetchall()
    
    actions = []
    for row in rows:
        actions.append({
            "id": row["id"],
            "sec_id": row["sec_id"],
            "ca_type": row["ca_type"],
            "ex_date": row["ex_date"],
            "record_date": row["record_date"],
            "pay_date": row["pay_date"],
            "declared_date": row["declared_date"],
            "amount": row["amount"],
            "currency": row["currency"],
            "split_ratio": row["split_ratio"],
            "split_from": row["split_from"],
            "split_to": row["split_to"],
            "split_direction": row["split_direction"],
            "dividend_type": row["dividend_type"],
            "frequency": row["frequency"],
            "adjusted": bool(row["adjusted"]),
            "source": row["source"],
            "notes": row["notes"],
            "created_at": row["created_at"]
        })
    
    conn.close()
    
    logger.info(f"📊 Listed {len(actions)} corporate actions (page {page}/{pages})")
    
    return {
        "data": actions,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }


@router.get("/summary")
async def get_corporate_actions_summary():
    """
    Get summary of corporate actions by type.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ca_type, COUNT(*) as count
        FROM corporate_actions
        GROUP BY ca_type
        ORDER BY count DESC
    """)
    
    by_type = {row["ca_type"]: row["count"] for row in cursor.fetchall()}
    
    cursor.execute("SELECT COUNT(*) FROM corporate_actions")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT sec_id) FROM corporate_actions")
    securities_count = cursor.fetchone()[0]
    
    conn.close()
    
    logger.info(f"📊 Corporate actions summary: {total} total")
    
    return {
        "total": total,
        "securities_with_actions": securities_count,
        "by_type": by_type
    }


@router.delete("")
async def delete_all_corporate_actions():
    """
    Delete all corporate actions from the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM corporate_actions")
        count_before = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM corporate_actions")
        conn.commit()
        
        logger.info(f"🗑️  Deleted {count_before} corporate actions")
        
        return {
            "success": True,
            "message": f"Deleted {count_before} corporate actions",
            "deleted_count": count_before
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to delete corporate actions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")
    finally:
        conn.close()


class BatchDeleteRequest(BaseModel):
    ids: List[int]


@router.post("/batch-delete")
async def batch_delete_corporate_actions(request: BatchDeleteRequest):
    """
    Delete selected corporate actions by IDs.
    """
    if not request.ids:
        return {"success": True, "deleted_count": 0}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        placeholders = ','.join(['?' for _ in request.ids])
        cursor.execute(f"DELETE FROM corporate_actions WHERE id IN ({placeholders})", request.ids)
        deleted_count = cursor.rowcount
        conn.commit()
        
        logger.info(f"🗑️  Deleted {deleted_count} selected corporate actions")
        
        return {
            "success": True,
            "message": f"Deleted {deleted_count} corporate actions",
            "deleted_count": deleted_count
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to delete corporate actions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")
    finally:
        conn.close()


@router.get("/status")
async def get_corporate_actions_status(symbol: Optional[str] = None):
    """
    Get corporate actions status for all symbols or a specific symbol.
    
    Returns status (grey/green/orange) for each symbol:
    - grey: No CA data available
    - green: CA data available and up-to-date
    - orange: New trades imported, CA may need refresh
    """
    try:
        from backend.utils.ca_status import get_ca_status
        
        status_data = get_ca_status(symbol)
        
        logger.info(f"📊 Retrieved CA status for {len(status_data)} symbols")
        
        return {
            "success": True,
            "data": status_data
        }
    except Exception as e:
        logger.error(f"❌ Failed to get CA status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/refresh")
async def refresh_corporate_actions():
    """
    Quick refresh: fetch corporate actions only for symbols that need updating.
    - Orange status (new transactions): always fetch
    - Green status: fetch if >24h since last fetch
    - Grey status: fetch if >7 days since last fetch
    """
    try:
        from backend.scripts.fetch_corporate_actions import fetch_and_import_corporate_actions
        
        logger.info("⚡ Starting quick refresh (incremental)...")
        
        result = fetch_and_import_corporate_actions(incremental=True)
        
        logger.info(f"✅ Quick refresh complete: {result['parsed']} parsed, {result['inserted']} inserted, {result['skipped']} skipped")
        
        return {
            "success": True,
            "message": f"Quick refresh: parsed {result['parsed']} corporate actions",
            "parsed": result['parsed'],
            "inserted": result['inserted'],
            "skipped": result['skipped'],
            "errors": result['errors'],
            "updated_transactions": result.get('updated_transactions', 0)
        }
    except Exception as e:
        logger.error(f"❌ Failed to refresh corporate actions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh: {str(e)}")


@router.post("/fetch")
async def fetch_corporate_actions():
    """
    Fetch corporate actions from yfinance for all securities in database.
    """
    try:
        from backend.scripts.fetch_corporate_actions import fetch_and_import_corporate_actions
        
        logger.info("🔄 Starting corporate actions fetch from yfinance...")
        
        result = fetch_and_import_corporate_actions()
        
        logger.info(f"✅ Corporate actions fetch complete: {result['parsed']} parsed, {result['inserted']} inserted, {result['skipped']} skipped")
        
        return {
            "success": True,
            "message": f"Parsed {result['parsed']} corporate actions from yfinance",
            "parsed": result['parsed'],
            "inserted": result['inserted'],
            "skipped": result['skipped'],
            "errors": result['errors']
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch corporate actions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch: {str(e)}")
