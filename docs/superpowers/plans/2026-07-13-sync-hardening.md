# Sync Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the analytics sync subsystem robust — a running sync no longer blocks the dashboard, survives tab navigation with persistent progress, cannot be double-started, and is actionable from the Dashboard where the staleness chips already live.

**Architecture:** Three root fixes found during Epic V testing. (1) Put SQLite in WAL mode with a busy-timeout so a long write sync stops blocking the dashboard read. (2) Lift sync orchestration out of the tab-scoped `SyncToolbar` into an app-level React context (`SyncProvider`) mounted above the tabs, so the awaited fetch and its progress state survive navigation and a global guard prevents overlapping runs. (3) Wire the Dashboard staleness chips and a new "Sync all" button to that provider so the Dashboard becomes the sync hub.

**Tech Stack:** FastAPI + SQLite (backend, `sqlite3` stdlib), Next.js 15 App Router + React 19 + TypeScript (frontend), pytest (backend tests), Jest + @testing-library/react (frontend tests).

## Global Constraints

- Backend tests run with `backend/venv/bin/python -m pytest`; frontend tests with `cd frontend && npx jest`.
- Frontend is EUR-base, English-only UI (carried from Epic V) — any new copy is English.
- No new dependencies. Provider uses React's built-in `createContext`/`useContext` only.
- Commit format: `[STORY-SH-n] type: description`, trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Plain git (there is no `scripts/git_ops.py`).
- Do NOT alter the header's existing IBKR/flex sync flow in `app/page.tsx` (`handleFlexImport`/`flexLoading`, the `🔄 Sync IBKR` button) — it works and is always mounted. The provider adds a *separate* lightweight `ibkr` action for the dashboard chip only.
- `backend/database/connection.py` carries a "check with the user before modifying" banner; the user has approved the WAL change for this epic.
- Sync step keys are exactly: `'fundamentals' | 'technical' | 'compute' | 'all' | 'ibkr'`. Backend sync paths (POSTed as `/api/proxy/api/sync/${path}`): `fundamentals`, `market-data`, `analytics`, `screen`, `ibkr`. "Technical" = `market-data` then `analytics`. "All" = Technical → `fundamentals` → `screen`.

---

### Task 1: SQLite WAL mode + busy-timeout

**Files:**
- Modify: `backend/database/connection.py:19-32` (`get_db_connection`)
- Test: `backend/tests/test_connection_wal.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `get_db_connection()` now returns a connection whose `PRAGMA journal_mode` is `wal` and whose `PRAGMA busy_timeout` is `30000`. Same return type (`sqlite3.Connection`) and existing behaviour (row_factory, foreign_keys) preserved.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_connection_wal.py`:

```python
"""WAL + busy-timeout: a read must not block behind a concurrent write."""
import sqlite3
import threading
import time

from backend.database import connection as conn_mod


def _point_db_at(tmp_path, monkeypatch):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    monkeypatch.setattr(conn_mod, "DB_DIR", db_dir)
    monkeypatch.setattr(conn_mod, "DB_FILE", db_dir / "finance.db")


def test_connection_is_wal_with_busy_timeout(tmp_path, monkeypatch):
    _point_db_at(tmp_path, monkeypatch)
    conn = conn_mod.get_db_connection()
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1  # preserved
    finally:
        conn.close()


def test_read_succeeds_during_open_write_transaction(tmp_path, monkeypatch):
    """With WAL, a reader sees the last committed snapshot while a writer holds
    an open transaction — it must NOT raise 'database is locked'."""
    _point_db_at(tmp_path, monkeypatch)
    setup = conn_mod.get_db_connection()
    setup.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    setup.execute("INSERT INTO t (id, v) VALUES (1, 'committed')")
    setup.commit()
    setup.close()

    writer = conn_mod.get_db_connection()
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO t (id, v) VALUES (2, 'uncommitted')")  # holds write lock

    reader = conn_mod.get_db_connection()
    try:
        rows = reader.execute("SELECT v FROM t ORDER BY id").fetchall()
        # Reader sees only the committed row, and crucially does not raise.
        assert [r[0] for r in rows] == ["committed"]
    finally:
        reader.close()
        writer.rollback()
        writer.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/venv/bin/python -m pytest backend/tests/test_connection_wal.py -v`
