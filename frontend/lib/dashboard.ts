// Types + fetch helper for the Dashboard tab (Epic V / Task 5).
// Mirrors backend/api/routes/dashboard.py `GET /api/dashboard` verbatim.

export interface AsOf {
  prices: string | null
  signals: string | null
  fundamentals: string | null
  ibkr: string | null
}

export interface NetWorth {
  value_eur: number
  day_change_eur: number
  day_change_pct: number
  unrealized_pnl_eur: number | null
  positions: number
  usd_exposure_pct: number
}

export interface AllocationItem {
  label: string
  value_eur: number
  pct: number
}

export interface Allocation {
  sector: AllocationItem[]
  position: AllocationItem[]
  currency: AllocationItem[]
}

export type AllocationMode = keyof Allocation

export interface PerfPoint {
  date: string
  value: number
}

export interface Performance {
  portfolio: PerfPoint[]
  benchmark: PerfPoint[]
}

export interface Mover {
  symbol: string
  close: number
  prev_close: number
  change_pct: number
  day_pnl_eur: number
}

export interface SellAction {
  symbol: string
  quantity: number
  return_pct: number | null
  fired: string[]
  n_fired: number
}

export interface BuyAction {
  symbol: string
  name: string | null
  verdict: string | null
  score_total: number | null
  gates_passed: number | null
}

export interface Actions {
  sell: SellAction[]
  buy: BuyAction[]
}

export interface DashboardPayload {
  as_of: AsOf
  fx_rate: number
  net_worth: NetWorth
  allocation: Allocation
  performance: Performance
  movers: Mover[]
  actions: Actions
}

export type DashboardWindow = '1M' | '3M' | '6M' | '1Y' | 'Max'

export const DASHBOARD_WINDOWS: DashboardWindow[] = ['1M', '3M', '6M', '1Y', 'Max']

export async function fetchDashboard(window: DashboardWindow): Promise<DashboardPayload> {
  const res = await fetch(`/api/proxy/api/dashboard?window=${window}`)
  if (!res.ok) throw new Error(`fetchDashboard: HTTP ${res.status}`)
  return res.json()
}

export const eurFmt = new Intl.NumberFormat('en-IE', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

export function formatEur(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return eurFmt.format(v)
}

export function formatSignedEur(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${v >= 0 ? '+' : ''}${eurFmt.format(v)}`
}

const eurCompactFmt = new Intl.NumberFormat('en-IE', {
  style: 'currency',
  currency: 'EUR',
  notation: 'compact',
  maximumFractionDigits: 1,
})

export function formatEurCompact(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return eurCompactFmt.format(v)
}

export function formatPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(digits)}%`
}

/** Renders an ISO date or timestamp as a short relative-time label, e.g. "3h ago", "07-09". */
export function relativeStaleness(iso: string | null): { label: string; level: 'fresh' | 'stale' | 'unknown' } {
  if (!iso) return { label: 'no data', level: 'unknown' }
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return { label: iso, level: 'unknown' }
  const hours = (Date.now() - then) / 36e5
  const level: 'fresh' | 'stale' = hours <= 24 ? 'fresh' : 'stale'
  if (hours < 1) return { label: '<1h', level }
  if (hours < 48) return { label: `${Math.round(hours)}h`, level }
  const days = Math.round(hours / 24)
  return { label: `${days}d`, level }
}
