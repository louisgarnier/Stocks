"""
Test Script - Transactions Sync Check

Tests backend endpoints and displays results for debugging frontend/backend sync issues.
Run this script to verify transaction counts match between database and API endpoints.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

def test_database():
    """Test 1: Direct database query"""
    print("\n" + "="*70)
    print("🔍 TEST 1: Direct Database Query")
    print("="*70)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Count
    cursor.execute("SELECT COUNT(*) FROM transactions")
    count = cursor.fetchone()[0]
    print(f"✅ COUNT(*) FROM transactions: {count}")
    
    # Get all
    cursor.execute("SELECT id, transaction_id, symbol, trade_date, trade_time FROM transactions ORDER BY id")
    rows = cursor.fetchall()
    print(f"✅ SELECT all transactions: {len(rows)} rows")
    
    print(f"\n📋 All transactions in database:")
    for i, row in enumerate(rows, 1):
        trade_time = row["trade_time"] if row["trade_time"] else "(empty)"
        print(f"  {i}. ID:{row['id']} | {row['transaction_id']} | {row['symbol']} | {row['trade_date']} | time:{trade_time}")
    
    conn.close()
    return count, len(rows)


def test_api_query():
    """Test 2: Simulate API query"""
    print("\n" + "="*70)
    print("🔍 TEST 2: API Query Simulation")
    print("="*70)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Simulate the exact query from list_transactions endpoint
    sql = """
        SELECT id, transaction_id, symbol, trade_date, trade_time, quantity, t_price, proceeds, comm_fee, currency
        FROM transactions
        ORDER BY trade_date DESC
        LIMIT 25 OFFSET 0
    """
    
    cursor.execute(sql)
    rows = cursor.fetchall()
    
    print(f"✅ API query returned: {len(rows)} rows")
    
    if rows:
        print(f"\n📋 API query results:")
        for i, row in enumerate(rows, 1):
            trade_time = row["trade_time"] if row["trade_time"] else "(empty)"
            print(f"  {i}. ID:{row['id']} | {row['transaction_id']} | {row['symbol']} | {row['trade_date']} | time:{trade_time}")
    else:
        print("   ⚠️  No rows returned!")
    
    # Test row access
    if rows:
        print(f"\n🔍 Testing row access:")
        row = rows[0]
        try:
            print(f"   row['id']: {row['id']}")
            print(f"   row['symbol']: {row['symbol']}")
            print(f"   row['trade_time']: '{row['trade_time']}' (None: {row['trade_time'] is None})")
        except Exception as e:
            print(f"   ❌ Error accessing row: {e}")
    
    conn.close()
    return len(rows)


def test_health_query():
    """Test 3: Health endpoint query"""
    print("\n" + "="*70)
    print("🔍 TEST 3: Health Endpoint Query")
    print("="*70)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM transactions")
    count = cursor.fetchone()[0]
    
    print(f"✅ Health endpoint would return: {count} transactions")
    
    conn.close()
    return count


def main():
    print("\n" + "="*70)
    print("🧪 TRANSACTIONS SYNC TEST")
    print("="*70)
    print("\nThis script tests:")
    print("  1. Direct database queries")
    print("  2. API endpoint query simulation")
    print("  3. Health endpoint query simulation")
    print("\nExpected: All should return the same count!")
    
    db_count, db_rows = test_database()
    api_rows = test_api_query()
    health_count = test_health_query()
    
    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    print(f"Database COUNT(*):        {db_count}")
    print(f"Database SELECT all:      {db_rows}")
    print(f"API query rows:           {api_rows}")
    print(f"Health endpoint count:    {health_count}")
    
    # Consistency check
    print("\n" + "="*70)
    print("✅ CONSISTENCY CHECK")
    print("="*70)
    
    all_match = True
    if db_count != db_rows:
        print(f"❌ Database COUNT vs SELECT: {db_count} != {db_rows}")
        all_match = False
    else:
        print(f"✅ Database COUNT = SELECT: {db_count}")
    
    if health_count != db_count:
        print(f"❌ Health vs Database: {health_count} != {db_count}")
        all_match = False
    else:
        print(f"✅ Health = Database: {health_count}")
    
    if api_rows != min(db_count, 25):
        print(f"❌ API query vs Database: {api_rows} != {min(db_count, 25)}")
        all_match = False
    else:
        print(f"✅ API query = Database (limited to 25): {api_rows}")
    
    if all_match:
        print("\n✅ ALL TESTS PASSED - Backend is consistent!")
        print("\n💡 If frontend shows different count, check:")
        print("   1. Browser console for API errors")
        print("   2. Network tab for API responses")
        print("   3. React state in DevTools")
    else:
        print("\n❌ INCONSISTENCIES FOUND - Backend has issues!")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
