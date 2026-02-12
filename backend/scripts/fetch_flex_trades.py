"""
IBKR Flex Queries - Fetch and Import Trades

Fetches trades from Interactive Brokers Flex Query API and imports them to database.
API Flow:
1. Request query execution → get reference code
2. Fetch results using reference code → get XML with trades
3. Filter trades after last DB date → insert new trades only
"""

import os
import sys
import time
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

# IBKR Flex API endpoints
FLEX_REQUEST_URL = "https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest"
FLEX_FETCH_URL = "https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement"


def request_flex_query(token: str, query_id: str) -> str | None:
    """
    Request a Flex Query execution.
    
    Args:
        token: IBKR Flex Token
        query_id: Flex Query ID
        
    Returns:
        Reference code to fetch results, or None if failed
    """
    logger.info(f"📡 Requesting Flex Query execution (Query ID: {query_id})")
    
    try:
        response = requests.get(
            FLEX_REQUEST_URL,
            params={"t": token, "q": query_id, "v": "3"},
            timeout=30
        )
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.text)
        
        # Check for errors
        status = root.find("Status")
        if status is not None and status.text != "Success":
            error_code = root.find("ErrorCode")
            error_msg = root.find("ErrorMessage")
            logger.error(f"❌ Flex Query request failed: {error_code.text if error_code is not None else 'Unknown'} - {error_msg.text if error_msg is not None else 'No message'}")
            return None
        
        # Get reference code
        reference_code = root.find("ReferenceCode")
        if reference_code is None or not reference_code.text:
            logger.error("❌ No reference code in response")
            return None
            
        logger.info(f"✅ Got reference code: {reference_code.text}")
        return reference_code.text
        
    except requests.RequestException as e:
        logger.error(f"❌ Request failed: {e}")
        return None
    except ET.ParseError as e:
        logger.error(f"❌ Failed to parse XML response: {e}")
        return None