Expected: FAIL — `test_connection_is_wal_with_busy_timeout` fails because `journal_mode` is `delete` (and busy_timeout is `0` / `5000`).

- [ ] **Step 3: Write minimal implementation**

Edit `get_db_connection()` in `backend/database/connection.py` so the connect + pragmas read:

```python
def get_db_connection():
    """
    Get a database connection.

    WAL mode lets readers see the last committed snapshot while a writer holds
    an open transaction (a long analytics sync no longer blocks the dashboard
    read); the busy-timeout waits on brief lock contention instead of raising
    'database is locked'.

    Returns:
        sqlite3.Connection: Database connection
    """
    # Ensure database directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    conn.execute("PRAGMA journal_mode=WAL")  # concurrent read-during-write
    conn.execute("PRAGMA busy_timeout=30000")  # wait up to 30s, don't error
    conn.execute("PRAGMA foreign_keys = ON")  # Enable CASCADE delete
    return conn
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_connection_wal.py -v`
Expected: PASS (both tests).

Then the full suite to confirm no regression from the mode change:
Run: `backend/venv/bin/python -m pytest backend/tests/ -q`
Expected: PASS (≥ 212 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/database/connection.py backend/tests/test_connection_wal.py
git commit -m "[STORY-SH-1] fix: WAL + busy-timeout so a sync doesn't block the dashboard read"
```

---

### Task 2: App-level SyncProvider (survives navigation, guards double-start)

**Files:**
- Create: `frontend/lib/sync-context.tsx` (the provider + `useSync` hook + orchestration)
- Create: `frontend/app/providers.tsx` (client wrapper mounting the provider above the app)
- Modify: `frontend/app/layout.tsx:22-27` (wrap `{children}` in `<Providers>`)
- Test: `frontend/__tests__/sync-context.test.tsx` (create)

**Interfaces:**
- Consumes: the backend sync endpoints via `POST /api/proxy/api/sync/${path}`.
- Produces (imported by Tasks 3 and 4):
  - `type StepKey = 'fundamentals' | 'technical' | 'compute' | 'all' | 'ibkr'`
  - `interface StepState { running: boolean; status: string | null; error: boolean }`
  - `function SyncProvider({ children }: { children: React.ReactNode }): JSX.Element`
  - `function useSync(): SyncContextValue` where
    ```ts
    interface SyncContextValue {
      state: Record<StepKey, StepState>
      anyRunning: boolean
      syncVersion: number            // increments after each successful step
      runFundamentals: () => void
      runTechnical: () => void
      runCompute: () => void
      runAll: () => void
      runIbkr: () => void
    }
    ```
  - Calling `useSync()` outside a `<SyncProvider>` throws `Error('useSync must be used within SyncProvider')`.

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/sync-context.test.tsx`:

```tsx
import { render, screen, act, waitFor } from '@testing-library/react';
import { SyncProvider, useSync } from '@/lib/sync-context';

// A tiny consumer we can mount/unmount to prove provider state outlives it.
function Probe() {
  const { state, anyRunning, syncVersion, runCompute } = useSync();
  return (
    <div>
      <span data-testid="compute-status">{state.compute.status ?? 'idle'}</span>
      <span data-testid="any-running">{anyRunning ? 'yes' : 'no'}</span>
      <span data-testid="version">{syncVersion}</span>
      <button onClick={runCompute}>compute</button>
    </div>
  );
}

beforeEach(() => {
  // Never-resolving fetch by default so we can observe the "running" window.
  global.fetch = jest.fn(() => new Promise(() => {})) as unknown as typeof fetch;
});

test('runCompute posts to the screen endpoint and sets running state', async () => {
  render(
    <SyncProvider>
      <Probe />
    </SyncProvider>,
  );
  expect(screen.getByTestId('compute-status').textContent).toBe('idle');
  act(() => {
    screen.getByText('compute').click();
  });
  await waitFor(() => expect(screen.getByTestId('any-running').textContent).toBe('yes'));
  expect(screen.getByTestId('compute-status').textContent).toMatch(/Running/);
  expect(global.fetch).toHaveBeenCalledWith(
    '/api/proxy/api/sync/screen',
    expect.objectContaining({ method: 'POST' }),
  );
});

test('a second run is ignored while one is already running (no double-start)', async () => {
  render(
    <SyncProvider>
      <Probe />
    </SyncProvider>,
  );
  act(() => screen.getByText('compute').click());
  await waitFor(() => expect(screen.getByTestId('any-running').textContent).toBe('yes'));
  (global.fetch as jest.Mock).mockClear();
  act(() => screen.getByText('compute').click()); // second click while running
  expect(global.fetch).not.toHaveBeenCalled();
});

test('successful run flips running off and bumps syncVersion', async () => {
  global.fetch = jest.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({}) }),
  ) as unknown as typeof fetch;
  render(
    <SyncProvider>
      <Probe />
    </SyncProvider>,
  );
  const before = Number(screen.getByTestId('version').textContent);
  act(() => screen.getByText('compute').click());
  await waitFor(() =>
    expect(screen.getByTestId('compute-status').textContent).toMatch(/Done/),
  );
  expect(screen.getByTestId('any-running').textContent).toBe('no');
  expect(Number(screen.getByTestId('version').textContent)).toBe(before + 1);
});

test('useSync outside provider throws', () => {
  // Suppress React's error boundary console noise for this assertion.
  const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
  expect(() => render(<Probe />)).toThrow(/useSync must be used within SyncProvider/);
  spy.mockRestore();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest __tests__/sync-context.test.tsx`
Expected: FAIL — module `@/lib/sync-context` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/lib/sync-context.tsx`:

```tsx
'use client';

import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { toast } from 'sonner';

export type StepKey = 'fundamentals' | 'technical' | 'compute' | 'all' | 'ibkr';

export interface StepState {
  running: boolean;
  status: string | null;
  error: boolean;
}

const INITIAL: Record<StepKey, StepState> = {
  fundamentals: { running: false, status: null, error: false },
  technical: { running: false, status: null, error: false },
  compute: { running: false, status: null, error: false },
  all: { running: false, status: null, error: false },
  ibkr: { running: false, status: null, error: false },
};

interface SyncContextValue {
  state: Record<StepKey, StepState>;
  anyRunning: boolean;
  syncVersion: number;
  runFundamentals: () => void;
  runTechnical: () => void;
  runCompute: () => void;
  runAll: () => void;
  runIbkr: () => void;
}

const SyncContext = createContext<SyncContextValue | null>(null);

async function post(path: string): Promise<void> {
  const res = await fetch(`/api/proxy/api/sync/${path}`, { method: 'POST' });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body === 'object' ? JSON.stringify(body) : String(body));
}

