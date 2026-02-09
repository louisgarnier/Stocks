"""
CSV Trades Parser

Parses IBKR CSV files to extract trades from the Trades section.
Only processes rows where:
- Column 0 = "Trades"
- Column 1 = "Data"
- Column 2 = "Order"
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import logger


def detect_delimiter(filepath: Path) -> str:
    """Detect the delimiter used in a CSV file (comma or semicolon)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        semicolons = first_line.count(';')
        commas = first_line.count(',')
        return ';' if semicolons > commas else ','


def parse_datetime(datetime_str: str) -> tuple[str, str]:
    """
    Parse IBKR datetime string to (date, time) tuple.
    Handles formats like: "2023-07-19, 03:00:05" or "2023-07-19"
    
    Returns:
        Tuple of (date, time) where:
        - date is in YYYY-MM-DD format
        - time is in HH:MM:SS format (or empty string if no time)
    """
    datetime_str = datetime_str.strip()
    if not datetime_str:
        return ("", "")
    
    # If contains comma, split date and time
    if ',' in datetime_str:
        parts = datetime_str.split(',', 1)
        date_part = parts[0].strip()
        time_part = parts[1].strip() if len(parts) > 1 else ""
        
        # Validate date format
        if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
            return (date_part, time_part)
        return (date_part, time_part)
    
    # No comma - just date
    if len(datetime_str) == 10 and datetime_str[4] == '-' and datetime_str[7] == '-':
        return (datetime_str, "")
    
    return (datetime_str, "")


def get_next_transaction_id(cursor) -> str:
    """
    Generate the next unique transaction_id.
    Format: YYYYMMDD00xxxxxx where xxxxxx is a sequential number (000001 to 100000).
    The sequential number never reuses deleted IDs - it always increments.
    
    Args:
        cursor: Database cursor (must be within a transaction for thread safety)
    
    Returns:
        A unique transaction_id for today's date
    """
    from datetime import datetime
    
    # Get today's date in YYYYMMDD format
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"{today}00"
    
    # Find the highest transaction_id for today
    cursor.execute("""
        SELECT transaction_id 
        FROM transactions 
        WHERE transaction_id LIKE ?
        ORDER BY transaction_id DESC 
        LIMIT 1
    """, (f"{prefix}%",))
    
    result = cursor.fetchone()
    
    if result:
        # Extract the sequential number from the last ID
        last_id = result[0]
        if len(last_id) >= len(prefix) + 6:
            try:
                last_seq = int(last_id[-6:])  # Last 6 digits
                next_seq = last_seq + 1
            except ValueError:
                next_seq = 1
        else:
            next_seq = 1
    else:
        # No transactions for today yet, start at 1
        next_seq = 1
    
    # Check if we exceed 100000
    if next_seq > 100000:
        logger.error(f"❌ Maximum transaction limit (100000) reached for {today}")
        raise ValueError(f"Maximum transaction limit (100000) reached for {today}")
    
    # Format: YYYYMMDD00xxxxxx (6 digits for sequence)
    transaction_id = f"{prefix}{next_seq:06d}"
    
    return transaction_id


def safe_float(value, default=0):
    """Safely convert a value to float, handling commas as thousands separator."""
    if not value or value == "":
        return default
    try:
        # Remove commas and convert to float
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return default


