'use client'

import { useEffect, useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  breakoutBadge,
  brokeOutLast3d,
  fetchOverview,
  formatMomentum,
  formatPct,
  matchesSearch,
  momentumColor,
  scoreTier,
  sortRows,
  verdictColors,
  verdictLabel,
  type ScreenerRow,
  type SortDir,
} from '@/lib/screener'

type SortKey =
  | 'symbol'
  | 'score_total'
  | 'score_tech'
  | 'score_fund'
  | 'gates_passed'
  | 'momentum_60d'
  | 'breakout_strength'
  | 'consolidation_quality'
  | 'roic'
  | 'roe'
  | 'gross_margin'
  | 'verdict'

const COLUMNS: { key: SortKey; label: string; align: 'l' | 'r' }[] = [
  { key: 'symbol', label: 'Symbol', align: 'l' },
  { key: 'score_total', label: 'Total', align: 'r' },
  { key: 'score_tech', label: 'Tech', align: 'r' },
  { key: 'score_fund', label: 'Fund', align: 'r' },
  { key: 'gates_passed', label: 'Quality gates', align: 'r' },
  { key: 'momentum_60d', label: 'Mom 60d', align: 'r' },
  { key: 'breakout_strength', label: 'Breakout', align: 'r' },
  { key: 'consolidation_quality', label: 'Consolidation', align: 'l' },
  { key: 'roic', label: 'ROIC', align: 'r' },
  { key: 'roe', label: 'ROE', align: 'r' },
  { key: 'gross_margin', label: 'Gross M', align: 'r' },
  { key: 'verdict', label: 'Verdict', align: 'r' },
]

