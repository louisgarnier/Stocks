#!/usr/bin/env python3
"""
Test script to compare Frontend (API) vs Backend (Database) data.

Verifies that the API returns consistent data with what's in the database.

Run: python backend/tests/test_frontend_backend_sync.py
"""

import requests
import sqlite3
import sys
from pathlib import Path

API_BASE_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "output" / "database" / "finance.db"


def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def compare_securities():
    """Compare securities from API vs Database."""
    print("\n" + "=" * 70)
    print("📊 SECURITIES COMPARISON (API vs Database)")
    print("=" * 70)
    
    # Get from API
    try:
        response = requests.get(f"{API_BASE_URL}/api/transactions/securities")
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return False
        api_data = response.json()
        api_securities = {s['symbol']: s for s in api_data.get('data', [])}
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False
    
    # Get from Database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as transaction_count,
            SUM(quantity) as total_quantity,
            MIN(trade_date) as first_trade,
            MAX(trade_date) as last_trade
        FROM transactions
        GROUP BY symbol
        ORDER BY symbol ASC
    """)
    db_securities = {row['symbol']: dict(row) for row in cursor.fetchall()}
    conn.close()
    
    print(f"\n📡 API:      {len(api_securities)} securities")
    print(f"💾 Database: {len(db_securities)} securities")
    
    # Compare counts
    if len(api_securities) != len(db_securities):
        print(f"\n❌ MISMATCH: Count differs!")
    else:
        print(f"\n✅ Count matches: {len(api_securities)} securities")
    
    # Check for missing securities
    api_symbols = set(api_securities.keys())
    db_symbols = set(db_securities.keys())
    
    only_in_api = api_symbols - db_symbols
    only_in_db = db_symbols - api_symbols
    
    if only_in_api:
        print(f"\n⚠️  Securities only in API: {only_in_api}")
    if only_in_db:
        print(f"\n⚠️  Securities only in DB: {only_in_db}")
    
    # Compare values
    mismatches = []
    for symbol in api_symbols & db_symbols:
        api_sec = api_securities[symbol]
        db_sec = db_securities[symbol]
        
        api_qty = api_sec.get('total_quantity', 0) or 0
        db_qty = db_sec.get('total_quantity', 0) or 0
        api_count = api_sec.get('transaction_count', 0)
        db_count = db_sec.get('transaction_count', 0)
        
        if abs(api_qty - db_qty) > 0.001 or api_count != db_count:
            mismatches.append({
                'symbol': symbol,
                'api_qty': api_qty,
                'db_qty': db_qty,
                'api_count': api_count,
                'db_count': db_count
            })
    
    if mismatches:
        print(f"\n❌ {len(mismatches)} securities with data mismatches:")
        for m in mismatches[:10]:
            print(f"   {m['symbol']}: API qty={m['api_qty']:.2f} vs DB qty={m['db_qty']:.2f}, "
                  f"API count={m['api_count']} vs DB count={m['db_count']}")
        return False
    else:
        print(f"\n✅ All securities data matches!")
    
    return True


def compare_transactions():
    """Compare transactions count from API vs Database."""
    print("\n" + "=" * 70)
    print("📄 TRANSACTIONS COMPARISON (API vs Database)")
    print("=" * 70)
    
    # Get from API
    try:
        response = requests.get(f"{API_BASE_URL}/api/transactions?page=1&limit=1")
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return False
        api_data = response.json()
        api_total = api_data.get('total', 0)
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False
    
    # Get from Database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM transactions")
    db_total = cursor.fetchone()['count']
    conn.close()
    
    print(f"\n📡 API:      {api_total} transactions")
    print(f"💾 Database: {db_total} transactions")
    
    if api_total != db_total:
        print(f"\n❌ MISMATCH: Transaction count differs by {abs(api_total - db_total)}!")
        return False
    else:
        print(f"\n✅ Transaction count matches: {api_total}")
    
    return True


def compare_health():
    """Compare health endpoint with database."""
    print("\n" + "=" * 70)
    print("🏥 HEALTH CHECK (API vs Database)")
    print("=" * 70)
    
    # Get from API
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return False
        health = response.json()
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False
    
    # Get from Database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM transactions")
    db_tx_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(DISTINCT symbol) as count FROM transactions")
    db_symbol_count = cursor.fetchone()['count']
    conn.close()
    
    api_tx_count = health.get('transactions', 0)
    api_positions = health.get('positions', 0)
    
    print(f"\n📡 API Health:")
    print(f"   - Status: {health.get('status')}")
    print(f"   - Database: {health.get('database')}")
    print(f"   - Transactions: {api_tx_count}")
    print(f"   - Positions: {api_positions}")
    
    print(f"\n💾 Database:")
    print(f"   - Transactions: {db_tx_count}")
    print(f"   - Unique symbols: {db_symbol_count}")
    
    issues = []
    if api_tx_count != db_tx_count:
        issues.append(f"Transactions: API={api_tx_count} vs DB={db_tx_count}")
    
    if issues:
        print(f"\n⚠️  Issues found:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print(f"\n✅ Health data consistent with database")
    
    return True


def main():
    """Main entry point."""
    print("=" * 70)
    print("🔍 FRONTEND vs BACKEND SYNC TEST")
    print("=" * 70)
    print(f"\n📁 Database: {DB_PATH}")
    print(f"🌐 API:      {API_BASE_URL}")
    
    if not DB_PATH.exists():
        print(f"\n❌ Database file not found: {DB_PATH}")
        sys.exit(1)
    
    results = []
    
    results.append(("Health Check", compare_health()))
    results.append(("Transactions", compare_transactions()))
    results.append(("Securities", compare_securities()))
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} - {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Frontend and Backend are in sync!")
    else:
        print("❌ SOME TESTS FAILED - Check the details above")
    print("=" * 70)
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
