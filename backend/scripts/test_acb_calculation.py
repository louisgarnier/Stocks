"""
Script de test pour calculer l'ACB (Adjusted Cost Base) correctement.

Méthode ACB:
- Sur chaque ACHAT: New ACB = (Previous total cost + New shares × New price) / (Previous shares + New shares)
- Sur chaque VENTE: ACB ne change pas, on réduit juste le nombre d'actions
"""

import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection


def calculate_acb_positions():
    """
    Calcule les positions avec la méthode ACB correcte.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Récupérer toutes les transactions, triées par date
    cursor.execute("""
        SELECT 
            t.symbol,
            t.trade_date,
            t.transaction_id,
            COALESCE(ut.updated_quantity, t.quantity) as quantity,
            COALESCE(ut.updated_price, t.t_price) as price,
            t.comm_fee,
            CASE WHEN ut.transaction_id IS NOT NULL THEN 1 ELSE 0 END as is_adjusted
        FROM transactions t
        LEFT JOIN updated_transactions ut ON t.transaction_id = ut.transaction_id
        WHERE t.symbol NOT LIKE '%.%'
        ORDER BY t.symbol, t.trade_date, t.transaction_id
    """)
    
    all_transactions = cursor.fetchall()
    conn.close()
    
    # Grouper par symbole
    symbol_transactions = defaultdict(list)
    for row in all_transactions:
        symbol_transactions[row[0]].append({
            'date': row[1],
            'tx_id': row[2],
            'quantity': row[3],
            'price': row[4],
            'commission': row[5] or 0,
            'is_adjusted': row[6]
        })
    
    print("=" * 120)
    print("📊 CALCUL ACB (ADJUSTED COST BASE) - MÉTHODE CORRECTE")
    print("=" * 120)
    print("\nRÈGLES:")
    print("  • Sur ACHAT (qty > 0): ACB = (Previous cost + New shares × New price) / (Previous shares + New shares)")
    print("  • Sur VENTE (qty < 0): ACB reste identique, on réduit juste le nombre d'actions")
    print("  • Realized gain = (Sale price - ACB) × shares sold")
    print("=" * 120)
    
    # Calculer pour chaque symbole
    results = {}
    
    for symbol in sorted(symbol_transactions.keys()):
        transactions = symbol_transactions[symbol]
        
        # Variables de tracking
        running_shares = 0
        running_total_cost = 0
        acb_per_share = 0
        total_realized_gain = 0
        
        transaction_details = []
        
        for tx in transactions:
            qty = tx['quantity']
            price = tx['price']
            commission = tx['commission']
            
            if qty > 0:
                # ACHAT
                # Commission est négative en DB, donc on soustrait (ce qui ajoute au coût)
                cost_of_purchase = (qty * price) - commission
                new_total_cost = running_total_cost + cost_of_purchase
                new_shares = running_shares + qty
                
                # Calculer le nouvel ACB
                if new_shares > 0:
                    acb_per_share = new_total_cost / new_shares
                
                running_total_cost = new_total_cost
                running_shares = new_shares
                
                transaction_details.append({
                    'date': tx['date'],
                    'type': 'BUY',
                    'qty': qty,
                    'price': price,
                    'commission': commission,
                    'cost': cost_of_purchase,
                    'running_shares': running_shares,
                    'acb': acb_per_share,
                    'realized_gain': 0,
                    'is_adjusted': tx['is_adjusted']
                })
                
            else:
                # VENTE
                shares_sold = abs(qty)
                sale_proceeds = shares_sold * price
                cost_basis_of_sold = shares_sold * acb_per_share
                # Commission est négative, donc on soustrait (ce qui réduit le gain)
                realized_gain = sale_proceeds - cost_basis_of_sold - commission
                
                # Réduire le nombre d'actions et le coût total
                running_shares += qty  # qty est négatif
                running_total_cost -= cost_basis_of_sold
                
                total_realized_gain += realized_gain
                
                transaction_details.append({
                    'date': tx['date'],
                    'type': 'SELL',
                    'qty': qty,
                    'price': price,
                    'commission': commission,
                    'cost': -cost_basis_of_sold,
                    'running_shares': running_shares,
                    'acb': acb_per_share,  # ACB ne change pas sur une vente
                    'realized_gain': realized_gain,
                    'is_adjusted': tx['is_adjusted']
                })
        
        # Stocker les résultats
        results[symbol] = {
            'final_shares': running_shares,
            'final_acb': acb_per_share,
            'final_total_cost': running_total_cost,
            'total_realized_gain': total_realized_gain,
            'transaction_count': len(transactions),
            'transactions': transaction_details
        }
    
    return results


def display_results(results, symbol_filter=None, show_transactions=True):
    """
    Affiche les résultats du calcul ACB.
    """
    symbols_to_show = [symbol_filter] if symbol_filter else sorted(results.keys())
    
    for symbol in symbols_to_show:
        if symbol not in results:
            print(f"\n❌ Symbole {symbol} non trouvé")
            continue
        
        data = results[symbol]
        
        print(f"\n{'=' * 120}")
        print(f"🔹 {symbol}")
        print(f"{'=' * 120}")
        
        if show_transactions:
            print(f"\n📋 Transactions détaillées:")
            print(f"{'Date':<12} {'Type':<6} {'Qty':>10} {'Price':>10} {'Comm':>8} {'Cost':>12} {'Shares':>10} {'ACB/share':>12} {'Realized Gain':>15} {'Note'}")
            print("-" * 120)
            
            for tx in data['transactions']:
                note = "🔄" if tx['is_adjusted'] else ""
                gain_str = f"${tx['realized_gain']:>13,.2f}" if tx['type'] == 'SELL' else "-"
                
                print(f"{tx['date']:<12} {tx['type']:<6} {tx['qty']:>10,.2f} "
                      f"${tx['price']:>9,.2f} ${tx['commission']:>7,.2f} "
                      f"${tx['cost']:>10,.2f} {tx['running_shares']:>10,.2f} "
                      f"${tx['acb']:>11,.4f} {gain_str:>15} {note}")
        
        print(f"\n📊 RÉSUMÉ FINAL:")
        print("-" * 80)
        print(f"   Actions restantes:       {data['final_shares']:>12,.2f}")
        print(f"   ACB par action:          ${data['final_acb']:>11,.4f}")
        print(f"   Coût total (ACB):        ${data['final_total_cost']:>11,.2f}")
        print(f"   Total transactions:      {data['transaction_count']:>12}")
        print(f"   Realized Gain (total):   ${data['total_realized_gain']:>11,.2f}")
        
        if abs(data['final_shares']) > 0.01:
            print(f"\n   ✅ Position OUVERTE")
            print(f"   📈 Market value @ current price = shares × current_price")
            print(f"   📈 Unrealized gain = market_value - ${data['final_total_cost']:,.2f}")
        else:
            print(f"\n   🔒 Position FERMÉE")
            print(f"   💰 Total realized gain: ${data['total_realized_gain']:,.2f}")


def compare_with_old_method(results):
    """
    Compare la méthode ACB avec l'ancienne méthode incorrecte.
    """
    print("\n" + "=" * 120)
    print("📊 COMPARAISON: ACB (CORRECT) vs ANCIENNE MÉTHODE (INCORRECT)")
    print("=" * 120)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT symbol, quantity, average_price, total_cost
        FROM positions
        WHERE ABS(quantity) > 0.01
        ORDER BY symbol
    """)
    
    old_positions = {row[0]: {'qty': row[1], 'avg': row[2], 'cost': row[3]} for row in cursor.fetchall()}
    conn.close()
    
    print(f"\n{'Symbol':<8} {'Shares':>10} {'ACB (correct)':>15} {'Old Avg':>15} {'Diff':>10} {'ACB Cost':>15} {'Old Cost':>15}")
    print("-" * 120)
    
    for symbol in sorted(results.keys()):
        if abs(results[symbol]['final_shares']) < 0.01:
            continue
        
        acb_shares = results[symbol]['final_shares']
        acb_avg = results[symbol]['final_acb']
        acb_cost = results[symbol]['final_total_cost']
        
        if symbol in old_positions:
            old_avg = old_positions[symbol]['avg']
            old_cost = old_positions[symbol]['cost']
            diff = acb_avg - old_avg
            diff_pct = (diff / old_avg * 100) if old_avg != 0 else 0
            
            # Highlight si différence significative
            marker = "⚠️ " if abs(diff_pct) > 1 else "  "
            
            print(f"{marker}{symbol:<8} {acb_shares:>10,.2f} ${acb_avg:>13,.4f} ${old_avg:>13,.4f} "
                  f"{diff:>9,.2f} ${acb_cost:>13,.2f} ${old_cost:>13,.2f}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test du calcul ACB')
    parser.add_argument('--symbol', '-s', help='Analyser un symbole spécifique')
    parser.add_argument('--compare', '-c', action='store_true', help='Comparer avec ancienne méthode')
    parser.add_argument('--no-transactions', action='store_true', help='Ne pas afficher les transactions détaillées')
    
    args = parser.parse_args()
    
    print("\n🔄 Calcul des positions avec méthode ACB...\n")
    results = calculate_acb_positions()
    
    if args.symbol:
        display_results(results, symbol_filter=args.symbol, show_transactions=not args.no_transactions)
    else:
        # Afficher seulement les positions ouvertes par défaut
        open_positions = {k: v for k, v in results.items() if abs(v['final_shares']) > 0.01}
        print(f"\n📊 Positions ouvertes: {len(open_positions)}")
        
        for symbol in sorted(open_positions.keys()):
            display_results({symbol: results[symbol]}, symbol, show_transactions=not args.no_transactions)
    
    if args.compare:
        compare_with_old_method(results)
    
    print("\n✅ Calcul terminé\n")
