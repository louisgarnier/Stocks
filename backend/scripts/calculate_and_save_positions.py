"""
Script de calcul et sauvegarde des positions en base de données.
Utilise la logique de la vue (updated_transactions en priorité, sinon transactions originales)
Exclut les symboles Forex (contenant '.')
"""

import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import logger


def calculate_and_save_positions() -> dict:
    """
    Calcule les positions pour tous les symboles et les sauvegarde en base.
    
    Returns:
        Dict avec les résultats du calcul
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    logger.info("📊 Calculating positions...")
    
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
            CASE WHEN ut.transaction_id IS NOT NULL THEN 1 ELSE 0 END as is_adjusted
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
        'transaction_count': 0,
        'adjusted_count': 0
    })
    
    for row in all_transactions:
        symbol = row[0]
        quantity = row[3]
        price = row[4]
        is_adjusted = row[7]
        
        positions[symbol]['total_quantity'] += quantity
        positions[symbol]['total_cost'] += (quantity * price)
        positions[symbol]['transaction_count'] += 1
        
        if is_adjusted:
            positions[symbol]['adjusted_count'] += 1
    
    # Supprimer les anciennes positions et insérer les nouvelles
    cursor.execute("DELETE FROM positions")
    
    now = datetime.now().isoformat()
    inserted = 0
    
    for symbol, pos in positions.items():
        total_qty = pos['total_quantity']
        total_cost = pos['total_cost']
        avg_price = total_cost / total_qty if total_qty != 0 else 0
        
        cursor.execute("""
            INSERT INTO positions (symbol, quantity, average_price, total_cost, transaction_count, adjusted_count, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol,
            round(total_qty, 4),
            round(avg_price, 4),
            round(total_cost, 2),
            pos['transaction_count'],
            pos['adjusted_count'],
            now
        ))
        inserted += 1
    
    conn.commit()
    conn.close()
    
    # Calculer les stats
    open_positions = sum(1 for pos in positions.values() if abs(pos['total_quantity']) > 0.01)
    closed_positions = len(positions) - open_positions
    
    logger.info(f"✅ Positions saved: {inserted} symbols ({open_positions} open, {closed_positions} closed)")
    
    return {
        "success": True,
        "total_symbols": len(positions),
        "open_positions": open_positions,
        "closed_positions": closed_positions,
        "last_updated": now
    }


def get_positions() -> dict:
    """
    Récupère les positions depuis la base de données.
    
    Returns:
        Dict avec les positions ouvertes et fermées
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT symbol, quantity, average_price, total_cost, transaction_count, adjusted_count, last_updated
        FROM positions
        ORDER BY symbol
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    open_positions = []
    closed_positions = []
    
    for row in rows:
        position = {
            "symbol": row[0],
            "quantity": row[1],
            "average_price": row[2],
            "total_cost": row[3],
            "transaction_count": row[4],
            "adjusted_count": row[5],
            "last_updated": row[6]
        }
        
        if abs(row[1]) > 0.01:
            open_positions.append(position)
        else:
            closed_positions.append(position)
    
    # Trier les positions ouvertes par valeur totale décroissante
    open_positions.sort(key=lambda x: abs(x['total_cost']), reverse=True)
    
    return {
        "open_positions": open_positions,
        "closed_positions": closed_positions,
        "total_symbols": len(rows),
        "open_count": len(open_positions),
        "closed_count": len(closed_positions),
        "last_updated": rows[0][6] if rows else None
    }


if __name__ == "__main__":
    result = calculate_and_save_positions()
    print(f"\n📊 Résultat: {result}")
