'use client'

import type { HoldingSignal } from '@/lib/holding-signals'
import { signalLabel, formatSignalValue } from '@/lib/holding-signals'

interface Props {
  signals: HoldingSignal[]
  currency: string
  colSpan: number
}

export function SignalsExpandPanel({ signals, currency, colSpan }: Props) {
  if (signals.length === 0) return null

  const fired = signals.filter((s) => s.fired)
  const notFired = signals.filter((s) => !s.fired)
  const lastEvaluated = signals[0].last_evaluated_at

  return (
    <tr style={{ background: '#fff7f7' }}>
      <td colSpan={colSpan} style={{ padding: 0, borderBottom: '1px solid #e5e7eb' }}>
        <div style={{ padding: '14px 24px 18px 24px', background: '#fff7f7' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
              Fired sell signals
            </span>
            <span style={{ fontSize: '11px', color: '#9ca3af' }}>
              last evaluated {lastEvaluated.replace('T', ' ').slice(0, 16)}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px' }}>
            {fired.map((s) => (
              <div key={s.signal_type} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px dashed #fecaca' }}>
                <span style={{ fontSize: '13px', color: '#1f2937' }}>
                  <span style={{ color: '#dc2626', marginRight: '6px' }}>❌</span>
                  {signalLabel(s.signal_type)}
                </span>
                <span style={{ fontSize: '12px', color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>
                  {formatSignalValue(s, currency)}
                </span>
              </div>
            ))}
          </div>

          {notFired.length > 0 && (
            <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px dashed #fecaca' }}>
              <span style={{ fontSize: '11px', color: '#9ca3af' }}>
                Not fired: {notFired.map((s) => signalLabel(s.signal_type)).join(', ')}
              </span>
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}
