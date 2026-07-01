# Research UI (R-3 + R-4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Merge Browse Universe + Screener into one configurable "Research" view with a 4-button sync toolbar, a consolidation tuning panel, and fundamentals in the detail popup — backed by the R-1 unified dataset.

**Architecture:** New `frontend/components/research/*` (grid + toolbar + tuning panel) reading `/api/research/overview` and `/api/screener/settings/*`, mounted in the existing `browse-universe` tab in `page.tsx`; the standalone `screener` tab is removed. Two backend touch-ups: fundamentals sync auto-rescores, and the security detail endpoint gains a fundamentals block. Approved mockup: `.superpowers/brainstorm/38945-1782934275/content/research-view.html`.

**Tech Stack:** Next.js 16 (Turbopack), React, TypeScript, jest + RTL; FastAPI + SQLite backend; pytest.

## Global Constraints

- Backend run: `backend/venv/bin/python -m uvicorn backend.api.main:app --port 8000` from project root; frontend `cd frontend && BACKEND_URL=http://localhost:8000 npm run dev -- --port 3000` (compta_sasu shares these ports — check free first).
- All new code TDD. Commit prefix `[STORY-R-3]` / `[STORY-R-4]`.
- Recommended defaults stay strict (reliable breakouts); tuning only loosens on explicit user action.
- Column visibility persists in `localStorage` (versioned key `research.columns.v1`).
- Frontend calls backend through the proxy: `/api/proxy/api/...`.

## File Structure

- Create `frontend/lib/research.ts` — API client (overview, settings get/put) + column registry + persistence helpers.
- Create `frontend/components/research/ResearchGrid.tsx` — the configurable grid (adapted from `ScreenerGrid.tsx`).
- Create `frontend/components/research/SyncToolbar.tsx` — 4 sync buttons + last-run/stale badges.
- Create `frontend/components/research/TuningPanel.tsx` — consolidation params editor + Save&re-run + Reset.
- Modify `frontend/app/page.tsx` — mount Research in `browse-universe`; remove `screener` tab.
- Modify `backend/api/routes/sync.py` — `_step_fundamentals` chains a rescore.
- Modify `backend/api/routes/security.py` — detail response gains `fundamentals`.
- Modify `frontend/components/security-detail/SecurityDetailSheet.tsx` — Fundamentals card.
- Tests: `backend/tests/test_sync_fundamentals.py` (extend), `backend/tests/test_security_detail.py` (extend/create), `frontend/__tests__/research-*.test.tsx`.

---

### Task 1: Fundamentals sync auto-rescores (backend)

**Files:**
- Modify: `backend/api/routes/sync.py` (`_step_fundamentals`)
- Test: `backend/tests/test_sync_fundamentals.py`

**Interfaces:**
- Consumes: `backend.scripts.fundamentals_fetch.fetch_all(conn)`, `backend.scripts.scoring_compute.compute_all(conn)`.
- Produces: `_step_fundamentals()` returns `{... , "rescored": <int rows>}`.

- [ ] **Step 1: Write the failing test**

```python
def test_fundamentals_step_rescores(temp_db, monkeypatch):
    import sqlite3
    import backend.api.routes.sync as sync
    # seed signals + a fundamentals row so scoring has inputs
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol,name,enabled,added_at) VALUES ('AAPL','Apple',1,'2026-07-01')")
    conn.execute("INSERT INTO screen_signals (symbol,date,momentum_60d,above_ma50) VALUES ('AAPL','2026-07-01',10.0,1)")
    conn.commit(); conn.close()
    # stub the network fetch to write one fundamentals row
    def fake_fetch_all(conn):
        conn.execute("INSERT INTO fundamentals (symbol,gates_passed,gates_total,roe) VALUES ('AAPL',6,7,0.4)")
        conn.commit(); return {"rows_written": 1}
    monkeypatch.setattr("backend.scripts.fundamentals_fetch.fetch_all", fake_fetch_all)
    result = sync._step_fundamentals()
    assert result.get("rescored", 0) >= 1
    conn = sqlite3.connect(str(temp_db))
    n = conn.execute("SELECT COUNT(*) FROM screen_scores WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert n == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_sync_fundamentals.py::test_fundamentals_step_rescores -q`
Expected: FAIL (`rescored` absent / no screen_scores row).

