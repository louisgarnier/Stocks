export type BreakoutDirection = 'none' | 'bullish' | 'bearish'
export type Verdict = 'strong_buy' | 'buy' | 'watch' | 'neutral' | 'avoid'

export interface ScreenerRow {
  symbol: string
  // Contract says these are never null, but live data currently has ~15 rows
  // with null name/sector (recently-added symbols pending metadata backfill) —
  // treat as nullable defensively.
  name: string | null
  sector: string | null
  signal_date: string | null
  momentum_5d: number | null
  momentum_20d: number | null
  momentum_60d: number | null
  multi_factor_momentum: number | null
  above_ma50: boolean | number | null
  above_ma200: boolean | number | null
  ma_cross_status: string | null
  trend_aligned: boolean | number | null
  is_8d_consec: boolean | number | null
  volume_spike: boolean | number | null
  dist_from_52w_high: number | null
  near_52w_high: boolean | number | null
  consolidation_quality: number | null
  support_level: number | null
  resistance_level: number | null
  consolidation_range_pct: number | null
  consolidation_timeframe: string | null
  breakout_status: string | null
  breakout_direction: BreakoutDirection | null
  breakout_strength: number | null
  breakout_volume_ratio: number | null
  breakout_date: string | null
  gross_margin: number | null
  roe: number | null
  roic: number | null
  levered_fcf_margin: number | null
  interest_cover: number | null
  eps_5y_growth: number | null
  gates_passed: number | null
  gates_total: number | null
  market_cap: number | null
  trailing_pe: number | null
  score_tech: number | null
  score_fund: number | null
  score_total: number | null
  verdict: Verdict | null
}

export interface ScreenerOverviewResponse {
  rows: ScreenerRow[]
  count: number
}

export async function fetchOverview(): Promise<ScreenerOverviewResponse> {
  const res = await fetch('/api/proxy/api/screener/overview')
  if (!res.ok) throw new Error(`fetchOverview: HTTP ${res.status}`)
  return res.json()
}

/** Fundamentals (gross_margin, roe, roic, levered_fcf_margin) are stored as 0-1 fractions. */
export function formatPct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${Math.round(v * 100)}%`
}

/** momentum_* fields are already percent values (12.0 => +12.0%). */
export function formatMomentum(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(1)}%`
}

export function momentumColor(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '#94a3b8'
  return v >= 0 ? '#15803d' : '#dc2626'
}

const VERDICT_LABELS: Record<Verdict, string> = {
  strong_buy: 'Strong buy',
  buy: 'Buy',
  watch: 'Watch',
  neutral: 'Neutral',
  avoid: 'Avoid',
}

export function verdictLabel(v: Verdict | null | undefined): string {
  if (!v) return '—'
  return VERDICT_LABELS[v] ?? v
}

export function verdictColors(v: Verdict | null | undefined): { bg: string; fg: string } {
  switch (v) {
    case 'strong_buy':
      return { bg: '#d1fae5', fg: '#065f46' }
    case 'buy':
      return { bg: '#e0e7ff', fg: '#4338ca' }
    case 'watch':
      return { bg: '#fef3c7', fg: '#92400e' }
    case 'neutral':
      return { bg: '#f1f5f9', fg: '#64748b' }
    case 'avoid':
      return { bg: '#fef2f2', fg: '#991b1b' }
    default:
      return { bg: '#f1f5f9', fg: '#94a3b8' }
  }
}

export interface BreakoutBadge {
  label: string
  bg: string
  fg: string
}

export function breakoutBadge(
  row: Pick<ScreenerRow, 'breakout_direction' | 'breakout_strength'>,
): BreakoutBadge {
  if (row.breakout_direction === 'bullish') {
    const strength =
      row.breakout_strength !== null && row.breakout_strength !== undefined
        ? ` · ${row.breakout_strength.toFixed(2)}`
        : ''
    return { label: `▲ Up${strength}`, bg: '#dcfce7', fg: '#15803d' }
  }
  if (row.breakout_direction === 'bearish') {
    return { label: '▼ Down', bg: '#fee2e2', fg: '#dc2626' }
  }
  return { label: '— none', bg: '#f1f5f9', fg: '#94a3b8' }
}

export type ScoreTier = 'hi' | 'mid' | 'lo' | 'bad'

export function scoreTier(score: number | null | undefined): { tier: ScoreTier; color: string } {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return { tier: 'bad', color: '#94a3b8' }
  }
  if (score >= 85) return { tier: 'hi', color: '#16a34a' }
  if (score >= 70) return { tier: 'mid', color: '#4f46e5' }
  if (score >= 55) return { tier: 'lo', color: '#d97706' }
  return { tier: 'bad', color: '#94a3b8' }
}

/**
 * True when the row's breakout is bullish and dated within the last 3 calendar
 * days (inclusive) of `today`.
 */
export function brokeOutLast3d(
  row: Pick<ScreenerRow, 'breakout_direction' | 'breakout_date'>,
  today: Date = new Date(),
): boolean {
  if (row.breakout_direction !== 'bullish' || !row.breakout_date) return false
  const bo = new Date(`${row.breakout_date}T00:00:00`)
  if (Number.isNaN(bo.getTime())) return false
  const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const boMidnight = new Date(bo.getFullYear(), bo.getMonth(), bo.getDate())
  const diffDays = Math.round((todayMidnight.getTime() - boMidnight.getTime()) / 86400000)
  return diffDays >= 0 && diffDays <= 3
}

/** Case-insensitive match against symbol or name; tolerates a null name/symbol. */
export function matchesSearch(
  row: Pick<ScreenerRow, 'symbol' | 'name'>,
  query: string,
): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const symbol = (row.symbol ?? '').toLowerCase()
  const name = (row.name ?? '').toLowerCase()
  return symbol.includes(q) || name.includes(q)
}

export type SortDir = 'asc' | 'desc'

/** Sorts rows by `key`; nulls/undefined always sort last regardless of direction. */
export function sortRows<T>(rows: T[], key: keyof T, dir: SortDir): T[] {
  const sign = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    const aNull = av === null || av === undefined
    const bNull = bv === null || bv === undefined
    if (aNull && bNull) return 0
    if (aNull) return 1
    if (bNull) return -1
    if (typeof av === 'string' && typeof bv === 'string') {
      return av.localeCompare(bv) * sign
    }
    if (av === bv) return 0
    return (av < bv ? -1 : 1) * sign
  })
}
