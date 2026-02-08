"""
IBKR Trade Import Script

Imports trades from IBKR CSV files (historical or daily) into the database.
Handles deduplication using IBKR TransactionID.

Based on: docs/project/requirements/RAW_REQUIREMENTS.md
"""

import os
import sys
import csv
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import get_logger, log_event

logger = get_logger("trades")

# Input directories
HISTORICAL_DIR = PROJECT_ROOT / "input" / "daily_trades" / "historical trades"
DAILY_DIR = PROJECT_ROOT / "input" / "daily_trades"


def parse_ibkr_csv(filepath: Path) -> List[Dict]:
    """
    Parse an IBKR Activity Statement CSV file and extract trades.
    
    Args:
        filepath: Path to the CSV file
        
    Returns:
        List of trade dictionaries
    """
    trades = []
    
    logger.info(f"📂 Parsing file: {filepath.name}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        header_found = False
        header_indices = {}
        
        for row in reader:
            if len(row) < 3:
                continue
            
            # Look for Trades header row
            if row[0] == 'Trades' and row[1] == 'Header':
                header_found = True
                # Map column names to indices
                for i, col in enumerate(row):
                    header_indices[col] = i
                continue
            
            # Parse trade data rows (only "Order" type, skip SubTotal/Total)
            if header_found and row[0] == 'Trades' and row[1] == 'Data' and row[2] == 'Order':
                # Only process Stocks
                asset_category = row[3] if len(row) > 3 else ''
                if asset_category != 'Stocks':
                    continue
                
                try:
                    # Extract fields based on IBKR CSV format
                    # Format varies - some files have Date and Time in separate columns
                    # Format 1: Trades,Data,Order,Stocks,{Currency},{Symbol},{Date/Time},{Quantity},...
                    # Format 2: Trades,Data,Order,Stocks,{Currency},{Symbol},{Date},{Time},{Quantity},...
                    
                    currency = row[4] if len(row) > 4 else ''
                    symbol = row[5] if len(row) > 5 else ''
                    
                    # Check if column 7 looks like a time (contains :) - means date/time are split
                    col7 = row[7] if len(row) > 7 else ''
                    if ':' in col7 and ',' not in row[6]:
                        # Format 2: Date and Time in separate columns
                        datetime_str = f"{row[6]}, {col7.strip()}"
                        quantity_str = row[8] if len(row) > 8 else '0'
                        t_price_str = row[9] if len(row) > 9 else '0'
                        c_price_str = row[10] if len(row) > 10 else '0'
                        proceeds_str = row[11] if len(row) > 11 else '0'
                        comm_fee_str = row[12] if len(row) > 12 else '0'
                    else:
                        # Format 1: Date/Time combined
                        datetime_str = row[6] if len(row) > 6 else ''
                        quantity_str = row[7] if len(row) > 7 else '0'
                        t_price_str = row[8] if len(row) > 8 else '0'
                        c_price_str = row[9] if len(row) > 9 else '0'
                        proceeds_str = row[10] if len(row) > 10 else '0'
                        comm_fee_str = row[11] if len(row) > 11 else '0'
                    
                    # Parse values
                    quantity = float(quantity_str.replace(',', '')) if quantity_str else 0
                    t_price = float(t_price_str.replace(',', '')) if t_price_str else 0
                    proceeds = float(proceeds_str.replace(',', '')) if proceeds_str else 0
                    comm_fee = float(comm_fee_str.replace(',', '')) if comm_fee_str else 0
                    
                    # Parse date (format: "2024-03-18, 10:46:15")
                    trade_date = ''
                    if datetime_str:
                        # Remove quotes and parse
                        datetime_str = datetime_str.strip('"')
                        try:
                            dt = datetime.strptime(datetime_str, "%Y-%m-%d, %H:%M:%S")
                            trade_date = dt.strftime("%Y-%m-%d")
                        except ValueError:
                            # Try alternative format
                            try:
                                dt = datetime.strptime(datetime_str, "%Y-%m-%d")
                                trade_date = dt.strftime("%Y-%m-%d")
                            except ValueError:
                                trade_date = datetime_str[:10] if len(datetime_str) >= 10 else datetime_str
                    
                    # Generate a unique transaction ID from the data
                    # IBKR doesn't always provide TransactionID in CSV, so we create one
                    transaction_id = f"{symbol}_{trade_date}_{datetime_str}_{quantity}_{t_price}"
                    transaction_id = re.sub(r'[^a-zA-Z0-9_-]', '', transaction_id)
                    
                    trade = {
                        'transaction_id': transaction_id,
                        'symbol': symbol,
                        'currency': currency,
                        'trade_date': trade_date,
                        'quantity': quantity,
                        't_price': abs(t_price),  # Price is always positive
                        'proceeds': proceeds,
                        'comm_fee': comm_fee,
                    }
                    
                    trades.append(trade)
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"⚠️ Failed to parse row: {row[:8]}... Error: {e}")
                    continue
    
    logger.info(f"✅ Parsed {len(trades)} trades from {filepath.name}")
    return trades