async function runTechnicalSteps(): Promise<void> {
  await post('market-data'); // prices
  await post('analytics'); // indicators
}

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<Record<StepKey, StepState>>(INITIAL);
  const [syncVersion, setSyncVersion] = useState(0);

  const anyRunning = useMemo(() => Object.values(state).some((s) => s.running), [state]);

  const run = useCallback(
    (key: StepKey, label: string, fn: () => Promise<void>) => {
      // Guard: never start a step while ANY step is running (no overlap).
      setState((prev) => {
        if (Object.values(prev).some((s) => s.running)) return prev;
        // fire the work exactly once, outside the state updater
        queueMicrotask(async () => {
          toast(`${label} sync started`);
          try {
            await fn();
            setState((s) => ({ ...s, [key]: { running: false, status: 'Done ✓', error: false } }));
            setSyncVersion((v) => v + 1);
            toast.success(`${label} sync complete`);
          } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            setState((s) => ({ ...s, [key]: { running: false, status: 'Failed', error: true } }));
            toast.error(`${label} sync failed`, { description: msg });
          }
        });
        return { ...prev, [key]: { running: true, status: 'Running…', error: false } };
      });
    },
    [],
  );

  const value = useMemo<SyncContextValue>(
    () => ({
      state,
      anyRunning,
      syncVersion,
      runFundamentals: () => run('fundamentals', 'Fundamentals', () => post('fundamentals')),
      runTechnical: () => run('technical', 'Technical', runTechnicalSteps),
      runCompute: () => run('compute', 'Compute', () => post('screen')),
      runAll: () =>
        run('all', 'Full', async () => {
          await runTechnicalSteps();
          await post('fundamentals');
          await post('screen');
        }),
      runIbkr: () => run('ibkr', 'IBKR', () => post('ibkr')),
    }),
    [state, anyRunning, syncVersion, run],
  );

  return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
}

