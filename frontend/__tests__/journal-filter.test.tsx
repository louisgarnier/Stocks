import { visibleTransactions, selectableIds } from '@/lib/journal';

test('hides CASH rows by default, shows with toggle', () => {
  const rows = [{ asset_category: 'CASH' }, { asset_category: 'STK' }, { asset_category: null }];
  expect(visibleTransactions(rows, false)).toHaveLength(2);
  expect(visibleTransactions(rows, true)).toHaveLength(3);
});

test('selectableIds excludes hidden CASH rows so select-all cannot select an unseen row', () => {
  const rows = [
    { transaction_id: 'tx-1', asset_category: 'CASH', symbol: 'EUR.USD' },
    { transaction_id: 'tx-2', asset_category: 'STK', symbol: 'AAPL' },
    { transaction_id: 'tx-3', asset_category: 'CASH', symbol: 'EUR.USD' },
    { transaction_id: 'tx-4', asset_category: null, symbol: 'MSFT' },
  ];
  const idsWithCashHidden = selectableIds(rows, false);
  expect(idsWithCashHidden).toEqual(['tx-2', 'tx-4']);
  expect(idsWithCashHidden).not.toContain('tx-1');
  expect(idsWithCashHidden).not.toContain('tx-3');

  const idsWithCashShown = selectableIds(rows, true);
  expect(idsWithCashShown).toEqual(['tx-1', 'tx-2', 'tx-3', 'tx-4']);
});
