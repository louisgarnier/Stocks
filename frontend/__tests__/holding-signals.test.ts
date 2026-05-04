import {
  signalLabel,
  formatSignalValue,
  pillColor,
  countFired,
} from '../lib/holding-signals'

describe('signalLabel', () => {
  it('maps known signal types to human labels', () => {
    expect(signalLabel('ma50_break')).toBe('MA50 break')
    expect(signalLabel('death_cross')).toBe('Death cross')
    expect(signalLabel('mrsi_flip')).toBe('MRSI flip')
    expect(signalLabel('stop_loss')).toBe('Stop loss')
    expect(signalLabel('trailing_drawdown')).toBe('Trailing drawdown')
  })

  it('falls back to the raw signal_type when unknown', () => {
    expect(signalLabel('made_up_signal')).toBe('made_up_signal')
  })
})

describe('formatSignalValue', () => {
  it('formats MA breaks as "value < threshold" with currency', () => {
    expect(
      formatSignalValue(
        { signal_type: 'ma50_break', fired: true, value: 138.4, threshold: 145.2, last_evaluated_at: '' },
        'USD',
      ),
    ).toBe('$138.40 < $145.20')
  })

  it('formats RSI weakness without currency', () => {
    expect(
      formatSignalValue(
        { signal_type: 'rsi_weakness', fired: true, value: 47, threshold: 50, last_evaluated_at: '' },
        'USD',
      ),
    ).toBe('RSI 47.0 < 50.0')
  })

  it('formats MRSI flip as crossed-below-zero text', () => {
    expect(
      formatSignalValue(
        { signal_type: 'mrsi_flip', fired: true, value: -0.02, threshold: 0, last_evaluated_at: '' },
        'USD',
      ),
    ).toBe('MRSI -0.020 crossed below 0')
  })

  it('returns "—" for null value/threshold', () => {
    expect(
      formatSignalValue(
        { signal_type: 'ma50_break', fired: false, value: null, threshold: null, last_evaluated_at: '' },
        'USD',
      ),
    ).toBe('—')
  })
})

describe('countFired', () => {
  const fired = { signal_type: 'x', fired: true, value: 1, threshold: 0, last_evaluated_at: '' }
  const ok = { signal_type: 'y', fired: false, value: 1, threshold: 0, last_evaluated_at: '' }

  it('counts only fired signals', () => {
    expect(countFired([fired, fired, ok])).toBe(2)
  })

  it('returns 0 for empty array', () => {
    expect(countFired([])).toBe(0)
  })
})

describe('pillColor', () => {
  it('green for 0 fired', () => expect(pillColor(0, true)).toBe('green'))
  it('yellow for 1 fired', () => expect(pillColor(1, true)).toBe('yellow'))
  it('yellow for 2 fired', () => expect(pillColor(2, true)).toBe('yellow'))
  it('red for 3+ fired', () => expect(pillColor(3, true)).toBe('red'))
  it('red for 11 fired', () => expect(pillColor(11, true)).toBe('red'))
  it('gray when no data', () => expect(pillColor(0, false)).toBe('gray'))
})
