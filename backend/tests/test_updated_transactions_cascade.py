"""
Test CASCADE delete for updated_transactions table

Verifies that deleting a transaction or CA automatically deletes related updated_transactions.
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "output" / "database" / "finance.db"


def test_cascade_delete_transaction():
    """Test that deleting a transaction cascades to updated_transactions."""
    print("\n" + "=" * 60)
    print("TEST 1: CASCADE DELETE - Transaction")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
    cursor = conn.cursor()
    
    # Insert test transaction
    test_tx_id = "TEST_CASCADE_TX_001"
    cursor.execute("""
        INSERT INTO transactions (transaction_id, symbol, trade_date, quantity, t_price)
        VALUES (?, 'TEST', '2020-01-01', 100, 10.0)
    """, (test_tx_id,))
    
    # Insert test CA
    cursor.execute("""
        INSERT INTO corporate_actions (sec_id, ca_type, ex_date, split_ratio)
        VALUES ('TEST', 'split', '2021-01-01', 4.0)
    """)
    ca_id = cursor.lastrowid
    
    # Insert test updated_transaction
    cursor.execute("""
        INSERT INTO updated_transactions (
            transaction_id, symbol, trade_date,
            original_quantity, original_price,
            updated_quantity, updated_price,
            split_ratio, ca_id, ca_type, ca_date
        ) VALUES (?, 'TEST', '2020-01-01', 100, 10.0, 400, 2.5, 4.0, ?, 'split', '2021-01-01')
    """, (test_tx_id, ca_id))
    
    conn.commit()
    
    # Verify updated_transaction exists
    cursor.execute("SELECT COUNT(*) FROM updated_transactions WHERE transaction_id = ?", (test_tx_id,))
    count_before = cursor.fetchone()[0]
    print(f"✓ Updated transactions before delete: {count_before}")
    assert count_before == 1, "Updated transaction should exist"
    
    # Delete the transaction
    cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", (test_tx_id,))
    conn.commit()
    
    # Verify updated_transaction was deleted (CASCADE)
    cursor.execute("SELECT COUNT(*) FROM updated_transactions WHERE transaction_id = ?", (test_tx_id,))
    count_after = cursor.fetchone()[0]
    print(f"✓ Updated transactions after delete: {count_after}")
    assert count_after == 0, "Updated transaction should be deleted via CASCADE"
    
    # Cleanup
    cursor.execute("DELETE FROM corporate_actions WHERE id = ?", (ca_id,))
    conn.commit()
    conn.close()
    
    print("✅ PASS: Transaction CASCADE delete works")


def test_cascade_delete_ca():
    """Test that deleting a CA cascades to updated_transactions."""
    print("\n" + "=" * 60)
    print("TEST 2: CASCADE DELETE - Corporate Action")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
    cursor = conn.cursor()
    
    # Insert test transaction
    test_tx_id = "TEST_CASCADE_TX_002"
    cursor.execute("""
        INSERT INTO transactions (transaction_id, symbol, trade_date, quantity, t_price)
        VALUES (?, 'TEST', '2020-01-01', 100, 10.0)
    """, (test_tx_id,))
    
    # Insert test CA
    cursor.execute("""
        INSERT INTO corporate_actions (sec_id, ca_type, ex_date, split_ratio)
        VALUES ('TEST', 'split', '2021-01-01', 4.0)
    """)
    ca_id = cursor.lastrowid
    
    # Insert test updated_transaction
    cursor.execute("""
        INSERT INTO updated_transactions (
            transaction_id, symbol, trade_date,
            original_quantity, original_price,
            updated_quantity, updated_price,
            split_ratio, ca_id, ca_type, ca_date
        ) VALUES (?, 'TEST', '2020-01-01', 100, 10.0, 400, 2.5, 4.0, ?, 'split', '2021-01-01')
    """, (test_tx_id, ca_id))
    
    conn.commit()
    
    # Verify updated_transaction exists
    cursor.execute("SELECT COUNT(*) FROM updated_transactions WHERE ca_id = ?", (ca_id,))
    count_before = cursor.fetchone()[0]
    print(f"✓ Updated transactions before delete: {count_before}")
    assert count_before == 1, "Updated transaction should exist"
    
    # Delete the CA
    cursor.execute("DELETE FROM corporate_actions WHERE id = ?", (ca_id,))
    conn.commit()
    
    # Verify updated_transaction was deleted (CASCADE)
    cursor.execute("SELECT COUNT(*) FROM updated_transactions WHERE ca_id = ?", (ca_id,))
    count_after = cursor.fetchone()[0]
    print(f"✓ Updated transactions after delete: {count_after}")
    assert count_after == 0, "Updated transaction should be deleted via CASCADE"
    
    # Cleanup
    cursor.execute("DELETE FROM transactions WHERE transaction_id = ?", (test_tx_id,))
    conn.commit()
    conn.close()
    
    print("✅ PASS: CA CASCADE delete works")


if __name__ == "__main__":
    print("\n🧪 Testing CASCADE delete for updated_transactions")
    
    try:
        test_cascade_delete_transaction()
        test_cascade_delete_ca()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
