import { render, screen, waitFor } from '@testing-library/react'
import { ScreenerGrid } from '../components/screener/ScreenerGrid'
import type { ScreenerRow } from '../lib/screener'

const row = (overrides: Partial<ScreenerRow> = {}): ScreenerRow => ({
  symbol: 'AAPL',
  name: 'Apple Inc',
  sector: 'Hardware',
  signal_date: '2026-06-30',
  momentum_5d: null,
  momentum_20d: null,
  momentum_60d: 12.0,
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
  breakout_direction: 'none',
  breakout_strength: null,
  breakout_volume_ratio: null,
  breakout_date: null,
  gross_margin: 0.73,
  roe: null,
  roic: null,
  levered_fcf_margin: null,
  interest_cover: null,
  eps_5y_growth: null,
  gates_passed: 5,
  gates_total: 7,
  market_cap: null,
  trailing_pe: null,
  score_tech: 82,
  score_fund: 71,
  score_total: 78,
  verdict: 'strong_buy',
  ...overrides,
})

const rows: ScreenerRow[] = [
  row({ symbol: 'AAPL', name: 'Apple Inc', verdict: 'strong_buy', gross_margin: 0.73 }),
  row({ symbol: 'MMM', name: '3M Co', sector: 'Industrials', score_total: 40, verdict: 'avoid', gross_margin: null }),
]

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ rows, count: rows.length }),
  }) as unknown as typeof fetch
})

afterEach(() => {
  jest.restoreAllMocks()
})

describe('ScreenerGrid', () => {
  it('renders a ticker, a Strong buy verdict, and a formatted percent', async () => {
    render(<ScreenerGrid />)

    await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())
    expect(screen.getByText('MMM')).toBeInTheDocument()
    expect(screen.getByText('Strong buy')).toBeInTheDocument()
    expect(screen.getByText('73%')).toBeInTheDocument()
    expect(screen.getByText('2 of 2 symbols')).toBeInTheDocument()
  })

  it('shows a loading state before data arrives', () => {
    render(<ScreenerGrid />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('shows a friendly empty state when there are no rows', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ rows: [], count: 0 }),
    })
    render(<ScreenerGrid />)
    await waitFor(() => expect(screen.getByText(/no screener data yet/i)).toBeInTheDocument())
  })
})
