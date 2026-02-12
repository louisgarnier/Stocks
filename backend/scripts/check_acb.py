#!/usr/bin/env python3
"""
Script simple pour vérifier le calcul ACB d'un symbole.
Usage: python check_acb.py SYMBOL
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection


def check_acb(symbol):
    """Calcule et affiche l'ACB pour un symbole donné."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Récupérer toutes les transactions pour ce symbole
    cursor.execute("""
        SELECT 
            trade_date,
            quantity,
            t_price,
            comm_fee,
            proceeds
        FROM transactions 
        WHERE symbol = ?
        ORDER BY trade_date, transaction_id
    """, (symbol,))
    
    transactions = cursor.fetchall()
    conn.close()
    
    if not transactions:
        print(f"❌ Aucune transaction trouvée pour {symbol}")
        return
    
    print(f"\n{'=' * 80}")
    print(f"📊 CALCUL ACB POUR {symbol}")
    print(f"{'=' * 80}\n")
    
    # Variables de tracking
    running_shares = 0
    running_cost = 0
    acb_per_share = 0
    total_realized_gain = 0
    
    print(f"{'Date':<12} {'Qty':>8} {'Price':>10} {'Comm':>8} {'Cost':>12} {'Shares':>10} {'ACB/share':>12} {'Realized':>12}")
    print("-" * 95)
    
    for tx in transactions:
        date, qty, price, comm, proceeds = tx
        comm = comm or 0
        
        if qty > 0:
            # ACHAT - commission est négative, donc on soustrait
            cost = (qty * price) - comm
            running_cost += cost
            running_shares += qty
            acb_per_share = running_cost / running_shares if running_shares > 0 else 0
            
            print(f"{date:<12} {qty:>8.2f} ${price:>9.2f} ${comm:>7.2f} ${cost:>10.2f} {running_shares:>10.2f} ${acb_per_share:>11.4f} {'-':>12}")
        else:
            # VENTE
            shares_sold = abs(qty)
            sale_proceeds = shares_sold * price
            cost_basis = shares_sold * acb_per_share
            realized = sale_proceeds - cost_basis - comm
            
            running_shares += qty  # qty est négatif
            running_cost -= cost_basis
            total_realized_gain += realized
            
            print(f"{date:<12} {qty:>8.2f} ${price:>9.2f} ${comm:>7.2f} ${-cost_basis:>10.2f} {running_shares:>10.2f} ${acb_per_share:>11.4f} ${realized:>10.2f}")
    
    print("-" * 95)
    print(f"\n📊 RÉSUMÉ:")
    print(f"   Actions restantes:    {running_shares:>10.2f}")
    print(f"   ACB par action:       ${acb_per_share:>10.4f}")
    print(f"   Coût total (ACB):     ${running_cost:>10.2f}")
    print(f"   Realized Gain total:  ${total_realized_gain:>10.2f}")
    print(f"   Transactions:         {len(transactions):>10}")
    
    if abs(running_shares) > 0.01:
        print(f"\n   ✅ Position OUVERTE")
    else:
        print(f"\n   🔒 Position FERMÉE")
    
    print(f"\n{'=' * 80}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_acb.py SYMBOL")
        print("Exemple: python check_acb.py SOFI")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    check_acb(symbol)
