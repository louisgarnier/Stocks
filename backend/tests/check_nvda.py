"""
Check NVDA transactions, splits, and updated transactions
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

def main():
    conn = get_db_connection()
    cursor = conn.cursor()

    print('=' * 70)
    print('NVDA - État Actuel')
    print('=' * 70)

    # Get NVDA split info
    cursor.execute("""
        SELECT id, ex_date, split_ratio, ca_type 
        FROM corporate_actions 
        WHERE sec_id = 'NVDA' AND ca_type IN ('split', 'spinoff')
    """)
    splits = cursor.fetchall()
    print(f'\n📊 Splits NVDA:')
    for split in splits:
        print(f'   ID={split[0]}, Date={split[1]}, Ratio={split[2]}, Type={split[3]}')

    split_date = splits[0][1] if splits else None

    # Get all NVDA transactions
    cursor.execute("""
        SELECT transaction_id, trade_date, quantity, t_price 
        FROM transactions 
        WHERE symbol = 'NVDA'
        ORDER BY trade_date
    """)
    transactions = cursor.fetchall()

    before_split = []
    after_split = []

    for tx in transactions:
        if split_date and tx[1] < split_date:
            before_split.append(tx)
        else:
            after_split.append(tx)

    print(f'\n📊 Transactions NVDA:')
    print(f'   Total: {len(transactions)}')
    print(f'   Before split ({split_date}): {len(before_split)}')
    print(f'   After split: {len(after_split)}')

    # Get updated transactions
    cursor.execute("""
        SELECT transaction_id, trade_date, original_quantity, original_price,
               updated_quantity, updated_price, split_ratio
        FROM updated_transactions 
        WHERE symbol = 'NVDA'
        ORDER BY trade_date
    """)
    updated = cursor.fetchall()

    print(f'\n📊 Updated Transactions NVDA: {len(updated)}')

    # Check if all transactions before split have updated_transactions
    tx_ids_before = set(tx[0] for tx in before_split)
    updated_ids = set(utx[0] for utx in updated)
    missing = tx_ids_before - updated_ids

    print(f'\n🔍 Vérification:')
    print(f'   Transactions avant split: {len(tx_ids_before)}')
    print(f'   Updated transactions: {len(updated_ids)}')
    print(f'   Missing: {len(missing)}')

    if missing:
        print(f'\n❌ Transactions avant split SANS updated_transaction:')
        for tx_id in list(missing)[:5]:
            cursor.execute("""
                SELECT trade_date, quantity, t_price 
                FROM transactions 
                WHERE transaction_id = ?
            """, (tx_id,))
            tx = cursor.fetchone()
            print(f'      {tx_id[:25]}... - {tx[0]} - qty={tx[1]:6.2f} - price=${tx[2]:8.2f}')
        if len(missing) > 5:
            print(f'      ... et {len(missing) - 5} autres')
    else:
        print(f'   ✅ Toutes les transactions avant split ont des updated_transactions')

    # Show sample updated transactions
    if updated:
        print(f'\n📋 Exemples Updated Transactions:')
        for utx in updated[:3]:
            print(f'   {utx[1]} - Orig: {utx[2]:6.2f} @ ${utx[3]:8.2f} → Upd: {utx[4]:6.2f} @ ${utx[5]:8.2f} (ratio={utx[6]})')

    # Check CA status
    cursor.execute("""
        SELECT status, last_fetched_at 
        FROM corporate_actions_status 
        WHERE sec_id = 'NVDA'
    """)
    ca_status = cursor.fetchone()
    print(f'\n🎨 CA Status NVDA: {ca_status[0] if ca_status else "N/A"}')

    conn.close()
    print('=' * 70)

if __name__ == "__main__":
    main()
