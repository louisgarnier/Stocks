"""
Script d'analyse détaillée du calcul de l'average price par security.
Montre toutes les transactions et explique le calcul étape par étape.
"""

import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection


def analyze_position_calculation(symbol: str = None, show_all: bool = False):
    """
    Analyse détaillée du calcul de la position et de l'average price.
    
    Pour chaque symbole, montre:
    - Toutes les transactions (date, quantité, prix, coût)
    - Le calcul cumulatif
    - L'average price calculé
    - Explication du calcul
    
    Args:
        symbol: Symbole spécifique à analyser (None = tous)
        show_all: True pour montrer tous les symboles, False pour les positions ouvertes uniquement
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Requête pour récupérer les transactions
    query = """
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
    """
    
    if symbol:
        query += f" AND t.symbol = '{symbol}'"
    
    query += " ORDER BY t.symbol, t.trade_date, t.transaction_id"
    
    cursor.execute(query)
    all_transactions = cursor.fetchall()
    
    if not all_transactions:
        print(f"❌ Aucune transaction trouvée pour {symbol or 'tous les symboles'}")
        conn.close()
        return
    
    # Grouper par symbole
    symbol_transactions = defaultdict(list)
    for row in all_transactions:
        symbol_transactions[row[0]].append({
            'date': row[1],
            'tx_id': row[2][:20] + '...' if len(row[2]) > 20 else row[2],
            'quantity': row[3],
            'price': row[4],
            'original_qty': row[5],
            'original_price': row[6],
            'is_adjusted': row[7],
            'split_ratio': row[8]
        })
    
    print("=" * 100)
    print("📊 ANALYSE DÉTAILLÉE DU CALCUL DES POSITIONS ET AVERAGE PRICE")
    print("=" * 100)
    print("\nMÉTHODOLOGIE:")
    print("-" * 100)
    print("1. Pour chaque transaction, on calcule le coût = quantity × price")
    print("2. On fait la somme de toutes les quantities → total_quantity")
    print("3. On fait la somme de tous les coûts → total_cost")
    print("4. Average Price = total_cost / total_quantity (moyenne pondérée)")
    print("\n⚠️  IMPORTANT: Cette méthode inclut TOUTES les transactions (achats + ventes)")
    print("    Si vous vendez une partie de votre position, cela affecte l'average price!")
    print("-" * 100)
    
    for sym in sorted(symbol_transactions.keys()):
        transactions = symbol_transactions[sym]
        
        # Calcul de la position
        total_qty = 0
        total_cost = 0
        buy_cost = 0
        buy_qty = 0
        sell_cost = 0
        sell_qty = 0
        
        print(f"\n\n{'=' * 100}")
        print(f"🔹 SYMBOLE: {sym}")
        print(f"{'=' * 100}")
        
        # Tableau détaillé des transactions
        print("\n📋 Transactions:")
        print(f"{'Date':<12} {'Qty':>10} {'Price':>14} {'Coût':>12} {'Qty Cumul':>10} {'Coût Cumul':>12} {'Note'}")
        print("-" * 90)
        
        running_qty = 0
        running_cost = 0
        
        for tx in transactions:
            qty = tx['quantity']
            price = tx['price']
            cost = qty * price
            
            # Cumul pour ce symbole
            total_qty += qty
            total_cost += cost
            
            # Séparation achats/ventes
            if qty > 0:
                buy_qty += qty
                buy_cost += cost
            else:
                sell_qty += abs(qty)
                sell_cost += abs(cost)
            
            running_qty += qty
            running_cost += cost
            
            # Indicateur d'ajustement
            note = ""
            if tx['is_adjusted']:
                note = f"🔄 (split {tx['split_ratio']})" if tx['split_ratio'] else "🔄"
            
            # Prix display
            price_display = f"${price:.2f}"
            if tx['is_adjusted'] and tx['original_price'] != price:
                price_display = f"${price:.2f} (was ${tx['original_price']:.2f})"
            
            print(f"{tx['date']:<12} {qty:>10,.2f} {price_display:>14} ${cost:>10,.2f} {running_qty:>10,.2f} ${running_cost:>10,.2f} {note}")
        
        # Résumé du calcul
        print(f"\n📊 RÉSUMÉ DU CALCUL:")
        print("-" * 80)
        print(f"   Total transactions:     {len(transactions)}")
        print(f"\n   🟢 ACHATS (qty > 0):")
        print(f"      Quantité totale:     {buy_qty:>12,.2f}")
        print(f"      Coût total:          ${buy_cost:>11,.2f}")
        print(f"      Avg price (achats):  ${buy_cost/buy_qty if buy_qty != 0 else 0:>11,.4f}")
        print(f"\n   🔴 VENTES (qty < 0):")
        print(f"      Quantité totale:     {sell_qty:>12,.2f}")
        print(f"      Coût total:          ${sell_cost:>11,.2f}")
        print(f"      Avg price (ventes):  ${sell_cost/sell_qty if sell_qty != 0 else 0:>11,.4f}")
        print(f"\n   📈 POSITION FINALE (toutes transactions):")
        print(f"      Quantité nette:      {total_qty:>12,.2f}")
        print(f"      Coût net:            ${total_cost:>11,.2f}")
        print(f"      AVERAGE PRICE:       ${total_cost/total_qty if total_qty != 0 else 0:>11,.4f}")
        
        if abs(total_qty) > 0.01:
            print(f"\n   ✅ Statut: POSITION OUVERTE")
        else:
            print(f"\n   🔒 Statut: POSITION FERMÉE (qty ≈ 0)")
        
        # Explication du calcul
        print(f"\n📝 EXPLICATION:")
        print("-" * 80)
        if total_qty != 0:
            avg_formula = f"${total_cost:,.2f} / {total_qty:,.2f} = ${total_cost/total_qty:,.4f}"
            print(f"   Average Price = Total Cost / Total Quantity")
            print(f"                 = {avg_formula}")
        else:
            print("   Average Price = N/A (position fermée, quantité = 0)")
        
        # Avertissements potentiels
        print(f"\n⚠️  VÉRIFICATIONS:")
        print("-" * 80)
        if sell_qty > 0 and buy_qty > 0:
            print("   • Des achats ET des ventes sont présents")
            print("   • L'average price actuel est une moyenne pondérée NET")
            print("   • Si vous voulez le 'cost basis' des actions restantes,")
            print("     il faut utiliser une méthode FIFO/LIFO différente")
        
        if abs(total_qty) < buy_qty * 0.5:
            print(f"   • ⚠️  Attention: Vous avez vendu plus de 50% de votre position!")
            print(f"     La moitié des achats a été 'contrebalancée' par des ventes")
        
        # Ligne de séparation
        print("\n" + "─" * 100)
    
    conn.close()
    print(f"\n✅ Analyse terminée pour {len(symbol_transactions)} symboles")


def analyze_specific_symbol(symbol: str):
    """Analyse détaillée d'un symbole spécifique avec toutes les transactions"""
    analyze_position_calculation(symbol=symbol)


