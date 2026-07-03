import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { ResearchGrid } from '../components/research/ResearchGrid'
import type { ResearchRow } from '../lib/research'

jest.mock('../lib/research', () => ({
  ...jest.requireActual('../lib/research'),
  fetchResearchOverview: jest.fn(),
}))

// eslint-disable-next-line @typescript-eslint/no-var-requires
const research = require('../lib/research')

const row = (overrides: Partial<ResearchRow> = {}): ResearchRow =>
  ({
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
    roe: 0.4,
    roic: 0.3,
    levered_fcf_margin: null,
    interest_cover: null,
    eps_5y_growth: null,
    gates_passed: 6,
    gates_total: 7,
    market_cap: null,
    trailing_pe: null,
    score_tech: 82,
    score_fund: 71,
    score_total: 52,
    verdict: 'watch',
    price: 259.1,
    indicator_date: '2026-06-30',
    ma_50: 261.5,
    ma_100: null,
    ma_150: null,
    ma_200: null,
    bb_upper_20: null,
    bb_lower_20: null,
    bb_width: null,
    rsi_14: 61.4,
    mrsi: null,
    atr_14: null,
    volume_ma_20: null,
    ...overrides,
  }) as ResearchRow

const rows: ResearchRow[] = [
  row({ symbol: 'AAPL', score_total: 52, verdict: 'watch' }),
  row({ symbol: 'KO', name: 'Coca-Cola', score_total: 70, verdict: 'buy', rsi_14: 58.2, price: 68.9 }),
]

beforeEach(() => {
  localStorage.clear()
  research.fetchResearchOverview.mockResolvedValue(rows)
})

afterEach(() => jest.clearAllMocks())

test('renders rows with default visible columns', async () => {
  render(<ResearchGrid onSelectSymbol={() => {}} />)
  await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())
  expect(screen.getByText('KO')).toBeInTheDocument()
  // Price is in DEFAULT_VISIBLE; MA200 is not.
  expect(screen.getByText('259.10')).toBeInTheDocument()
})

test('row click fires onSelectSymbol with the symbol', async () => {
  const onSelect = jest.fn()
  render(<ResearchGrid onSelectSymbol={onSelect} />)
  await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())
  fireEvent.click(screen.getByText('AAPL'))
  expect(onSelect).toHaveBeenCalledWith('AAPL')
})

test('hidden column becomes visible after toggling it in the Columns menu', async () => {
  render(<ResearchGrid onSelectSymbol={() => {}} />)
  await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument())
  // MA200 header not present by default.
  expect(screen.queryByRole('columnheader', { name: /MA200/i })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Columns/i }))
  const menu = screen.getByTestId('columns-menu')
  fireEvent.click(within(menu).getByLabelText('MA200'))
  await waitFor(() =>
    expect(screen.getByRole('columnheader', { name: /MA200/i })).toBeInTheDocument(),
  )
})

test('search filters rows', async () => {
  render(<ResearchGrid onSelectSymbol={() => {}} />)
  await waitFor(() => expect(screen.getByText('KO')).toBeInTheDocument())
  fireEvent.change(screen.getByPlaceholderText(/Filter symbol/i), { target: { value: 'KO' } })
  expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
  expect(screen.getByText('KO')).toBeInTheDocument()
})
