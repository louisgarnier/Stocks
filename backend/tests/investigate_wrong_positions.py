"""
Investigation des positions incorrectes
Symboles à vérifier : ATRA, BWA, DOCN, LULU, OKTA, PATH, PHIN, SOUN, SGLD, SOFI
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

def investigate_symbol(symbol: str):
    """Analyse détaillée d'un symbole"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"\n{'=' * 80}")
    print(f"🔍 INVESTIGATION: {symbol}")
    print(f"{'=' * 80}")
    
    # 1. Transactions originales
    cursor.execute("""
        SELECT transaction_id, trade_date, quantity, t_price
        FROM transactions
        WHERE symbol = ?
        ORDER BY trade_date
    """, (symbol,))
    original_txs = cursor.fetchall()
    
    print(f"\n📊 TRANSACTIONS ORIGINALES: {len(original_txs)}")
    print(f"{'Date':<12} {'Qty':>10} {'Price':>12} {'Running':>12} {'TX ID':<30}")
    print("-" * 80)
    
    running = 0
    for tx in original_txs:
        tx_id, date, qty, price = tx
        running += qty
        print(f"{date:<12} {qty:>10.2f} ${price:>11.2f} {running:>12.2f} {tx_id[:28]}")
    
    print(f"\n   Position finale (originale): {running:.2f}")
    
    # 2. Updated transactions
    cursor.execute("""
        SELECT ut.transaction_id, t.trade_date, ut.updated_quantity, ut.updated_price, 
               ut.split_ratio, t.quantity as orig_qty, t.t_price as orig_price
        FROM updated_transactions ut
        JOIN transactions t ON ut.transaction_id = t.transaction_id
        WHERE ut.symbol = ?
        ORDER BY t.trade_date
    """, (symbol,))
    updated_txs = cursor.fetchall()
    
    print(f"\n📊 UPDATED TRANSACTIONS: {len(updated_txs)}")
    if updated_txs:
        print(f"{'Date':<12} {'Updated Qty':>12} {'Updated Price':>14} {'Original Qty':>12} {'Original Price':>14} {'Ratio':>8}")
        print("-" * 80)
        
        for tx in updated_txs:
            tx_id, date, upd_qty, upd_price, ratio, orig_qty, orig_price = tx
            print(f"{date:<12} {upd_qty:>12.2f} ${upd_price:>13.2f} {orig_qty:>12.2f} ${orig_price:>13.2f} {ratio:>8.2f}")
    
    # 3. Calcul avec la logique de la vue
    cursor.execute("""
        SELECT 
            t.trade_date,
            COALESCE(ut.updated_quantity, t.quantity) as quantity,
            COALESCE(ut.updated_price, t.t_price) as price,
            t.quantity as original_quantity,
            CASE WHEN ut.transaction_id IS NOT NULL THEN 1 ELSE 0 END as is_adjusted
        FROM transactions t
        LEFT JOIN updated_transactions ut ON t.transaction_id = ut.transaction_id
        WHERE t.symbol = ?
        ORDER BY t.trade_date
    """, (symbol,))
    adjusted_txs = cursor.fetchall()
    
    print(f"\n📊 CALCUL AVEC VUE (updated en priorité): {len(adjusted_txs)}")
    print(f"{'Date':<12} {'Qty':>10} {'Price':>12} {'Running':>12} {'Status':<10}")
    print("-" * 80)
    
    running_adjusted = 0
    for tx in adjusted_txs:
        date, qty, price, orig_qty, is_adjusted = tx
        running_adjusted += qty
        status = "🔄 Adjusted" if is_adjusted else "✅ Original"
        print(f"{date:<12} {qty:>10.2f} ${price:>11.2f} {running_adjusted:>12.2f} {status}")
    
    print(f"\n   Position finale (ajustée): {running_adjusted:.2f}")
    
    # 4. Splits pour ce symbole
    cursor.execute("""
        SELECT id, ex_date, split_ratio, ca_type
        FROM corporate_actions
        WHERE sec_id = ? AND ca_type IN ('split', 'spinoff')
        ORDER BY ex_date
    """, (symbol,))
    splits = cursor.fetchall()
    
    if splits:
        print(f"\n📊 SPLITS: {len(splits)}")
        for split in splits:
            split_id, ex_date, ratio, ca_type = split
            print(f"   {ex_date}: ratio={ratio} ({ca_type})")
    else:
        print(f"\n📊 SPLITS: Aucun")
    
    conn.close()
    
    print(f"\n{'=' * 80}\n")

if __name__ == "__main__":
    # Symboles à investiguer
    wrong_symbols = ['ATRA', 'BWA', 'DOCN', 'LULU', 'OKTA', 'PATH', 'PHIN', 'SOUN']
    incorrect_symbols = ['SGLD', 'SOFI']
    
    print("🔍 INVESTIGATION DES POSITIONS INCORRECTES")
    print("=" * 80)
    
    print("\n⚠️  POSITIONS FAUSSES (négatives ou incorrectes):")
    for symbol in wrong_symbols:
        investigate_symbol(symbol)
    
    print("\n⚠️  POSITIONS INCORRECTES (valeurs erronées):")
    for symbol in incorrect_symbols:
        investigate_symbol(symbol)
