export interface HoldingSignal {
  signal_type: string
  fired: boolean
  value: number | null
  threshold: number | null
  last_evaluated_at: string
}

export interface HoldingSignalsResponse {
  items: Array<HoldingSignal & { symbol: string }>
  count: number
}

export type SignalsBySymbol = Record<string, HoldingSignal[]>
export type PillColor = 'green' | 'yellow' | 'red' | 'gray'

const LABELS: Record<string, string> = {
  ma50_break: 'MA50 break',
  ma100_break: 'MA100 break',
  ma150_break: 'MA150 break',
  ma200_break: 'MA200 break',
  death_cross: 'Death cross',
  volume_dryup: 'Volume dryup',
  distribution_day: 'Distribution day',
  rsi_weakness: 'RSI weakness',
  mrsi_flip: 'MRSI flip',
  trailing_drawdown: 'Trailing drawdown',
  stop_loss: 'Stop loss',
}

export function signalLabel(signalType: string): string {
  return LABELS[signalType] ?? signalType
}

export function countFired(signals: HoldingSignal[]): number {
  return signals.reduce((n, s) => n + (s.fired ? 1 : 0), 0)
}

export function pillColor(firedCount: number, hasData: boolean): PillColor {
  if (!hasData) return 'gray'
  if (firedCount === 0) return 'green'
  if (firedCount <= 2) return 'yellow'
  return 'red'
}

function fmtCurrency(v: number, currency: string): string {
  const sym = currency === 'EUR' ? '€' : currency === 'GBP' ? '£' : '$'
  return `${sym}${v.toFixed(2)}`
}

export function formatSignalValue(s: HoldingSignal, currency: string): string {
  if (s.value === null || s.threshold === null) return '—'
  const v = s.value
  const t = s.threshold
  switch (s.signal_type) {
    case 'ma50_break':
    case 'ma100_break':
    case 'ma150_break':
    case 'ma200_break':
    case 'trailing_drawdown':
    case 'stop_loss':
      return `${fmtCurrency(v, currency)} < ${fmtCurrency(t, currency)}`
    case 'death_cross':
      return `MA50 ${fmtCurrency(v, currency)} crossed below MA150 ${fmtCurrency(t, currency)}`
    case 'volume_dryup':
      return `5d avg ${Math.round(v).toLocaleString()} < ${Math.round(t).toLocaleString()}`
    case 'distribution_day':
      return `vol ${Math.round(v).toLocaleString()} > ${Math.round(t).toLocaleString()}`
    case 'rsi_weakness':
      return `RSI ${v.toFixed(1)} < ${t.toFixed(1)}`
    case 'mrsi_flip':
      return `MRSI ${v.toFixed(3)} crossed below 0`
    default:
      return `${v} vs ${t}`
  }
}

export async function fetchHoldingSignals(): Promise<SignalsBySymbol> {
  const res = await fetch('/api/proxy/api/holding-signals')
  if (!res.ok) throw new Error(`fetchHoldingSignals: HTTP ${res.status}`)
  const data: HoldingSignalsResponse = await res.json()
  const map: SignalsBySymbol = {}
  for (const item of data.items) {
    const { symbol, ...rest } = item
    if (!map[symbol]) map[symbol] = []
    map[symbol].push(rest)
  }
  return map
}