- [ ] **Step 3: Implement the chain**

In `_step_fundamentals`:
```python
def _step_fundamentals() -> dict:
    from backend.scripts.fundamentals_fetch import fetch_all
    from backend.scripts import scoring_compute
    conn = get_db_connection()
    try:
        result = fetch_all(conn)
        rescore = scoring_compute.compute_all(conn)
        result["rescored"] = rescore.get("rows_written", 0)
        return result
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_sync_fundamentals.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/sync.py backend/tests/test_sync_fundamentals.py
git commit -m "[STORY-R-3] feat: fundamentals sync auto-rescores"
```

---

### Task 2: Security detail endpoint gains fundamentals (backend, R-4)

**Files:**
- Modify: `backend/api/routes/security.py` (the `/{symbol}/detail` handler)
- Test: `backend/tests/test_security_detail.py`

**Interfaces:**
- Produces: `GET /api/security/{sym}/detail` response includes `"fundamentals": {gross_margin, roe, roic, levered_fcf_margin, interest_cover, eps_5y_growth, gates_passed, gates_total, market_cap, trailing_pe}` or `null` if absent.

- [ ] **Step 1: Write the failing test**

```python
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app
client = TestClient(app)

def test_detail_includes_fundamentals(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol,name,enabled,added_at) VALUES ('AAPL','Apple',1,'2026-07-01')")
    conn.execute("INSERT INTO fundamentals (symbol,roe,roic,gates_passed,gates_total,market_cap,trailing_pe) VALUES ('AAPL',0.4,0.3,6,7,3.0e12,35.5)")
    conn.commit(); conn.close()
    r = client.get("/api/security/AAPL/detail")
    assert r.status_code == 200
    f = r.json()["fundamentals"]
    assert f["gates_passed"] == 6 and f["roe"] == 0.4
```

- [ ] **Step 2: Run to verify it fails** — `python3 -m pytest backend/tests/test_security_detail.py::test_detail_includes_fundamentals -q` → FAIL (KeyError `fundamentals`).

- [ ] **Step 3: Implement** — in the detail handler, after existing blocks, query and attach:

