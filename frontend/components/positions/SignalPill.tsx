'use client'

import type { PillColor } from '@/lib/holding-signals'
import { pillColor } from '@/lib/holding-signals'

interface Props {
  firedCount: number
  hasData: boolean
  expanded: boolean
  onToggle?: () => void
}

const STYLES: Record<PillColor, { bg: string; fg: string; border: string }> = {
  green:  { bg: '#dcfce7', fg: '#15803d', border: '#bbf7d0' },
  yellow: { bg: '#fef9c3', fg: '#a16207', border: '#fde68a' },
  red:    { bg: '#fee2e2', fg: '#b91c1c', border: '#fecaca' },
  gray:   { bg: '#f3f4f6', fg: '#6b7280', border: '#e5e7eb' },
}

const EMOJI: Record<PillColor, string> = {
  green: '🟢', yellow: '🟡', red: '🔴', gray: '⚪',
}

export function SignalPill({ firedCount, hasData, expanded, onToggle }: Props) {
  const color = pillColor(firedCount, hasData)
  const s = STYLES[color]

  let label: string
  if (!hasData) label = 'N/A'
  else if (firedCount === 0) label = 'All clear'
  else label = `${firedCount} fired`

  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    background: s.bg,
    color: s.fg,
    border: `1px solid ${s.border}`,
    borderRadius: '14px',
    padding: '4px 10px',
    fontSize: '12px',
    fontWeight: 600,
  }

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onToggle?.()
  }

  if (firedCount === 0 || !hasData) {
    return (
      <span style={baseStyle}>
        {EMOJI[color]} {label}
      </span>
    )
  }

  return (
    <button type="button" onClick={handleClick} style={{ ...baseStyle, cursor: 'pointer' }}>
      <span style={{ fontSize: '10px' }}>{expanded ? '▼' : '▶'}</span>
      {EMOJI[color]} {label}
    </button>
  )
}
