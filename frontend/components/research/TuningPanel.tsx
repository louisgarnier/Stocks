'use client'

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { getConsolidationParams, putConsolidationParams } from '@/lib/research'

// Friendly labels for known tunable keys; unknown keys fall back to the raw key.
const LABELS: Record<string, string> = {
  max_consolidation_range_pct: 'Max range %',
  min_pct_in_channel: '% bars in channel',
  min_pct_closes_in_channel: '% closes in channel',
  min_boundary_touches: 'Min boundary touches',
  zigzag_deviation: 'ZigZag deviation %',
  min_consolidation_duration: 'Min duration (days)',
  lookback_days: 'Lookback (days)',
  min_days_between_swings: 'Min days between swings',
  breakout_confirmation_pct: 'Breakout confirmation %',
  volume_lookback_days: 'Volume lookback (days)',
  min_resistance_touches: 'Min resistance touches',
  min_support_touches: 'Min support touches',
  extreme_grouping_tolerance: 'Extreme grouping tol.',
  max_daily_change: 'Max daily change %',
  min_volume_threshold: 'Min volume threshold',
  max_volatility_filter: 'Max volatility filter',
  channel_test_tolerance: 'Channel test tolerance',
  min_touches_per_level: 'Min touches per level',
  min_range_size_pct: 'Min range size %',
  min_bounces_in_channel: 'Min bounces in channel',
}

const label = (key: string) => LABELS[key] ?? key

type NumericParams = Record<string, number>

// Keep only scalar-number params; skip arrays (e.g. `timeframes`) which have no
// single-input representation.
function numericOnly(obj: Record<string, unknown>): NumericParams {
  const out: NumericParams = {}
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'number') out[k] = v
  }
  return out
}

export function TuningPanel({ onRerun }: { onRerun: () => void }) {
  const [values, setValues] = useState<NumericParams>({})
  const [defaults, setDefaults] = useState<NumericParams>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getConsolidationParams()
      .then((res) => {
        setValues(numericOnly(res.params))
        setDefaults(numericOnly(res.defaults))
      })
      .catch((e) => toast.error('Failed to load parameters', { description: e instanceof Error ? e.message : String(e) }))
      .finally(() => setLoading(false))
  }, [])

  const keys = useMemo(() => Object.keys(defaults), [defaults])

  const setValue = (key: string, raw: string) => {
    const n = Number(raw)
    setValues((v) => ({ ...v, [key]: Number.isNaN(n) ? v[key] : n }))
  }

  const reset = () => setValues({ ...defaults })

  const save = async () => {
    setSaving(true)
    try {
      await putConsolidationParams(values)
      const res = await fetch('/api/proxy/api/sync/screen', { method: 'POST' })
      if (!res.ok) throw new Error(`sync/screen HTTP ${res.status}`)
      toast.success('Parameters saved — signals recomputed')
      onRerun()
    } catch (e) {
      toast.error('Save & re-run failed', { description: e instanceof Error ? e.message : String(e) })
    } finally {
      setSaving(false)
    }
  }

  const isDirty = keys.some((k) => values[k] !== defaults[k])

  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #e8eaed',
        borderRadius: '12px',
        padding: '14px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', gap: '12px', flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: '14px', color: '#0f1729' }}>
          Analytics parameters — Consolidation / S-R / ZigZag / Breakout
        </span>
        <span style={{ fontSize: '11px', color: '#94a3b8' }}>
          Recommended defaults keep breakout signals reliable. Loosen to surface more (lower-quality) candidates.
        </span>
      </div>

      {loading ? (
        <div style={{ padding: '20px 0', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>Loading parameters…</div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '14px' }}>
            {keys.map((key) => (
              <div key={key}>
                <label
                  htmlFor={`param-${key}`}
                  style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: '#64748b', marginBottom: '3px' }}
                >
                  {label(key)}
                </label>
                <input
                  id={`param-${key}`}
                  type="number"
                  step="any"
                  value={values[key] ?? ''}
                  onChange={(e) => setValue(key, e.target.value)}
                  style={{
                    width: '100%',
                    fontSize: '13px',
                    fontFamily: 'monospace',
                    padding: '6px 9px',
                    borderRadius: '7px',
                    border: values[key] !== defaults[key] ? '1px solid #c7d2fe' : '1px solid #e2e5ea',
                    background: values[key] !== defaults[key] ? '#eef2ff' : '#fff',
                  }}
                />
                <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '2px' }}>recommended {defaults[key]}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '14px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={save}
              disabled={saving}
              style={{
                background: '#4f46e5',
                border: '1px solid #4f46e5',
                borderRadius: '8px',
                padding: '8px 16px',
                fontWeight: 700,
                fontSize: '13px',
                color: '#fff',
                cursor: saving ? 'default' : 'pointer',
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? 'Saving…' : 'Save & re-run analytics'}
            </button>
            <button
              type="button"
              onClick={reset}
              disabled={!isDirty}
              style={{
                background: '#fff',
                border: '1px solid #e2e5ea',
                borderRadius: '8px',
                padding: '8px 13px',
                fontSize: '13px',
                color: isDirty ? '#475569' : '#cbd0d8',
                cursor: isDirty ? 'pointer' : 'default',
              }}
            >
              Reset to recommended
            </button>
            {isDirty && (
              <span style={{ fontSize: '11px', color: '#d97706' }}>
                Unsaved changes — re-run to apply to the grid.
              </span>
            )}
          </div>
        </>
      )}
    </div>
  )
}
