import { visibleTransactions } from '@/lib/journal';

test('hides CASH rows by default, shows with toggle', () => {
  const rows = [{ asset_category: 'CASH' }, { asset_category: 'STK' }, { asset_category: null }];
  expect(visibleTransactions(rows, false)).toHaveLength(2);
  expect(visibleTransactions(rows, true)).toHaveLength(3);
});
