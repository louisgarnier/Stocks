export interface TxRow {
  asset_category: string | null;
}

export function visibleTransactions<T extends TxRow>(rows: T[], showCash: boolean): T[] {
  return showCash ? rows : rows.filter(r => r.asset_category !== 'CASH');
}

export interface SelectableTxRow extends TxRow {
  transaction_id: string;
}

/** IDs of only the rows the Journal table actually renders (visible-rows-only),
 * so "select all" can never select a hidden CASH row the user never saw. */
export function selectableIds<T extends SelectableTxRow>(rows: T[], showCash: boolean): string[] {
  return visibleTransactions(rows, showCash).map(r => r.transaction_id);
}
