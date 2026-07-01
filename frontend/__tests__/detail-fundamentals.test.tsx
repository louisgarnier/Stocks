import { render, screen, waitFor } from '@testing-library/react'
import { SecurityDetailSheet } from '../components/security-detail/SecurityDetailSheet'

function mockDetail(fundamentals: unknown) {
  return {
    symbol: 'AAPL', is_held: false, universe: null, position: null,
    transactions: [], indicators: null, fundamentals, bars: [],
  }
}

function stubFetch(body: unknown) {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(body), text: () => Promise.resolve('') }),
  ) as unknown as typeof fetch
}

afterEach(() => jest.restoreAllMocks())

test('renders Fundamentals card when present', async () => {
  stubFetch(mockDetail({
    gross_margin: 0.47, roe: 0.4, roic: 0.3, levered_fcf_margin: 0.2,
    interest_cover: 13.8, eps_5y_growth: 0.05, gates_passed: 6, gates_total: 7,
    market_cap: 3.0e12, trailing_pe: 35.5,
  }))
  render(<SecurityDetailSheet symbol="AAPL" onClose={() => {}} />)
  await waitFor(() => expect(screen.getByText('Fundamentals')).toBeInTheDocument())
  expect(screen.getByText('40.0%')).toBeInTheDocument() // ROE
  expect(screen.getByText('6/7')).toBeInTheDocument() // gates
})

test('no Fundamentals card when absent', async () => {
  stubFetch(mockDetail(null))
  render(<SecurityDetailSheet symbol="MSFT" onClose={() => {}} />)
  await waitFor(() => expect(screen.getByText(/MSFT/)).toBeInTheDocument())
  expect(screen.queryByText('Fundamentals')).not.toBeInTheDocument()
})