export function useSync(): SyncContextValue {
  const ctx = useContext(SyncContext);
  if (!ctx) throw new Error('useSync must be used within SyncProvider');
  return ctx;
}
```

Create `frontend/app/providers.tsx`:

```tsx
'use client';

import { SyncProvider } from '@/lib/sync-context';

export function Providers({ children }: { children: React.ReactNode }) {
  return <SyncProvider>{children}</SyncProvider>;
}
```

Modify `frontend/app/layout.tsx` — import and wrap. The `<body>` block becomes:

```tsx
import { Providers } from './providers';
// ...
      <body>
        <Providers>{children}</Providers>
        <Toaster richColors position="top-right" />
      </body>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx jest __tests__/sync-context.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/sync-context.tsx frontend/app/providers.tsx frontend/app/layout.tsx frontend/__tests__/sync-context.test.tsx
git commit -m "[STORY-SH-2] feat: app-level SyncProvider — sync survives navigation + double-start guard"
```

---

### Task 3: SyncToolbar consumes the provider (progress persists across tabs)

**Files:**
- Modify: `frontend/components/research/SyncToolbar.tsx` (replace local `useState` orchestration with `useSync()`)
- Modify: `frontend/app/page.tsx:275,1359` (drop the `onSynced`/`refreshResearch` wiring that the provider's `syncVersion` now drives; see Step 3)
- Test: `frontend/__tests__/synctoolbar.test.tsx` (create — the toolbar had no dedicated test)

**Interfaces:**
- Consumes: `useSync()` from Task 2 (`state`, `anyRunning`, `runFundamentals`, `runTechnical`, `runCompute`, `runAll`).
- Produces: `SyncToolbar` renders four buttons whose running/status/error come from provider state. It no longer accepts an `onSynced` prop.

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/synctoolbar.test.tsx`:

