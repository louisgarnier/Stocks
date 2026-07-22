'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  formatMomentum,
  formatPct,
  matchesSearch,
  momentumColor,
  scoreTier,
  sortRows,
  verdictColors,
  verdictLabel,
  type Verdict,
  type SortDir,
} from '@/lib/screener'
import {
  ALL_COLUMNS,
  DEFAULT_VISIBLE,
  fetchResearchOverview,
  GROUP_COLORS,
  loadVisibleColumns,
  saveVisibleColumns,
  type ColAlign,
  type ColumnDef,
  type ResearchRow,
} from '@/lib/research'

const th = (align: ColAlign, sorted: boolean): React.CSSProperties => ({
  textAlign: align === 'l' ? 'left' : 'right',
  fontSize: '10px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: sorted ? '#4f46e5' : '#94a3b8',
  padding: '10px 7px',
  background: '#fafafb',
  borderBottom: '1px solid #e8eaed',
  whiteSpace: 'nowrap',
  cursor: 'pointer',
  userSelect: 'none',
})

const groupTh = (group: string): React.CSSProperties => ({
  textAlign: 'left',
  fontSize: '9px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: '#94a3b8',
  padding: '6px 7px 4px',
  background: '#fafafb',
  borderBottom: `2px solid ${GROUP_COLORS[group] ?? '#e8eaed'}`,
  whiteSpace: 'nowrap',
})

const td = (align: ColAlign): React.CSSProperties => ({
  textAlign: align === 'l' ? 'left' : 'right',
  padding: '10px 7px',
  borderBottom: '1px solid #f1f2f4',
  whiteSpace: 'nowrap',
})

function chipStyle(on: boolean): React.CSSProperties {
  return {
    fontSize: '12px',
    fontWeight: 600,
    padding: '6px 11px',
    borderRadius: '999px',
    border: on ? '1px solid #c7d2fe' : '1px solid #e2e5ea',
    background: on ? '#eef2ff' : '#fff',
    color: on ? '#4338ca' : '#475569',
    cursor: 'pointer',
  }
}

function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function VerdictBadge({ v }: { v: Verdict | null }) {
  const c = verdictColors(v)
  return (
    <span
      style={{
        fontSize: '10px',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '.03em',
        padding: '4px 9px',
        borderRadius: '6px',
        color: c.fg,
        background: c.bg,
      }}
    >
      {verdictLabel(v)}
    </span>
  )
}

// Renders one cell's value for a given column key. Keeps the special-cased
// financial formatting (verdicts, gates, momentum colours, percent fractions)
// while falling back to a plain fixed-decimal number for everything numeric.
function renderCell(col: ColumnDef, r: ResearchRow): React.ReactNode {
  const key = col.key
  const raw = (r as unknown as Record<string, unknown>)[key]

  switch (key) {
    case 'symbol':
      return (
        <>
          <div style={{ fontWeight: 700, fontSize: '14px', letterSpacing: '-.01em', color: '#0f1729' }}>
            {r.symbol}
          </div>
          <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '1px' }}>{r.name ?? '—'}</div>
        </>
      )
    case 'name':
      return <span style={{ color: '#475569' }}>{r.name ?? '—'}</span>
    case 'sector':
      return <span style={{ color: '#475569' }}>{r.sector ?? '—'}</span>
    case 'verdict':
      return <VerdictBadge v={r.verdict} />
    case 'gates_passed':
      return r.gates_passed !== null
        ? `${r.gates_passed}/${r.gates_total ?? 7}`
        : '—'
    case 'score_total':
    case 'score_tech':
    case 'score_fund': {
      const v = raw as number | null
      if (v === null || v === undefined) return '—'
      const color = key === 'score_total' ? scoreTier(v).color : '#64748b'
      return <span style={{ fontWeight: key === 'score_total' ? 700 : 400, color }}>{Math.round(v)}</span>
    }
    case 'momentum_60d':
    case 'momentum_20d':
    case 'momentum_5d': {
      const v = raw as number | null
      return <span style={{ color: momentumColor(v), fontWeight: 600 }}>{formatMomentum(v)}</span>
    }
    case 'dist_from_52w_high':
      return formatMomentum(raw as number | null)
    case 'gross_margin':
    case 'roe':
    case 'roic':
      return formatPct(raw as number | null)
    case 'consolidation_quality':
      return raw !== null && raw !== undefined ? Math.round(raw as number) : '—'
    case 'consolidation_range_pct':
    case 'breakout_strength':
      return num(raw as number | null, 2)
    case 'rsi_14':
      return num(raw as number | null, 1)
    case 'mrsi':
      return num(raw as number | null, 3)
    case 'market_cap':
    case 'volume': {
      const v = raw as number | null
      if (v === null || v === undefined) return '—'
      if (v >= 1e12) return `${(v / 1e12).toFixed(2)}T`
      if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
      if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M`
      if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`
      return String(v)
    }
    case 'volume_ratio': {
      const v = raw as number | null
      if (v === null || v === undefined) return '—'
      // >1.5× normal volume reads as notable; tint it.
      const color = v >= 1.5 ? '#b45309' : '#64748b'
      return <span style={{ color, fontWeight: v >= 1.5 ? 600 : 400 }}>{`${v.toFixed(2)}×`}</span>
    }
    case 'ma_cross_status':
    case 'breakout_status':
      return raw ? String(raw) : '—'
    // Boolean flags render as a compact ✓ / – rather than "true"/"false".
    case 'trend_aligned':
    case 'above_ma50':
    case 'above_ma200':
    case 'is_8d_consec':
    case 'volume_spike':
    case 'near_52w_high':
      if (raw === null || raw === undefined) return '—'
      return raw ? <span style={{ color: '#15803d', fontWeight: 700 }}>✓</span> : <span style={{ color: '#cbd5e1' }}>–</span>
    default:
      if (typeof raw === 'number') return num(raw, 2)
      if (raw === null || raw === undefined) return '—'
      return String(raw)
  }
}

