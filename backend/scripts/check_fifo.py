#!/usr/bin/env python3
"""
Script pour calculer le cost basis avec la méthode FIFO (First In First Out).
Usage: python check_fifo.py SYMBOL
"""

import sys
from pathlib import Path
from collections import deque

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection


def check_fifo(symbol):
    """Calcule et affiche le cost basis FIFO pour un symbole donné."""
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
    
    print(f"\n{'=' * 95}")
    print(f"📊 CALCUL FIFO (FIRST IN FIRST OUT) POUR {symbol}")
    print(f"{'=' * 95}\n")
    
    # Queue FIFO pour tracker les lots d'achat
    # Chaque lot = (shares, cost_per_share_with_commission)
    lots = deque()
    
    total_shares = 0
    total_cost = 0
    total_realized_gain = 0
    
    print(f"{'Date':<12} {'Qty':>8} {'Price':>10} {'Comm':>8} {'Action':<40} {'Shares':>10} {'Avg Cost':>12} {'Realized':>12}")
    print("-" * 115)
    
    for tx in transactions:
        date, qty, price, comm, proceeds = tx
        comm = comm or 0
        
        if qty > 0:
            # ACHAT - ajouter un nouveau lot à la queue
            # Commission négative, donc on soustrait pour l'ajouter au coût
            cost_per_share = price - (comm / qty)
            total_cost_of_lot = qty * cost_per_share
            
            lots.append({
                'shares': qty,
                'cost_per_share': cost_per_share,
                'date': date
            })
            
            total_shares += qty
            total_cost += total_cost_of_lot
            avg_cost = total_cost / total_shares if total_shares > 0 else 0
            
            action = f"BUY - Add lot @ ${cost_per_share:.4f}/share"
            print(f"{date:<12} {qty:>8.2f} ${price:>9.2f} ${comm:>7.2f} {action:<40} {total_shares:>10.2f} ${avg_cost:>11.4f} {'-':>12}")
            
        else:
            # VENTE - retirer des lots en FIFO
            shares_to_sell = abs(qty)
            sale_price = price
            total_cost_basis = 0
            shares_sold = 0
            lots_used = []
            
            remaining_to_sell = shares_to_sell
            
            while remaining_to_sell > 0 and lots:
                lot = lots[0]  # Premier lot (FIFO)
                
                if lot['shares'] <= remaining_to_sell:
                    # Vendre tout le lot
                    shares_from_lot = lot['shares']
                    cost_from_lot = shares_from_lot * lot['cost_per_share']
                    total_cost_basis += cost_from_lot
                    shares_sold += shares_from_lot
                    remaining_to_sell -= shares_from_lot
                    lots_used.append(f"{shares_from_lot:.0f}@${lot['cost_per_share']:.2f}")
                    lots.popleft()  # Retirer le lot complètement vendu
                else:
                    # Vendre une partie du lot
                    shares_from_lot = remaining_to_sell
                    cost_from_lot = shares_from_lot * lot['cost_per_share']
                    total_cost_basis += cost_from_lot
                    shares_sold += shares_from_lot
                    lots_used.append(f"{shares_from_lot:.0f}@${lot['cost_per_share']:.2f}")
                    lot['shares'] -= remaining_to_sell
                    remaining_to_sell = 0
            
            # Calculer le gain réalisé
            sale_proceeds = shares_to_sell * sale_price
            realized_gain = sale_proceeds - total_cost_basis - comm
            
            total_shares += qty  # qty est négatif
            total_cost -= total_cost_basis
            total_realized_gain += realized_gain
            
            avg_cost = total_cost / total_shares if total_shares > 0 else 0
            
            action = f"SELL - Used lots: {', '.join(lots_used[:3])}"
            if len(lots_used) > 3:
                action += "..."
            
            print(f"{date:<12} {qty:>8.2f} ${price:>9.2f} ${comm:>7.2f} {action:<40} {total_shares:>10.2f} ${avg_cost:>11.4f} ${realized_gain:>10.2f}")
    
    print("-" * 115)
    print(f"\n📊 RÉSUMÉ FIFO:")
    print(f"   Actions restantes:    {total_shares:>10.2f}")
    print(f"   Coût total:           ${total_cost:>10.2f}")
    print(f"   Avg cost (FIFO):      ${total_cost/total_shares if total_shares > 0 else 0:>10.4f}")
    print(f"   Realized Gain total:  ${total_realized_gain:>10.2f}")
    print(f"   Lots restants:        {len(lots):>10}")
    
    if lots:
        print(f"\n   📦 Détail des lots restants:")
        for i, lot in enumerate(lots, 1):
            print(f"      Lot {i}: {lot['shares']:.2f} shares @ ${lot['cost_per_share']:.4f} (acheté le {lot['date']})")
    
    if abs(total_shares) > 0.01:
        print(f"\n   ✅ Position OUVERTE")
    else:
        print(f"\n   🔒 Position FERMÉE")
    
    print(f"\n{'=' * 95}\n")
    
    return {
        'shares': total_shares,
        'cost': total_cost,
        'avg_cost': total_cost / total_shares if total_shares > 0 else 0,
        'realized_gain': total_realized_gain
    }


