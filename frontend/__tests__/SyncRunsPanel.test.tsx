import { render, screen, fireEvent } from '@testing-library/react'
import { SyncRunsPanel } from '../components/sync-runs/SyncRunsPanel'
import type { SyncRun } from '../lib/sync-runs'

const baseRun: SyncRun = {
  id: 1,
  started_at: '2026-05-05T10:00:00+02:00',
  finished_at: '2026-05-05T10:00:13+02:00',
  duration_ms: 13000,
  action: 'analytics',
  status: 'success',
  summary: '2 ok · 0 error',
  details: { steps: [{ name: 'indicators', status: 'ok' }, { name: 'holding_signals', status: 'ok' }] },
}

describe('SyncRunsPanel', () => {
  it('renders empty state when there are no runs', () => {
    render(<SyncRunsPanel runs={[]} />)
    expect(screen.getByText(/no sync runs recorded yet/i)).toBeInTheDocument()
  })

  it('renders an action label, status badge, duration and summary per row', () => {
    render(<SyncRunsPanel runs={[baseRun]} />)
    expect(screen.getByText('Recompute analytics')).toBeInTheDocument()
    expect(screen.getByText(/✅ Success/)).toBeInTheDocument()
    expect(screen.getByText('13.0s')).toBeInTheDocument()
    expect(screen.getByText('2 ok · 0 error')).toBeInTheDocument()
  })

  it('expands details when row is clicked', () => {
    render(<SyncRunsPanel runs={[baseRun]} />)
    // Before click: no Steps section header
    expect(screen.queryByText(/^Steps$/)).toBeNull()
    fireEvent.click(screen.getByText('Recompute analytics'))
    // After click: Steps section header + each step name (in the structured list)
    expect(screen.getByText(/^Steps$/)).toBeInTheDocument()
    expect(screen.getAllByText('indicators').length).toBeGreaterThan(0)
    expect(screen.getAllByText('holding_signals').length).toBeGreaterThan(0)
  })

  it('lists failed symbols in details for market-data runs', () => {
    const md: SyncRun = {
      ...baseRun,
      id: 2,
      action: 'market_data',
      status: 'partial',
      summary: '552 symbols · 12,345 new bars · 1 dropped (TSMC)',
      details: { failures: [{ symbol: 'TSMC', reason: 'yfinance returned no data (invalid ticker?)' }] },
    }
    render(<SyncRunsPanel runs={[md]} />)
    fireEvent.click(screen.getByText('Sync market data'))
    expect(screen.getByText(/Failed symbols/i)).toBeInTheDocument()
    // TSMC appears as the bold li label in the structured list
    expect(screen.getAllByText('TSMC').length).toBeGreaterThan(0)
    // Reason appears at least in the structured list (also in raw json — both fine)
    expect(screen.getAllByText(/yfinance returned no data/i).length).toBeGreaterThan(0)
  })

  it('does not show expand chevron when details is null', () => {
    const noDetails: SyncRun = { ...baseRun, id: 3, details: null }
    render(<SyncRunsPanel runs={[noDetails]} />)
    expect(screen.queryByText('▶')).toBeNull()
    expect(screen.queryByText('▼')).toBeNull()
  })
})