export function ResearchGrid({ onSelectSymbol }: { onSelectSymbol: (symbol: string) => void }) {
  const [rows, setRows] = useState<ResearchRow[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [visible, setVisible] = useState<string[]>(DEFAULT_VISIBLE)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement | null>(null)

  const [search, setSearch] = useState('')
  const [minScoreOn, setMinScoreOn] = useState(false)
  const [gatesOn, setGatesOn] = useState(false)
  const [breakoutOn, setBreakoutOn] = useState(false)
  const [consolOn, setConsolOn] = useState(false)
  const [sortKey, setSortKey] = useState<string>('score_total')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  useEffect(() => {
    setVisible(loadVisibleColumns())
  }, [])

  const load = () => {
    setLoading(true)
    setError(null)
    fetchResearchOverview()
      .then((data) => setRows(data))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load research data'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  // Close the Columns menu on outside click.
  useEffect(() => {
    if (!menuOpen) return
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [menuOpen])

  const visibleColumns = useMemo(
    () => ALL_COLUMNS.filter((c) => visible.includes(c.key)),
    [visible],
  )

  // Group header row: collapse maximal runs of *adjacent* visible columns that
  // share the same `group` into one spanning cell. Walked defensively (not
  // assumed) so a hidden middle column correctly splits a group into two runs
  // instead of aggregating its total count across the whole table.
  const groupRuns = useMemo(() => {
    const runs: { group: string; span: number }[] = []
    for (const col of visibleColumns) {
      const last = runs[runs.length - 1]
      if (last && last.group === col.group) {
        last.span += 1
      } else {
        runs.push({ group: col.group, span: 1 })
      }
    }
    return runs
  }, [visibleColumns])

  const filtered = useMemo(() => {
    if (!rows) return []
    let out = rows.filter((r) => {
      if (!matchesSearch(r, search)) return false
      if (minScoreOn && !(r.score_total !== null && r.score_total >= 60)) return false
      if (gatesOn && !(r.gates_passed !== null && r.gates_passed >= 5)) return false
      if (breakoutOn && r.breakout_direction !== 'bullish') return false
      if (consolOn && !(r.consolidation_quality !== null && r.consolidation_quality > 0)) return false
      return true
    })
    out = sortRows(out, sortKey as keyof ResearchRow, sortDir)
    return out
  }, [rows, search, minScoreOn, gatesOn, breakoutOn, consolOn, sortKey, sortDir])

  const toggleSort = (key: string) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const toggleColumn = (key: string) => {
    setVisible((prev) => {
      const next = prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
      saveVisibleColumns(next)
      return next
    })
  }

  const groups = useMemo(() => {
    const g: Record<string, ColumnDef[]> = {}
    for (const c of ALL_COLUMNS) {
      ;(g[c.group] ??= []).push(c)
    }
    return g
  }, [])

  return (
    <div
      style={{
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        color: '#0f1729',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', flexWrap: 'wrap' }}>
        <Input
          placeholder="Filter symbol or company…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ minWidth: '210px', height: 'auto', padding: '7px 11px', fontSize: '13px' }}
        />
        <span style={chipStyle(minScoreOn)} onClick={() => setMinScoreOn((v) => !v)}>
          Score ≥ 60
        </span>
        <span style={chipStyle(gatesOn)} onClick={() => setGatesOn((v) => !v)}>
          Gates ≥ 5
        </span>
        <span style={chipStyle(breakoutOn)} onClick={() => setBreakoutOn((v) => !v)}>
          Breakout only
        </span>
        <span style={chipStyle(consolOn)} onClick={() => setConsolOn((v) => !v)}>
          In consolidation
        </span>
        <span style={{ flex: 1 }} />
        <div ref={menuRef} style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            style={{
              fontSize: '13px',
              fontWeight: 600,
              padding: '7px 12px',
              borderRadius: '8px',
              border: '1px solid #e2e5ea',
              background: '#fff',
              color: '#475569',
              cursor: 'pointer',
            }}
          >
            ▦ Columns
          </button>
          {menuOpen && (
            <div
              data-testid="columns-menu"
              style={{
                position: 'absolute',
                right: 0,
                top: 'calc(100% + 6px)',
                zIndex: 20,
                width: '240px',
                maxHeight: '360px',
                overflowY: 'auto',
                background: '#fff',
                border: '1px solid #e2e5ea',
                borderRadius: '10px',
                boxShadow: '0 8px 24px rgba(16,23,41,.12)',
                padding: '10px 12px',
              }}
            >
              {Object.entries(groups).map(([group, cols]) => (
                <div key={group} style={{ marginBottom: '8px' }}>
                  <div
                    style={{
                      fontSize: '9px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '.05em',
                      color: '#94a3b8',
                      margin: '4px 0',
                    }}
                  >
                    {group}
                  </div>
                  {cols.map((c) => (
                    <label
                      key={c.key}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '13px',
                        padding: '3px 0',
                        cursor: 'pointer',
                        color: '#334155',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={visible.includes(c.key)}
                        onChange={() => toggleColumn(c.key)}
                        aria-label={c.label}
                      />
                      {c.label}
                    </label>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
        <a
          href="/api/proxy/api/research/overview?format=csv"
          download
          style={{
            fontSize: '13px',
            fontWeight: 600,
            padding: '7px 12px',
            borderRadius: '8px',
            border: '1px solid #e2e5ea',
            background: '#fff',
            color: '#475569',
            cursor: 'pointer',
            textDecoration: 'none',
          }}
        >
          ↓ Export CSV
        </a>
      </div>

      {loading && (
        <div style={{ padding: '48px 0', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>Loading…</div>
      )}

      {!loading && error && (
        <div style={{ padding: '32px', textAlign: 'center', color: '#dc2626', fontSize: '13px' }}>
          <div style={{ marginBottom: '10px' }}>Failed to load research data: {error}</div>
          <button
            onClick={load}
            style={{
              fontSize: '13px',
              fontWeight: 600,
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #e2e5ea',
              background: '#fff',
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && rows !== null && (
        <>
          <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '8px' }}>
            {filtered.length} of {rows.length} symbols
          </div>
          <div
            style={{
              border: '1px solid #e8eaed',
              borderRadius: '12px',
              overflow: 'auto',
              maxHeight: '640px',
              background: '#fff',
              boxShadow: '0 1px 2px rgba(16,23,41,.04)',
            }}
          >
            <Table style={{ fontSize: '13px' }}>
              <TableHeader>
                <TableRow style={{ border: 'none' }}>
                  {groupRuns.map((run, i) => (
                    <TableHead
                      key={`${run.group}-${i}`}
                      colSpan={run.span}
                      style={groupTh(run.group)}
                    >
                      {run.group}
                    </TableHead>
                  ))}
                </TableRow>
                <TableRow style={{ border: 'none' }}>
                  {visibleColumns.map((col) => (
                    <TableHead
                      key={col.key}
                      onClick={() => toggleSort(col.key)}
                      style={th(col.align, sortKey === col.key)}
                    >
                      {col.label}
                      {sortKey === col.key && (
                        <span style={{ color: '#cbd0d8', fontSize: '9px', marginLeft: '3px' }}>
                          {sortDir === 'asc' ? '▲' : '▼'}
                        </span>
                      )}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((r) => (
                  <TableRow
                    key={r.symbol}
                    onClick={() => onSelectSymbol(r.symbol)}
                    style={{ cursor: 'pointer' }}
                  >
                    {visibleColumns.map((col) => (
                      <TableCell
                        key={col.key}
                        className={col.align === 'r' ? 'tabular-nums' : undefined}
                        style={{
                          ...td(col.align),
                          fontVariantNumeric: col.align === 'r' ? 'tabular-nums' : undefined,
                        }}
                      >
                        {renderCell(col, r)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div style={{ padding: '8px 2px', fontSize: '11px', color: '#94a3b8' }}>
            Click a row → detail popup (About · Position · Transactions · Indicators · Fundamentals · Bars)
            {' · '}
            <Badge
              style={{
                fontSize: '9px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '.04em',
                color: '#b45309',
                background: '#fef3c7',
                border: '1px solid #fde68a',
                padding: '2px 7px',
                borderRadius: '999px',
              }}
            >
              Provisional scoring
            </Badge>
          </div>
        </>
      )}
    </div>
  )
}
