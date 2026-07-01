import {
  brokeOutLast3d,
  formatPct,
  formatMomentum,
  verdictLabel,
  breakoutBadge,
  matchesSearch,
  scoreTier,
  sortRows,
  type ScreenerRow,
} from '../lib/screener'

const baseRow = (overrides: Partial<ScreenerRow> = {}): ScreenerRow => ({
  symbol: 'AAPL',
  name: 'Apple Inc',
  sector: 'Hardware',
  signal_date: '2026-06-30',
  momentum_5d: null,
  momentum_20d: null,
  momentum_60d: null,
  multi_factor_momentum: null,
  above_ma50: null,
  above_ma200: null,
  ma_cross_status: null,
  trend_aligned: null,
  is_8d_consec: null,
  volume_spike: null,
  dist_from_52w_high: null,
  near_52w_high: null,
  consolidation_quality: null,
  support_level: null,
  resistance_level: null,
  consolidation_range_pct: null,
  consolidation_timeframe: null,
  breakout_status: null,
  breakout_direction: null,
  breakout_strength: null,
  breakout_volume_ratio: null,
  breakout_date: null,
  gross_margin: null,
  roe: null,
  roic: null,
  levered_fcf_margin: null,
  interest_cover: null,
  eps_5y_growth: null,
  gates_passed: null,
  gates_total: null,
  market_cap: null,
  trailing_pe: null,
  score_tech: null,
  score_fund: null,
  score_total: null,
  verdict: null,
  ...overrides,
})

describe('brokeOutLast3d', () => {
  const today = new Date(2026, 6, 1) // 2026-07-01 local

  it('is true for a bullish row dated today', () => {
    const row = baseRow({ breakout_direction: 'bullish', breakout_date: '2026-07-01' })
    expect(brokeOutLast3d(row, today)).toBe(true)
  })

  it('is true for a bullish row dated exactly 3 days ago (inclusive)', () => {
    const row = baseRow({ breakout_direction: 'bullish', breakout_date: '2026-06-28' })
    expect(brokeOutLast3d(row, today)).toBe(true)
  })

  it('is false for a bullish row dated 5 days ago', () => {
    const row = baseRow({ breakout_direction: 'bullish', breakout_date: '2026-06-26' })
    expect(brokeOutLast3d(row, today)).toBe(false)
  })

  it('is false for a bearish row dated today', () => {
    const row = baseRow({ breakout_direction: 'bearish', breakout_date: '2026-07-01' })
    expect(brokeOutLast3d(row, today)).toBe(false)
  })

  it('is false when breakout_date is null', () => {
    const row = baseRow({ breakout_direction: 'bullish', breakout_date: null })
    expect(brokeOutLast3d(row, today)).toBe(false)
  })
})

describe('formatPct (fraction -> percent)', () => {
  it('formats 0.73 as "73%"', () => {
    expect(formatPct(0.73)).toBe('73%')
  })

  it('formats null as an em-dash', () => {
    expect(formatPct(null)).toBe('—')
  })

  it('formats 0 as "0%" (not em-dash)', () => {
    expect(formatPct(0)).toBe('0%')
  })
})

describe('formatMomentum', () => {
  it('formats a positive value with a leading plus', () => {
    expect(formatMomentum(12.0)).toBe('+12.0%')
  })

  it('formats a negative value without a double sign', () => {
    expect(formatMomentum(-8.3)).toBe('-8.3%')
  })

  it('formats null as an em-dash', () => {
    expect(formatMomentum(null)).toBe('—')
  })
})

describe('verdictLabel', () => {
  it('title-cases known verdicts', () => {
    expect(verdictLabel('strong_buy')).toBe('Strong buy')
    expect(verdictLabel('avoid')).toBe('Avoid')
  })

  it('renders an em-dash for null', () => {
    expect(verdictLabel(null)).toBe('—')
  })
})

describe('breakoutBadge', () => {
  it('shows strength when bullish and strength present', () => {
    expect(breakoutBadge({ breakout_direction: 'bullish', breakout_strength: 0.82 }).label).toBe(
      '▲ Up · 0.82',
    )
  })

  it('shows "— none" for none/null direction', () => {
    expect(breakoutBadge({ breakout_direction: 'none', breakout_strength: null }).label).toBe(
      '— none',
    )
  })
})

describe('scoreTier', () => {
  it('tiers scores per the approved thresholds', () => {
    expect(scoreTier(91).tier).toBe('hi')
    expect(scoreTier(78).tier).toBe('mid')
    expect(scoreTier(60).tier).toBe('lo')
    expect(scoreTier(20).tier).toBe('bad')
    expect(scoreTier(null).tier).toBe('bad')
  })
})

describe('matchesSearch', () => {
  // Regression: live data has ~15 rows with null `name` despite the API
  // contract saying name/sector are never null (recently-added symbols
  // pending metadata backfill). A naive r.name.toLowerCase() call crashed
  // the whole grid ("Cannot read properties of null") when searching.
  it('does not throw when name is null and matches on symbol', () => {
    const row = { symbol: 'ACHR', name: null }
    expect(() => matchesSearch(row, 'achr')).not.toThrow()
    expect(matchesSearch(row, 'achr')).toBe(true)
  })

  it('returns false when name is null and query does not match symbol', () => {
    const row = { symbol: 'ACHR', name: null }
    expect(matchesSearch(row, 'archer aviation')).toBe(false)
  })

  it('matches case-insensitively on name', () => {
    expect(matchesSearch({ symbol: 'AAPL', name: 'Apple Inc' }, 'apple')).toBe(true)
  })

  it('empty query matches everything', () => {
    expect(matchesSearch({ symbol: 'AAPL', name: null }, '')).toBe(true)
  })
})

describe('sortRows', () => {
  it('sorts numeric fields with nulls last, both directions', () => {
    const rows = [
      baseRow({ symbol: 'A', score_total: 50 }),
      baseRow({ symbol: 'B', score_total: null }),
      baseRow({ symbol: 'C', score_total: 90 }),
    ]
    expect(sortRows(rows, 'score_total', 'desc').map((r) => r.symbol)).toEqual(['C', 'A', 'B'])
    expect(sortRows(rows, 'score_total', 'asc').map((r) => r.symbol)).toEqual(['A', 'C', 'B'])
  })

  it('sorts string fields alphabetically', () => {
    const rows = [baseRow({ symbol: 'ZZZ' }), baseRow({ symbol: 'AAA' })]
    expect(sortRows(rows, 'symbol', 'asc').map((r) => r.symbol)).toEqual(['AAA', 'ZZZ'])
  })
})
