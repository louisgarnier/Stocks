// Types + fetch helper for the Dashboard tab (Epic V / Task 5).
// Mirrors backend/api/routes/dashboard.py `GET /api/dashboard` verbatim.

export interface AsOfEntry {
  date: string | null
  checked_at: string | null
  level: 'fresh' | 'stale' | 'unknown'
}

export interface AsOf {
  prices: AsOfEntry
  signals: AsOfEntry
  fundamentals: AsOfEntry
  ibkr: AsOfEntry
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
  fx_rate: number | null
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

/** "2026-07-10" or full ISO timestamp → "07-10"; null → "—". */
export function shortDate(iso: string | null): string {
  if (!iso) return '—'
  const m = iso.match(/^\d{4}-(\d{2})-(\d{2})/)
  return m ? `${m[1]}-${m[2]}` : iso
}

/** Relative time since an ISO timestamp, e.g. "<1h", "2h ago", "3d ago". */
export function relativeTime(iso: string | null): string {
  if (!iso) return 'never'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return iso
  const hours = (Date.now() - then) / 36e5
  if (hours < 1) return '<1h'
  if (hours < 48) return `${Math.round(hours)}h ago`
  return `${Math.round(hours / 24)}d ago`
}