const th = (align: 'l' | 'r', sorted: boolean): React.CSSProperties => ({
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

const td = (align: 'l' | 'r'): React.CSSProperties => ({
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

function GatesMeter({ passed, total }: { passed: number | null; total: number | null }) {
  if (passed === null || passed === undefined || total === null || total === undefined) {
    return <span style={{ color: '#cbd0d8' }}>—</span>
  }
  const segs = Array.from({ length: total }, (_, i) => i < passed)
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ display: 'inline-flex', gap: '2px' }}>
        {segs.map((on, i) => (
          <span
            key={i}
            style={{
              width: '6px',
              height: '14px',
              borderRadius: '2px',
              background: on ? '#16a34a' : '#e5e8ec',
              display: 'inline-block',
            }}
          />
        ))}
      </span>
      <b style={{ fontSize: '12px', fontWeight: 700 }}>
        {passed}/{total}
      </b>
    </div>
  )
}

export function ScreenerGrid() {
  const [rows, setRows] = useState<ScreenerRow[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [sector, setSector] = useState('all')
  const [minScoreOn, setMinScoreOn] = useState(false)
  const [gatesOn, setGatesOn] = useState(false)
  const [breakoutOn, setBreakoutOn] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('score_total')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const load = () => {
    setLoading(true)
    setError(null)
    fetchOverview()
      .then((data) => setRows(data.rows))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load screener data'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const sectors = useMemo(() => {
    if (!rows) return []
    return Array.from(new Set(rows.map((r) => r.sector).filter((s): s is string => Boolean(s)))).sort()
  }, [rows])

  const filtered = useMemo(() => {
    if (!rows) return []
    let out = rows.filter((r) => {
      if (!matchesSearch(r, search)) return false
      if (sector !== 'all' && r.sector !== sector) return false
      if (minScoreOn && !(r.score_total !== null && r.score_total >= 70)) return false
      if (gatesOn && !(r.gates_passed !== null && r.gates_passed >= 5)) return false
      if (breakoutOn && !brokeOutLast3d(r)) return false
      return true
    })
    out = sortRows<ScreenerRow>(out, sortKey, sortDir)
    return out
  }, [rows, search, sector, minScoreOn, gatesOn, breakoutOn, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const isEmptyData =
    !loading && !error && rows !== null && (rows.length === 0 || rows.every((r) => r.score_total === null))

  return (
    <div
      style={{
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        color: '#0f1729',
        background: '#fbfbfc',
        padding: '22px 16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '18px' }}>
        <div>
          <h1 style={{ fontSize: '22px', fontWeight: 700, letterSpacing: '-0.02em', margin: 0 }}>Screener</h1>
          <div style={{ fontSize: '13px', color: '#64748b', marginTop: '3px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Diagnostic view — buy-side candidates across your tracked universe</span>
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
        </div>
      </div>

      {loading && (
        <div style={{ padding: '48px 0', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>Loading…</div>
      )}

      {!loading && error && (
        <div style={{ padding: '32px', textAlign: 'center', color: '#dc2626', fontSize: '13px' }}>
          <div style={{ marginBottom: '10px' }}>Failed to load screener data: {error}</div>
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

      {!loading && !error && isEmptyData && (
        <div style={{ padding: '48px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
          No screener data yet. Run the screen sync from Configuration.
        </div>
      )}

      {!loading && !error && rows !== null && !isEmptyData && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px', flexWrap: 'wrap' }}>
            <Input
              placeholder="Search ticker or company…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ minWidth: '230px', height: 'auto', padding: '7px 11px', fontSize: '13px' }}
            />
            <Select value={sector} onValueChange={setSector}>
              <SelectTrigger style={{ fontSize: '13px', height: 'auto', padding: '7px 11px' }}>
                <SelectValue placeholder="All sectors" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All sectors</SelectItem>
                {sectors.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span style={chipStyle(minScoreOn)} onClick={() => setMinScoreOn((v) => !v)}>
              Score ≥ 70
            </span>
            <span style={chipStyle(gatesOn)} onClick={() => setGatesOn((v) => !v)}>
              Gates ≥ 5/7
            </span>
            <span style={chipStyle(breakoutOn)} onClick={() => setBreakoutOn((v) => !v)}>
              Just broke out (last 3d) {breakoutOn ? '✓' : ''}
            </span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>
              {filtered.length} of {rows.length} symbols
            </span>
          </div>

          <div
            style={{
              border: '1px solid #e8eaed',
              borderRadius: '12px',
              overflow: 'hidden',
              background: '#fff',
              boxShadow: '0 1px 2px rgba(16,23,41,.04)',
            }}
          >
            <Table style={{ fontSize: '13px' }}>
              <TableHeader>
                <TableRow style={{ border: 'none' }}>
                  {COLUMNS.map((col) => (
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
                {filtered.map((r) => {
                  const tier = scoreTier(r.score_total)
                  const bo = breakoutBadge(r)
                  const vColors = verdictColors(r.verdict)
                  return (
                    <TableRow key={r.symbol} style={{ cursor: 'default' }}>
                      <TableCell style={td('l')}>
                        <div style={{ fontWeight: 700, fontSize: '14px', letterSpacing: '-.01em' }}>{r.symbol}</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '1px' }}>
                          {r.name ?? '—'}{' '}
                          {r.sector && (
                            <span
                              style={{
                                fontSize: '9px',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                letterSpacing: '.03em',
                                color: '#64748b',
                                background: '#f1f5f9',
                                padding: '2px 6px',
                                borderRadius: '4px',
                              }}
                            >
                              {r.sector}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell style={td('r')}>
                        <div
                          className="tabular-nums"
                          style={{ fontSize: '16px', fontWeight: 700, color: tier.color, fontVariantNumeric: 'tabular-nums' }}
                        >
                          {r.score_total !== null ? Math.round(r.score_total) : '—'}
                        </div>
                        {r.score_total !== null && (
                          <div style={{ height: '4px', width: '46px', background: '#eef0f3', borderRadius: '3px', marginTop: '4px', marginLeft: 'auto', overflow: 'hidden' }}>
                            <span
                              style={{
                                display: 'block',
                                height: '100%',
                                borderRadius: '3px',
                                width: `${Math.max(0, Math.min(100, r.score_total))}%`,
                                background: tier.color,
                              }}
                            />
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="tabular-nums" style={{ ...td('r'), color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
                        {r.score_tech !== null ? Math.round(r.score_tech) : '—'}
                      </TableCell>
                      <TableCell className="tabular-nums" style={{ ...td('r'), color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
                        {r.score_fund !== null ? Math.round(r.score_fund) : '—'}
                      </TableCell>
                      <TableCell style={td('r')}>
                        <GatesMeter passed={r.gates_passed} total={r.gates_total} />
                      </TableCell>
                      <TableCell
                        className="tabular-nums"
                        style={{ ...td('r'), color: momentumColor(r.momentum_60d), fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}
                      >
                        {formatMomentum(r.momentum_60d)}
                      </TableCell>
                      <TableCell style={td('r')}>
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            letterSpacing: '.03em',
                            padding: '3px 8px',
                            borderRadius: '5px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: bo.fg,
                            background: bo.bg,
                          }}
                        >
                          {bo.label}
                        </span>
                      </TableCell>
                      <TableCell style={td('l')}>
                        {r.consolidation_quality !== null ? (
                          <>
                            <b className="tabular-nums" style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                              {Math.round(r.consolidation_quality)}
                            </b>
                            <span style={{ fontSize: '10px', color: '#94a3b8', marginLeft: '4px' }}>
                              {r.consolidation_timeframe ?? ''}
                            </span>
                          </>
                        ) : (
                          <span style={{ color: '#cbd0d8' }}>—</span>
                        )}
                      </TableCell>
                      <TableCell className="tabular-nums" style={{ ...td('r'), fontVariantNumeric: 'tabular-nums' }}>
                        {formatPct(r.roic)}
                      </TableCell>
                      <TableCell className="tabular-nums" style={{ ...td('r'), fontVariantNumeric: 'tabular-nums' }}>
                        {formatPct(r.roe)}
                      </TableCell>
                      <TableCell className="tabular-nums" style={{ ...td('r'), fontVariantNumeric: 'tabular-nums' }}>
                        {formatPct(r.gross_margin)}
                      </TableCell>
                      <TableCell style={td('r')}>
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            letterSpacing: '.03em',
                            padding: '4px 9px',
                            borderRadius: '6px',
                            color: vColors.fg,
                            background: vColors.bg,
                          }}
                        >
                          {verdictLabel(r.verdict)}
                        </span>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>

          <div style={{ display: 'flex', gap: '18px', marginTop: '12px', fontSize: '11px', color: '#94a3b8', flexWrap: 'wrap' }}>
            <span>
              <b style={{ color: '#64748b', fontWeight: 600 }}>Total</b> = blended tech + fundamental (provisional, Phase 1 — weights not yet calibrated)
            </span>
            <span>
              <b style={{ color: '#64748b', fontWeight: 600 }}>Quality gates</b> = MOAT scorecard, gates passed / 7
            </span>
            <span>
              <b style={{ color: '#64748b', fontWeight: 600 }}>Breakout</b> = last 3–4 days · strength 0–1
            </span>
            <span>Click any row → deep-dive (Phase 3)</span>
          </div>
        </>
      )}
    </div>
  )
}