def compare_fifo_vs_acb(symbol):
    """Compare FIFO avec ACB pour un symbole."""
    print("\n" + "=" * 95)
    print(f"📊 COMPARAISON FIFO vs ACB POUR {symbol}")
    print("=" * 95)
    
    # Calculer FIFO
    fifo_result = check_fifo(symbol)
    
    # Calculer ACB
    from check_acb import check_acb
    print("\n" + "=" * 95)
    print("📊 CALCUL ACB (AVERAGE COST) - Pour comparaison")
    print("=" * 95 + "\n")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT trade_date, quantity, t_price, comm_fee
        FROM transactions 
        WHERE symbol = ?
        ORDER BY trade_date, transaction_id
    """, (symbol,))
    
    transactions = cursor.fetchall()
    conn.close()
    
    running_shares = 0
    running_cost = 0
    
    for tx in transactions:
        date, qty, price, comm = tx
        comm = comm or 0
        
        if qty > 0:
            cost = (qty * price) - comm
            running_cost += cost
            running_shares += qty
        else:
            shares_sold = abs(qty)
            acb = running_cost / running_shares if running_shares > 0 else 0
            cost_basis = shares_sold * acb
            running_shares += qty
            running_cost -= cost_basis
    
    acb_avg = running_cost / running_shares if running_shares > 0 else 0
    
    print(f"\n📊 RÉSUMÉ ACB:")
    print(f"   Actions restantes:    {running_shares:>10.2f}")
    print(f"   Coût total:           ${running_cost:>10.2f}")
    print(f"   Avg cost (ACB):       ${acb_avg:>10.4f}")
    
    print("\n" + "=" * 95)
    print("🔍 COMPARAISON FINALE")
    print("=" * 95)
    print(f"\n{'Méthode':<15} {'Shares':>10} {'Total Cost':>15} {'Avg Cost':>15} {'Différence':>15}")
    print("-" * 70)
    print(f"{'FIFO':<15} {fifo_result['shares']:>10.2f} ${fifo_result['cost']:>13.2f} ${fifo_result['avg_cost']:>13.4f} {'-':>15}")
    print(f"{'ACB (Average)':<15} {running_shares:>10.2f} ${running_cost:>13.2f} ${acb_avg:>13.4f} ${fifo_result['avg_cost'] - acb_avg:>13.4f}")
    
    diff_pct = ((fifo_result['avg_cost'] - acb_avg) / acb_avg * 100) if acb_avg != 0 else 0
    print(f"\n⚠️  Différence: ${fifo_result['avg_cost'] - acb_avg:.4f}/share ({diff_pct:+.2f}%)")
    
    if abs(diff_pct) > 1:
        print(f"   → FIFO et ACB donnent des résultats {'TRÈS ' if abs(diff_pct) > 5 else ''}différents!")
    else:
        print(f"   → FIFO et ACB donnent des résultats similaires")
    
    print("\n" + "=" * 95 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_fifo.py SYMBOL [--compare]")
        print("Exemple: python check_fifo.py SOFI")
        print("         python check_fifo.py SOFI --compare")
        sys.exit(1)
    
    symbol = sys.argv[1].upper()
    
    if len(sys.argv) > 2 and sys.argv[2] == '--compare':
        compare_fifo_vs_acb(symbol)
    else:
        check_fifo(symbol)
