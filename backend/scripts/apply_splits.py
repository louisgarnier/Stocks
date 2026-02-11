"""
Apply Splits Script

Applique les splits/spinoffs aux transactions et crée les updated_transactions.
Script simple et séparé du fetch CA.
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection
from backend.api.utils.logger import logger


def apply_all_splits() -> dict:
    """
    Applique tous les splits aux transactions concernées.
    
    Returns:
        Dict avec le nombre de transactions mises à jour
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updated_count = 0
    symbols_processed = []
    
    # 1. Récupérer tous les splits/spinoffs
    cursor.execute("""
        SELECT DISTINCT sec_id
        FROM corporate_actions
        WHERE ca_type IN ('split', 'spinoff')
    """)
    symbols_with_splits = [row[0] for row in cursor.fetchall()]
    
    if not symbols_with_splits:
        logger.info("⏭️  Aucun split/spinoff trouvé en base")
        conn.close()
        return {'updated': 0, 'symbols': []}
    
    logger.info(f"🔄 Application des splits pour {len(symbols_with_splits)} symbole(s)...")
    
    # 2. Pour chaque symbole avec des splits
    for symbol in symbols_with_splits:
        # Récupérer les splits pour ce symbole
        cursor.execute("""
            SELECT id, ex_date, split_ratio, ca_type
            FROM corporate_actions
            WHERE sec_id = ? AND ca_type IN ('split', 'spinoff')
            ORDER BY ex_date ASC
        """, (symbol,))
        splits = cursor.fetchall()
        
        if not splits:
            continue
        
        # Récupérer les transactions pour ce symbole
        cursor.execute("""
            SELECT transaction_id, trade_date, quantity, t_price
            FROM transactions
            WHERE symbol = ?
            ORDER BY trade_date ASC
        """, (symbol,))
        transactions = cursor.fetchall()
        
        if not transactions:
            logger.info(f"   ⏭️  {symbol}: aucune transaction")
            continue
        
        # Supprimer les anciennes updated_transactions pour ce symbole (idempotent)
        cursor.execute("DELETE FROM updated_transactions WHERE symbol = ?", (symbol,))
        
        symbol_updated = 0
        
        # 3. Pour chaque transaction, appliquer les splits applicables
        for tx in transactions:
            tx_id, trade_date, original_qty, original_price = tx
            
            # Calculer le ratio cumulé de tous les splits après cette transaction
            cumulative_ratio = 1.0
            applicable_splits = []
            
            for split in splits:
                split_id, ex_date, split_ratio, ca_type = split
                
                # Le split s'applique si la transaction est AVANT la date ex
                if trade_date < ex_date:
                    cumulative_ratio *= split_ratio
                    applicable_splits.append({
                        'id': split_id,
                        'ex_date': ex_date,
                        'ratio': split_ratio,
                        'ca_type': ca_type
                    })
            
            # Si aucun split applicable, pas besoin de créer une updated_transaction
            if cumulative_ratio == 1.0:
                continue
            
            # Calculer les nouvelles valeurs
            updated_qty = original_qty * cumulative_ratio
            updated_price = original_price / cumulative_ratio if cumulative_ratio != 0 else original_price
            
            # Utiliser le dernier split applicable pour les métadonnées
            last_split = applicable_splits[-1]
            
            # Insérer dans updated_transactions
            cursor.execute("""
                INSERT INTO updated_transactions (
                    transaction_id, symbol, trade_date,
                    original_quantity, original_price,
                    updated_quantity, updated_price,
                    split_ratio, ca_id, ca_type, ca_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx_id, symbol, trade_date,
                original_qty, original_price,
                updated_qty, updated_price,
                cumulative_ratio, last_split['id'], last_split['ca_type'], last_split['ex_date']
            ))
            
            symbol_updated += 1
            updated_count += 1
        
        if symbol_updated > 0:
            symbols_processed.append(symbol)
            logger.info(f"   ✅ {symbol}: {symbol_updated} transaction(s) mise(s) à jour")
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Total: {updated_count} transaction(s) mise(s) à jour pour {len(symbols_processed)} symbole(s)")
    
    return {
        'updated': updated_count,
        'symbols': symbols_processed
    }


if __name__ == "__main__":
    result = apply_all_splits()
    print(f"\n📊 Résultat: {result['updated']} transactions mises à jour")
    if result['symbols']:
        print(f"   Symboles: {', '.join(result['symbols'])}")
