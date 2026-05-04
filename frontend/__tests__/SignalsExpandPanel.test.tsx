import { render, screen } from '@testing-library/react'
import { SignalsExpandPanel } from '../components/positions/SignalsExpandPanel'
import type { HoldingSignal } from '../lib/holding-signals'

const sig = (signal_type: string, fired: boolean, value: number | null = 100, threshold: number | null = 110): HoldingSignal => ({
  signal_type, fired, value, threshold, last_evaluated_at: '2026-05-04T09:02:14',
})

describe('SignalsExpandPanel', () => {
  it('lists each fired signal with its formatted value', () => {
    render(
      <table><tbody><SignalsExpandPanel
        signals={[sig('ma50_break', true, 138.4, 145.2), sig('rsi_weakness', true, 47, 50)]}
        currency="USD"
        colSpan={6}
      /></tbody></table>,
    )
    expect(screen.getByText('MA50 break')).toBeInTheDocument()
    expect(screen.getByText('$138.40 < $145.20')).toBeInTheDocument()
    expect(screen.getByText('RSI weakness')).toBeInTheDocument()
    expect(screen.getByText('RSI 47.0 < 50.0')).toBeInTheDocument()
  })

  it('lists not-fired signals in the muted footer', () => {
    render(
      <table><tbody><SignalsExpandPanel
        signals={[sig('ma50_break', true), sig('ma200_break', false), sig('death_cross', false)]}
        currency="USD"
        colSpan={6}
      /></tbody></table>,
    )
    expect(screen.getByText(/not fired:/i).textContent).toContain('MA200 break')
    expect(screen.getByText(/not fired:/i).textContent).toContain('Death cross')
  })

  it('renders timestamp', () => {
    render(
      <table><tbody><SignalsExpandPanel
        signals={[sig('ma50_break', true)]}
        currency="USD"
        colSpan={6}
      /></tbody></table>,
    )
    expect(screen.getByText(/last evaluated/i)).toBeInTheDocument()
  })

  it('renders nothing if signals array is empty', () => {
    const { container } = render(
      <table><tbody><SignalsExpandPanel signals={[]} currency="USD" colSpan={6} /></tbody></table>,
    )
    expect(container.querySelector('td')).toBeNull()
  })
})
