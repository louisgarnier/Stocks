import {
  loadVisibleColumns,
  saveVisibleColumns,
  DEFAULT_VISIBLE,
  ALL_COLUMNS,
} from '../lib/research'

describe('research column persistence', () => {
  beforeEach(() => localStorage.clear())

  test('defaults when nothing saved', () => {
    expect(loadVisibleColumns()).toEqual(DEFAULT_VISIBLE)
  })

  test('round-trips saved columns', () => {
    saveVisibleColumns(['symbol', 'rsi_14', 'verdict'])
    expect(loadVisibleColumns()).toEqual(['symbol', 'rsi_14', 'verdict'])
  })

  test('falls back to defaults on corrupt storage', () => {
    localStorage.setItem('research.columns.v1', 'not-json{')
    expect(loadVisibleColumns()).toEqual(DEFAULT_VISIBLE)
  })

  test('every default column exists in ALL_COLUMNS', () => {
    const keys = new Set(ALL_COLUMNS.map((c) => c.key))
    for (const k of DEFAULT_VISIBLE) expect(keys.has(k)).toBe(true)
  })

  // CSV↔table parity: every field emitted by /api/research/overview?format=csv
  // must be selectable in the grid. Guards against fields drifting into the
  // export but being un-addable as a column (the original "gaps" complaint).
  const CSV_FIELDS = [
    'symbol', 'name', 'sector', 'price', 'indicator_date', 'ma_50', 'ma_100',
    'ma_150', 'ma_200', 'bb_upper_20', 'bb_lower_20', 'bb_width', 'rsi_14',
    'mrsi', 'atr_14', 'volume_ma_20', 'signal_date', 'momentum_5d',
    'momentum_20d', 'momentum_60d', 'multi_factor_momentum', 'above_ma50',
    'above_ma200', 'ma_cross_status', 'trend_aligned', 'is_8d_consec',
    'volume_spike', 'dist_from_52w_high', 'near_52w_high', 'consolidation_quality',
    'support_level', 'resistance_level', 'consolidation_range_pct',
    'consolidation_timeframe', 'breakout_status', 'breakout_direction',
    'breakout_strength', 'breakout_volume_ratio', 'breakout_date',
    'breakout_support', 'breakout_resistance', 'breakout_range_pct',
    'breakout_duration_days', 'gross_margin', 'roe', 'roic', 'levered_fcf_margin',
    'interest_cover', 'eps_5y_growth', 'gates_passed', 'gates_total',
    'market_cap', 'trailing_pe', 'score_tech', 'score_fund', 'score_total',
    'verdict',
  ]

  test('every CSV export field is selectable in the grid', () => {
    const keys = new Set(ALL_COLUMNS.map((c) => c.key))
    const missing = CSV_FIELDS.filter((f) => !keys.has(f))
    expect(missing).toEqual([])
  })

  test('no duplicate column keys', () => {
    const keys = ALL_COLUMNS.map((c) => c.key)
    expect(keys.length).toBe(new Set(keys).size)
  })
})
