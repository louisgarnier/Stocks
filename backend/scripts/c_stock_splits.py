"""
Stock Splits Fetcher and Applier

Fetches stock splits from Yahoo Finance for all symbols in the database,
stores them in the stock_splits table, and applies adjustments to historical transactions.

Usage:
    python backend/scripts/c_stock_splits.py --fetch     # Fetch splits from Yahoo Finance
    python backend/scripts/c_stock_splits.py --apply     # Apply splits to transactions
    python backend/scripts/c_stock_splits.py --all       # Fetch and apply
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import yfinance as yf

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import get_logger, log_event

logger = get_logger("splits")


def get_unique_symbols() -> List[str]:
    """Get all unique symbols from transactions table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT symbol FROM transactions WHERE symbol NOT LIKE '%.%'")
    symbols = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    logger.info(f"📊 Found {len(symbols)} unique symbols in database")
    return symbols


def fetch_splits_for_symbol(symbol: str) -> List[Dict]:
    """
    Fetch stock splits from Yahoo Finance for a given symbol.
    
    Args:
        symbol: Stock ticker symbol
        
    Returns:
        List of split dictionaries with date and ratio
    """
    try:
        ticker = yf.Ticker(symbol)
        splits = ticker.splits
        
        if splits.empty:
            return []
        
        result = []
        for date, ratio in splits.items():
            result.append({
                "symbol": symbol,
                "split_date": date.strftime("%Y-%m-%d"),
                "split_ratio": float(ratio)
            })
        
        return result
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to fetch splits for {symbol}: {e}")
        return []


def fetch_all_splits() -> Dict:
    """
    Fetch splits for all symbols in the database.
    
    Returns:
        Dict with counts of fetched and stored splits
    """
    logger.info("🚀 Starting stock splits fetch from Yahoo Finance...")
    
    symbols = get_unique_symbols()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total_fetched = 0
    total_stored = 0
    total_skipped = 0
    
    for symbol in symbols:
        splits = fetch_splits_for_symbol(symbol)
        
        for split in splits:
            total_fetched += 1
            
            # Check if already exists
            cursor.execute(
                "SELECT id FROM stock_splits WHERE symbol = ? AND split_date = ?",
                (split["symbol"], split["split_date"])
            )
            
            if cursor.fetchone():
                total_skipped += 1
                continue
            
            # Insert new split
            cursor.execute("""
                INSERT INTO stock_splits (symbol, split_date, split_ratio, fetched_at)
                VALUES (?, ?, ?, ?)
            """, (
                split["symbol"],
                split["split_date"],
                split["split_ratio"],
                datetime.now().isoformat()
            ))
            total_stored += 1
            logger.info(f"📈 Stored split: {split['symbol']} {split['split_ratio']}:1 on {split['split_date']}")
    
    conn.commit()
    conn.close()
    
    log_event("FETCHED", "StockSplits", details={
        "symbols_checked": len(symbols),
        "splits_found": total_fetched,
        "splits_stored": total_stored,
        "splits_skipped": total_skipped
    })
    
    logger.info(f"✅ Splits fetch complete: {total_stored} new, {total_skipped} existing")
    
    return {
        "success": True,
        "symbols_checked": len(symbols),
        "splits_found": total_fetched,
        "splits_stored": total_stored,
        "splits_skipped": total_skipped
    }


