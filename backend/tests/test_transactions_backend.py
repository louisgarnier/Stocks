"""
Backend Test - Transactions Count and Listing

Tests the backend API endpoints to verify transaction counts and listings.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.routes.transactions import list_transactions
from fastapi.testclient import TestClient
from backend.api.main import app

def test_database_count():
    """Test: Count transactions directly from database."""
    print("\n" + "="*60)
    print("🔍 TEST 1: Database Direct Count")
    print("="*60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM transactions")
    count = cursor.fetchone()[0]
    
    print(f"✅ Database COUNT(*): {count}")
    
    # Get all transaction IDs
    cursor.execute("SELECT transaction_id, symbol, trade_date FROM transactions ORDER BY id")
    rows = cursor.fetchall()
    
    print(f"✅ Database SELECT all: {len(rows)} rows")
    print(f"\n📋 Transactions in database:")
    for i, row in enumerate(rows, 1):
        print(f"  {i}. {row[0]} | {row[1]} | {row[2]}")
    
    conn.close()
    return count, len(rows)


def test_health_endpoint():
    """Test: Health endpoint transaction count."""
    print("\n" + "="*60)
    print("🔍 TEST 2: Health Endpoint")
    print("="*60)
    
    client = TestClient(app)
    response = client.get("/health")
    
    if response.status_code == 200:
        data = response.json()
        count = data.get("transactions", 0)
        print(f"✅ Health endpoint returned: {count} transactions")
        print(f"   Full response: {data}")
        return count
    else:
        print(f"❌ Health endpoint failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None


def test_list_transactions_endpoint():
    """Test: List transactions endpoint."""
    print("\n" + "="*60)
    print("🔍 TEST 3: List Transactions Endpoint")
    print("="*60)
    
    client = TestClient(app)
    response = client.get("/api/transactions?page=1&limit=25")
    
    if response.status_code == 200:
        data = response.json()
        total = data.get("total", 0)
        data_list = data.get("data", [])
        
        print(f"✅ List endpoint returned:")
        print(f"   Total: {total}")
        print(f"   Data array length: {len(data_list)}")
        print(f"   Page: {data.get('page', 'N/A')}")
        print(f"   Pages: {data.get('pages', 'N/A')}")
        
        if data_list:
            print(f"\n📋 First {min(5, len(data_list))} transactions:")
            for i, tx in enumerate(data_list[:5], 1):
                print(f"  {i}. ID: {tx.get('id')}, transaction_id: {tx.get('transaction_id')}, symbol: {tx.get('symbol')}")
        else:
            print("   ⚠️  No transactions in data array!")
        
        return total, len(data_list)
    else:
        print(f"❌ List endpoint failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None, None


def test_query_structure():
    """Test: Verify the SQL query structure."""
    print("\n" + "="*60)
    print("🔍 TEST 4: SQL Query Structure")
    print("="*60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Test the exact query used by the API
    sql = """
        SELECT id, transaction_id, symbol, trade_date, trade_time, quantity, t_price, proceeds, comm_fee, currency
        FROM transactions
        ORDER BY trade_date DESC
        LIMIT 25 OFFSET 0
    """
    
    cursor.execute(sql)
    rows = cursor.fetchall()
    
    print(f"✅ SQL query returned: {len(rows)} rows")
    
    if rows:
        print(f"\n📋 Query results:")
        for i, row in enumerate(rows, 1):
            print(f"  {i}. ID: {row[0]}, transaction_id: {row[1]}, symbol: {row[2]}")
    else:
        print("   ⚠️  Query returned no rows!")
    
    # Check column names
    cursor.execute("PRAGMA table_info(transactions)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    print(f"\n📋 Table columns: {', '.join(column_names)}")
    
    conn.close()
    return len(rows)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 BACKEND TRANSACTIONS TEST SUITE")
    print("="*60)
    
    # Run all tests
    db_count, db_rows = test_database_count()
    health_count = test_health_endpoint()
    list_total, list_data = test_list_transactions_endpoint()
    query_rows = test_query_structure()
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    print(f"Database COUNT(*): {db_count}")
    print(f"Database SELECT all: {db_rows}")
    print(f"Health endpoint: {health_count}")
    print(f"List endpoint total: {list_total}")
    print(f"List endpoint data length: {list_data}")
    print(f"SQL query rows: {query_rows}")
    
    # Check consistency
    print("\n" + "="*60)
    print("✅ CONSISTENCY CHECK")
    print("="*60)
    
    all_match = True
    if db_count != db_rows:
        print(f"❌ Database COUNT vs SELECT mismatch: {db_count} != {db_rows}")
        all_match = False
    
    if health_count != db_count:
        print(f"❌ Health endpoint mismatch: {health_count} != {db_count}")
        all_match = False
    
    if list_total != db_count:
        print(f"❌ List endpoint total mismatch: {list_total} != {db_count}")
        all_match = False
    
    if list_data != min(db_count, 25):
        print(f"❌ List endpoint data length mismatch: {list_data} != {min(db_count, 25)}")
        all_match = False
    
    if query_rows != list_data:
        print(f"❌ SQL query vs API mismatch: {query_rows} != {list_data}")
        all_match = False
    
    if all_match:
        print("✅ All counts match!")
    else:
        print("❌ Inconsistencies found!")
