export interface TxRow {
  asset_category: string | null;
}

export function visibleTransactions<T extends TxRow>(rows: T[], showCash: boolean): T[] {
  return showCash ? rows : rows.filter(r => r.asset_category !== 'CASH');
}
