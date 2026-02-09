"""
Test Transactions Count - Backend vs Frontend

This script displays:
- Number of trades in database
- Number of trades returned by API endpoints
- Parsed/Inserted/Skipped counts from import logs

Run: python3 backend/tests/test_transactions_count.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

def main():
    print("\n" + "="*70)
    print("📊 TRANSACTIONS COUNT TEST")
    print("="*70)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Database count
    cursor.execute("SELECT COUNT(*) FROM transactions")
    db_count = cursor.fetchone()[0]
    print(f"\n✅ DATABASE:")
    print(f"   Total transactions: {db_count}")
    
    # 2. List all transactions
    cursor.execute("""
        SELECT id, transaction_id, symbol, trade_date, trade_time 
        FROM transactions 
        ORDER BY id
    """)
    rows = cursor.fetchall()
    print(f"\n📋 All transactions in database ({len(rows)}):")
    for i, row in enumerate(rows, 1):
        time_str = row["trade_time"] if row["trade_time"] else "(no time)"
        print(f"   {i}. ID:{row['id']} | {row['transaction_id']} | {row['symbol']} | {row['trade_date']} | {time_str}")
    
    # 3. Test API query (simulate what frontend calls)
    cursor.execute("""
        SELECT id, transaction_id, symbol, trade_date, trade_time, quantity, t_price, proceeds, comm_fee, currency
        FROM transactions
        ORDER BY trade_date DESC
        LIMIT 25 OFFSET 0
    """)
    api_rows = cursor.fetchall()
    print(f"\n✅ API ENDPOINT SIMULATION:")
    print(f"   Query would return: {len(api_rows)} transactions")
    
    if api_rows:
        print(f"\n📋 API query results ({len(api_rows)}):")
        for i, row in enumerate(api_rows, 1):
            time_str = row["trade_time"] if row["trade_time"] else "(no time)"
            print(f"   {i}. ID:{row['id']} | {row['transaction_id']} | {row['symbol']} | {row['trade_date']} | {time_str}")
    else:
        print("   ⚠️  No transactions returned by API query!")
    
    # 4. Import logs summary
    cursor.execute("""
        SELECT 
            COUNT(*) as total_logs,
            SUM(parsed) as total_parsed,
            SUM(inserted) as total_inserted,
            SUM(skipped) as total_skipped,
            SUM(errors) as total_errors
        FROM import_logs
    """)
    log_summary = cursor.fetchone()
    
    print(f"\n✅ IMPORT LOGS SUMMARY:")
    print(f"   Total imports: {log_summary[0]}")
    print(f"   Total parsed: {log_summary[1] or 0}")
    print(f"   Total inserted: {log_summary[2] or 0}")
    print(f"   Total skipped: {log_summary[3] or 0}")
    print(f"   Total errors: {log_summary[4] or 0}")
    
    # 5. Recent import logs
    cursor.execute("""
        SELECT filename, import_date, parsed, inserted, skipped, errors, status
        FROM import_logs
        ORDER BY import_date DESC
        LIMIT 5
    """)
    recent_logs = cursor.fetchall()
    
    if recent_logs:
        print(f"\n📋 Last 5 imports:")
        for i, log in enumerate(recent_logs, 1):
            print(f"   {i}. {log['filename']} | {log['import_date']}")
            print(f"      Parsed: {log['parsed']} | Inserted: {log['inserted']} | Skipped: {log['skipped']} | Errors: {log['errors']} | Status: {log['status']}")
    
    conn.close()
    
    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    print(f"Database COUNT(*):           {db_count}")
    print(f"Database SELECT all:         {len(rows)}")
    print(f"API query simulation:        {len(api_rows)}")
    print(f"Import logs total inserted:  {log_summary[2] or 0}")
    
    # Check consistency
    print("\n" + "="*70)
    print("✅ CONSISTENCY CHECK")
    print("="*70)
    
    issues = []
    if db_count != len(rows):
        issues.append(f"Database COUNT vs SELECT: {db_count} != {len(rows)}")
    if len(api_rows) != len(rows):
        issues.append(f"API query vs SELECT: {len(api_rows)} != {len(rows)}")
    
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("✅ All backend counts are consistent!")
        print(f"\n💡 If frontend shows 0 transactions:")
        print(f"   1. Check browser console for API errors")
        print(f"   2. Check Network tab - is /api/proxy/api/transactions returning data?")
        print(f"   3. Check if React state is updating after API call")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
