"""
Transactions API Routes

Handles loading and listing transactions.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional, List
import sys
from pathlib import Path
from pydantic import BaseModel

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import api_logger as logger

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=500),
    sort_by: str = Query("trade_date", regex="^(trade_date|symbol|quantity|t_price)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    symbol: Optional[str] = None
):
    """
    List transactions with pagination and filtering.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build WHERE clause
    where_clauses = []
    params = []
    
    if symbol:
        where_clauses.append("symbol = ?")
        params.append(symbol.upper())
    
    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    # Get total count
    count_sql = f"SELECT COUNT(*) FROM transactions {where_sql}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]
    
    # Calculate pagination
    pages = (total + limit - 1) // limit if total > 0 else 1
    offset = (page - 1) * limit
    
    # Build ORDER BY
    order_by = f"{sort_by} {sort_order.upper()}"
    
    # Get transactions - SELECT all fields to match Transaction model
    sql = f"""
        SELECT id, transaction_id, source_file, asset_category, currency, symbol,
               trade_date, trade_time, quantity, t_price, c_price, proceeds, comm_fee, basis,
               original_transaction_id, stock_splits_applied, updated_quantity, updated_t_price,
               created_at, updated_at
        FROM transactions
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
    """
    cursor.execute(sql, params + [limit, offset])
    rows = cursor.fetchall()
    
    transactions = []
    for row in rows:
        # sqlite3.Row supports dict-like access but not .get()
        # Access trade_time directly, default to empty string if None
        trade_time = row["trade_time"] if row["trade_time"] is not None else ""
        
        transactions.append({
            "id": row["id"],
            "transaction_id": row["transaction_id"],
            "source_file": row["source_file"],
            "asset_category": row["asset_category"],
            "currency": row["currency"],
            "symbol": row["symbol"],
            "trade_date": row["trade_date"],
            "trade_time": trade_time,
            "quantity": row["quantity"],
            "t_price": row["t_price"],
            "c_price": row["c_price"],
            "proceeds": row["proceeds"],
            "comm_fee": row["comm_fee"],
            "basis": row["basis"],
            "original_transaction_id": row["original_transaction_id"],
            "stock_splits_applied": row["stock_splits_applied"],
            "updated_quantity": row["updated_quantity"],
            "updated_t_price": row["updated_t_price"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })
    
    conn.close()
    
    logger.info(f"📊 Listed {len(transactions)} transactions (page {page}/{pages})")
    
    return {
        "data": transactions,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }


@router.get("/import-logs")
async def get_import_logs():
    """
    Get import history/logs.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, filename, import_date, parsed, inserted, skipped, errors, status
        FROM import_logs
        ORDER BY import_date DESC
        LIMIT 50
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "id": row["id"],
            "filename": row["filename"],
            "import_date": row["import_date"],
            "parsed": row["parsed"],
            "inserted": row["inserted"],
            "skipped": row["skipped"],
            "errors": row["errors"],
            "status": row["status"]
        })
    
    logger.info(f"📋 Listed {len(logs)} import logs")
    
    return {
        "logs": logs,
        "total": len(logs)
    }


@router.post("/upload")
async def upload_transactions(file: UploadFile = File(...)):
    """
    Upload and import transactions from a CSV file.
    """
    logger.info(f"📥 File upload: {file.filename}")
    
    # Save uploaded file temporarily
    import tempfile
    import shutil
    
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = Path(tmp_file.name)
        
        logger.info(f"📁 Saved temp file: {tmp_path}")
        
        # Parse CSV file
        from backend.scripts.parse_csv_trades import parse_csv_file, insert_trades
        
        trades = parse_csv_file(tmp_path)
        logger.info(f"📊 Parsed {len(trades)} trades from {file.filename}")
        
        if not trades:
            # Log the empty import
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO import_logs (filename, parsed, inserted, skipped, errors, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (file.filename, 0, 0, 0, 0, "empty"))
            conn.commit()
            conn.close()
            
            return {
                "success": False,
                "message": f"No trades found in {file.filename}",
                "filename": file.filename,
                "parsed": 0,
                "inserted": 0,
                "skipped": 0,
                "errors": 0,
                "error_details": []
            }
        
        # Insert trades
        result = insert_trades(trades)
        
        # Log the import
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO import_logs (filename, parsed, inserted, skipped, errors, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            file.filename,
            len(trades),
            result["inserted"],
            result["skipped"],
            result.get("errors", 0),
            "success" if result.get("errors", 0) == 0 else "partial"
        ))
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"Parsed {len(trades)} trades: {result['inserted']} inserted, {result['skipped']} skipped, {result['errors']} errors",
            "filename": file.filename,
            "parsed": len(trades),
            "inserted": result["inserted"],
            "skipped": result["skipped"],
            "errors": result.get("errors", 0),
            "error_details": result.get("error_details", [])
        }
    
    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Traceback: {error_trace}")
        
        # Log the failed import
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO import_logs (filename, parsed, inserted, skipped, errors, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (file.filename, 0, 0, 0, 1, "error"))
            conn.commit()
            conn.close()
        except Exception as log_error:
            logger.error(f"❌ Failed to log import error: {log_error}")
        
        return {
            "success": False,
            "message": f"Error processing file: {str(e)}",
            "filename": file.filename,
            "parsed": 0,
            "inserted": 0,
            "skipped": 0,
            "errors": 1,
            "error_details": [str(e), error_trace.split('\n')[-2] if len(error_trace.split('\n')) > 1 else ""]
        }
    
    finally:
        # Clean up temp file
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
                logger.debug(f"🗑️  Cleaned up temp file: {tmp_path}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to delete temp file: {e}")


@router.delete("")
async def delete_all_transactions():
    """
    Delete all transactions from the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM transactions")
        count_before = cursor.fetchone()[0]
        
        # Delete all transactions
        cursor.execute("DELETE FROM transactions")
        conn.commit()
        
        logger.info(f"🗑️  Deleted {count_before} transactions")
        
        return {
            "success": True,
            "message": f"Deleted {count_before} transactions",
            "deleted_count": count_before
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to delete transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete transactions: {str(e)}")
    finally:
        conn.close()


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: str):
    """
    Delete a single transaction by transaction_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if transaction exists
        cursor.execute("SELECT id, symbol, trade_date FROM transactions WHERE transaction_id = ?", (transaction_id,))
        transaction = cursor.fetchone()
        
        if not transaction:
            raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
        
        # Delete the transaction
        cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", (transaction_id,))
        conn.commit()
        
        logger.info(f"🗑️  Deleted transaction {transaction_id} ({transaction['symbol']} {transaction['trade_date']})")
        
        return {
            "success": True,
            "message": f"Deleted transaction {transaction_id}",
            "transaction_id": transaction_id
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to delete transaction {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete transaction: {str(e)}")
    finally:
        conn.close()


@router.post("/delete-batch")
async def delete_transactions_batch(transaction_ids: List[str]):
    """
    Delete multiple transactions by their transaction_ids.
    """
    if not transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verify all transactions exist
        placeholders = ','.join(['?'] * len(transaction_ids))
        cursor.execute(f"SELECT transaction_id FROM transactions WHERE transaction_id IN ({placeholders})", transaction_ids)
        existing_ids = [row[0] for row in cursor.fetchall()]
        
        missing_ids = set(transaction_ids) - set(existing_ids)
        if missing_ids:
            logger.warning(f"⚠️  Some transaction IDs not found: {missing_ids}")
        
        if not existing_ids:
            raise HTTPException(status_code=404, detail="No transactions found to delete")
        
        # Delete the transactions
        placeholders = ','.join(['?'] * len(existing_ids))
        cursor.execute(f"DELETE FROM transactions WHERE transaction_id IN ({placeholders})", existing_ids)
        conn.commit()
        
        deleted_count = cursor.rowcount
        
        logger.info(f"🗑️  Deleted {deleted_count} transactions")
        
        return {
            "success": True,
            "message": f"Deleted {deleted_count} transactions",
            "deleted_count": deleted_count,
            "requested_count": len(transaction_ids),
            "missing_ids": list(missing_ids) if missing_ids else []
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to delete transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete transactions: {str(e)}")
    finally:
        conn.close()


@router.delete("/import-logs")
async def delete_all_import_logs():
    """
    Delete all import logs from the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM import_logs")
        count_before = cursor.fetchone()[0]
        
        # Delete all import logs
        cursor.execute("DELETE FROM import_logs")
        conn.commit()
        
        logger.info(f"🗑️  Deleted {count_before} import logs")
        
        return {
            "success": True,
            "message": f"Deleted {count_before} import logs",
            "deleted_count": count_before
        }
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to delete import logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete import logs: {str(e)}")
    finally:
        conn.close()
