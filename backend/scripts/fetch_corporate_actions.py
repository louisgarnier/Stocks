#!/usr/bin/env python3
"""
Fetch Corporate Actions from yfinance for all securities in database.

This script fetches dividends, splits, and capital gains distributions
for all tickers starting from their first trade date.

Run: python backend/scripts/fetch_corporate_actions.py
"""

import yfinance as yf
import pandas as pd
import time
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "output" / "database" / "finance.db"
OUTPUT_DIR = PROJECT_ROOT / "output"


def get_securities_from_db() -> list[dict]:
    """
    Get all unique securities and their first trade date from the database.
    
    Returns:
        List of dicts with 'symbol' and 'first_trade_date'
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            symbol,
            MIN(trade_date) as first_trade_date,
            currency
        FROM transactions
        GROUP BY symbol
        ORDER BY symbol ASC
    """)
    
    securities = []
    for row in cursor.fetchall():
        securities.append({
            'symbol': row['symbol'],
            'first_trade_date': row['first_trade_date'],
            'currency': row['currency'] or 'USD'
        })
    
    conn.close()
    logger.info(f"📊 Found {len(securities)} securities in database")
    return securities


def fetch_corporate_actions_for_ticker(
    symbol: str,
    start_date: str,
    currency: str = "USD"
) -> list[dict]:
    """
    Fetch all corporate actions for a single ticker.
    
    Args:
        symbol: Ticker symbol
        start_date: Start date in YYYY-MM-DD format
        currency: Currency for the security
        
    Returns:
        List of corporate action dicts
    """
    actions = []
    start_dt = pd.Timestamp(start_date).tz_localize(None)  # Timezone-naive for comparison
    
    try:
        ticker = yf.Ticker(symbol)
        
        # 1. Fetch Dividends
        try:
            dividends = ticker.dividends
            if dividends is not None and len(dividends) > 0:
                for date, amount in dividends.items():
                    # Convert to timezone-naive for comparison
                    ex_date_ts = pd.Timestamp(date).tz_localize(None) if date.tzinfo else pd.Timestamp(date)
                    if ex_date_ts >= start_dt:
                        # Try to determine dividend type
                        dividend_type = "regular"  # Default assumption
                        
                        actions.append({
                            'sec_id': symbol,
                            'ca_type': 'dividend',
                            'ex_date': ex_date_ts.strftime("%Y-%m-%d"),
                            'record_date': None,
                            'pay_date': None,
                            'declared_date': None,
                            'amount': float(amount),
                            'currency': currency,
                            'split_ratio': None,
                            'split_from': None,
                            'split_to': None,
                            'dividend_type': dividend_type,
                            'frequency': None,
                            'adjusted': True,  # yfinance returns adjusted dividends by default
                            'source': 'yfinance',
                            'notes': None
                        })
        except Exception as e:
            logger.debug(f"   No dividends for {symbol}: {e}")
        
        # 2. Fetch Stock Splits
        try:
            splits = ticker.splits
            if splits is not None and len(splits) > 0:
                for date, ratio in splits.items():
                    # Convert to timezone-naive for comparison
                    ex_date_ts = pd.Timestamp(date).tz_localize(None) if date.tzinfo else pd.Timestamp(date)
                    if ex_date_ts >= start_dt and ratio != 0:
                        # Ratio is new/old (e.g., 4.0 means 4-for-1)
                        split_ratio = float(ratio)
                        
                        # Determine split_from and split_to
                        if split_ratio >= 1:
                            # Forward split (e.g., 4-for-1)
                            split_to = int(split_ratio) if split_ratio == int(split_ratio) else split_ratio
                            split_from = 1
                        else:
                            # Reverse split (e.g., 1-for-10 = 0.1)
                            split_from = int(1 / split_ratio) if (1 / split_ratio) == int(1 / split_ratio) else round(1 / split_ratio, 2)
                            split_to = 1
                        
                        actions.append({
                            'sec_id': symbol,
                            'ca_type': 'split',
                            'ex_date': ex_date_ts.strftime("%Y-%m-%d"),
                            'record_date': None,
                            'pay_date': None,
                            'declared_date': None,
                            'amount': None,
                            'currency': None,
                            'split_ratio': split_ratio,
                            'split_from': split_from,
                            'split_to': split_to,
                            'dividend_type': None,
                            'frequency': None,
                            'adjusted': True,
                            'source': 'yfinance',
                            'notes': f"{'Forward' if split_ratio >= 1 else 'Reverse'} split {split_to}:{split_from}"
                        })
        except Exception as e:
            logger.debug(f"   No splits for {symbol}: {e}")
        
        # 3. Fetch Capital Gains (for ETFs/Mutual Funds)
        try:
            capital_gains = ticker.capital_gains
            if capital_gains is not None and len(capital_gains) > 0:
                for date, amount in capital_gains.items():
                    # Convert to timezone-naive for comparison
                    ex_date_ts = pd.Timestamp(date).tz_localize(None) if date.tzinfo else pd.Timestamp(date)
                    if ex_date_ts >= start_dt:
                        actions.append({
                            'sec_id': symbol,
                            'ca_type': 'capital_gain',
                            'ex_date': ex_date_ts.strftime("%Y-%m-%d"),
                            'record_date': None,
                            'pay_date': None,
                            'declared_date': None,
                            'amount': float(amount),
                            'currency': currency,
                            'split_ratio': None,
                            'split_from': None,
                            'split_to': None,
                            'dividend_type': 'capital_gain',
                            'frequency': None,
                            'adjusted': True,
                            'source': 'yfinance',
                            'notes': None
                        })
        except Exception as e:
            logger.debug(f"   No capital gains for {symbol}: {e}")
        
        # 4. Try to get additional actions from get_actions() (combined dividends + splits)
        try:
            all_actions = ticker.actions
            if all_actions is not None and len(all_actions) > 0:
                # This is a fallback - actions already fetched above should be primary
                pass  # Already covered by dividends and splits above
        except Exception as e:
            logger.debug(f"   get_actions() not available for {symbol}: {e}")
        
        # 5. Note: Spinoffs, M&A, Rights Issues, Symbol Changes are NOT available in yfinance
        # Add a note action if we found nothing and these might exist
        if len(actions) == 0:
            # Check ticker info for any hints
            try:
                info = ticker.info
                if info:
                    # Check if there are any corporate action hints in the info
                    pass
            except:
                pass
        
    except Exception as e:
        logger.warning(f"⚠️  Error fetching {symbol}: {e}")
        # Add an error note
        actions.append({
            'sec_id': symbol,
            'ca_type': 'error',
            'ex_date': None,
            'record_date': None,
            'pay_date': None,
            'declared_date': None,
            'amount': None,
            'currency': None,
            'split_ratio': None,
            'split_from': None,
            'split_to': None,
            'dividend_type': None,
            'frequency': None,
            'adjusted': None,
            'source': 'yfinance',
            'notes': f"Error: {str(e)}"
        })
    
    return actions