```tsx
import { render, screen, act, waitFor } from '@testing-library/react';
import { SyncProvider } from '@/lib/sync-context';
import { SyncToolbar } from '@/components/research/SyncToolbar';

beforeEach(() => {
  global.fetch = jest.fn(() => new Promise(() => {})) as unknown as typeof fetch;
});

function mount() {
  return render(
    <SyncProvider>
      <SyncToolbar />
    </SyncProvider>,
  );
}

test('clicking Compute signals drives provider and shows Running on that button', async () => {
  mount();
  act(() => screen.getByRole('button', { name: /Compute signals/ }).click());
  await waitFor(() =>
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/api/sync/screen',
      expect.objectContaining({ method: 'POST' }),
    ),
  );
  // The Compute button's status line reflects running state.
  expect(screen.getByText(/Running/)).toBeInTheDocument();
});

test('progress persists when the toolbar unmounts and remounts (tab switch)', async () => {
  // Provider is mounted ABOVE the toolbar and stays mounted; a `show` flag
  // mounts/unmounts the toolbar to simulate leaving and returning to the tab.
  function Harness() {
    const [show, setShow] = React.useState(true);
    return (
      <SyncProvider>
        <button onClick={() => setShow((s) => !s)}>toggle</button>
        {show && <SyncToolbar />}
      </SyncProvider>
    );
  }
  render(<Harness />);

  // Start a sync while the toolbar is mounted (never-resolving fetch → stays Running).
  act(() => screen.getByRole('button', { name: /Compute signals/ }).click());
  await waitFor(() => expect(screen.getByText(/Running/)).toBeInTheDocument());

  // Leave the tab (unmount the toolbar) then return (remount it).
  act(() => screen.getByText('toggle').click()); // unmount toolbar
  expect(screen.queryByRole('button', { name: /Compute signals/ })).toBeNull();
  act(() => screen.getByText('toggle').click()); // remount toolbar

  // The remounted toolbar reflects the still-running step from provider state.
  expect(screen.getByText(/Running/)).toBeInTheDocument();
});
```

> Implementer note: add `import React from 'react';` at the top of this test file for the `React.useState` in the harness. Keep the first test as-is.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest __tests__/synctoolbar.test.tsx`
Expected: FAIL — `SyncToolbar` still uses local state / accepts `onSynced`; the `Running` assertion or the provider wiring fails to compile against the new import.

- [ ] **Step 3: Write minimal implementation**

Rewrite `frontend/components/research/SyncToolbar.tsx` to consume the provider (drop local `useState`, `INITIAL`, `post`, `runTechnical`, and the `onSynced` prop):

```tsx
'use client';

import { useSync } from '@/lib/sync-context';

export function SyncToolbar() {
  const { state, anyRunning, runFundamentals, runTechnical, runCompute, runAll } = useSync();

  const Btn = ({
    stepKey,
    label,
    icon,
    subtitle,
    primary,
    onClick,
  }: {
    stepKey: 'fundamentals' | 'technical' | 'compute' | 'all';
    label: string;
    icon: string;
    subtitle: string;
    primary?: boolean;
    onClick: () => void;
  }) => {
    const st = state[stepKey];
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
    );
  };

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
      <Btn stepKey="fundamentals" label="Fundamentals" icon="⟳" subtitle="fetch + auto-rescore" onClick={runFundamentals} />
      <Btn stepKey="technical" label="Technical" icon="⟳" subtitle="prices + indicators" onClick={runTechnical} />
      <Btn stepKey="compute" label="Compute signals" icon="⟳" subtitle="screen + score" onClick={runCompute} />
      <Btn stepKey="all" label="Run all" icon="▶" subtitle="Technical → Fundamentals → Compute" primary onClick={runAll} />
    </div>
  );
}
```

In `frontend/app/page.tsx`: the research grid must refetch when a sync completes. Replace the old `onSynced` wiring with a `syncVersion` effect.
- At the `SyncToolbar` render site (was `<SyncToolbar onSynced={refreshResearch} />`, ~line 1359), change to `<SyncToolbar />`.
- Add near the other hooks (top of the component), alongside `const refreshResearch = () => setResearchKey((k) => k + 1);` (line 275):

```tsx
  const { syncVersion } = useSync();
  useEffect(() => {
    // A sync finished (from the toolbar OR the dashboard) — refresh the grid.
    if (syncVersion > 0) setResearchKey((k) => k + 1);
  }, [syncVersion]);
```

Add the import at the top of `page.tsx`: `import { useSync } from '@/lib/sync-context';` and ensure `useEffect` is imported from `react`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx jest __tests__/synctoolbar.test.tsx`
Expected: PASS.

