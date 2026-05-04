# STORY-G-5 — Positions tab Signals column + click-to-expand panel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Signals` column to the Positions tab showing a colored pill (🟢/🟡/🔴/⚪) per holding, with click-to-expand inline panel listing fired sell signals — without disturbing the existing row → SecurityDetailSheet click behavior.

**Architecture:** Three small files isolated under `frontend/components/positions/` + `frontend/lib/`. Page-level state added to the existing dashboard for `signalsBySymbol` (fetched alongside positions) and `expandedSignalSymbols` (a Set). Inline `<tr><td colSpan>` expand row beneath each clicked-pill row — no new shadcn primitive, matches existing inline-styled pattern. Pill click `stopPropagation`s so the row click still opens the Sheet.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind v4 (existing). Jest + Testing Library for tests (config repaired in Task 0). Backend endpoints already exist from STORY-G-3: `GET /api/holding-signals`, `POST /api/sync/holding-signals`.

---

## File structure

| File | Responsibility |
|---|---|
| `frontend/jest.config.js` (create) | Wire `next/jest` so SWC transforms TSX in tests |
| `frontend/lib/holding-signals.ts` (create) | Types, fetch helper, signal label/format/pill-color utilities (pure functions) |
| `frontend/__tests__/holding-signals.test.ts` (create) | Unit tests for the pure utilities |
| `frontend/components/positions/SignalPill.tsx` (create) | Colored pill with chevron, click handler, stop-propagation |
| `frontend/__tests__/SignalPill.test.tsx` (create) | Render + click tests |
| `frontend/components/positions/SignalsExpandPanel.tsx` (create) | Inline tr panel: fired list grid + not-fired footer + timestamp |
| `frontend/__tests__/SignalsExpandPanel.test.tsx` (create) | Render fired/all-clear/N-A states |
| `frontend/app/page.tsx` (modify) | State + fetch + summary card + filter checkbox + Signals column + expand row |
| `frontend/__tests__/example.test.tsx` (delete or rewrite) | Stale template test referencing non-existent "Template Project" text |

---

### Task 0: Repair frontend Jest config

The existing `frontend/__tests__/example.test.tsx` cannot parse — there is no `jest.config.js` so JSX/TSX falls through to default Babel without React preset. Fix once for the whole project; subsequent tasks depend on this.

**Files:**
- Create: `frontend/jest.config.js`
- Delete: `frontend/__tests__/example.test.tsx` (refers to "Template Project" string that no longer exists in page.tsx)

- [ ] **Step 1: Create `frontend/jest.config.js`**

```javascript
const nextJest = require('next/jest')

const createJestConfig = nextJest({
  // Path to Next.js app — loads next.config + .env files
  dir: './',
})

const customJestConfig = {
  setupFilesAfterEach: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
}

module.exports = createJestConfig(customJestConfig)
```

- [ ] **Step 2: Delete the stale template test**

```bash
rm /Users/louisgarnier/Claude/Stocks/frontend/__tests__/example.test.tsx
```

- [ ] **Step 3: Verify jest runs cleanly with no test files**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx jest --passWithNoTests`
Expected: `No tests found, exiting with code 0`

- [ ] **Step 4: Commit**

```bash
git add frontend/jest.config.js frontend/__tests__/example.test.tsx
git commit -m "[STORY-G-5] chore: wire next/jest for frontend tests; drop stale template test"
```

---

### Task 1: Helper module `holding-signals.ts`

Pure TypeScript: types matching backend API + label/format/pill-color helpers. No React, no fetch yet — those come in step 4 of this task.

**Files:**
- Create: `frontend/lib/holding-signals.ts`
- Test: `frontend/__tests__/holding-signals.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/__tests__/holding-signals.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run tests, expect failure (no module yet)**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx jest holding-signals.test`
Expected: FAIL — `Cannot find module '../lib/holding-signals'`

- [ ] **Step 3: Create the module**

Create `frontend/lib/holding-signals.ts`:

```typescript
export interface HoldingSignal {
  signal_type: string
  fired: boolean
  value: number | null
  threshold: number | null
  last_evaluated_at: string
}

export interface HoldingSignalsResponse {
  items: Array<HoldingSignal & { symbol: string }>
  count: number
}

