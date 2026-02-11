"""
Test CASCADE delete et CA status après suppression de transactions
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

def test_cascade_delete():
    """Test que la suppression d'une transaction supprime ses updated_transactions."""
    print("\n" + "=" * 60)
    print("TEST 1: CASCADE DELETE")
    print("=" * 60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get NVDA transactions
    cursor.execute("SELECT transaction_id FROM transactions WHERE symbol = 'NVDA' LIMIT 1")
    result = cursor.fetchone()
    
    if not result:
        print("❌ No NVDA transactions found")
        conn.close()
        return False
    
    tx_id = result[0]
    
    # Check updated_transactions before
    cursor.execute("SELECT COUNT(*) FROM updated_transactions WHERE transaction_id = ?", (tx_id,))
    count_before = cursor.fetchone()[0]
    print(f"📊 Updated transactions before delete: {count_before}")
    
    # Delete the transaction
    cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", (tx_id,))
    conn.commit()
    
    # Check updated_transactions after
    cursor.execute("SELECT COUNT(*) FROM updated_transactions WHERE transaction_id = ?", (tx_id,))
    count_after = cursor.fetchone()[0]
    print(f"📊 Updated transactions after delete: {count_after}")
    
    # Rollback to restore
    conn.rollback()
    conn.close()
    
    if count_before > 0 and count_after == 0:
        print("✅ CASCADE delete works!")
        return True
    else:
        print(f"❌ CASCADE delete failed: before={count_before}, after={count_after}")
        return False


def test_ca_status_after_delete():
    """Test que le CA status passe à orange après suppression."""
    print("\n" + "=" * 60)
    print("TEST 2: CA STATUS AFTER DELETE")
    print("=" * 60)
    
    from backend.utils.ca_status import get_ca_status, set_ca_status
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get NVDA status before
    status_before = get_ca_status('NVDA')
    print(f"📊 NVDA CA status before: {status_before.get('NVDA', {}).get('status', 'N/A')}")
    
    # Set to green first
    set_ca_status(['NVDA'], 'green')
    status_green = get_ca_status('NVDA')
    print(f"📊 NVDA CA status (set to green): {status_green.get('NVDA', {}).get('status', 'N/A')}")
    
    # Get a transaction
    cursor.execute("SELECT transaction_id FROM transactions WHERE symbol = 'NVDA' LIMIT 1")
    result = cursor.fetchone()
    
    if not result:
        print("❌ No NVDA transactions found")
        conn.close()
        return False
    
    tx_id = result[0]
    
    # Delete transaction and set status to orange
    cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", (tx_id,))
    conn.commit()
    set_ca_status(['NVDA'], 'orange')
    
    # Check status after
    status_after = get_ca_status('NVDA')
    print(f"📊 NVDA CA status after delete: {status_after.get('NVDA', {}).get('status', 'N/A')}")
    
    # Rollback
    conn.rollback()
    conn.close()
    
    if status_after.get('NVDA', {}).get('status') == 'orange':
        print("✅ CA status correctly set to orange!")
        return True
    else:
        print("❌ CA status not set to orange")
        return False


if __name__ == "__main__":
    print("\n🧪 Testing CASCADE delete and CA status")
    
    test1 = test_cascade_delete()
    test2 = test_ca_status_after_delete()
    
    print("\n" + "=" * 60)
    if test1 and test2:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