def insert_trades(trades: List[Dict]) -> Dict:
    """
    Insert trades into the database, skipping duplicates.
    
    Args:
        trades: List of trade dictionaries
        
    Returns:
        Dict with inserted and skipped counts
    """
    if not trades:
        return {"inserted": 0, "skipped": 0, "total": 0}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for trade in trades:
        # Check if transaction already exists
        cursor.execute(
            "SELECT id FROM transactions WHERE transaction_id = ?",
            (trade['transaction_id'],)
        )
        
        if cursor.fetchone():
            skipped += 1
            continue
        
        # Insert new transaction
        cursor.execute("""
            INSERT INTO transactions (
                transaction_id, symbol, trade_date, quantity, 
                t_price, proceeds, comm_fee, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade['transaction_id'],
            trade['symbol'],
            trade['trade_date'],
            trade['quantity'],
            trade['t_price'],
            trade['proceeds'],
            trade['comm_fee'],
            datetime.now().isoformat()
        ))
        inserted += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"📊 Inserted: {inserted}, Skipped (duplicates): {skipped}")
    
    return {
        "inserted": inserted,
        "skipped": skipped,
        "total": inserted + skipped
    }


def import_historical_files() -> Dict:
    """
    Import all historical CSV files from the historical trades directory.
    
    Returns:
        Dict with total counts
    """
    logger.info("🚀 Starting historical import...")
    
    if not HISTORICAL_DIR.exists():
        logger.error(f"❌ Historical directory not found: {HISTORICAL_DIR}")
        return {"success": False, "message": "Historical directory not found"}
    
    csv_files = list(HISTORICAL_DIR.glob("*.csv"))
    
    if not csv_files:
        logger.warning("⚠️ No CSV files found in historical directory")
        return {"success": False, "message": "No CSV files found"}
    
    logger.info(f"📁 Found {len(csv_files)} CSV files")
    
    total_inserted = 0
    total_skipped = 0
    
    for filepath in sorted(csv_files):
        trades = parse_ibkr_csv(filepath)
        result = insert_trades(trades)
        total_inserted += result["inserted"]
        total_skipped += result["skipped"]
    
    log_event("IMPORTED", "HistoricalTrades", details={
        "files": len(csv_files),
        "inserted": total_inserted,
        "skipped": total_skipped
    })
    
    logger.info(f"✅ Historical import complete: {total_inserted} inserted, {total_skipped} skipped")
    
    return {
        "success": True,
        "message": f"Imported {total_inserted} trades from {len(csv_files)} files",
        "files": len(csv_files),
        "inserted": total_inserted,
        "skipped": total_skipped
    }


def import_daily_file(filepath: Path) -> Dict:
    """
    Import a single daily CSV file.
    
    Args:
        filepath: Path to the CSV file
        
    Returns:
        Dict with counts
    """
    logger.info(f"🚀 Importing daily file: {filepath.name}")
    
    if not filepath.exists():
        return {"success": False, "message": f"File not found: {filepath}"}
    
    trades = parse_ibkr_csv(filepath)
    result = insert_trades(trades)
    
    log_event("IMPORTED", "DailyTrades", details={
        "file": filepath.name,
        "inserted": result["inserted"],
        "skipped": result["skipped"]
    })
    
    return {
        "success": True,
        "message": f"Imported {result['inserted']} trades",
        **result
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Import IBKR trades from CSV files")
    parser.add_argument("--historical", action="store_true", help="Import all historical files")
    parser.add_argument("--file", type=str, help="Import a specific file")
    
    args = parser.parse_args()
    
    if args.historical:
        result = import_historical_files()
    elif args.file:
        result = import_daily_file(Path(args.file))
    else:
        print("Usage:")
        print("  python b_daily_trades.py --historical    # Import all historical files")
        print("  python b_daily_trades.py --file <path>   # Import a specific file")
        sys.exit(1)
    
    print(f"\nResult: {result}")
    sys.exit(0 if result.get("success") else 1)