Then the full frontend suite (research-grid and page tests must still pass):
Run: `cd frontend && npx jest`
Expected: PASS (all suites).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/research/SyncToolbar.tsx frontend/app/page.tsx frontend/__tests__/synctoolbar.test.tsx
git commit -m "[STORY-SH-3] refactor: SyncToolbar consumes SyncProvider; grid refetches on syncVersion"
```

---

### Task 4: Dashboard sync hub — actionable chips + "Sync all"

**Files:**
- Modify: `frontend/components/dashboard/StalenessChips.tsx` (chips become buttons wired to the provider + live "syncing…" state)
- Modify: `frontend/components/dashboard/Dashboard.tsx:21-67` (add a "Sync all" button beside the chips; refetch on `syncVersion`)
- Test: `frontend/__tests__/staleness-chips.test.tsx` (create)

**Interfaces:**
- Consumes: `useSync()` from Task 2. Chip→action mapping: `prices → runTechnical`, `signals → runCompute`, `fundamentals → runFundamentals`, `ibkr → runIbkr`. The `all` step drives the "Sync all" button.
- Produces: no new exported symbols; `StalenessChips` keeps its `{ asOf }` prop.

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/staleness-chips.test.tsx`:

```tsx
import { render, screen, act, waitFor } from '@testing-library/react';
import { SyncProvider } from '@/lib/sync-context';
import { StalenessChips } from '@/components/dashboard/StalenessChips';
import type { AsOf } from '@/lib/dashboard';

const asOf: AsOf = {
  prices: '2026-07-10',
  signals: '2026-07-10',
  fundamentals: '2026-07-10',
  ibkr: '2026-07-12',
};

beforeEach(() => {
  global.fetch = jest.fn(() => new Promise(() => {})) as unknown as typeof fetch;
});

test('clicking the prices chip triggers the technical (market-data) sync', async () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} />
    </SyncProvider>,
  );
  act(() => screen.getByRole('button', { name: /prices/ }).click());
  await waitFor(() =>
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/proxy/api/sync/market-data',
      expect.objectContaining({ method: 'POST' }),
    ),
  );
});

test('a chip shows a syncing state while its step runs', async () => {
  render(
    <SyncProvider>
      <StalenessChips asOf={asOf} />
    </SyncProvider>,
  );
  act(() => screen.getByRole('button', { name: /signals/ }).click());
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /signals/ })).toHaveTextContent(/syncing|…/i),
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest __tests__/staleness-chips.test.tsx`
Expected: FAIL — chips are `<span>`s (no `button` role) and do not call the provider.

- [ ] **Step 3: Write minimal implementation**

Rewrite `frontend/components/dashboard/StalenessChips.tsx` so each chip is a button wired to its step; while the step runs, show `…`:

```tsx
'use client';

import { relativeStaleness, type AsOf } from '@/lib/dashboard';
import { useSync, type StepKey } from '@/lib/sync-context';

const LABELS: Record<keyof AsOf, string> = {
  prices: 'prices',
  signals: 'signals',
  fundamentals: 'fundamentals',
  ibkr: 'IBKR',
};

// Which provider step each chip triggers.
const STEP_FOR: Record<keyof AsOf, StepKey> = {
  prices: 'technical',
  signals: 'compute',
  fundamentals: 'fundamentals',
  ibkr: 'ibkr',
};

export function StalenessChips({ asOf }: { asOf: AsOf }) {
  const { state, anyRunning, runTechnical, runCompute, runFundamentals, runIbkr } = useSync();
  const ACTION: Record<StepKey, () => void> = {
    technical: runTechnical,
    compute: runCompute,
    fundamentals: runFundamentals,
    ibkr: runIbkr,
    all: () => {},
  };
  const keys = Object.keys(LABELS) as (keyof AsOf)[];
  return (
    <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
      {keys.map((key) => {
        const { label, level } = relativeStaleness(asOf[key]);
        const step = STEP_FOR[key];
        const running = state[step].running;
        const cls =
          level === 'fresh'
            ? 'bg-success/15 text-success'
            : level === 'stale'
              ? 'bg-warning/15 text-warning'
              : 'bg-muted text-muted-foreground';
        return (
          <button
            key={key}
            type="button"
            onClick={ACTION[step]}
            disabled={anyRunning}
            title={`Refresh ${LABELS[key]}`}
            className={`rounded-full px-2.5 py-1 ${cls} ${anyRunning ? 'cursor-default opacity-70' : 'cursor-pointer hover:brightness-95'}`}
          >
            {running ? '…' : '●'} {LABELS[key]} {running ? 'syncing' : label}
          </button>
        );
      })}
    </div>
  );
}
```