def fetch_flex_results(token: str, reference_code: str, max_retries: int = 5) -> str | None:
    """
    Fetch Flex Query results using reference code.
    
    Args:
        token: IBKR Flex Token
        reference_code: Reference code from request
        max_retries: Maximum number of retries (results may not be ready immediately)
        
    Returns:
        XML content with results, or None if failed
    """
    logger.info(f"📥 Fetching Flex Query results...")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(
                FLEX_FETCH_URL,
                params={"q": reference_code, "t": token, "v": "3"},
                timeout=60
            )
            response.raise_for_status()
            
            # Check if results are ready (might get a "please wait" response)
            if "FlexQueryResponse" in response.text or "FlexStatementResponse" in response.text:
                logger.info(f"✅ Results received (attempt {attempt + 1})")
                return response.text
            
            # Check for error
            try:
                root = ET.fromstring(response.text)
                status = root.find("Status")
                if status is not None and status.text == "Warn":
                    # Results not ready yet
                    logger.info(f"⏳ Results not ready, waiting... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)
                    continue
                elif status is not None and status.text != "Success":
                    error_msg = root.find("ErrorMessage")
                    logger.error(f"❌ Fetch failed: {error_msg.text if error_msg is not None else 'Unknown error'}")
                    return None
            except ET.ParseError:
                # If we can't parse it as simple XML, it might be the full response
                return response.text
                
        except requests.RequestException as e:
            logger.error(f"❌ Fetch request failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
    
    logger.error(f"❌ Max retries ({max_retries}) reached")
    return None


def parse_trades_from_xml(xml_content: str) -> list[dict]:
    """
    Parse trades from Flex Query XML response.
    
    Args:
        xml_content: XML string from Flex Query
        
    Returns:
        List of trade dictionaries
    """
    trades = []
    
    try:
        root = ET.fromstring(xml_content)
        
        # Find all Trade elements
        trade_elements = root.findall(".//Trade")
        
        if not trade_elements:
            trade_elements = root.findall(".//Trades/Trade")
        
        if not trade_elements:
            trade_elements = root.findall(".//Order")
        
        logger.info(f"📊 Found {len(trade_elements)} trade elements in XML")
        
        for trade in trade_elements:
            # Get transaction ID (IBKR's unique identifier)
            transaction_id = (
                trade.get("transactionID") or 
                trade.get("tradeID") or 
                trade.get("ibOrderID") or
                ""
            )
            
            # Get trade date in YYYYMMDD format from API
            trade_date_raw = trade.get("tradeDate", "")
            
            trade_data = {
                "original_transaction_id": transaction_id,
                "symbol": trade.get("symbol", ""),
                "currency": trade.get("currency", ""),
                "asset_category": trade.get("assetCategory", "Stocks"),
                "trade_date_raw": trade_date_raw,  # YYYYMMDD format
                "trade_date": convert_date_format(trade_date_raw),  # YYYY-MM-DD format
                "trade_time": "",  # Flex API doesn't always provide time separately
                "quantity": safe_float(trade.get("quantity", "")),
                "t_price": abs(safe_float(trade.get("tradePrice", ""))),
                "proceeds": safe_float(trade.get("proceeds", "")),
                "comm_fee": safe_float(trade.get("ibCommission", "")),
                "cost": safe_float(trade.get("cost", "")),
                "basis": safe_float(trade.get("costBasis", "")),
                "fifo_pnl": safe_float(trade.get("fifoPnlRealized", "")),
                "buy_sell": trade.get("buySell", ""),
            }
            
            # Only include trades with valid data
            if trade_data["symbol"] and trade_data["trade_date"]:
                trades.append(trade_data)
                
    except ET.ParseError as e:
        logger.error(f"❌ Failed to parse trades XML: {e}")
        logger.error(f"Response preview: {xml_content[:500]}")
        
    return trades


def parse_positions_from_xml(xml_content: str) -> list[dict]:
    """
    Parse open positions from Flex Query XML response.
    
    Args:
        xml_content: XML string from Flex Query
        
    Returns:
        List of position dictionaries
    """
    positions = []
    
    try:
        root = ET.fromstring(xml_content)
        
        # Find all OpenPosition elements
        position_elements = root.findall(".//OpenPosition")
        
        if not position_elements:
            position_elements = root.findall(".//OpenPositions/OpenPosition")
        
        logger.info(f"📊 Found {len(position_elements)} position elements in XML")
        
        for pos in position_elements:
            position_data = {
                "symbol": pos.get("symbol", ""),
                "quantity": safe_float(pos.get("position", "")),
                "cost_basis_money": safe_float(pos.get("costBasisMoney", "")),
                "cost_basis_price": safe_float(pos.get("costBasisPrice", "")),
                "mark_price": safe_float(pos.get("markPrice", "")),
                "position_value": safe_float(pos.get("positionValue", "")),
                "unrealized_pnl": safe_float(pos.get("fifoPnlUnrealized", "")),
                "currency": pos.get("currency", ""),
                "asset_category": pos.get("assetCategory", "Stocks"),
            }
            
            # Only include positions with valid data
            if position_data["symbol"] and position_data["quantity"] != 0:
                positions.append(position_data)
                
    except ET.ParseError as e:
        logger.error(f"❌ Failed to parse positions XML: {e}")
        
    return positions


def save_positions_ibkr(positions: list[dict]) -> dict:
    """
    Save IBKR positions to positions_ibkr table.
    Replaces all existing data (DELETE + INSERT).
    
    Args:
        positions: List of position dicts from parse_positions_from_xml
        
    Returns:
        Dict with save results
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # Clear existing positions
    cursor.execute("DELETE FROM positions_ibkr")
    
    inserted = 0
    for pos in positions:
        try:
            cursor.execute("""
                INSERT INTO positions_ibkr (
                    symbol, quantity, cost_basis_money, cost_basis_price,
                    mark_price, position_value, unrealized_pnl,
                    currency, asset_category, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pos["symbol"],
                pos["quantity"],
                pos["cost_basis_money"],
                pos["cost_basis_price"],
                pos["mark_price"],
                pos["position_value"],
                pos["unrealized_pnl"],
                pos["currency"],
                pos["asset_category"],
                now
            ))
            inserted += 1
        except Exception as e:
            logger.error(f"❌ Failed to insert position {pos.get('symbol', '?')}: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Saved {inserted} IBKR positions to positions_ibkr")
    
    return {
        "positions_inserted": inserted,
        "last_updated": now
    }


def convert_date_format(date_str: str) -> str:
    """
    Convert date from YYYYMMDD to YYYY-MM-DD format.
    
    Args:
        date_str: Date in YYYYMMDD format
        
    Returns:
        Date in YYYY-MM-DD format, or empty string if invalid
    """
    if not date_str or len(date_str) != 8:
        return ""
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except Exception:
        return ""


def safe_float(value, default=0.0) -> float:
    """Safely convert a value to float."""
    if not value or value == "":
        return default
    try:
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return default


def get_last_trade_date() -> str | None:
    """
    Get the most recent trade_date from the transactions table.
    
    Returns:
        Date string in YYYY-MM-DD format, or None if no transactions
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT MAX(trade_date) FROM transactions
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        return result[0]
    return None


def get_next_transaction_id(cursor) -> str:
    """
    Generate a unique transaction_id that is NEVER reused.
    Format: YYYYMMDD + timestamp_ms (last 8 digits) + random (2 digits)
    
    This ensures uniqueness even if transactions are deleted.
    
    Args:
        cursor: Database cursor (must be within a transaction)
    
    Returns:
        A unique transaction_id
    """
    import random
    
    today = datetime.now().strftime("%Y%m%d")
    # Use milliseconds since midnight + random to ensure uniqueness
    now = datetime.now()
    ms_since_midnight = (now.hour * 3600 + now.minute * 60 + now.second) * 1000 + now.microsecond // 1000
    random_suffix = random.randint(0, 99)
    
    # Format: YYYYMMDD + 8 digits (ms) + 2 digits (random)
    transaction_id = f"{today}{ms_since_midnight:08d}{random_suffix:02d}"
    
    # Check if it exists (extremely unlikely but let's be safe)
    cursor.execute("SELECT 1 FROM transactions WHERE transaction_id = ?", (transaction_id,))
    if cursor.fetchone():
        # Retry with different random
        import time
        time.sleep(0.001)  # Wait 1ms
        return get_next_transaction_id(cursor)
    
    return transaction_id


def check_original_transaction_exists(cursor, original_transaction_id: str) -> bool:
    """
    Check if a trade with this original_transaction_id already exists in DB.
    
    Args:
        cursor: Database cursor
        original_transaction_id: IBKR transaction ID
        
    Returns:
        True if exists, False otherwise
    """
    if not original_transaction_id:
        return False
    
    cursor.execute("""
        SELECT 1 FROM transactions 
        WHERE original_transaction_id = ?
        LIMIT 1
    """, (original_transaction_id,))
    
    return cursor.fetchone() is not None


def get_similar_trades_count(cursor, symbol: str, trade_date: str, quantity: float, t_price: float) -> tuple[int, int]:
    """
    Count how many similar trades exist in DB (matching symbol, date, quantity, price).
    Returns both total count and count with original_transaction_id.
    
    Args:
        cursor: Database cursor
        symbol: Stock symbol
        trade_date: Trade date (YYYY-MM-DD)
        quantity: Trade quantity
        t_price: Trade price
        
    Returns:
        Tuple of (total_count, count_with_original_id)
    """
    # Use a small tolerance for price comparison (0.0001 for 4 decimal precision)
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN original_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as with_orig_id
        FROM transactions 
        WHERE symbol = ? 
        AND trade_date = ? 
        AND quantity = ?
        AND ABS(t_price - ?) < 0.0001
    """, (symbol, trade_date, quantity, t_price))
    
    result = cursor.fetchone()
    if result:
        return (result[0] or 0, result[1] or 0)
    return (0, 0)