def apply_splits_to_transactions() -> Dict:
    """
    Apply stock splits to historical transactions.
    
    For each transaction BEFORE a split date:
    - updated_quantity = quantity × split_ratio
    - updated_t_price = t_price ÷ split_ratio
    - stock_splits_applied = description of splits applied
    
    Returns:
        Dict with count of adjusted transactions
    """
    logger.info("🚀 Applying stock splits to transactions...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all splits ordered by date
    cursor.execute("""
        SELECT symbol, split_date, split_ratio 
        FROM stock_splits 
        ORDER BY symbol, split_date
    """)
    splits = cursor.fetchall()
    
    if not splits:
        logger.info("ℹ️ No splits found in database")
        return {"success": True, "adjusted": 0, "message": "No splits to apply"}
    
    logger.info(f"📊 Found {len(splits)} splits to process")
    
    # Group splits by symbol
    splits_by_symbol = {}
    for symbol, split_date, split_ratio in splits:
        if symbol not in splits_by_symbol:
            splits_by_symbol[symbol] = []
        splits_by_symbol[symbol].append((split_date, split_ratio))
    
    total_adjusted = 0
    total_already_applied = 0
    
    for symbol, symbol_splits in splits_by_symbol.items():
        # Get transactions for this symbol that haven't been adjusted
        cursor.execute("""
            SELECT id, trade_date, quantity, t_price, stock_splits_applied
            FROM transactions 
            WHERE symbol = ?
            ORDER BY trade_date
        """, (symbol,))
        
        transactions = cursor.fetchall()
        
        for tx_id, trade_date, quantity, t_price, already_applied in transactions:
            # Calculate cumulative split ratio for this transaction
            cumulative_ratio = 1.0
            applied_splits = []
            
            for split_date, split_ratio in symbol_splits:
                # If transaction is BEFORE the split, apply it
                if trade_date < split_date:
                    cumulative_ratio *= split_ratio
                    applied_splits.append(f"{split_ratio}:1 ({split_date})")
            
            if cumulative_ratio == 1.0:
                # No splits apply to this transaction
                if not already_applied:
                    cursor.execute("""
                        UPDATE transactions 
                        SET stock_splits_applied = 'no split',
                            updated_quantity = quantity,
                            updated_t_price = t_price
                        WHERE id = ?
                    """, (tx_id,))
                continue
            
            # Build description
            splits_desc = f"{symbol} " + ", ".join(applied_splits)
            
            # Check if already applied with same description
            if already_applied == splits_desc:
                total_already_applied += 1
                continue
            
            # Calculate adjusted values
            updated_quantity = quantity * cumulative_ratio
            updated_t_price = t_price / cumulative_ratio if t_price else None
            
            # Update transaction
            cursor.execute("""
                UPDATE transactions 
                SET updated_quantity = ?,
                    updated_t_price = ?,
                    stock_splits_applied = ?
                WHERE id = ?
            """, (updated_quantity, updated_t_price, splits_desc, tx_id))
            
            total_adjusted += 1
            logger.info(f"📈 Adjusted {symbol}: {quantity} → {updated_quantity} (×{cumulative_ratio})")
    
    # Mark splits as applied
    cursor.execute("""
        UPDATE stock_splits 
        SET applied_at = ? 
        WHERE applied_at IS NULL
    """, (datetime.now().isoformat(),))
    
    conn.commit()
    conn.close()
    
    log_event("APPLIED", "StockSplits", details={
        "adjusted": total_adjusted,
        "already_applied": total_already_applied
    })
    
    logger.info(f"✅ Splits applied: {total_adjusted} transactions adjusted, {total_already_applied} already done")
    
    return {
        "success": True,
        "adjusted": total_adjusted,
        "already_applied": total_already_applied,
        "message": f"Adjusted {total_adjusted} transactions"
    }


def fetch_and_apply() -> Dict:
    """Fetch splits and apply them in one operation."""
    fetch_result = fetch_all_splits()
    apply_result = apply_splits_to_transactions()
    
    return {
        "success": True,
        "fetch": fetch_result,
        "apply": apply_result
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch and apply stock splits")
    parser.add_argument("--fetch", action="store_true", help="Fetch splits from Yahoo Finance")
    parser.add_argument("--apply", action="store_true", help="Apply splits to transactions")
    parser.add_argument("--all", action="store_true", help="Fetch and apply")
    
    args = parser.parse_args()
    
    if args.all:
        result = fetch_and_apply()
    elif args.fetch:
        result = fetch_all_splits()
    elif args.apply:
        result = apply_splits_to_transactions()
    else:
        print("Usage:")
        print("  python c_stock_splits.py --fetch   # Fetch splits from Yahoo Finance")
        print("  python c_stock_splits.py --apply   # Apply splits to transactions")
        print("  python c_stock_splits.py --all     # Fetch and apply")
        sys.exit(1)
    
    print(f"\nResult: {result}")
    sys.exit(0 if result.get("success") else 1)