In `frontend/components/dashboard/Dashboard.tsx`: import `useSync`, add a "Sync all" button next to `<StalenessChips />` (around line 67), and refetch the dashboard when `syncVersion` changes. Concretely:
- Add import: `import { useSync } from '@/lib/sync-context';`
- Inside `Dashboard`, read: `const { runAll, anyRunning, syncVersion } = useSync();`
- Add a `useEffect` that re-runs the existing dashboard fetch when `syncVersion` changes (mirror the existing window-change fetch effect — add `syncVersion` to its dependency array, or add a dedicated effect calling the same loader).
- Render the button beside the chips, e.g. replacing the lone `<StalenessChips asOf={data.as_of} />` with:

```tsx
<div className="flex flex-wrap items-center justify-between gap-2">
  <StalenessChips asOf={data.as_of} />
  <button
    type="button"
    onClick={runAll}
    disabled={anyRunning}
    className="rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground disabled:opacity-60"
  >
    {anyRunning ? 'Syncing…' : 'Sync all'}
  </button>
</div>
```

> Implementer note: match the actual fetch-loader name in `Dashboard.tsx` (the function the window buttons call) when adding the `syncVersion` refetch effect — reuse it, do not duplicate the fetch logic.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx jest __tests__/staleness-chips.test.tsx`
Expected: PASS.

Then confirm the existing dashboard test still passes:
Run: `cd frontend && npx jest __tests__/dashboard.test.tsx`
Expected: PASS (update `dashboard.test.tsx` to wrap the rendered `<Dashboard />` in `<SyncProvider>` if it renders the component directly and now throws "must be used within SyncProvider").

- [ ] **Step 5: Commit**

```bash
git add frontend/components/dashboard/StalenessChips.tsx frontend/components/dashboard/Dashboard.tsx frontend/__tests__/staleness-chips.test.tsx frontend/__tests__/dashboard.test.tsx
git commit -m "[STORY-SH-4] feat: Dashboard sync hub — actionable staleness chips + Sync all"
```

---

### Task 5: E2E smoke + docs close-out

**Files:**
- Modify: `frontend/e2e/dashboard_smoke.py` (add sync-hub + survive-navigation assertions)
- Modify: `docs/project/config/build-log.md`, `docs/project/config/codebase.md`, `docs/project/config/epics/ACTIVE.md`, `workflow/ADR.md`, `workflow/ERRORS.md`

- [ ] **Step 1: Extend the E2E smoke**

Add to `frontend/e2e/dashboard_smoke.py` a section that, against the live app on :3010, asserts the sync hub exists and survives navigation. Because a real sync is slow, do NOT run a full sync in the smoke — assert the wiring, not completion:

```python
    # ---- 6. Sync hub: chips + Sync all present and actionable ---------------
    print("== Sync hub (Dashboard) ==")
    page.locator("button:has-text('Dashboard')").first.click()
    page.wait_for_timeout(2500)
    check(page.locator("button:has-text('Sync all')").count() == 1, "Dashboard has a 'Sync all' button")
    # staleness chips are now buttons (actionable)
    chip = page.locator("button", has_text="prices").first
    check(chip.count() >= 1, "prices staleness chip is a button (actionable)")

    # ---- 7. A started sync survives a tab switch ---------------------------
    print("== Sync survives navigation ==")
    page.once("dialog", lambda d: d.dismiss())
    page.locator("button:has-text('Sync all')").first.click()  # kick off
    page.wait_for_timeout(800)
    page.locator("button:has-text('Browse Universe')").first.click()  # leave immediately
    page.wait_for_timeout(800)
    page.locator("button:has-text('Dashboard')").first.click()  # come back
    page.wait_for_timeout(800)
    # The Sync-all button should still read "Syncing…" (provider outlived the nav).
    syncing = page.locator("button:has-text('Syncing')").count()
    check(syncing >= 1, "sync still running after leaving and returning to the tab")