export type SignalsBySymbol = Record<string, HoldingSignal[]>
export type PillColor = 'green' | 'yellow' | 'red' | 'gray'

const LABELS: Record<string, string> = {
  ma50_break: 'MA50 break',
  ma100_break: 'MA100 break',
  ma150_break: 'MA150 break',
  ma200_break: 'MA200 break',
  death_cross: 'Death cross',
  volume_dryup: 'Volume dryup',
  distribution_day: 'Distribution day',
  rsi_weakness: 'RSI weakness',
  mrsi_flip: 'MRSI flip',
  trailing_drawdown: 'Trailing drawdown',
  stop_loss: 'Stop loss',
}

export function signalLabel(signalType: string): string {
  return LABELS[signalType] ?? signalType
}

export function countFired(signals: HoldingSignal[]): number {
  return signals.reduce((n, s) => n + (s.fired ? 1 : 0), 0)
}

export function pillColor(firedCount: number, hasData: boolean): PillColor {
  if (!hasData) return 'gray'
  if (firedCount === 0) return 'green'
  if (firedCount <= 2) return 'yellow'
  return 'red'
}

function fmtCurrency(v: number, currency: string): string {
  const sym = currency === 'EUR' ? '€' : currency === 'GBP' ? '£' : '$'
  return `${sym}${v.toFixed(2)}`
}

export function formatSignalValue(s: HoldingSignal, currency: string): string {
  if (s.value === null || s.threshold === null) return '—'
  const v = s.value
  const t = s.threshold
  switch (s.signal_type) {
    case 'ma50_break':
    case 'ma100_break':
    case 'ma150_break':
    case 'ma200_break':
    case 'trailing_drawdown':
    case 'stop_loss':
      return `${fmtCurrency(v, currency)} < ${fmtCurrency(t, currency)}`
    case 'death_cross':
      return `MA50 ${fmtCurrency(v, currency)} crossed below MA150 ${fmtCurrency(t, currency)}`
    case 'volume_dryup':
      return `5d avg ${Math.round(v).toLocaleString()} < ${Math.round(t).toLocaleString()}`
    case 'distribution_day':
      return `vol ${Math.round(v).toLocaleString()} > ${Math.round(t).toLocaleString()}`
    case 'rsi_weakness':
      return `RSI ${v.toFixed(1)} < ${t.toFixed(1)}`
    case 'mrsi_flip':
      return `MRSI ${v.toFixed(3)} crossed below 0`
    default:
      return `${v} vs ${t}`
  }
}

export async function fetchHoldingSignals(): Promise<SignalsBySymbol> {
  const res = await fetch('/api/proxy/api/holding-signals')
  if (!res.ok) throw new Error(`fetchHoldingSignals: HTTP ${res.status}`)
  const data: HoldingSignalsResponse = await res.json()
  const map: SignalsBySymbol = {}
  for (const item of data.items) {
    const { symbol, ...rest } = item
    if (!map[symbol]) map[symbol] = []
    map[symbol].push(rest)
  }
  return map
}
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx jest holding-signals.test`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/holding-signals.ts frontend/__tests__/holding-signals.test.ts
git commit -m "[STORY-G-5] feat: holding-signals client lib (types, label/format/pill-color helpers)"
```

---

### Task 2: `SignalPill` component

A standalone clickable badge, color-coded. Caller passes the count + whether it has data; the pill knows nothing about data fetching.

