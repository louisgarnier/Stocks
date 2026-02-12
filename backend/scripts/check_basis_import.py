#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Vérifier les transactions SOFI avec basis
cursor.execute('SELECT COUNT(*) FROM transactions WHERE symbol="SOFI" AND basis != 0')
count_with_basis = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM transactions WHERE symbol="SOFI"')
total_sofi = cursor.fetchone()[0]

print(f'Transactions SOFI: {total_sofi}')
print(f'Avec basis != 0: {count_with_basis}')

if count_with_basis > 0:
    print('\nExemples de transactions avec basis:')
    cursor.execute('SELECT trade_date, quantity, t_price, basis FROM transactions WHERE symbol="SOFI" AND basis != 0 ORDER BY trade_date LIMIT 10')
    print('Date         Qty      Price     Basis')
    print('-' * 50)
    for row in cursor.fetchall():
        print(f'{row[0]:<12} {row[1]:>8.2f} ${row[2]:>8.2f} ${row[3]:>10.2f}')
else:
    print('\nAucune transaction avec basis != 0')
    print('\nVérifions les dernières transactions importées:')
    cursor.execute('SELECT trade_date, quantity, t_price, basis, source_file FROM transactions WHERE symbol="SOFI" ORDER BY created_at DESC LIMIT 5')
    print('\nDate         Qty      Price     Basis      Source')
    print('-' * 70)
    for row in cursor.fetchall():
        print(f'{row[0]:<12} {row[1]:>8.2f} ${row[2]:>8.2f} ${row[3]:>10.2f} {row[4]}')

conn.close()