def fetch_all_corporate_actions(
    securities: list[dict],
    global_start_date: Optional[str] = None
) -> pd.DataFrame:
    """
    Fetch corporate actions for all securities.
    
    Args:
        securities: List of dicts with 'symbol', 'first_trade_date', 'currency'
        global_start_date: Optional override for start date (uses first_trade_date if None)
        
    Returns:
        DataFrame with all corporate actions
    """
    all_actions = []
    total = len(securities)
    
    # Track unsupported CA types
    unsupported_note = {
        'sec_id': 'N/A',
        'ca_type': 'info',
        'ex_date': None,
        'record_date': None,
        'pay_date': None,
        'declared_date': None,
        'amount': None,
        'currency': None,
        'split_ratio': None,
        'split_from': None,
        'split_to': None,
        'dividend_type': None,
        'frequency': None,
        'adjusted': None,
        'source': 'yfinance',
        'notes': 'Spinoffs, M&A, Rights Issues, Symbol Changes are NOT available via yfinance API'
    }
    all_actions.append(unsupported_note)
    
    for i, security in enumerate(securities, 1):
        symbol = security['symbol']
        start_date = global_start_date or security['first_trade_date']
        currency = security['currency']
        
        logger.info(f"[{i}/{total}] Fetching {symbol} (from {start_date})...")
        
        actions = fetch_corporate_actions_for_ticker(symbol, start_date, currency)
        all_actions.extend(actions)
        
        # Rate limiting - be nice to Yahoo Finance
        if i < total:
            time.sleep(0.5)
    
    # Create DataFrame
    df = pd.DataFrame(all_actions)
    
    # Filter out info/error rows for sorting, then add back
    data_rows = df[~df['ca_type'].isin(['info', 'error'])]
    meta_rows = df[df['ca_type'].isin(['info', 'error'])]
    
    # Sort by sec_id and ex_date
    if len(data_rows) > 0:
        data_rows = data_rows.sort_values(['sec_id', 'ex_date'], ascending=[True, True])
    
    # Combine back
    df = pd.concat([data_rows, meta_rows], ignore_index=True)
    
    return df