def show_calculation_methods():
    """Montre les différentes méthodes de calcul de l'average price"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MÉTHODES DE CALCUL DE L'AVERAGE PRICE                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

1️⃣  METHODE ACTUELLE (moyenne pondérée NETTE de toutes les transactions):
    
    Average Price = Σ(quantity × price) / Σ(quantity)
    
    ✓ Simple à calculer
    ✗ Peut donner des résultats contre-intuitifs si beaucoup de ventes
    ✗ Ne reflète pas le "cost basis" réel des actions restantes

    Exemple problématique:
    - Achat 100 actions @ $10 = $1000
    - Vente 50 actions @ $15 = -$750 (gain de $250)
    - Achat 50 actions @ $20 = $1000
    
    Calcul actuel:
    - Qty totale: 100 - 50 + 50 = 100
    - Coût total: $1000 - $750 + $1000 = $1250
    - Avg price: $1250 / 100 = $12.50
    
    Mais le "cost basis" réel des 100 actions restantes est:
    - 50 actions @ $20 (dernier achat) = $1000
    - Les 50 premières ont été vendues avec gain
    - Donc avg price devrait être ~$20 pour les actions restantes!

2️⃣  METHODE FIFO (First In First Out) - plus précise pour le cost basis:
    
    On suppose que les premières actions achetées sont les premières vendues.
    L'average price = coût des actions restantes / nombre d'actions restantes
    
    Exemple avec FIFO:
    - Achat 100 @ $10
    - Vente 50 @ $15 (vend les 50 premières achetées @ $10)
    - Achat 50 @ $20
    - Actions restantes: 50 @ $10 + 50 @ $20 = $1500 / 100 = $15.00

3️⃣  METHODE DES ACHATS UNIQUEMENT:
    
    Average Price = Σ(achats × price) / Σ(achats)
    
    Ignorer complètement les ventes dans le calcul.
    
    Dans l'exemple:
    - Achat 100 @ $10 + Achat 50 @ $20 = $2000 / 150 = $13.33

4️⃣  METHODE DU DERNIER COÛT:
    
    Average Price = prix du dernier achat
    
    Dans l'exemple: $20.00

╔══════════════════════════════════════════════════════════════════════════════╗
║                        QUELLE MÉTHODE UTILISER?                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

• Pour le P&L réalisé → Méthode FIFO (obligatoire fiscalement)
• Pour le "cost basis" des actions restantes → FIFO ou LIFO
• Pour une vue simple du portefeuille → Moyenne pondérée (actuelle)
• Pour l'average price "intuitif" → Méthode des achats uniquement

""")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyse détaillée du calcul des positions')
    parser.add_argument('--symbol', '-s', help='Analyser un symbole spécifique')
    parser.add_argument('--all', '-a', action='store_true', help='Montrer tous les symboles (même fermés)')
    parser.add_argument('--methods', '-m', action='store_true', help='Expliquer les différentes méthodes de calcul')
    
    args = parser.parse_args()
    
    if args.methods:
        show_calculation_methods()
    elif args.symbol:
        analyze_specific_symbol(args.symbol)
    else:
        # Par défaut: analyser les positions ouvertes
        print("\nUsage:")
        print("  python analyze_position_calculation.py --symbol SOFI    # Analyser SOFI")
        print("  python analyze_position_calculation.py --all              # Tous les symboles")
        print("  python analyze_position_calculation.py --methods          # Expliquer les méthodes")
        print("\nAnalysons quelques symboles en exemple:\n")
        
        # Analyser quelques symboles populaires
        for sym in ['SOFI', 'TSLA', 'SGLD']:
            try:
                analyze_specific_symbol(sym)
            except Exception as e:
                print(f"❌ Erreur pour {sym}: {e}")
