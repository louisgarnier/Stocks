'use client'

import { useState } from 'react'
import { toast } from 'sonner'

type StepKey = 'fundamentals' | 'technical' | 'compute' | 'all'

interface StepState {
  running: boolean
  status: string | null
  error: boolean
}

const INITIAL: Record<StepKey, StepState> = {
  fundamentals: { running: false, status: null, error: false },
  technical: { running: false, status: null, error: false },
  compute: { running: false, status: null, error: false },
  all: { running: false, status: null, error: false },
}

async function post(path: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/proxy/api/sync/${path}`, { method: 'POST' })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof body === 'object' ? JSON.stringify(body) : String(body))
  return body as Record<string, unknown>
}

// Technical = prices then indicators (analytics recomputes indicators).
async function runTechnical() {
  await post('market-data')
  await post('analytics')
}

export function SyncToolbar({ onSynced }: { onSynced?: () => void } = {}) {
  const [state, setState] = useState<Record<StepKey, StepState>>(INITIAL)

  const set = (key: StepKey, patch: Partial<StepState>) =>
    setState((s) => ({ ...s, [key]: { ...s[key], ...patch } }))

  const run = async (key: StepKey, label: string, fn: () => Promise<unknown>) => {
    if (state[key].running) return
    set(key, { running: true, status: 'Running…', error: false })
    toast(`${label} sync started`)
    try {
      await fn()
      set(key, { running: false, status: 'Done ✓', error: false })
      toast.success(`${label} sync complete`)
      onSynced?.()
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set(key, { running: false, status: 'Failed', error: true })
      toast.error(`${label} sync failed`, { description: msg })
    }
  }

  const anyRunning = Object.values(state).some((s) => s.running)

  const Btn = ({
    stepKey,
    label,
    icon,
    subtitle,
    primary,
    onClick,
  }: {
    stepKey: StepKey
    label: string
    icon: string
    subtitle: string
    primary?: boolean
    onClick: () => void
  }) => {
    const st = state[stepKey]
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <button
          type="button"
          onClick={onClick}
          disabled={anyRunning}
          style={{
            background: primary ? '#4f46e5' : '#fff',
            border: `1px solid ${primary ? '#4f46e5' : '#e2e5ea'}`,
            borderRadius: '8px',
            padding: primary ? '8px 16px' : '8px 13px',
            fontWeight: primary ? 700 : 600,
            fontSize: '13px',
            cursor: anyRunning ? 'default' : 'pointer',
            opacity: anyRunning && !st.running ? 0.6 : 1,
            color: primary ? '#fff' : '#0f1729',
            whiteSpace: 'nowrap',
          }}
        >
          {st.running ? '…' : icon} {label}
        </button>
        <span
          style={{
            fontSize: '10px',
            color: st.error ? '#dc2626' : st.status === 'Done ✓' ? '#16a34a' : '#94a3b8',
          }}
        >
          {st.status ?? subtitle}
        </span>
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'stretch',
        background: '#fff',
        border: '1px solid #e8eaed',
        borderRadius: '12px',
        padding: '12px',
        flexWrap: 'wrap',
      }}
    >
      <Btn
        stepKey="fundamentals"
        label="Fundamentals"
        icon="⟳"
        subtitle="fetch + auto-rescore"
        onClick={() => run('fundamentals', 'Fundamentals', () => post('fundamentals'))}
      />
      <Btn
        stepKey="technical"
        label="Technical"
        icon="⟳"
        subtitle="prices + indicators"
        onClick={() => run('technical', 'Technical', runTechnical)}
      />
      <Btn
        stepKey="compute"
        label="Compute signals"
        icon="⟳"
        subtitle="screen + score"
        onClick={() => run('compute', 'Compute', () => post('screen'))}
      />
      <Btn
        stepKey="all"
        label="Run all"
        icon="▶"
        subtitle="Technical → Fundamentals → Compute"
        primary
        onClick={() =>
          run('all', 'Full', async () => {
            await runTechnical()
            await post('fundamentals')
            await post('screen')
          })
        }
      />
    </div>
  )
}
