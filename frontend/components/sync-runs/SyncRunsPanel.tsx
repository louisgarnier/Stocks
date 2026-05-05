'use client'

import { useState } from 'react'
import {
  actionLabel,
  formatDuration,
  statusStyle,
  type SyncRun,
} from '@/lib/sync-runs'

interface Props {
  runs: SyncRun[]
  onRefresh?: () => void
  loading?: boolean
}

export function SyncRunsPanel({ runs, onRefresh, loading }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const toggle = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div style={{ marginTop: '32px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#1f2937', margin: 0 }}>Sync Runs</h3>
          <p style={{ fontSize: '12px', color: '#6b7280', margin: '4px 0 0 0' }}>
            Every sync action — what was attempted, what succeeded, what failed.
          </p>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            style={{
              padding: '6px 12px', backgroundColor: 'transparent', color: '#6b7280',
              border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '12px',
              cursor: loading ? 'wait' : 'pointer',
            }}
          >
            {loading ? 'Refreshing…' : '↻ Refresh'}
          </button>
        )}
      </div>

      {runs.length === 0 ? (
        <div style={{ padding: '24px', textAlign: 'center', backgroundColor: '#f9fafb', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
          <p style={{ fontSize: '14px', color: '#6b7280' }}>No sync runs recorded yet — click any sync button to populate.</p>
        </div>
      ) : (
        <div style={{ border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f9fafb' }}>
                <th style={{ padding: '10px 12px', width: '32px', borderBottom: '1px solid #e5e7eb' }} />
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>When</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Action</th>
                <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Status</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Duration</th>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #e5e7eb' }}>Summary</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const sty = statusStyle(run.status)
                const isOpen = expanded.has(run.id)
                const hasDetails = run.details !== null && run.details !== undefined
                return (
                  <Row
                    key={run.id}
                    run={run}
                    sty={sty}
                    isOpen={isOpen}
                    hasDetails={hasDetails}
                    onToggle={() => toggle(run.id)}
                  />
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function Row({
  run, sty, isOpen, hasDetails, onToggle,
}: {
  run: SyncRun
  sty: { bg: string; fg: string; label: string }
  isOpen: boolean
  hasDetails: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr style={{ borderBottom: '1px solid #e5e7eb', cursor: hasDetails ? 'pointer' : 'default' }} onClick={hasDetails ? onToggle : undefined}>
        <td style={{ padding: '10px 12px', textAlign: 'center', color: '#9ca3af' }}>
          {hasDetails ? (isOpen ? '▼' : '▶') : ''}
        </td>
        <td style={{ padding: '10px 12px', color: '#1f2937', whiteSpace: 'nowrap' }}>
          {new Date(run.started_at).toLocaleString('fr-FR', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
          })}
        </td>
        <td style={{ padding: '10px 12px', color: '#1f2937', fontWeight: 500 }}>{actionLabel(run.action)}</td>
        <td style={{ padding: '10px 12px', textAlign: 'center' }}>
          <span style={{
            padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600,
            backgroundColor: sty.bg, color: sty.fg,
          }}>
            {sty.label}
          </span>
        </td>
        <td style={{ padding: '10px 12px', textAlign: 'right', color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>
          {formatDuration(run.duration_ms)}
        </td>
        <td style={{ padding: '10px 12px', color: '#374151' }}>{run.summary ?? '—'}</td>
      </tr>
      {isOpen && hasDetails && (
        <tr style={{ background: '#f9fafb' }}>
          <td colSpan={6} style={{ padding: 0 }}>
            <DetailsBlock details={run.details} />
          </td>
        </tr>
      )}
    </>
  )
}

function DetailsBlock({ details }: { details: unknown }) {
  // For market_data with failures: show them as a list. For step-based (ibkr/analytics): show the per-step list.
  // Otherwise: pretty-print the raw JSON (capped to 1.5KB so it doesn't blow up the page).
  const d = details as { failures?: Array<{ symbol: string; reason: string }>; steps?: Array<{ name: string; status: string; result?: unknown; error?: string }> } | null
  return (
    <div style={{ padding: '12px 24px 16px 36px' }}>
      {d?.failures && d.failures.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <p style={{ fontSize: '11px', fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.4px', margin: '0 0 6px 0' }}>
            Failed symbols ({d.failures.length})
          </p>
          <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#374151' }}>
            {d.failures.slice(0, 50).map((f, i) => (
              <li key={i}><strong>{f.symbol}</strong> — <span style={{ color: '#6b7280' }}>{f.reason}</span></li>
            ))}
            {d.failures.length > 50 && (
              <li style={{ color: '#9ca3af' }}>… {d.failures.length - 50} more</li>
            )}
          </ul>
        </div>
      )}
      {d?.steps && d.steps.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <p style={{ fontSize: '11px', fontWeight: 700, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.4px', margin: '0 0 6px 0' }}>
            Steps
          </p>
          <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#374151' }}>
            {d.steps.map((s, i) => (
              <li key={i}>
                {s.status === 'ok' ? '✅' : '❌'} <strong>{s.name}</strong>
                {s.error && <span style={{ color: '#dc2626' }}> — {s.error}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <details>
        <summary style={{ fontSize: '11px', color: '#9ca3af', cursor: 'pointer' }}>raw json</summary>
        <pre style={{ fontSize: '11px', color: '#374151', background: '#fff', padding: '8px', borderRadius: '4px', maxHeight: '300px', overflow: 'auto', margin: '6px 0 0 0' }}>
          {JSON.stringify(details, null, 2).slice(0, 1500)}
        </pre>
      </details>
    </div>
  )
}
