#!/usr/bin/env python3
"""
Calcule l'average cost en utilisant le cost basis IBKR directement depuis la DB.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection


def calculate_with_ibkr_basis(symbol):
    """Calcule l'average cost en utilisant le basis IBKR."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT trade_date, quantity, t_price, basis
        FROM transactions 
        WHERE symbol = ?
        ORDER BY trade_date, transaction_id
    """, (symbol,))
    
    transactions = cursor.fetchall()
    conn.close()
    
    if not transactions:
        print(f"❌ Aucune transaction pour {symbol}")
        return
    
    print(f"\n{'=' * 80}")
    print(f"📊 CALCUL AVEC COST BASIS IBKR POUR {symbol}")
    print(f"{'=' * 80}\n")
    
    total_shares = 0
    total_cost = 0
    
    print(f"{'Date':<12} {'Qty':>8} {'Price':>10} {'Basis':>12} {'Shares':>10} {'Avg Cost':>12}")
    print("-" * 80)
    
    for tx in transactions:
        date, qty, price, basis = tx
        basis = basis or 0
        
        if qty > 0:
            # ACHAT - utiliser le basis IBKR directement
            total_cost += basis
            total_shares += qty
        else:
            # VENTE - retirer le cost basis (si IBKR le fournit)
            # Si basis = 0, on doit calculer nous-mêmes
            if basis != 0:
                # IBKR fournit le cost basis de la vente (négatif normalement)
                total_cost += basis  # basis est négatif pour les ventes
                total_shares += qty  # qty est négatif
            else:
                # Pas de basis fourni, on utilise l'average cost actuel
                shares_sold = abs(qty)
                avg_cost = total_cost / total_shares if total_shares > 0 else 0
                cost_of_sold = shares_sold * avg_cost
                total_cost -= cost_of_sold
                total_shares += qty
        
        avg_cost = total_cost / total_shares if total_shares > 0 else 0
        
        print(f"{date:<12} {qty:>8.2f} ${price:>9.2f} ${basis:>10.2f} {total_shares:>10.2f} ${avg_cost:>11.4f}")
    
    print("-" * 80)
    print(f"\n📊 RÉSUMÉ:")
    print(f"   Actions restantes:    {total_shares:>10.2f}")
    print(f"   Coût total:           ${total_cost:>10.2f}")
    print(f"   Avg cost (IBKR):      ${avg_cost:>10.4f}")
    print(f"\n{'=' * 80}\n")
    
    return avg_cost


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_ibkr_basis.py SYMBOL")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    calculate_with_ibkr_basis(symbol)
