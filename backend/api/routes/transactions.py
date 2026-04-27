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
        where_clauses.append("symbol LIKE ?")
        params.append(f"{symbol.upper()}%")
    
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
        
        # Update CA status to 'orange' for actually inserted symbols only
        inserted_symbols = result.get("inserted_symbols", [])
        if inserted_symbols:
            from backend.utils.ca_status import set_ca_status
            try:
                set_ca_status(inserted_symbols, 'orange')
                logger.info(f"🟠 Set CA status to 'orange' for {len(inserted_symbols)} symbols: {inserted_symbols}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to update CA status: {e}")
        
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
        # Get affected symbols before deletion
        cursor.execute("SELECT DISTINCT symbol FROM transactions")
        affected_symbols = [row[0] for row in cursor.fetchall()]
        
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM transactions")
        count_before = cursor.fetchone()[0]
        
        # Delete all transactions
        cursor.execute("DELETE FROM transactions")
        conn.commit()
        
        logger.info(f"🗑️  Deleted {count_before} transactions")
        
        # Set CA status to orange for affected symbols
        if affected_symbols:
            try:
                from backend.utils.ca_status import set_ca_status
                set_ca_status(affected_symbols, 'orange')
                logger.info(f"🟠 Set CA status to 'orange' for {len(affected_symbols)} symbols after deletion")
            except Exception as e:
                logger.warning(f"⚠️  Failed to update CA status: {e}")
        
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
        
        symbol = transaction['symbol']
        
        # Delete the transaction
        cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", (transaction_id,))
        conn.commit()
        
        logger.info(f"🗑️  Deleted transaction {transaction_id} ({symbol} {transaction['trade_date']})")
        
        # Set CA status to orange for this symbol
        try:
            from backend.utils.ca_status import set_ca_status
            set_ca_status([symbol], 'orange')
            logger.info(f"🟠 Set CA status to 'orange' for {symbol} after deletion")
        except Exception as e:
            logger.warning(f"⚠️  Failed to update CA status: {e}")
        
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
        # Get affected symbols before deletion
        placeholders = ','.join(['?'] * len(transaction_ids))
        cursor.execute(f"SELECT DISTINCT symbol FROM transactions WHERE transaction_id IN ({placeholders})", transaction_ids)
        affected_symbols = [row[0] for row in cursor.fetchall()]
        
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
        
        # Set CA status to orange for affected symbols
        if affected_symbols:
            try:
                from backend.utils.ca_status import set_ca_status
                set_ca_status(affected_symbols, 'orange')
                logger.info(f"🟠 Set CA status to 'orange' for {len(affected_symbols)} symbols after deletion")
            except Exception as e:
                logger.warning(f"⚠️  Failed to update CA status: {e}")
        
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


@router.get("/export")
async def export_transactions():
    """
    Export all transactions as CSV.
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT transaction_id, original_transaction_id, source_file, asset_category, currency, symbol,
               trade_date, trade_time, quantity, t_price, c_price, proceeds, comm_fee, basis,
               created_at
        FROM transactions
        ORDER BY trade_date DESC, symbol ASC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'transaction_id', 'original_transaction_id', 'source_file', 'asset_category', 'currency', 'symbol',
        'trade_date', 'trade_time', 'quantity', 't_price', 'c_price', 'proceeds', 'comm_fee', 'basis',
        'created_at'
    ])
    
    # Data
    for row in rows:
        writer.writerow([
            row['transaction_id'],
            row['original_transaction_id'] or '',
            row['source_file'] or '',
            row['asset_category'] or '',
            row['currency'] or '',
            row['symbol'],
            row['trade_date'],
            row['trade_time'] or '',
            row['quantity'],
            row['t_price'] or '',
            row['c_price'] or '',
            row['proceeds'] or '',
            row['comm_fee'] or '',
            row['basis'] or '',
            row['created_at'] or ''
        ])
    
    output.seek(0)
    
    logger.info(f"📤 Exported {len(rows)} transactions to CSV")
    
    # Return as downloadable CSV
    from datetime import datetime
    filename = f"transactions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/securities")
async def list_securities():
    """
    List all unique securities (symbols) with their position summary.
    Returns count, total quantity (position), and transaction stats per symbol.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                symbol,
                COUNT(*) as transaction_count,
                SUM(quantity) as total_quantity,
                MIN(trade_date) as first_trade,
                MAX(trade_date) as last_trade,
                asset_category,
                currency
            FROM transactions
            GROUP BY symbol
            ORDER BY symbol ASC
        """)
        
        rows = cursor.fetchall()
        
        securities = []
        for row in rows:
            securities.append({
                "symbol": row["symbol"],
                "transaction_count": row["transaction_count"],
                "total_quantity": row["total_quantity"],
                "first_trade": row["first_trade"],
                "last_trade": row["last_trade"],
                "asset_category": row["asset_category"],
                "currency": row["currency"]
            })
        
        logger.info(f"📊 Listed {len(securities)} securities")
        
        return {
            "data": securities,
            "total": len(securities)
        }
    except Exception as e:
        logger.error(f"❌ Failed to list securities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list securities: {str(e)}")
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


@router.get("/adjusted")
async def list_adjusted_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=500),
    sort_by: str = Query("trade_date", regex="^(trade_date|symbol|quantity|t_price)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    symbol: Optional[str] = None
):
    """
    List adjusted transactions from the transactions_adjusted view.
    This view combines transactions with updated_transactions, using adjusted values when available.
    Excludes Forex symbols (containing '.').
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if symbol:
            where_clauses.append("symbol = ?")
            params.append(symbol)
        
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        # Count total
        count_query = f"SELECT COUNT(*) FROM transactions_adjusted {where_sql}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get paginated data
        offset = (page - 1) * limit
        query = f"""
            SELECT 
                transaction_id,
                symbol,
                trade_date,
                quantity,
                t_price,
                original_quantity,
                original_price,
                is_adjusted,
                split_ratio,
                ca_type,
                ca_date,
                currency,
                commission,
                cost
            FROM transactions_adjusted
            {where_sql}
            ORDER BY {sort_by} {sort_order}
            LIMIT ? OFFSET ?
        """
        
        cursor.execute(query, params + [limit, offset])
        rows = cursor.fetchall()
        
        transactions = []
        for row in rows:
            transactions.append({
                "transaction_id": row[0],
                "symbol": row[1],
                "trade_date": row[2],
                "quantity": row[3],
                "t_price": row[4],
                "original_quantity": row[5],
                "original_price": row[6],
                "is_adjusted": bool(row[7]),
                "split_ratio": row[8],
                "ca_type": row[9],
                "ca_date": row[10],
                "currency": row[11],
                "commission": row[12],
                "cost": row[13]
            })
        
        conn.close()
        
        return {
            "transactions": transactions,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch adjusted transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch adjusted transactions: {str(e)}")


@router.post("/apply-splits")
async def apply_splits():
    """
    Applique tous les splits/spinoffs aux transactions concernées.
    Crée/met à jour les entrées dans updated_transactions.
    """
    try:
        from backend.scripts.apply_splits import apply_all_splits
        
        logger.info("🔄 Application des splits aux transactions...")
        
        result = apply_all_splits()
        
        logger.info(f"✅ Splits appliqués: {result['updated']} transaction(s) mise(s) à jour")
        
        return {
            "success": True,
            "message": f"Splits appliqués à {result['updated']} transaction(s)",
            "updated": result['updated'],
            "symbols": result['symbols']
        }
    except Exception as e:
        logger.error(f"❌ Failed to apply splits: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply splits: {str(e)}")
