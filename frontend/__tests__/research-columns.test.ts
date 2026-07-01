import {
  loadVisibleColumns,
  saveVisibleColumns,
  DEFAULT_VISIBLE,
  ALL_COLUMNS,
} from '../lib/research'

describe('research column persistence', () => {
  beforeEach(() => localStorage.clear())

  test('defaults when nothing saved', () => {
    expect(loadVisibleColumns()).toEqual(DEFAULT_VISIBLE)
  })

  test('round-trips saved columns', () => {
    saveVisibleColumns(['symbol', 'rsi_14', 'verdict'])
    expect(loadVisibleColumns()).toEqual(['symbol', 'rsi_14', 'verdict'])
  })

  test('falls back to defaults on corrupt storage', () => {
    localStorage.setItem('research.columns.v1', 'not-json{')
    expect(loadVisibleColumns()).toEqual(DEFAULT_VISIBLE)
  })

  test('every default column exists in ALL_COLUMNS', () => {
    const keys = new Set(ALL_COLUMNS.map((c) => c.key))
    for (const k of DEFAULT_VISIBLE) expect(keys.has(k)).toBe(true)
  })
})
