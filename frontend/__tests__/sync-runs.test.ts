import { actionLabel, statusStyle, formatDuration } from '../lib/sync-runs'

describe('actionLabel', () => {
  it('maps known actions to human labels', () => {
    expect(actionLabel('ibkr')).toBe('Sync IBKR')
    expect(actionLabel('market_data')).toBe('Sync market data')
    expect(actionLabel('analytics')).toBe('Recompute analytics')
    expect(actionLabel('manual_add')).toBe('Add manual ticker')
  })

  it('falls back to raw value for unknown actions', () => {
    expect(actionLabel('something_new')).toBe('something_new')
  })
})

describe('statusStyle', () => {
  it('returns distinct colors per status', () => {
    expect(statusStyle('success').label).toContain('Success')
    expect(statusStyle('partial').label).toContain('Partial')
    expect(statusStyle('error').label).toContain('Error')
    expect(statusStyle('success').bg).not.toBe(statusStyle('error').bg)
  })

  it('falls back to a neutral style for unknown status', () => {
    expect(statusStyle('weird').label).toBe('weird')
  })
})

describe('formatDuration', () => {
  it('shows ms under 1s', () => expect(formatDuration(123)).toBe('123ms'))
  it('shows seconds with 1 decimal under 1m', () => expect(formatDuration(1500)).toBe('1.5s'))
  it('shows whole seconds at minute scale', () => expect(formatDuration(75_000)).toBe('75s'))
  it('handles null', () => expect(formatDuration(null)).toBe('—'))
})