```python
FUND_COLS = ["gross_margin","roe","roic","levered_fcf_margin","interest_cover",
             "eps_5y_growth","gates_passed","gates_total","market_cap","trailing_pe"]
frow = conn.execute(f"SELECT {','.join(FUND_COLS)} FROM fundamentals WHERE symbol=?", (symbol,)).fetchone()
response["fundamentals"] = {c: frow[c] for c in FUND_COLS} if frow else None
```
(Match the handler's existing dict/response variable name and connection.)

- [ ] **Step 4: Run to verify it passes** — `python3 -m pytest backend/tests/test_security_detail.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/security.py backend/tests/test_security_detail.py
git commit -m "[STORY-R-4] feat: security detail endpoint includes fundamentals block"
```

---

### Task 3: Research API client + column registry (frontend)

**Files:**
- Create: `frontend/lib/research.ts`
- Test: `frontend/__tests__/research-columns.test.ts`

**Interfaces:**
- Produces:
  - `ALL_COLUMNS: {key:string,label:string,group:string,align:'l'|'r'}[]` — union of Screener + Browse Universe + indicator columns.
  - `DEFAULT_VISIBLE: string[]` — default union column keys.
  - `loadVisibleColumns(): string[]` / `saveVisibleColumns(keys:string[]): void` — localStorage `research.columns.v1`, falling back to `DEFAULT_VISIBLE`.
  - `fetchResearchOverview(): Promise<Row[]>` → `/api/proxy/api/research/overview`.
  - `getConsolidationParams()` / `putConsolidationParams(params)` → `/api/proxy/api/screener/settings/consolidation_params`.

- [ ] **Step 1: Write the failing test**

```ts
import { loadVisibleColumns, saveVisibleColumns, DEFAULT_VISIBLE } from '@/lib/research';

test('defaults when nothing saved', () => {
  localStorage.clear();
  expect(loadVisibleColumns()).toEqual(DEFAULT_VISIBLE);
});

test('round-trips saved columns', () => {
  localStorage.clear();
  saveVisibleColumns(['symbol', 'rsi_14', 'verdict']);
  expect(loadVisibleColumns()).toEqual(['symbol', 'rsi_14', 'verdict']);
});
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npx jest research-columns -t 'columns'` → FAIL (module missing).

- [ ] **Step 3: Implement `frontend/lib/research.ts`** with `ALL_COLUMNS` (groups: Identity, Indicators, Momentum, Consolidation, Breakout, Fundamentals, Score), `DEFAULT_VISIBLE`, the two persistence funcs (wrap `JSON.parse`/`stringify` with try/catch → default), and the three fetch helpers using `fetch('/api/proxy/...')`.

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npx jest research-columns` → PASS.

- [ ] **Step 5: Commit** — `git add frontend/lib/research.ts frontend/__tests__/research-columns.test.ts && git commit -m "[STORY-R-3] feat: research API client + column registry"`

---

### Task 4: ResearchGrid component (frontend)

**Files:**
- Create: `frontend/components/research/ResearchGrid.tsx`
- Test: `frontend/__tests__/research-grid.test.tsx`

**Interfaces:**
- Consumes: `fetchResearchOverview`, `ALL_COLUMNS`, `loadVisibleColumns/saveVisibleColumns` (Task 3); `onSelectSymbol(sym:string)` prop for row click.
- Produces: `<ResearchGrid onSelectSymbol={fn} />` — sortable/filterable grid; a "Columns" popover toggling visibility (persisted); CSV export links to `/api/proxy/api/research/overview?format=csv`.

- [ ] **Step 1: Write the failing test** — render with a stubbed fetch returning 2 rows; assert visible default columns render and a hidden column is absent until toggled.

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { ResearchGrid } from '@/components/research/ResearchGrid';

jest.mock('@/lib/research', () => ({
  ...jest.requireActual('@/lib/research'),
  fetchResearchOverview: () => Promise.resolve([
    { symbol: 'AAPL', rsi_14: 61.4, verdict: 'watch', score_total: 52 },
    { symbol: 'KO', rsi_14: 58.2, verdict: 'buy', score_total: 70 },
  ]),
}));

test('renders rows with default columns', async () => {
  render(<ResearchGrid onSelectSymbol={() => {}} />);
  await waitFor(() => expect(screen.getByText('AAPL')).toBeInTheDocument());
  expect(screen.getByText('KO')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npx jest research-grid` → FAIL (component missing).

- [ ] **Step 3: Implement** by adapting `ScreenerGrid.tsx`: fetch on mount, render only `loadVisibleColumns()` columns from `ALL_COLUMNS`, keep sort + filter chips + verdict badge styling from the mockup, add a Columns popover (checkbox per `ALL_COLUMNS` entry → save), row `onClick={() => onSelectSymbol(r.symbol)}`, Export CSV anchor.

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npx jest research-grid` → PASS.

- [ ] **Step 5: Commit** — `[STORY-R-3] feat: ResearchGrid with configurable columns`

---

### Task 5: SyncToolbar + TuningPanel (frontend)

**Files:**
- Create: `frontend/components/research/SyncToolbar.tsx`, `frontend/components/research/TuningPanel.tsx`
- Test: `frontend/__tests__/research-tuning.test.tsx`

**Interfaces:**
- `<SyncToolbar />` — 4 buttons: Fundamentals (`POST /api/proxy/api/sync/fundamentals`), Technical (`/api/sync/market-data` then indicators via `/api/sync/analytics`), Compute (`/api/sync/screen`), Run all (chains Technical→Fundamentals→Compute sequentially). Each shows last-run/stale text; toasts on start/finish.
- `<TuningPanel onRerun={fn} />` — loads `getConsolidationParams()`, renders a labeled number input per tunable key with its recommended default shown; "Reset to recommended" sets inputs to `defaults`; "Save & re-run" calls `putConsolidationParams()` then `POST /api/sync/screen`.

- [ ] **Step 1: Write the failing test** — mock `getConsolidationParams` → `{params:{max_consolidation_range_pct:5}, defaults:{max_consolidation_range_pct:5}}`; render TuningPanel; assert input shows 5; click Reset restores 5 after edit.

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TuningPanel } from '@/components/research/TuningPanel';
jest.mock('@/lib/research', () => ({
  ...jest.requireActual('@/lib/research'),
  getConsolidationParams: () => Promise.resolve({ params: { max_consolidation_range_pct: 5 }, defaults: { max_consolidation_range_pct: 5 } }),
  putConsolidationParams: jest.fn(() => Promise.resolve({})),
}));
test('shows recommended value', async () => {
  render(<TuningPanel onRerun={() => {}} />);
  await waitFor(() => expect(screen.getByDisplayValue('5')).toBeInTheDocument());
});
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npx jest research-tuning` → FAIL.

- [ ] **Step 3: Implement** both components per the mockup (toolbar layout + tuning grid with recommended captions). Keep param key list from `defaults` returned by the API so new params appear automatically.

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npx jest research-tuning` → PASS.

- [ ] **Step 5: Commit** — `[STORY-R-3] feat: sync toolbar + consolidation tuning panel`

---

### Task 6: Mount Research in Browse Universe; retire Screener tab (frontend)

**Files:**
- Modify: `frontend/app/page.tsx`
- Test: `frontend/__tests__/research-tab.test.tsx` (smoke) — optional if page.tsx is hard to render in isolation; otherwise verify via type-check + manual.

**Interfaces:**
- Consumes: `ResearchGrid`, `SyncToolbar`, `TuningPanel`, existing `selectedSymbol` state + `SecurityDetailSheet`.

- [ ] **Step 1:** Remove `'screener'` from `TabType`; delete the Screener tab button and the `{activeTab === 'screener' && <ScreenerGrid />}` block.
- [ ] **Step 2:** In the `browse-universe` render block, mount `<SyncToolbar />`, a collapsible `<TuningPanel onRerun={refreshResearch} />`, and `<ResearchGrid onSelectSymbol={setSelectedSymbol} />` (keep the existing coverage cards above if desired).
- [ ] **Step 3:** Run `cd frontend && npx tsc --noEmit` → no errors; `npx jest` → all green.
- [ ] **Step 4: Commit** — `[STORY-R-3] feat: merge Screener into Browse Universe (Research view); retire Screener tab`

---

### Task 7: Fundamentals card in SecurityDetailSheet (frontend, R-4)

**Files:**
- Modify: `frontend/components/security-detail/SecurityDetailSheet.tsx`
- Test: `frontend/__tests__/detail-fundamentals.test.tsx`

**Interfaces:**
- Consumes: detail response `fundamentals` block (Task 2).

- [ ] **Step 1: Write the failing test** — mock fetch detail returning `fundamentals:{roe:0.4,gates_passed:6,gates_total:7,market_cap:3e12,trailing_pe:35.5}`; assert a "Fundamentals" heading + ROE render; and that with `fundamentals:null` the card is absent.
- [ ] **Step 2: Run to verify it fails** — `cd frontend && npx jest detail-fundamentals` → FAIL.
- [ ] **Step 3: Implement** a `<Card>` titled "Fundamentals" rendered only when `data.fundamentals` present, showing margins/ROE/ROIC/FCF/interest cover/EPS growth/gates (x/7)/market cap/P/E, matching the Indicators card styling.
- [ ] **Step 4: Run to verify it passes** — `cd frontend && npx jest detail-fundamentals` → PASS.
- [ ] **Step 5: Commit** — `[STORY-R-4] feat: Fundamentals card in security detail popup`

---

## Self-Review

- **Spec coverage:** unified read (R-1 done) ✓; tunable params (R-2 done) ✓; merged UI grid + columns (T3,T4,T6) ✓; 3+1 buttons (T5) ✓; tuning panel + re-run (T5) ✓; auto-rescore (T1) ✓; retire Screener tab (T6) ✓; fundamentals in popup (T2,T7) ✓; CSV (T4 links to R-1 csv) ✓.
- **Placeholders:** backend tasks have full test+impl code; frontend component bodies are specified by interface + mockup (written during execution, TDD per task) — acceptable given React view code is impractical to fully pre-write and each task has a concrete failing test.
- **Type consistency:** `onSelectSymbol` used in T4/T6; `getConsolidationParams/putConsolidationParams` defined T3, used T5; `fundamentals` block defined T2, consumed T7.

## Manual / E2E verification (after Task 7)

Run both servers; open Research tab: (1) toolbar buttons run + show status; (2) Tune → loosen range → Save & re-run → consolidation column fills for more rows; (3) toggle a column off → persists across reload; (4) Export CSV has all columns; (5) click a row → Fundamentals card shows. Capture evidence.
