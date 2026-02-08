"""
IBKR Flex Web Service API Fetcher

Fetches transaction data from IBKR using the Flex Web Service API.
Two-step process: SendRequest -> GetStatement

Based on: docs/project/requirements/RAW_REQUIREMENTS.md
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

from backend.api.utils.logger import flex_logger as logger, log_event

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env")

# Configuration
FLEX_BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
TOKEN = os.getenv("IBKR_FLEX_TOKEN")
QUERY_ID = os.getenv("IBKR_QUERY_ID")
OUTPUT_DIR = PROJECT_ROOT / "input" / "daily_trades"
WAIT_TIME = 20  # seconds to wait between SendRequest and GetStatement


class FlexFetchError(Exception):
    """Custom exception for Flex API errors."""
    pass


def send_request(query_id: str) -> str:
    """
    Step 1: Request report generation from IBKR.
    
    Args:
        query_id: The Flex Query ID to use
    
    Returns:
        str: Reference code for retrieving the report
        
    Raises:
        FlexFetchError: If the request fails
    """
    logger.info(f"📡 Sending request to IBKR Flex Web Service (Query: {query_id})...")
    
    if not TOKEN or not query_id:
        raise FlexFetchError("Missing IBKR_FLEX_TOKEN or Query ID")
    
    try:
        response = requests.get(
            f"{FLEX_BASE_URL}/SendRequest",
            params={"t": TOKEN, "q": query_id, "v": 3},
            headers={"User-Agent": "Python/IBKR-Portfolio-Tracker"},
            timeout=30
        )
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.text)
        status = root.find("Status")
        
        if status is None or status.text != "Success":
            error_msg = root.find("ErrorMessage")
            error_text = error_msg.text if error_msg is not None else "Unknown error"
            raise FlexFetchError(f"SendRequest failed: {error_text}")
        
        ref_code = root.find("ReferenceCode")
        if ref_code is None:
            raise FlexFetchError("No ReferenceCode in response")
        
        logger.info(f"✅ Got reference code: {ref_code.text}")
        return ref_code.text
        
    except requests.RequestException as e:
        raise FlexFetchError(f"HTTP error during SendRequest: {e}")
    except ET.ParseError as e:
        raise FlexFetchError(f"Failed to parse XML response: {e}")


def get_statement(ref_code: str) -> bytes:
    """
    Step 2: Retrieve the generated report.
    
    Args:
        ref_code: Reference code from SendRequest
        
    Returns:
        bytes: Raw report data (CSV or XML)
        
    Raises:
        FlexFetchError: If retrieval fails
    """
    logger.info(f"📥 Retrieving statement with reference code: {ref_code}")
    
    try:
        response = requests.get(
            f"{FLEX_BASE_URL}/GetStatement",
            params={"t": TOKEN, "q": ref_code, "v": 3},
            headers={"User-Agent": "Python/IBKR-Portfolio-Tracker"},
            timeout=60
        )
        response.raise_for_status()
        
        # Check if response is an error XML
        if response.text.startswith("<?xml") or response.text.startswith("<"):
            try:
                root = ET.fromstring(response.text)
                status = root.find("Status")
                if status is not None and status.text != "Success":
                    error_msg = root.find("ErrorMessage")
                    error_text = error_msg.text if error_msg is not None else "Unknown error"
                    raise FlexFetchError(f"GetStatement failed: {error_text}")
            except ET.ParseError:
                pass  # Not XML, probably CSV data
        
        logger.info(f"✅ Retrieved {len(response.content)} bytes of data")
        return response.content
        
    except requests.RequestException as e:
        raise FlexFetchError(f"HTTP error during GetStatement: {e}")


def save_report(data: bytes) -> Path:
    """
    Save the report to the output directory.
    
    Args:
        data: Raw report data
        
    Returns:
        Path: Path to saved file
    """
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Detect format (CSV or XML)
    if data.startswith(b"<?xml") or data.startswith(b"<"):
        extension = "xml"
    else:
        extension = "csv"
    
    filename = f"flex_report_{timestamp}.{extension}"
    filepath = OUTPUT_DIR / filename
    
    with open(filepath, "wb") as f:
        f.write(data)
    
    logger.info(f"💾 Saved report to: {filepath}")
    return filepath


def count_records(data: bytes) -> int:
    """
    Count the number of records in the report.
    
    Args:
        data: Raw report data
        
    Returns:
        int: Number of records (approximate)
    """
    try:
        text = data.decode("utf-8")
        # Count Trade elements in XML
        return text.count("<Trade ")
    except:
        return 0


def parse_and_insert_xml(filepath: Path) -> dict:
    """
    Parse XML Flex report and insert trades into database.
    
    Args:
        filepath: Path to the XML file
        
    Returns:
        dict with inserted and skipped counts
    """
    from backend.database.connection import get_db_connection
    
    logger.info(f"📂 Parsing XML file: {filepath.name}")
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"❌ Failed to parse XML: {e}")
        return {"inserted": 0, "skipped": 0, "error": str(e)}
    
    # Find all Trade elements
    trades = root.findall(".//Trade")
    
    if not trades:
        logger.warning("⚠️ No trades found in XML")
        return {"inserted": 0, "skipped": 0}
    
    logger.info(f"📊 Found {len(trades)} trades in XML")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for trade in trades:
        # Extract attributes
        transaction_id = trade.get("transactionID", "")
        symbol = trade.get("symbol", "")
        trade_date_raw = trade.get("tradeDate", "")
        quantity = float(trade.get("quantity", 0))
        t_price = float(trade.get("tradePrice", 0))
        proceeds = float(trade.get("proceeds", 0))
        comm_fee = float(trade.get("ibCommission", 0))
        
        # Format date (YYYYMMDD -> YYYY-MM-DD)
        if len(trade_date_raw) == 8:
            trade_date = f"{trade_date_raw[:4]}-{trade_date_raw[4:6]}-{trade_date_raw[6:8]}"
        else:
            trade_date = trade_date_raw
        
        # Check for duplicate
        cursor.execute(
            "SELECT id FROM transactions WHERE transaction_id = ?",
            (transaction_id,)
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
            transaction_id,
            symbol,
            trade_date,
            quantity,
            abs(t_price),
            proceeds,
            comm_fee,
            datetime.now().isoformat()
        ))
        inserted += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"📊 Inserted: {inserted}, Skipped (duplicates): {skipped}")
    
    return {"inserted": inserted, "skipped": skipped}


def fetch_flex_report() -> dict:
    """
    Main function to fetch a Flex report from IBKR.
    Uses the configured query (365 days) and skips duplicates automatically.
    
    Returns:
        dict: Result with success status, message, file path, and record count
    """
    logger.info("🚀 Starting Flex report fetch...")
    
    if not QUERY_ID:
        return {
            "success": False,
            "message": "Missing IBKR_QUERY_ID in environment",
            "file": None,
            "records": 0
        }
    
    query_id = QUERY_ID
    
    try:
        # Step 1: Send request
        ref_code = send_request(query_id)
        
        # Wait for report generation
        logger.info(f"⏳ Waiting {WAIT_TIME} seconds for report generation...")
        time.sleep(WAIT_TIME)
        
        # Step 2: Get statement
        data = get_statement(ref_code)
        
        # Save report
        filepath = save_report(data)
        
        # Count records in XML
        record_count = count_records(data)
        
        # Parse XML and insert into database
        parse_result = parse_and_insert_xml(filepath)
        inserted = parse_result.get("inserted", 0)
        skipped = parse_result.get("skipped", 0)
        
        log_event("FETCHED", "FlexReport", details={
            "file": str(filepath),
            "records": record_count,
            "inserted": inserted,
            "skipped": skipped
        })
        
        logger.info(f"✅ Flex fetch complete: {inserted} new, {skipped} duplicates")
        
        return {
            "success": True,
            "message": f"Fetched {record_count} trades, inserted {inserted} new",
            "file": str(filepath),
            "records": inserted
        }
        
    except FlexFetchError as e:
        logger.error(f"❌ Flex fetch failed: {e}")
        return {
            "success": False,
            "message": str(e),
            "file": None,
            "records": 0
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return {
            "success": False,
            "message": f"Unexpected error: {e}",
            "file": None,
            "records": 0
        }


if __name__ == "__main__":
    result = fetch_flex_report()
    print(f"\nResult: {result}")
    sys.exit(0 if result["success"] else 1)