def insert_flex_trades(trades: list[dict], source_file: str) -> dict:
    """
    Insert trades from Flex API into the database.
    
    Logic:
    1. Group Flex trades by signature (symbol, date, qty, price)
    2. For each group:
       a. Check how many trades with these original_transaction_ids exist in DB
       b. Check how many similar trades exist in DB (with or without original_id)
       c. Insert only what's missing
    
    This handles:
    - Pure Flex reimports (original_transaction_id match)
    - CSV + Flex hybrid (count matching)
    - Deleted trades reimport
    
    Args:
        trades: List of trade dictionaries from Flex API
        source_file: Source identifier (e.g., "flex_api_last_year")
        
    Returns:
        Dict with detailed counts
    """
    if not trades:
        return {"fetched": 0, "skipped": 0, "inserted": 0, "errors": 0, "warnings": 0}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Stats
    fetched = len(trades)
    inserted = 0
    skipped_exists = 0  # original_transaction_id already exists
    skipped_count_match = 0  # similar trades count matches
    warnings = 0  # count mismatch (inserted additional)
    errors = 0
    warning_details = []
    skipped_exists_details = []  # Details of skipped by original_transaction_id
    skipped_count_match_details = []  # Details of skipped by count match
    inserted_symbols = set()  # Track symbols that were actually inserted
    
    logger.info(f"📊 Processing {fetched} trades from Flex API")
    
    # Group trades by signature (symbol + date + qty + price) to count duplicates in Flex
    from collections import defaultdict
    flex_trade_groups = defaultdict(list)
    
    for trade in trades:
        signature = (
            trade["symbol"],
            trade["trade_date"],
            trade["quantity"],
            round(trade["t_price"], 4)  # Use 4 decimals for better precision
        )
        flex_trade_groups[signature].append(trade)
    
    logger.info(f"   Unique trade signatures: {len(flex_trade_groups)}")
    
    # PHASE 1: Pre-calculate all DB counts and filter existing trades BEFORE any insertion
    # This prevents the bug where inserted trades are counted for subsequent groups
    groups_to_process = []
    
    for signature, group_trades in flex_trade_groups.items():
        symbol, trade_date, quantity, t_price = signature
        flex_count = len(group_trades)
        
        # Check which original_transaction_ids already exist
        trades_with_new_orig_id = []
        for trade in group_trades:
            original_id = trade.get("original_transaction_id", "")
            if original_id and check_original_transaction_exists(cursor, original_id):
                skipped_exists += 1
                if len(skipped_exists_details) < 20:
                    skipped_exists_details.append(f"{symbol} {trade_date} qty={quantity} price={t_price} orig_id={original_id}")
            else:
                trades_with_new_orig_id.append(trade)
        
        if not trades_with_new_orig_id:
            continue
        
        # Get DB counts for similar trades (BEFORE any insertion)
        db_total, db_with_orig_id = get_similar_trades_count(cursor, symbol, trade_date, quantity, t_price)
        
        # Store for phase 2
        groups_to_process.append({
            "signature": signature,
            "flex_count": flex_count,
            "trades_with_new_orig_id": trades_with_new_orig_id,
            "db_total": db_total
        })
    
    # PHASE 2: Insert trades based on pre-calculated counts
    for group in groups_to_process:
        signature = group["signature"]
        symbol, trade_date, quantity, t_price = signature
        flex_count = group["flex_count"]
        trades_with_new_orig_id = group["trades_with_new_orig_id"]
        db_total = group["db_total"]
        
        # Calculate how many we should have after import
        # flex_count = total trades from Flex for this signature
        # db_total = total similar trades in DB
        # skipped_exists for this group = flex_count - len(trades_with_new_orig_id)
        
        # The target is: we want exactly flex_count trades in DB for this signature
        # Currently we have: db_total
        # So we need to insert: max(0, flex_count - db_total)
        
        to_insert_count = max(0, flex_count - db_total)
        
        if to_insert_count == 0:
            # Already have enough in DB
            for trade in trades_with_new_orig_id:
                skipped_count_match += 1
                if len(skipped_count_match_details) < 20:  # Limit to first 20
                    orig_id = trade.get("original_transaction_id", "")
                    skipped_count_match_details.append(f"{symbol} {trade_date} qty={quantity} price={t_price} orig_id={orig_id} (DB has {db_total}, Flex has {flex_count})")
            continue
        
        # Log warning if we're adding to existing trades (potential mismatch)
        if db_total > 0 and to_insert_count > 0 and to_insert_count < len(trades_with_new_orig_id):
            warnings += 1
            warning_msg = f"{symbol} {trade_date} qty={quantity} price={t_price}: Flex={flex_count}, DB={db_total} → inserting {to_insert_count}"
            warning_details.append(warning_msg)
            logger.warning(f"⚠️  {warning_msg}")
        
        # Insert the required number of trades
        inserted_in_group = 0
        for trade in trades_with_new_orig_id:
            if inserted_in_group >= to_insert_count:
                skipped_count_match += 1
                if len(skipped_count_match_details) < 20:
                    orig_id = trade.get("original_transaction_id", "")
                    skipped_count_match_details.append(f"{symbol} {trade_date} qty={quantity} price={t_price} orig_id={orig_id} (DB has {db_total}, Flex has {flex_count})")
                continue
            
            # Generate new transaction_id
            try:
                transaction_id = get_next_transaction_id(cursor)
            except Exception as e:
                errors += 1
                logger.error(f"❌ {e}")
                continue
            
            # Insert the trade
            try:
                cursor.execute("""
                    INSERT INTO transactions (
                        transaction_id, original_transaction_id, source_file, 
                        asset_category, currency, symbol,
                        trade_date, trade_time, quantity, t_price, 
                        proceeds, comm_fee, basis,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transaction_id,
                    trade["original_transaction_id"],
                    source_file,
                    trade["asset_category"],
                    trade["currency"],
                    trade["symbol"],
                    trade["trade_date"],
                    trade["trade_time"],
                    trade["quantity"],
                    trade["t_price"],
                    trade["proceeds"],
                    trade["comm_fee"],
                    trade.get("basis", 0),
                    datetime.now().isoformat()
                ))
                inserted += 1
                inserted_in_group += 1
                inserted_symbols.add(trade["symbol"])
            except Exception as e:
                errors += 1
                logger.error(f"❌ Failed to insert {trade.get('symbol', '?')} {trade.get('trade_date', '?')}: {e}")
    
    conn.commit()
    conn.close()
    
    # Collect unique symbols from all trades
    unique_symbols = list(set([trade["symbol"] for trade in trades]))
    
    # Log summary
    total_skipped = skipped_exists + skipped_count_match
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("📊 FLEX IMPORT RESULTS")
    logger.info("=" * 60)
    logger.info(f"   Trades fetched from API:      {fetched}")
    logger.info(f"   ✅ Inserted (new trades):      {inserted}")
    logger.info(f"   ⏭️  Skipped (already exist):    {skipped_exists}")
    logger.info(f"   🔄 Skipped (count match):      {skipped_count_match}")
    logger.info(f"   ⚠️  Warnings (count mismatch):  {warnings}")
    logger.info(f"   ❌ Errors:                      {errors}")
    logger.info("=" * 60)
    
    if skipped_exists_details:
        logger.info("")
        logger.info("⏭️  Skipped (already exist) details:")
        for detail in skipped_exists_details[:10]:
            logger.info(f"   {detail}")
        if len(skipped_exists_details) > 10:
            logger.info(f"   ... and {len(skipped_exists_details) - 10} more")
    
    if skipped_count_match_details:
        logger.info("")
        logger.info("🔄 Skipped (count match) details:")
        for detail in skipped_count_match_details[:10]:
            logger.info(f"   {detail}")
        if len(skipped_count_match_details) > 10:
            logger.info(f"   ... and {len(skipped_count_match_details) - 10} more")
    
    if warning_details:
        logger.info("")
        logger.info("⚠️  Warning details:")
        for detail in warning_details[:10]:
            logger.info(f"   {detail}")
        if len(warning_details) > 10:
            logger.info(f"   ... and {len(warning_details) - 10} more warnings")
    
    return {
        "fetched": fetched,
        "inserted": inserted,
        "skipped": total_skipped,
        "skipped_exists": skipped_exists,
        "skipped_count_match": skipped_count_match,
        "warnings": warnings,
        "warning_details": warning_details[:10],
        "errors": errors,
        "symbols": unique_symbols,
        "inserted_symbols": list(inserted_symbols)
    }


def fetch_and_import_flex_trades(query_type: str = "last_year") -> dict:
    """
    Main function to fetch trades from IBKR Flex Query and import to DB.
    
    Args:
        query_type: "last_year" or "last_month"
        
    Returns:
        Dict with import results
    """
    # Get credentials from environment
    token = os.getenv("IBKR_FLEX_TOKEN")
    
    if query_type == "last_year":
        query_id = os.getenv("IBKR_QUERY_ID_last_year")
        source_file = "flex_api_last_year"
    elif query_type == "last_month":
        query_id = os.getenv("IBKR_QUERY_ID_last_month")
        source_file = "flex_api_last_month"
    else:
        logger.error(f"❌ Invalid query_type: {query_type}")
        return {"error": f"Invalid query_type: {query_type}"}
    
    # Validate credentials
    if not token:
        logger.error("❌ IBKR_FLEX_TOKEN not set in environment")
        return {"error": "IBKR_FLEX_TOKEN not set"}
    if not query_id:
        logger.error(f"❌ IBKR_QUERY_ID_{query_type} not set in environment")
        return {"error": f"IBKR_QUERY_ID_{query_type} not set"}
    
    logger.info(f"🚀 Starting Flex Query fetch ({query_type})")
    logger.info(f"   Token: {token[:4]}...{token[-4:] if len(token) > 8 else '****'}")
    logger.info(f"   Query ID: {query_id}")
    
    # Step 1: Request query execution
    reference_code = request_flex_query(token, query_id)
    if not reference_code:
        return {"error": "Failed to get reference code"}
    
    # Step 2: Wait a moment before fetching
    time.sleep(1)
    
    # Step 3: Fetch results
    xml_content = fetch_flex_results(token, reference_code)
    if not xml_content:
        return {"error": "Failed to fetch results"}
    
    # Step 4: Parse trades
    trades = parse_trades_from_xml(xml_content)
    
    # Step 5: Insert trades
    results = insert_flex_trades(trades, source_file)
    
    # Step 6: Parse and save positions
    positions = parse_positions_from_xml(xml_content)
    if positions:
        positions_results = save_positions_ibkr(positions)
        results["positions_imported"] = positions_results["positions_inserted"]
        results["positions_last_updated"] = positions_results["last_updated"]
    else:
        logger.info("ℹ️  No positions found in Flex Query response")
        results["positions_imported"] = 0
    
    return results


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🔄 IBKR Flex Query - Fetch and Import Trades")
    logger.info("=" * 60)
    
    # Fetch and import trades from last_year query
    results = fetch_and_import_flex_trades("last_year")
    
    if "error" in results:
        logger.error(f"❌ Error: {results['error']}")
    # Results are already logged in insert_flex_trades
