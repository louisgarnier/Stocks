"""
Transactions API Routes

Endpoints for managing and viewing transactions.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import api_logger as logger

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class Transaction(BaseModel):
    id: int
    transaction_id: str
    symbol: str
    trade_date: str
    quantity: float
    t_price: Optional[float]
    proceeds: Optional[float]
    comm_fee: Optional[float]
    updated_quantity: Optional[float]
    updated_t_price: Optional[float]
    stock_splits_applied: Optional[str]
    created_at: str


class PaginatedTransactions(BaseModel):
    data: List[Transaction]
    total: int
    page: int
    limit: int
    pages: int


@router.get("", response_model=PaginatedTransactions)
async def list_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=200, description="Items per page (25, 50, 100, 200)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    sort_by: str = Query("trade_date", description="Column to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc")
):
    """
    List transactions with pagination, filtering, and sorting.
    
    - **page**: Page number (1-indexed)
    - **limit**: Number of items per page (max 200)
    - **symbol**: Optional filter by stock symbol
    - **sort_by**: Column to sort by (trade_date, symbol, quantity, t_price, proceeds)
    - **sort_order**: Sort order (asc or desc)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Validate sort column
    valid_columns = ["trade_date", "symbol", "quantity", "t_price", "proceeds", "comm_fee", "id"]
    if sort_by not in valid_columns:
        sort_by = "trade_date"
    
    # Validate sort order
    sort_order = "ASC" if sort_order.lower() == "asc" else "DESC"
    
    # Build query
    where_clause = ""
    params = []
    
    if symbol:
        where_clause = "WHERE symbol LIKE ?"
        params.append(f"%{symbol.upper()}%")
    
    # Get total count
    cursor.execute(f"SELECT COUNT(*) FROM transactions {where_clause}", params)
    total = cursor.fetchone()[0]
    
    # Calculate pagination
    offset = (page - 1) * limit
    pages = (total + limit - 1) // limit if total > 0 else 1
    
    # Get transactions
    cursor.execute(f"""
        SELECT id, transaction_id, symbol, trade_date, quantity, 
               t_price, proceeds, comm_fee, updated_quantity, 
               updated_t_price, stock_splits_applied, created_at
        FROM transactions
        {where_clause}
        ORDER BY {sort_by} {sort_order}, id DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    
    rows = cursor.fetchall()
    conn.close()
    
    transactions = [
        Transaction(
            id=row["id"],
            transaction_id=row["transaction_id"],
            symbol=row["symbol"],
            trade_date=row["trade_date"],
            quantity=row["quantity"],
            t_price=row["t_price"],
            proceeds=row["proceeds"],
            comm_fee=row["comm_fee"],
            updated_quantity=row["updated_quantity"],
            updated_t_price=row["updated_t_price"],
            stock_splits_applied=row["stock_splits_applied"],
            created_at=row["created_at"]
        )
        for row in rows
    ]
    
    logger.info(f"📊 Listed {len(transactions)} transactions (page {page}/{pages})")
    
    return PaginatedTransactions(
        data=transactions,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )


@router.get("/symbols")
async def list_symbols():
    """
    Get list of unique symbols in transactions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT symbol, COUNT(*) as count
        FROM transactions
        GROUP BY symbol
        ORDER BY symbol
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    symbols = [{"symbol": row["symbol"], "count": row["count"]} for row in rows]
    
    return {"symbols": symbols, "total": len(symbols)}