def parse_csv_file(filepath: Path) -> List[Dict]:
    """
    Parse an IBKR CSV file and extract trades.
    
    Returns:
        List of trade dictionaries
    """
    trades = []
    delimiter = detect_delimiter(filepath)
    line_number = 0
    debug_rows = []  # Store first few rows for debugging
    
    logger.info(f"📂 Parsing CSV file: {filepath.name} (delimiter: '{delimiter}')")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)
            
            for row in reader:
                line_number += 1
                
                # Debug: store first 20 rows
                if line_number <= 20:
                    debug_rows.append({
                        'line': line_number,
                        'row': row,
                        'len': len(row),
                        'first_3': row[:3] if len(row) >= 3 else row
                    })
                
                # Skip rows that don't have enough columns
                if len(row) < 3:
                    continue
                
                # Check if this is a trade row: Trades,Data,Order
                # Also check for case-insensitive matches and variations
                col0 = row[0].strip() if len(row) > 0 else ""
                col1 = row[1].strip() if len(row) > 1 else ""
                col2 = row[2].strip() if len(row) > 2 else ""
                
                is_trade_row = (
                    (col0 == "Trades" or col0.upper() == "TRADES") and
                    (col1 == "Data" or col1.upper() == "DATA") and
                    (col2 == "Order" or col2.upper() == "ORDER")
                )
                
                if is_trade_row:
                    try:
                        # Format: Trades,Data,Order,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,C. Price,Proceeds,Comm/Fee,Basis,Realized P/L,MTM P/L,Code
                        asset_category = row[3] if len(row) > 3 else ""
                        currency = row[4] if len(row) > 4 else ""
                        symbol = row[5] if len(row) > 5 else ""
                        datetime_str = row[6] if len(row) > 6 else ""
                        
                        # Handle numeric values with comma as thousands separator
                        quantity = safe_float(row[7] if len(row) > 7 else "")
                        t_price = safe_float(row[8] if len(row) > 8 else "")
                        c_price = safe_float(row[9] if len(row) > 9 else "")
                        proceeds = safe_float(row[10] if len(row) > 10 else "")
                        comm_fee = safe_float(row[11] if len(row) > 11 else "")
                        basis = safe_float(row[12] if len(row) > 12 else "")
                        
                        # Skip non-stock trades
                        if asset_category != "Stocks":
                            continue
                        
                        # Parse date and time
                        trade_date, trade_time = parse_datetime(datetime_str)
                        if not trade_date:
                            logger.warning(f"⚠️  Skipping trade on line {line_number}: invalid date")
                            continue
                        
                        # Note: transaction_id will be generated during insertion to ensure uniqueness
                        
                        trades.append({
                            "source_file": filepath.name,
                            "asset_category": asset_category,
                            "currency": currency,
                            "symbol": symbol,
                            "trade_date": trade_date,
                            "trade_time": trade_time,
                            "quantity": quantity,
                            "t_price": abs(t_price),
                            "c_price": c_price,
                            "proceeds": proceeds,
                            "comm_fee": comm_fee,
                            "basis": basis
                        })
                        
                    except (IndexError, ValueError) as e:
                        logger.warning(f"⚠️  Failed to parse trade on line {line_number}: {e}")
                        continue
    
    except Exception as e:
        logger.error(f"❌ Failed to read file {filepath}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Log debug info if no trades found
    if len(trades) == 0 and debug_rows:
        logger.warning(f"⚠️  No trades found. First {len(debug_rows)} rows:")
        for dbg in debug_rows[:10]:
            logger.warning(f"  Line {dbg['line']}: {dbg['first_3']} (len={dbg['len']})")
    
    logger.info(f"✅ Parsed {len(trades)} trades from {filepath.name}")
    return trades


def insert_trades(trades: List[Dict]) -> Dict:
    """
    Insert trades into the database.
    
    Returns:
        Dict with inserted, skipped, and errors counts
    """
    if not trades:
        return {"inserted": 0, "skipped": 0, "errors": 0}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    errors = 0
    error_details = []
    
    logger.info(f"🔄 Starting insertion of {len(trades)} trades")
    
    # Use a transaction to ensure atomicity and prevent race conditions
    for trade in trades:
        # Check for duplicates: symbol + trade_date + trade_time + quantity + t_price
        cursor.execute("""
            SELECT id FROM transactions 
            WHERE symbol = ? 
            AND trade_date = ? 
            AND (trade_time = ? OR (trade_time IS NULL AND ? IS NULL))
            AND quantity = ? 
            AND t_price = ?
        """, (
            trade["symbol"],
            trade["trade_date"],
            trade["trade_time"],
            trade["trade_time"],
            trade["quantity"],
            trade["t_price"]
        ))
        
        if cursor.fetchone():
            skipped += 1
            continue
        
        # Generate unique transaction_id for this trade (within the same connection)
        try:
            transaction_id = get_next_transaction_id(cursor)
        except ValueError as e:
            # Maximum limit reached
            errors += 1
            error_details.append(str(e))
            logger.error(f"❌ {e}")
            continue
        
        # Insert trade with generated transaction_id
        try:
            cursor.execute("""
                INSERT INTO transactions (
                    transaction_id, source_file, asset_category, currency, symbol,
                    trade_date, trade_time, quantity, t_price, c_price, proceeds, comm_fee, basis,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction_id,
                trade["source_file"],
                trade["asset_category"],
                trade["currency"],
                trade["symbol"],
                trade["trade_date"],
                trade["trade_time"],
                trade["quantity"],
                trade["t_price"],
                trade["c_price"],
                trade["proceeds"],
                trade["comm_fee"],
                trade["basis"],
                datetime.now().isoformat()
            ))
            inserted += 1
        except Exception as e:
            errors += 1
            error_msg = f"Failed to insert {trade.get('symbol', '?')} {trade.get('trade_date', '?')}: {str(e)}"
            error_details.append(error_msg)
            logger.error(f"❌ {error_msg}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Insertion complete: {inserted} inserted, {skipped} skipped, {errors} errors out of {len(trades)} total")
    
    return {
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
        "error_details": error_details[:10]  # Limit to first 10 errors
    }


if __name__ == "__main__":
    # Test with the provided file
    test_file = PROJECT_ROOT / "input" / "daily_trades" / "historical trades" / "U7850924_2023_2023.csv"
    
    if test_file.exists():
        trades = parse_csv_file(test_file)
        print(f"\n📊 Found {len(trades)} trades")
        
        if trades:
            print(f"\nFirst trade example:")
            print(f"  Symbol: {trades[0]['symbol']}")
            print(f"  Date: {trades[0]['trade_date']}")
            print(f"  Quantity: {trades[0]['quantity']}")
            print(f"  Price: ${trades[0]['t_price']}")
            print(f"  Transaction ID: {trades[0]['transaction_id']}")
    else:
        print(f"❌ Test file not found: {test_file}")
