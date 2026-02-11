"""
Investigation du bug d'import ATRA - quantité et prix décalés
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Récupérer les 2 transactions ATRA suspectes
tx_ids = ['202602105255110786', '202602105254898261']

print('🔍 INVESTIGATION TRANSACTIONS ATRA')
print('=' * 80)

for tx_id in tx_ids:
    cursor.execute('''
        SELECT transaction_id, symbol, trade_date, quantity, t_price, 
               currency, comm_fee, proceeds, basis
        FROM transactions
        WHERE transaction_id = ?
    ''', (tx_id,))
    
    row = cursor.fetchone()
    if row:
        print(f'\nTransaction ID: {row[0]}')
        print(f'Symbol: {row[1]}')
        print(f'Date: {row[2]}')
        print(f'Quantity: {row[3]}')
        print(f'Price: {row[4]}')
        print(f'Currency: {row[5]}')
        print(f'Comm/Fee: {row[6]}')
        print(f'Proceeds: {row[7]}')
        print(f'Basis: {row[8]}')
    else:
        print(f'\n❌ Transaction {tx_id} non trouvée')

# Toutes les transactions ATRA
print('\n' + '=' * 80)
print('TOUTES LES TRANSACTIONS ATRA:')
print('=' * 80)

cursor.execute('''
    SELECT transaction_id, trade_date, quantity, t_price, proceeds, comm_fee, basis
    FROM transactions
    WHERE symbol = 'ATRA'
    ORDER BY trade_date
''')

for row in cursor.fetchall():
    print(f'\nDate: {row[1]}')
    print(f'Quantity: {row[2]}')
    print(f'Price: {row[3]}')
    print(f'Proceeds: {row[4]}')
    print(f'Comm/Fee: {row[5]}')
    print(f'Basis: {row[6]}')
    print(f'TX ID: {row[0][:30]}...')

# Vérifier updated_transactions
print('\n' + '=' * 80)
print('UPDATED TRANSACTIONS ATRA:')
print('=' * 80)

cursor.execute('''
    SELECT ut.transaction_id, t.trade_date, ut.updated_quantity, ut.updated_price,
           ut.split_ratio, t.quantity as orig_qty, t.t_price as orig_price
    FROM updated_transactions ut
    JOIN transactions t ON ut.transaction_id = t.transaction_id
    WHERE ut.symbol = 'ATRA'
    ORDER BY t.trade_date
''')

rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f'\nDate: {row[1]}')
        print(f'Original: {row[5]:.2f} @ ${row[6]:.2f}')
        print(f'Updated: {row[2]:.2f} @ ${row[3]:.2f}')
        print(f'Ratio: {row[4]}')
        print(f'TX ID: {row[0][:30]}...')
else:
    print('Aucune updated transaction')

conn.close()
