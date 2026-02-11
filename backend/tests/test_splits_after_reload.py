"""
Test que les splits sont appliqués aux transactions rechargées
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

def main():
    print("\n🧪 Test: Splits appliqués après reload de transactions")
    print("=" * 60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier les symboles avec splits
    cursor.execute("""
        SELECT DISTINCT sec_id, COUNT(*) as split_count
        FROM corporate_actions
        WHERE ca_type IN ('split', 'spinoff')
        GROUP BY sec_id
    """)
    symbols_with_splits = cursor.fetchall()
    
    print(f"\n📊 Symboles avec splits dans la DB:")
    for row in symbols_with_splits:
        print(f"   {row[0]}: {row[1]} split(s)")
    
    # Pour chaque symbole avec splits, vérifier les updated_transactions
    print(f"\n🔍 Vérification des updated_transactions:")
    
    total_tx = 0
    total_updated = 0
    
    for symbol, split_count in symbols_with_splits:
        # Compter transactions
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE symbol = ?", (symbol,))
        tx_count = cursor.fetchone()[0]
        
        # Compter updated_transactions
        cursor.execute("SELECT COUNT(*) FROM updated_transactions WHERE symbol = ?", (symbol,))
        updated_count = cursor.fetchone()[0]
        
        total_tx += tx_count
        total_updated += updated_count
        
        status = "✅" if updated_count > 0 else "❌"
        print(f"   {status} {symbol}: {tx_count} transactions → {updated_count} updated")
    
    print(f"\n📊 Total:")
    print(f"   Transactions: {total_tx}")
    print(f"   Updated transactions: {total_updated}")
    
    # Vérifier qu'il n'y a pas de transactions "orphelines"
    cursor.execute("""
        SELECT t.symbol, COUNT(*) as tx_count
        FROM transactions t
        WHERE EXISTS (
            SELECT 1 FROM corporate_actions ca
            WHERE ca.sec_id = t.symbol
            AND ca.ca_type IN ('split', 'spinoff')
        )
        AND NOT EXISTS (
            SELECT 1 FROM updated_transactions ut
            WHERE ut.transaction_id = t.transaction_id
        )
        GROUP BY t.symbol
    """)
    orphans = cursor.fetchall()
    
    if orphans:
        print(f"\n⚠️  Transactions sans updated_transactions (alors qu'il y a des splits):")
        for symbol, count in orphans:
            print(f"   {symbol}: {count} transaction(s) orpheline(s)")
    else:
        print(f"\n✅ Aucune transaction orpheline - tous les splits sont appliqués!")
    
    conn.close()
    
    print("=" * 60)

if __name__ == "__main__":
    main()