def extract_split_direction(notes: str) -> Optional[str]:
    """Extract split direction (forward/reverse) from notes."""
    if notes:
        notes_lower = notes.lower()
        if 'forward' in notes_lower:
            return 'forward'
        elif 'reverse' in notes_lower:
            return 'reverse'
    return None


def insert_corporate_actions_to_db(df: pd.DataFrame) -> dict:
    """
    Insert corporate actions into the database.
    
    Returns:
        Dict with parsed, inserted, skipped, errors counts
    """
    # Filter out info/error rows
    data_df = df[~df['ca_type'].isin(['info', 'error'])].copy()
    parsed = len(data_df)
    
    if parsed == 0:
        return {'parsed': 0, 'inserted': 0, 'skipped': 0, 'errors': 0, 'skipped_details': []}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    errors = 0
    skipped_details = []
    inserted_details = []
    
    for _, row in data_df.iterrows():
        try:
            # Extract split direction from notes
            split_direction = extract_split_direction(row.get('notes'))
            
            # Check for existing record (unique constraint: sec_id, ca_type, ex_date)
            cursor.execute("""
                SELECT id FROM corporate_actions 
                WHERE sec_id = ? AND ca_type = ? AND ex_date = ?
            """, (row['sec_id'], row['ca_type'], row['ex_date']))
            
            if cursor.fetchone():
                skipped += 1
                if len(skipped_details) < 10:
                    skipped_details.append(f"{row['sec_id']} {row['ca_type']} {row['ex_date']}")
                continue
            
            # Insert new record
            cursor.execute("""
                INSERT INTO corporate_actions (
                    sec_id, ca_type, ex_date, record_date, pay_date, declared_date,
                    amount, currency, split_ratio, split_from, split_to, split_direction,
                    dividend_type, frequency, adjusted, source, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['sec_id'],
                row['ca_type'],
                row['ex_date'],
                row.get('record_date'),
                row.get('pay_date'),
                row.get('declared_date'),
                row.get('amount'),
                row.get('currency'),
                row.get('split_ratio'),
                row.get('split_from'),
                row.get('split_to'),
                split_direction,
                row.get('dividend_type'),
                row.get('frequency'),
                1 if row.get('adjusted') else 0,
                row.get('source', 'yfinance'),
                row.get('notes')
            ))
            inserted += 1
            if len(inserted_details) < 10:
                inserted_details.append(f"{row['sec_id']} {row['ca_type']} {row['ex_date']}")
            
        except Exception as e:
            logger.error(f"❌ Error inserting CA for {row['sec_id']}: {e}")
            errors += 1
    
    conn.commit()
    conn.close()
    
    # Log summary
    logger.info("=" * 60)
    logger.info("💾 DATABASE IMPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"   📥 Parsed from yfinance:    {parsed}")
    logger.info(f"   ✅ Inserted (new):          {inserted}")
    logger.info(f"   ⏭️  Skipped (already exist): {skipped}")
    logger.info(f"   ❌ Errors:                  {errors}")
    
    if inserted_details:
        logger.info("")
        logger.info("✅ Inserted details:")
        for detail in inserted_details:
            logger.info(f"   + {detail}")
        if inserted > 10:
            logger.info(f"   ... and {inserted - 10} more")
    
    if skipped_details:
        logger.info("")
        logger.info("⏭️  Skipped details (already in DB):")
        for detail in skipped_details:
            logger.info(f"   - {detail}")
        if skipped > 10:
            logger.info(f"   ... and {skipped - 10} more")
    
    logger.info("=" * 60)
    
    return {'parsed': parsed, 'inserted': inserted, 'skipped': skipped, 'errors': errors, 'skipped_details': skipped_details}


def print_summary(df: pd.DataFrame):
    """Print a summary of corporate actions found."""
    print("\n" + "=" * 70)
    print("📊 CORPORATE ACTIONS SUMMARY")
    print("=" * 70)
    
    # Filter out info/error rows
    data_df = df[~df['ca_type'].isin(['info', 'error'])]
    
    if len(data_df) == 0:
        print("\n❌ No corporate actions found for any security.")
        return
    
    # Summary by CA type
    print("\n📈 By Corporate Action Type:")
    ca_summary = data_df.groupby('ca_type').size()
    for ca_type, count in ca_summary.items():
        print(f"   {ca_type:<20} {count:>5}")
    
    print(f"\n   {'TOTAL':<20} {len(data_df):>5}")
    
    # Summary by ticker
    print("\n📊 By Security:")
    ticker_summary = data_df.groupby(['sec_id', 'ca_type']).size().unstack(fill_value=0)
    
    # Print header
    ca_types = list(ticker_summary.columns)
    header = f"   {'Symbol':<10}"
    for ct in ca_types:
        header += f" {ct:>12}"
    header += f" {'Total':>8}"
    print(header)
    print("   " + "-" * (len(header) - 3))
    
    # Print each ticker
    for symbol in ticker_summary.index:
        row = f"   {symbol:<10}"
        total = 0
        for ct in ca_types:
            count = ticker_summary.loc[symbol, ct]
            row += f" {count:>12}"
            total += count
        row += f" {total:>8}"
        print(row)
    
    # Tickers with no CAs
    all_symbols = set(df['sec_id'].unique())
    symbols_with_ca = set(data_df['sec_id'].unique())
    no_ca_symbols = all_symbols - symbols_with_ca - {'N/A'}
    
    if no_ca_symbols:
        print(f"\n⚠️  Securities with NO corporate actions found: {len(no_ca_symbols)}")
        print(f"   {', '.join(sorted(no_ca_symbols))}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("🏢 CORPORATE ACTIONS FETCHER (yfinance)")
    print("=" * 70)
    
    # Get securities from database
    if not DB_PATH.exists():
        logger.error(f"❌ Database not found: {DB_PATH}")
        return
    
    securities = get_securities_from_db()
    
    if not securities:
        logger.error("❌ No securities found in database")
        return
    
    # Get earliest date across all securities
    earliest_date = min(s['first_trade_date'] for s in securities)
    print(f"\n📅 Earliest trade date in DB: {earliest_date}")
    print(f"📊 Securities to process: {len(securities)}")
    print()
    
    # Fetch all corporate actions
    df = fetch_all_corporate_actions(securities)
    
    # Print summary
    print_summary(df)
    
    # Insert into database
    print("\n" + "=" * 70)
    print("💾 INSERTING INTO DATABASE")
    print("=" * 70)
    
    result = insert_corporate_actions_to_db(df)
    
    print(f"\n   ✅ Inserted: {result['inserted']}")
    print(f"   ⏭️  Skipped (already exist): {result['skipped']}")
    print(f"   ❌ Errors: {result['errors']}")
    
    # Export to CSV
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    csv_path = OUTPUT_DIR / f"corporate_actions_{today}.csv"
    df.to_csv(csv_path, index=False)
    
    print(f"\n💾 Also exported to: {csv_path}")
    
    print("\n" + "=" * 70)
    print("✅ Done!")
    print("=" * 70)
    
    return {'df': df, 'db_result': result}


def fetch_and_import_corporate_actions(incremental: bool = False) -> dict:
    """
    Fetch corporate actions from yfinance and insert into database.
    Called from API endpoint.
    
    Args:
        incremental: If True, only fetch symbols that need updating (orange status, >24h, >7d)
                    If False, fetch all symbols (full refresh)
    
    Returns:
        Dict with parsed, inserted, skipped, errors counts
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    
    securities = get_securities_from_db()
    
    if not securities:
        raise ValueError("No securities found in database")
    
    # Filter securities if incremental mode
    if incremental:
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get CA status for all symbols
        cursor.execute("SELECT sec_id, status, last_fetched_at FROM corporate_actions_status")
        status_map = {row[0]: {'status': row[1], 'last_fetched': row[2]} for row in cursor.fetchall()}
        conn.close()
        
        filtered_securities = []
        now = datetime.now()
        
        for sec in securities:
            symbol = sec['symbol']
            status_info = status_map.get(symbol, {})
            status = status_info.get('status')
            last_fetched = status_info.get('last_fetched')
            
            # Always fetch if orange (new transactions)
            if status == 'orange':
                filtered_securities.append(sec)
                continue
            
            # Fetch if green and >24h
            if status == 'green' and last_fetched:
                last_fetch_dt = datetime.fromisoformat(last_fetched)
                if (now - last_fetch_dt) > timedelta(hours=24):
                    filtered_securities.append(sec)
                    continue
            
            # Fetch if grey and >7 days
            if status == 'grey' and last_fetched:
                last_fetch_dt = datetime.fromisoformat(last_fetched)
                if (now - last_fetch_dt) > timedelta(days=7):
                    filtered_securities.append(sec)
                    continue
            
            # Fetch if never fetched
            if not last_fetched:
                filtered_securities.append(sec)
        
        logger.info(f"⚡ Incremental mode: fetching {len(filtered_securities)}/{len(securities)} symbols")
        securities = filtered_securities
        
        if not securities:
            logger.info("✅ All symbols are up to date, nothing to fetch")
            return {
                'parsed': 0,
                'inserted': 0,
                'skipped': 0,
                'errors': 0,
                'updated_transactions': 0
            }
    
    # Fetch all corporate actions
    df = fetch_all_corporate_actions(securities)
    
    # Insert into database
    db_result = insert_corporate_actions_to_db(df)
    
    # Update CA status for each symbol
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.ca_status import set_ca_status
        
        # Filter out info/error rows
        data_df = df[~df['ca_type'].isin(['info', 'error'])]
        
        # Group by symbol to determine status
        symbols_with_ca = set(data_df['sec_id'].unique()) if len(data_df) > 0 else set()
        all_symbols = [sec['symbol'] for sec in securities]
        
        # Set green for symbols with CA
        if symbols_with_ca:
            set_ca_status(list(symbols_with_ca), 'green')
            logger.info(f"✅ Set CA status to 'green' for {len(symbols_with_ca)} symbols")
        
        # Set grey for symbols without CA
        symbols_without_ca = set(all_symbols) - symbols_with_ca
        if symbols_without_ca:
            set_ca_status(list(symbols_without_ca), 'grey')
            logger.info(f"⚪ Set CA status to 'grey' for {len(symbols_without_ca)} symbols")
    except Exception as e:
        logger.warning(f"⚠️  Failed to update CA status: {e}")
    
    return {
        'parsed': db_result['parsed'],
        'inserted': db_result['inserted'],
        'skipped': db_result['skipped'],
        'errors': db_result['errors']
    }


if __name__ == "__main__":
    main()