```

> Implementer note: if the started sync completes faster than the navigation window (small universe / warm cache), this assertion can flake. If it flakes on a live run, relax it to assert the dashboard *remained interactive during the sync* (net-worth hero still visible, no "Loading dashboard…" stuck state) — which is the real WAL win — rather than asserting the "Syncing…" label specifically. Document whichever you kept.

- [ ] **Step 2: Run the smoke**

Ensure backend (:8010) and frontend (:3010) are running, then:
Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 frontend/e2e/dashboard_smoke.py`
Expected: `SMOKE PASSED — all assertions green.` (0 console errors). Paste the output into the commit / story evidence.

- [ ] **Step 3: Docs**

- `workflow/ADR.md` — ADR-4: SQLite WAL + busy-timeout is the concurrency contract (readers never block behind an analytics write); sync orchestration lives in an app-level `SyncProvider` (survives navigation, single-flight guard), not in tab-scoped component state.
- `workflow/ERRORS.md` — entry: "Dashboard stuck on 'Loading…' during a sync" → root cause SQLite `delete` journal mode blocks reads behind a long write; prevention rule: all connections go through `get_db_connection()` which is WAL + 30s busy-timeout; never open `sqlite3.connect` directly. Second entry: "Sync appears to stop when leaving Browse Universe" → root cause tab-scoped `useState` + no lifted state; prevention rule: long-running operations belong in the app-level provider, never in a conditionally-rendered tab.
- `docs/project/config/codebase.md` — new modules: `frontend/lib/sync-context.tsx` (SyncProvider/useSync), `frontend/app/providers.tsx`; note `connection.py` now WAL.
- `docs/project/config/build-log.md` — Sync Hardening epic summary + smoke evidence.
- `docs/project/config/epics/ACTIVE.md` — mark Sync Hardening shipped; note next = Epic S Phase 2 (calibration, brainstorm parked with decisions banked).

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/dashboard_smoke.py docs/project/config/build-log.md docs/project/config/codebase.md docs/project/config/epics/ACTIVE.md workflow/ADR.md workflow/ERRORS.md
git commit -m "[STORY-SH-5] test+docs: sync-hub E2E smoke + Sync Hardening close-out"
```

---

## Self-Review

**Spec coverage:**
- Root fix (1) DB locks → Task 1 (WAL + busy-timeout). ✓
- Root fix (2) sync lost on navigation / double-start → Task 2 (provider) + Task 3 (toolbar consumes it). ✓
- Root fix (3) chips passive / sync not on dashboard → Task 4 (actionable chips + Sync all). ✓
- Verification + docs → Task 5. ✓

**Placeholder scan:** The only intentionally-scaffolded item is Task 3 Step 1's second test (explicitly flagged with an implementer note to replace with a real persistence assertion) and two "implementer note" adaptation points (Dashboard loader name in Task 4, smoke flake fallback in Task 5) — these are adaptation guidance against real unknowns, not vague requirements. All code steps carry complete code.

**Type consistency:** `StepKey` (5 members incl. `ibkr`) and `StepState` are defined once in `lib/sync-context.tsx` (Task 2) and imported by Tasks 3–4. `useSync()` action names (`runFundamentals/runTechnical/runCompute/runAll/runIbkr`) and `syncVersion` are used identically in Tasks 3 and 4. Backend paths (`market-data`/`analytics`/`fundamentals`/`screen`/`ibkr`) match the toolbar's original calls and the chip mapping.
