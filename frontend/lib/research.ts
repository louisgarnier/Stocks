import type { ScreenerRow } from './screener'

// Unified research row = screener fields + latest close price + latest indicators.
export interface ResearchRow extends ScreenerRow {
  price: number | null
  indicator_date: string | null
  ma_50: number | null
  ma_100: number | null
  ma_150: number | null
  ma_200: number | null
  bb_upper_20: number | null
  bb_lower_20: number | null
  bb_width: number | null
  rsi_14: number | null
  mrsi: number | null
  atr_14: number | null
  volume_ma_20: number | null
}

export type ColAlign = 'l' | 'r'
export interface ColumnDef {
  key: string
  label: string
  group: string
  align: ColAlign
}

// Every column available in the grid, grouped. The "Columns" menu is built from this.
export const ALL_COLUMNS: ColumnDef[] = [
  { key: 'symbol', label: 'Symbol', group: 'Identity', align: 'l' },
  { key: 'name', label: 'Name', group: 'Identity', align: 'l' },
  { key: 'sector', label: 'Sector', group: 'Identity', align: 'l' },
  { key: 'price', label: 'Price', group: 'Price', align: 'r' },
  { key: 'ma_50', label: 'MA50', group: 'Indicators', align: 'r' },
  { key: 'ma_200', label: 'MA200', group: 'Indicators', align: 'r' },
  { key: 'rsi_14', label: 'RSI', group: 'Indicators', align: 'r' },
  { key: 'mrsi', label: 'MRSI', group: 'Indicators', align: 'r' },
  { key: 'atr_14', label: 'ATR', group: 'Indicators', align: 'r' },
  { key: 'bb_width', label: 'BB width', group: 'Indicators', align: 'r' },
  { key: 'momentum_60d', label: 'Mom 60d', group: 'Momentum', align: 'r' },
  { key: 'momentum_20d', label: 'Mom 20d', group: 'Momentum', align: 'r' },
  { key: 'momentum_5d', label: 'Mom 5d', group: 'Momentum', align: 'r' },
  { key: 'ma_cross_status', label: 'MA cross', group: 'Momentum', align: 'l' },
  { key: 'dist_from_52w_high', label: '% from 52wH', group: 'Momentum', align: 'r' },
  { key: 'support_level', label: 'Support', group: 'Consolidation', align: 'r' },
  { key: 'resistance_level', label: 'Resist.', group: 'Consolidation', align: 'r' },
  { key: 'consolidation_quality', label: 'Consol.', group: 'Consolidation', align: 'r' },
  { key: 'consolidation_range_pct', label: 'Consol. range %', group: 'Consolidation', align: 'r' },
  { key: 'breakout_status', label: 'Breakout', group: 'Breakout', align: 'l' },
  { key: 'breakout_strength', label: 'Breakout str', group: 'Breakout', align: 'r' },
  // bounds from the breakout detector's own consolidation pass (independent of
  // the Consolidation group's ZigZag detector)
  { key: 'breakout_support', label: 'Brk support', group: 'Breakout', align: 'r' },
  { key: 'breakout_resistance', label: 'Brk resist.', group: 'Breakout', align: 'r' },
  { key: 'breakout_range_pct', label: 'Brk range %', group: 'Breakout', align: 'r' },
  { key: 'breakout_duration_days', label: 'Brk days', group: 'Breakout', align: 'r' },
  { key: 'gross_margin', label: 'Gross M', group: 'Fundamentals', align: 'r' },
  { key: 'roe', label: 'ROE', group: 'Fundamentals', align: 'r' },
  { key: 'roic', label: 'ROIC', group: 'Fundamentals', align: 'r' },
  { key: 'gates_passed', label: 'Gates', group: 'Fundamentals', align: 'r' },
  { key: 'market_cap', label: 'Mkt cap', group: 'Fundamentals', align: 'r' },
  { key: 'trailing_pe', label: 'P/E', group: 'Fundamentals', align: 'r' },
  { key: 'score_tech', label: 'Tech', group: 'Score', align: 'r' },
  { key: 'score_fund', label: 'Fund', group: 'Score', align: 'r' },
  { key: 'score_total', label: 'Score', group: 'Score', align: 'r' },
  { key: 'verdict', label: 'Verdict', group: 'Score', align: 'r' },
]

// Accent colors for the grouped header row's bottom border, keyed by ColumnDef.group.
// Identity/Price/Fundamentals/Score are intentionally absent — they fall back to
// var(--border) in the UI.
export const GROUP_COLORS: Record<string, string> = {
  Momentum: '#5b9bd5',
  Indicators: '#8f7ee8',
  Breakout: '#d9a441',
  Consolidation: '#4fd08d',
}

// Default visible = the approved-mockup set (union of Screener + Browse Universe + key indicators).
export const DEFAULT_VISIBLE: string[] = [
  'symbol', 'price', 'rsi_14', 'ma_50', 'momentum_60d',
  'support_level', 'resistance_level', 'consolidation_quality', 'breakout_status',
  'roic', 'gates_passed', 'score_total', 'verdict',
]

const STORAGE_KEY = 'research.columns.v1'

export function loadVisibleColumns(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_VISIBLE
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length > 0) return parsed
    return DEFAULT_VISIBLE
  } catch {
    return DEFAULT_VISIBLE
  }
}

export function saveVisibleColumns(keys: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(keys))
  } catch {
    /* ignore quota / private-mode errors */
  }
}

export interface ResearchOverviewResponse {
  rows: ResearchRow[]
  count: number
}

export async function fetchResearchOverview(): Promise<ResearchRow[]> {
  const res = await fetch('/api/proxy/api/research/overview')
  if (!res.ok) throw new Error(`fetchResearchOverview: HTTP ${res.status}`)
  const body: ResearchOverviewResponse = await res.json()
  return body.rows
}

export interface ParamsResponse {
  key: string
  params: Record<string, number | number[]>
  defaults: Record<string, number | number[]>
}

export async function getConsolidationParams(): Promise<ParamsResponse> {
  const res = await fetch('/api/proxy/api/screener/settings/consolidation_params')
  if (!res.ok) throw new Error(`getConsolidationParams: HTTP ${res.status}`)
  return res.json()
}

export async function putConsolidationParams(
  params: Record<string, number>,
): Promise<ParamsResponse> {
  const res = await fetch('/api/proxy/api/screener/settings/consolidation_params', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ params }),
  })
  if (!res.ok) throw new Error(`putConsolidationParams: HTTP ${res.status}`)
  return res.json()
}