**Files:**
- Create: `frontend/components/positions/SignalPill.tsx`
- Test: `frontend/__tests__/SignalPill.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/__tests__/SignalPill.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { SignalPill } from '../components/positions/SignalPill'

describe('SignalPill', () => {
  it('renders "All clear" when 0 fired and has data', () => {
    render(<SignalPill firedCount={0} hasData expanded={false} />)
    expect(screen.getByText(/all clear/i)).toBeInTheDocument()
  })

  it('renders "N fired" with collapsed chevron when fired > 0', () => {
    render(<SignalPill firedCount={3} hasData expanded={false} onToggle={() => {}} />)
    expect(screen.getByText(/3 fired/i)).toBeInTheDocument()
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders N/A when no data', () => {
    render(<SignalPill firedCount={0} hasData={false} expanded={false} />)
    expect(screen.getByText(/n\/a/i)).toBeInTheDocument()
  })

  it('calls onToggle and stops propagation when clicked', () => {
    const onToggle = jest.fn()
    const onRowClick = jest.fn()
    render(
      <table><tbody>
        <tr onClick={onRowClick}>
          <td><SignalPill firedCount={2} hasData expanded={false} onToggle={onToggle} /></td>
        </tr>
      </tbody></table>,
    )
    fireEvent.click(screen.getByRole('button'))
    expect(onToggle).toHaveBeenCalledTimes(1)
    expect(onRowClick).not.toHaveBeenCalled()
  })

  it('does not render a button when 0 fired (nothing to expand)', () => {
    render(<SignalPill firedCount={0} hasData expanded={false} />)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests, expect failure**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx jest SignalPill.test`
Expected: FAIL — `Cannot find module`

- [ ] **Step 3: Create the component**

Create `frontend/components/positions/SignalPill.tsx`:

```tsx
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
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx jest SignalPill.test`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/components/positions/SignalPill.tsx frontend/__tests__/SignalPill.test.tsx
git commit -m "[STORY-G-5] feat: SignalPill component (green/yellow/red/gray, stop-propagation on click)"
```

---

### Task 3: `SignalsExpandPanel` component

The inline panel that appears underneath the row when the pill is clicked. Renders fired signals in a 2-column grid + a muted "not fired" footer + a timestamp.

**Files:**
- Create: `frontend/components/positions/SignalsExpandPanel.tsx`
- Test: `frontend/__tests__/SignalsExpandPanel.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/__tests__/SignalsExpandPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { SignalsExpandPanel } from '../components/positions/SignalsExpandPanel'
import type { HoldingSignal } from '../lib/holding-signals'

const sig = (signal_type: string, fired: boolean, value: number | null = 100, threshold: number | null = 110): HoldingSignal => ({
  signal_type, fired, value, threshold, last_evaluated_at: '2026-05-04T09:02:14',
})

