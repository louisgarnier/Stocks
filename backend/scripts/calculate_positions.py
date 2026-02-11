"""
Script de calcul des positions en utilisant la logique de la vue
(updated_transactions en priorité, sinon transactions originales)
Exclut les symboles Forex (contenant '.')
"""

import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

def calculate_positions():
    """
    Calcule les positions pour tous les symboles en utilisant la logique :
    - Si transaction_id existe dans updated_transactions : utiliser updated_quantity/price
    - Sinon : utiliser quantity/t_price de transactions
    - Exclut les symboles Forex (contenant '.')
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("=" * 80)
    print("📊 CALCUL DES POSITIONS (avec updated_transactions, hors Forex)")
    print("=" * 80)
    
    # Requête avec LEFT JOIN (logique de la vue)
    # Exclure les symboles Forex (contenant '.')
    cursor.execute("""
        SELECT 
            t.symbol,
            t.trade_date,
            t.transaction_id,
            COALESCE(ut.updated_quantity, t.quantity) as quantity,
            COALESCE(ut.updated_price, t.t_price) as price,
            t.quantity as original_quantity,
            t.t_price as original_price,
            CASE WHEN ut.transaction_id IS NOT NULL THEN 1 ELSE 0 END as is_adjusted,
            ut.split_ratio
        FROM transactions t
        LEFT JOIN updated_transactions ut ON t.transaction_id = ut.transaction_id
        WHERE t.symbol NOT LIKE '%.%'
        ORDER BY t.symbol, t.trade_date
    """)
    
    all_transactions = cursor.fetchall()
    
    # Grouper par symbole
    positions = defaultdict(lambda: {
        'total_quantity': 0,
        'total_cost': 0,
        'transactions': [],
        'adjusted_count': 0,
        'original_count': 0
    })
    
    for row in all_transactions:
        symbol = row[0]
        trade_date = row[1]
        tx_id = row[2]
        quantity = row[3]
        price = row[4]
        original_qty = row[5]
        original_price = row[6]
        is_adjusted = row[7]
        split_ratio = row[8]
        
        positions[symbol]['total_quantity'] += quantity
        positions[symbol]['total_cost'] += (quantity * price)
        positions[symbol]['transactions'].append({
            'date': trade_date,
            'tx_id': tx_id[:25] + '...',
            'quantity': quantity,
            'price': price,
            'original_qty': original_qty,
            'original_price': original_price,
            'is_adjusted': is_adjusted,
            'split_ratio': split_ratio
        })
        
        if is_adjusted:
            positions[symbol]['adjusted_count'] += 1
        else:
            positions[symbol]['original_count'] += 1
    
    # Afficher les résultats
    print(f"\n📈 POSITIONS PAR SYMBOLE ({len(positions)} symboles)\n")
    
    for symbol in sorted(positions.keys()):
        pos = positions[symbol]
        total_qty = pos['total_quantity']
        total_cost = pos['total_cost']
        avg_price = total_cost / total_qty if total_qty != 0 else 0
        
        print(f"\n{'─' * 80}")
        print(f"🔹 {symbol}")
        print(f"{'─' * 80}")
        print(f"   Position totale:     {total_qty:>10.2f} actions")
        print(f"   Coût total:          ${total_cost:>10,.2f}")
        print(f"   Prix moyen:          ${avg_price:>10.2f}")
        print(f"   Transactions:        {len(pos['transactions'])} total")
        print(f"      - Ajustées (🔄):  {pos['adjusted_count']}")
        print(f"      - Originales (✅): {pos['original_count']}")
        
        # Afficher détail des transactions si position non nulle ou < 10 transactions
        if abs(total_qty) > 0.01 or len(pos['transactions']) <= 10:
            print(f"\n   📋 Détail des transactions:")
            print(f"   {'Date':<12} {'Qty':>8} {'Price':>10} {'Original Qty':>12} {'Original Price':>14} {'Status':<10}")
            print(f"   {'-' * 76}")
            
            for tx in pos['transactions']:
                status = f"🔄 {tx['split_ratio']}" if tx['is_adjusted'] else "✅ Original"
                orig_qty_str = f"{tx['original_qty']:>12.2f}" if tx['is_adjusted'] else "-"
                orig_price_str = f"${tx['original_price']:>13.2f}" if tx['is_adjusted'] else "-"
                
                print(f"   {tx['date']:<12} {tx['quantity']:>8.2f} ${tx['price']:>9.2f} {orig_qty_str} {orig_price_str} {status}")
    
    # Résumé global
    print(f"\n{'=' * 80}")
    print(f"📊 RÉSUMÉ GLOBAL")
    print(f"{'=' * 80}")
    
    total_transactions = sum(len(pos['transactions']) for pos in positions.values())
    total_adjusted = sum(pos['adjusted_count'] for pos in positions.values())
    total_original = sum(pos['original_count'] for pos in positions.values())
    
    print(f"   Total symboles:           {len(positions)}")
    print(f"   Total transactions:       {total_transactions}")
    print(f"      - Ajustées (🔄):       {total_adjusted}")
    print(f"      - Originales (✅):      {total_original}")
    
    # Positions ouvertes (non nulles)
    open_positions = {sym: pos for sym, pos in positions.items() if abs(pos['total_quantity']) > 0.01}
    print(f"   Positions ouvertes:       {len(open_positions)}")
    
    if open_positions:
        print(f"\n   🔓 Positions ouvertes:")
        for symbol in sorted(open_positions.keys()):
            qty = open_positions[symbol]['total_quantity']
            cost = open_positions[symbol]['total_cost']
            avg = cost / qty if qty != 0 else 0
            print(f"      {symbol:<6} {qty:>10.2f} actions @ ${avg:>8.2f} = ${cost:>12,.2f}")
    
    # Positions fermées (nulles)
    closed_positions = {sym: pos for sym, pos in positions.items() if abs(pos['total_quantity']) <= 0.01}
    if closed_positions:
        print(f"\n   🔒 Positions fermées: {len(closed_positions)}")
        for symbol in sorted(closed_positions.keys()):
            print(f"      {symbol}")
    
    print(f"\n{'=' * 80}\n")
    
    conn.close()
    
    return positions

if __name__ == "__main__":
    calculate_positions()
