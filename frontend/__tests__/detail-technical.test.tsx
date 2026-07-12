import { render, screen, waitFor } from '@testing-library/react'
import { SecurityDetailSheet } from '../components/security-detail/SecurityDetailSheet'

function mockDetail(technical: unknown, breakout: unknown, zigzag: unknown) {
  return {
    symbol: 'NVDA', is_held: false, universe: null, position: null,
    transactions: [], indicators: null, fundamentals: null, bars: [],
    technical, breakout, zigzag,
  }
}

const noBreakout = {
  status: 'no_consolidation_patterns', direction: 'none', strength: null,
  volume_ratio: null, support: null, resistance: null, range_pct: null,
  duration_days: null, date: '2026-07-09',
}

function stubFetch(body: unknown) {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body), text: () => Promise.resolve('') }),
  ) as unknown as typeof fetch
}

afterEach(() => jest.restoreAllMocks())

test('renders Technical signals card with momentum, MA cross and zigzag swings', async () => {
  stubFetch(mockDetail(
    {
      momentum_5d: 2.63, momentum_20d: -2.6, momentum_60d: 7.12,
      multi_factor_momentum: 2.41, ma_cross_status: 'All Bullish',
      trend_aligned: 1, volume_spike: 0, near_52w_high: 0,
      dist_from_52w_high: -14.3, mrsi: -0.021, signal_date: '2026-07-09',
    },
    noBreakout,
    { deviation_pct: 6.0, window_days: 40, swings: [{ date: '2026-05-14', price: 236.54, type: 'peak' }] },
  ))
  render(<SecurityDetailSheet symbol="NVDA" onClose={() => {}} />)
  await waitFor(() => expect(screen.getByText('Technical signals')).toBeInTheDocument())
  expect(screen.getByText('All Bullish')).toBeInTheDocument()
  expect(screen.getByText('+7.12%')).toBeInTheDocument()
  expect(screen.getByText(/05-14 @236.54/)).toBeInTheDocument()
})

test('no Breakout block when status is no_consolidation_patterns', async () => {
  stubFetch(mockDetail(null, noBreakout, { deviation_pct: 6.0, window_days: 40, swings: [] }))
  render(<SecurityDetailSheet symbol="NVDA" onClose={() => {}} />)
  await waitFor(() => expect(screen.getByText('Technical signals')).toBeInTheDocument())
  expect(screen.queryByText('Breakout')).not.toBeInTheDocument()
})

test('renders Breakout block when a pattern is detected', async () => {
  stubFetch(mockDetail(
    null,
    { status: 'breakout_detected', direction: 'bullish', strength: 3.04, volume_ratio: 1.02,
      support: 190.0, resistance: 200.0, range_pct: 5.0, duration_days: 40, date: '2026-07-09' },
    { deviation_pct: 6.0, window_days: 40, swings: [] },
  ))
  render(<SecurityDetailSheet symbol="NVDA" onClose={() => {}} />)
  await waitFor(() => expect(screen.getByText('Breakout')).toBeInTheDocument())
  expect(screen.getByText('190.00 → 200.00')).toBeInTheDocument()
})