describe('SignalsExpandPanel', () => {
  it('lists each fired signal with its formatted value', () => {
    render(
      <table><tbody><SignalsExpandPanel
        signals={[sig('ma50_break', true, 138.4, 145.2), sig('rsi_weakness', true, 47, 50)]}
        currency="USD"
        colSpan={6}
      /></tbody></table>,
    )
    expect(screen.getByText('MA50 break')).toBeInTheDocument()
    expect(screen.getByText('$138.40 < $145.20')).toBeInTheDocument()
    expect(screen.getByText('RSI weakness')).toBeInTheDocument()
    expect(screen.getByText('RSI 47.0 < 50.0')).toBeInTheDocument()
  })

  it('lists not-fired signals in the muted footer', () => {
    render(
      <table><tbody><SignalsExpandPanel
        signals={[sig('ma50_break', true), sig('ma200_break', false), sig('death_cross', false)]}
        currency="USD"
        colSpan={6}
      /></tbody></table>,
    )
    expect(screen.getByText(/not fired:/i).textContent).toContain('MA200 break')
    expect(screen.getByText(/not fired:/i).textContent).toContain('Death cross')
  })

  it('renders timestamp', () => {
    render(
      <table><tbody><SignalsExpandPanel
        signals={[sig('ma50_break', true)]}
        currency="USD"
        colSpan={6}
      /></tbody></table>,
    )
    expect(screen.getByText(/last evaluated/i)).toBeInTheDocument()
  })

  it('renders nothing if signals array is empty', () => {
    const { container } = render(
      <table><tbody><SignalsExpandPanel signals={[]} currency="USD" colSpan={6} /></tbody></table>,
    )
    expect(container.querySelector('td')).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests, expect failure**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx jest SignalsExpandPanel.test`
Expected: FAIL — `Cannot find module`

- [ ] **Step 3: Create the component**

Create `frontend/components/positions/SignalsExpandPanel.tsx`:

```tsx
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
```

- [ ] **Step 4: Run tests, expect pass**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx jest SignalsExpandPanel.test`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/components/positions/SignalsExpandPanel.tsx frontend/__tests__/SignalsExpandPanel.test.tsx
git commit -m "[STORY-G-5] feat: SignalsExpandPanel inline tr with fired list grid + not-fired footer"
```

---

### Task 4: Wire into Positions tab in `page.tsx`

Add state, fetch, summary card, filter checkbox, table column, and expand row. All other tabs/code paths untouched.

**Files:**
- Modify: `frontend/app/page.tsx` (state declarations near line 230, fetch in `fetchPositions` ~line 610, JSX in Positions tab ~line 2631-2817)

- [ ] **Step 1: Add the imports at the top of page.tsx**

Change the existing `import { useEffect, useState } from 'react';` to also import `Fragment`:

```typescript
import { useEffect, useState, Fragment } from 'react';
```

Add three new imports below the existing component imports (around line 12, after `SecurityDetailSheet`):

```typescript
import { SignalPill } from '@/components/positions/SignalPill';
import { SignalsExpandPanel } from '@/components/positions/SignalsExpandPanel';
import { fetchHoldingSignals, countFired, type SignalsBySymbol } from '@/lib/holding-signals';
```

- [ ] **Step 2: Add state hooks alongside existing positions state**

After the existing `const [positionsSymbolFilter, setPositionsSymbolFilter] = useState<string>('')` line, add:

```typescript
const [signalsBySymbol, setSignalsBySymbol] = useState<SignalsBySymbol>({})
const [expandedSignalSymbols, setExpandedSignalSymbols] = useState<Set<string>>(new Set())
const [onlySignalsFired, setOnlySignalsFired] = useState(false)
```

- [ ] **Step 3: Fetch signals alongside positions**

The existing `fetchPositions` (at line ~610 in `frontend/app/page.tsx`) is:

```typescript
const fetchPositions = async () => {
  try {
    const response = await fetch('/api/proxy/api/positions');
    if (response.ok) {
      const data = await response.json();
      setPositions(data);
    }
  } catch (err) {
    console.error('❌ Failed to fetch positions:', err);
  }
};
```

Replace it with:

```typescript
const fetchPositions = async () => {
  try {
    const response = await fetch('/api/proxy/api/positions');
    if (response.ok) {
      const data = await response.json();
      setPositions(data);
    }
  } catch (err) {
    console.error('❌ Failed to fetch positions:', err);
  }
  try {
    const map = await fetchHoldingSignals();
    setSignalsBySymbol(map);
  } catch (err) {
    console.warn('⚠️ holding-signals fetch failed:', err);
    setSignalsBySymbol({});
  }
};
```

The two try blocks are independent — if positions fetch fails, signals still attempt; if signals fail (e.g. fresh DB with no rows yet), positions still render with all-N/A pills.

- [ ] **Step 4: Add a toggle helper near other handlers**

Near the existing `handlePositionsSort` function, add:

```typescript
const toggleSignalExpand = (symbol: string) => {
  setExpandedSignalSymbols((prev) => {
    const next = new Set(prev)
    if (next.has(symbol)) next.delete(symbol)
    else next.add(symbol)
    return next
  })
}
```

- [ ] **Step 5: Filter holdings without signals when checkbox on**

The existing `getSortedAndFilteredPositions` (at line ~628) is:

```typescript
const getSortedAndFilteredPositions = (): Position[] => {
  if (!positions?.positions) return [];
  let filtered = positions.positions;
  if (positionsSymbolFilter) {
    filtered = filtered.filter((pos: Position) =>
      pos.symbol.toLowerCase().includes(positionsSymbolFilter.toLowerCase())
    );
  }
  return [...filtered].sort((a: Position, b: Position) => {
    let aVal: number | string = a[positionsSortBy];
    let bVal: number | string = b[positionsSortBy];
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase();
      bVal = (bVal as string).toLowerCase();
    }
    if (aVal < bVal) return positionsSortOrder === 'asc' ? -1 : 1;
    if (aVal > bVal) return positionsSortOrder === 'asc' ? 1 : -1;
    return 0;
  });
};
```

Insert the new filter right after the existing symbol filter. After the closing `}` of the `if (positionsSymbolFilter) { ... }` block, add:

```typescript
  if (onlySignalsFired) {
    filtered = filtered.filter((pos: Position) => countFired(signalsBySymbol[pos.symbol] ?? []) > 0);
  }
```

The `[...filtered].sort(...)` block stays unchanged.

- [ ] **Step 6: Add the second summary card**

Inside the Positions tab summary cards block (currently a single Open Positions card around line 2654), add a second card after it:

```tsx
{(() => {
  const heldSyms = positions?.positions?.map((p) => p.symbol) ?? []
  const flagged = heldSyms.filter((s) => countFired(signalsBySymbol[s] ?? []) > 0).length
  if (flagged === 0) return null
  return (
    <div style={{ backgroundColor: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '16px', minWidth: '180px' }}>
      <p style={{ fontSize: '12px', color: '#dc2626', fontWeight: '500', margin: 0 }}>⚠️ Holdings with sell signals</p>
      <p style={{ fontSize: '24px', fontWeight: '600', color: '#b91c1c', margin: 0 }}>
        {flagged}<span style={{ fontSize: '14px', fontWeight: 500, color: '#9ca3af', marginLeft: '6px' }}>of {heldSyms.length}</span>
      </p>
    </div>
  )
})()}
```

- [ ] **Step 7: Add the "Only with signals fired" filter checkbox**

In the row currently containing just `<h4>IBKR Open Positions</h4>` and the symbol-filter `<input>`, replace the right side group with:

```tsx
<div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
  <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#6b7280', cursor: 'pointer' }}>
    <input
      type="checkbox"
      checked={onlySignalsFired}
      onChange={(e) => setOnlySignalsFired(e.target.checked)}
      style={{ cursor: 'pointer' }}
    />
    Only with signals fired
  </label>
  <input
    type="text"
    placeholder="Filter by symbol..."
    value={positionsSymbolFilter}
    onChange={(e) => setPositionsSymbolFilter(e.target.value.toUpperCase())}
    style={{ padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '13px', width: '180px' }}
  />
</div>
```

- [ ] **Step 8: Add the Signals column header**

In the existing column-config array (the one with `symbol`, `quantity`, `cost_basis_price`, `position_value`, `unrealized_pnl`), the Signals column is NOT sortable, so add it as a separate `<th>` after the `.map(...)` block:

```tsx
<th style={{ padding: '12px', textAlign: 'center', fontSize: '12px', fontWeight: 600, color: '#6b7280', borderBottom: '1px solid #e5e7eb', width: '120px' }}>
  Signals
</th>
```

- [ ] **Step 9: Add the Signals `<td>` and the expand row inside the row map**

Inside the existing `.map((pos: Position) => { ... return (<tr ...>...</tr>) })`, change the return to a fragment with the original `<tr>` plus an optional `<SignalsExpandPanel>` row. Replace the `return (<tr>...</tr>)` block with:

```tsx
const signals = signalsBySymbol[pos.symbol] ?? []
const hasData = signals.length > 0
const fired = countFired(signals)
const expanded = expandedSignalSymbols.has(pos.symbol)
return (
  <Fragment key={pos.symbol}>
    <tr
      style={{ borderBottom: '1px solid #e5e7eb', cursor: 'pointer', background: fired > 0 && expanded ? '#fff7f7' : undefined }}
      onClick={() => setSelectedSymbol(pos.symbol)}
    >
      <td style={{ padding: '12px', fontSize: '14px', fontWeight: '600', color: '#1f2937' }}>
        {pos.symbol}
        <span style={{ fontSize: '11px', color: '#9ca3af', fontWeight: '400', marginLeft: '6px' }}>{pos.currency}</span>
      </td>
      <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', color: '#1f2937' }}>{pos.quantity.toFixed(0)}</td>
      <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', color: '#1f2937' }}>{currencySymbol}{pos.cost_basis_price.toFixed(2)}</td>
      <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '500', color: '#1f2937' }}>{currencySymbol}{(pos.position_value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      <td style={{ padding: '12px', textAlign: 'right', fontSize: '14px', fontWeight: '500', color: pos.unrealized_pnl >= 0 ? '#16a34a' : '#dc2626' }}>{pos.unrealized_pnl >= 0 ? '+' : ''}{currencySymbol}{(pos.unrealized_pnl || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
      <td style={{ padding: '12px', textAlign: 'center' }}>
        <SignalPill firedCount={fired} hasData={hasData} expanded={expanded} onToggle={() => toggleSignalExpand(pos.symbol)} />
      </td>
    </tr>
    {expanded && hasData && fired > 0 && (
      <SignalsExpandPanel signals={signals} currency={pos.currency} colSpan={6} />
    )}
  </Fragment>
)
```

The `Fragment` import added in Step 1 is what allows `<Fragment key={...}>` here.

- [ ] **Step 10: Update the tfoot colSpan from 3 to keep totals row alignment**

Look at the tfoot rows: each currency total has `<td colSpan={3}>` followed by 2 individual `<td>` (Market Value, P&L). Now there's a 6th column. Add an empty `<td>` at the end of each total row:

```tsx
// after the existing P&L <td> in each total row, add:
<td style={{ padding: '12px' }} />
```

(Apply to USD, EUR, OTHER total rows.)

- [ ] **Step 11: Type-check the file**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit`
Expected: no errors

- [ ] **Step 12: Lint**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npm run lint -- --max-warnings 0`
Expected: no errors

- [ ] **Step 13: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "[STORY-G-5] feat: wire Signals column + expand panel into Positions tab"
```

---

### Task 5: End-to-end smoke test

Verify in the browser against real data, then mark the story closed.

- [ ] **Step 1: Start backend**

Run in a terminal: `cd /Users/louisgarnier/Claude/Stocks && bash start.sh` (or whatever the project's launcher is)

- [ ] **Step 2: Trigger a sync to populate signals**

Run: `curl -X POST http://localhost:8000/api/sync/holding-signals`
Expected: `{"success": true, "symbols_processed": N, "signals_evaluated": M}` with N matching held-position count.

- [ ] **Step 3: Open the frontend at http://localhost:3000 → Positions tab**

Verify by visual inspection:
- Signals column appears as the 6th column with a colored pill per row
- 0-fired holdings show 🟢 "All clear" (non-clickable span)
- 1-2-fired holdings show 🟡 "N fired" button with chevron
- 3+-fired holdings show 🔴 "N fired" button
- Holdings with no indicators yet show ⚪ "N/A"
- Clicking a yellow/red pill expands an inline panel; click again collapses it
- Clicking the row (anywhere outside the pill) opens the Security Detail Sheet
- Pill click does NOT open the Sheet (stop-propagation works)
- "Only with signals fired" checkbox filters the table
- "⚠️ Holdings with sell signals" summary card appears when ≥1 signal is fired anywhere

- [ ] **Step 4: Update ACTIVE.md to mark G-5 done**

Edit `/Users/louisgarnier/Claude/Stocks/docs/project/config/epics/ACTIVE.md` — flip `⏳ G-5` to `✅ G-5`.

- [ ] **Step 5: Commit smoke confirmation + ACTIVE.md update**

```bash
git add docs/project/config/epics/ACTIVE.md
git commit -m "[STORY-G-5] docs: mark Positions tab Signals column shipped"
```

---

## Acceptance criteria (from spec)

- [x] Positions tab traffic light renders correctly per holding — Task 4 step 9
- [x] Click-to-expand shows fired signals with values — Task 3 + Task 4 step 9
- [x] Sync time <10s for typical 15-holding portfolio — backend (already verified in STORY-G-2)
- [ ] Threshold changes in Configuration take effect on next sync — out of scope for G-5; covered in G-6

## Out of scope for G-5 (explicitly)

- Configuration sub-section to toggle signals + tune thresholds (that's G-6)
- Signals card inside SecurityDetailSheet (bonus item, separate follow-up)
- Per-position muting (deferred per spec)
- Real-time polling — signals refresh only when `fetchPositions` runs

## Risks

| Risk | Mitigation |
|---|---|
| `fetchHoldingSignals` 500s on first load (no signals computed yet) | Wrapped in try/catch; falls back to empty map; pills render as ⚪ N/A everywhere |
| `colSpan` math drifts if someone adds another column later | Hard-coded `6` in two places — kept short comment in code if useful (see below) |
| React 19 + RTL 14 compatibility quirks | Mitigated by `next/jest` config; if tests still fail, bump `@testing-library/react` to 16.x as a follow-up |
