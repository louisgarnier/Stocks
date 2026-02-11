"""
Test manuel pour appliquer les splits aux transactions existantes
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.utils.split_calculator import apply_splits_to_transactions

DB_PATH = PROJECT_ROOT / "output" / "database" / "finance.db"

def main():
    print("\n🧪 Manual Split Application Test")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Get all symbols with splits
    cursor.execute("""
        SELECT DISTINCT sec_id 
        FROM corporate_actions 
        WHERE ca_type IN ('split', 'spinoff')
    """)
    symbols_with_splits = [row[0] for row in cursor.fetchall()]
    
    print(f"\n📊 Found {len(symbols_with_splits)} symbols with splits:")
    for sym in symbols_with_splits:
        print(f"   - {sym}")
    
    updated_count = 0
    
    for symbol in symbols_with_splits:
        # Get splits
        cursor.execute("""
            SELECT id, ex_date, split_ratio, ca_type
            FROM corporate_actions
            WHERE sec_id = ? AND ca_type IN ('split', 'spinoff')
            ORDER BY ex_date ASC
        """, (symbol,))
        splits = [{'id': row[0], 'ex_date': row[1], 'split_ratio': row[2], 'ca_type': row[3]} 
                 for row in cursor.fetchall()]
        
        # Get transactions
        cursor.execute("""
            SELECT transaction_id, trade_date, quantity, t_price
            FROM transactions
            WHERE symbol = ?
            ORDER BY trade_date ASC
        """, (symbol,))
        transactions = [{'transaction_id': row[0], 'trade_date': row[1], 
                       'quantity': row[2], 't_price': row[3]} 
                      for row in cursor.fetchall()]
        
        if not transactions:
            print(f"\n⏭️  {symbol}: No transactions")
            continue
        
        # Apply splits
        updated_txs = apply_splits_to_transactions(symbol, splits, transactions)
        
        if updated_txs:
            print(f"\n✅ {symbol}: {len(updated_txs)} updated transactions")
            
            # Delete existing
            cursor.execute("DELETE FROM updated_transactions WHERE symbol = ?", (symbol,))
            
            # Insert new
            for utx in updated_txs:
                cursor.execute("""
                    INSERT INTO updated_transactions (
                        transaction_id, symbol, trade_date,
                        original_quantity, original_price,
                        updated_quantity, updated_price,
                        split_ratio, ca_id, ca_type, ca_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    utx['transaction_id'], utx['symbol'], utx['trade_date'],
                    utx['original_quantity'], utx['original_price'],
                    utx['updated_quantity'], utx['updated_price'],
                    utx['split_ratio'], utx['ca_id'], utx['ca_type'], utx['ca_date']
                ))
                updated_count += 1
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM updated_transactions")
    total = cursor.fetchone()[0]
    
    print("\n" + "=" * 60)
    print(f"✅ Total updated transactions created: {total}")
    print("=" * 60)
    
    conn.close()

if __name__ == "__main__":
    main()
