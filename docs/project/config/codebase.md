# Codebase — IBKR Portfolio Tracker

> Stage 7 — AI's map of the codebase. Updated after every story that adds or modifies modules.
> AI MUST read this before touching any existing module.
>
> Each module section has TWO parts:
> - **Current State** — always accurate, used before coding
> - **Change Log** — append-only, audit trail (newest at top)

## Last updated: 2026-04-28 (after Epic B; before Epic C kicks off)

---

## Codebase Map

```
backend/
├── api/
│   ├── main.py              FastAPI app + CORS + router registration
│   ├── routes/
│   │   ├── sync.py          /api/sync/* pipeline (4 steps + orchestrator + market-data wired in C)
│   │   ├── positions.py     GET /api/positions (raw IBKR snapshot, no recon)
│   │   ├── transactions.py  CRUD/list/upload/export trades + filters (date_from, date_to, side)
│   │   ├── corporate_actions.py  CRUD + status + refresh (date_from, date_to filters)
│   │   ├── updated_transactions.py  Split-adjusted view (date_from, date_to, ca_type, symbol LIKE)
│   │   ├── universe.py      [Epic C] tracked_universe CRUD + index toggles + refresh
│   │   ├── market_data.py   [Epic C] OHLCV read endpoint
│   │   ├── indicators.py    [Epic D] indicator read endpoint
│   │   ├── holding_signals.py  [Epic G] sell signal CRUD + sync
│   │   ├── security.py      [Epic H] /api/security/{symbol}/detail
│   │   └── tech_analysis.py [Epics E, F] breakouts + consolidations + S/R
│   ├── utils/
│   │   └── logger.py        Centralized logger
│   └── middleware/
│       └── logging_middleware.py  HTTP req/resp logging
├── database/
│   ├── connection.py        get_db_connection() returning sqlite3.Connection
│   └── schema.sql           single source of truth for tables + views
├── scripts/
│   ├── fetch_flex_trades.py            IBKR Flex client + parsers + writers
│   ├── fetch_corporate_actions.py      yfinance corp actions fetcher
│   ├── apply_splits.py                 Apply known splits → updated_transactions
│   ├── parse_csv_trades.py             CSV upload path
│   ├── universe_seeders.py             [Epic C] Wikipedia scrapers per index
│   ├── market_data_ingestor.py         [Epic C] Batched yfinance OHLCV downloader
│   ├── indicators_compute.py           [Epic D] Incremental indicator compute
│   ├── breakout_detector.py            [Epic E] Range Breakout (port d_breakout_detector_3)
│   ├── trend_breakout.py               [Epic E] Trend Breakout (4-condition)
│   ├── consolidation_detector.py       [Epic E] ZigZag + BB Squeeze
│   ├── sr_technical.py                 [Epic E] Technical S/R (zigzag/MA/round/volume)
│   ├── options_ingestor.py             [Epic F] yfinance options chain → DB
│   └── sr_options.py                   [Epic F] Max pain + walls
├── tests/
│   ├── conftest.py          Shared fixtures (temp_db, flex_xml_minimal, stub_flex_http)
│   ├── fixtures/
│   │   └── flex_response_minimal.xml   Sample IBKR XML for tests
│   ├── test_api.py
│   ├── test_database.py
│   ├── test_corporate_actions.py
│   ├── test_sync_routes.py
│   └── ... (one test_*.py per module being tested)
├── utils/
│   └── ca_status.py         Per-symbol CA grey/green/orange management
└── requirements.txt

frontend/
├── app/
│   ├── page.tsx             3-tab dashboard (Positions / Transactions / Configuration); 2200+ lines, refactored as touched
│   ├── api/proxy/           Next.js → FastAPI proxy
│   ├── globals.css          Tailwind v4 directives (after Epic C)
│   └── layout.tsx
├── components/
│   └── ui/                  [Epic C] shadcn/ui copies (Button, Card, Dialog, etc.)
├── lib/
│   └── utils.ts             [Epic C] shadcn cn() helper
└── package.json

docs/
├── project/
│   ├── config/              FILLED docs (brainstorm, prd, architecture, logging, codebase, build-log, epics/)
│   └── requirements/        TEMPLATES (1-BRAINSTORM through 7-CODEBASE) — read-only
├── plans/                   Per-story implementation plans + ROADMAP.md
└── workflow/, guides/, implementation/

input/                       CSV uploads, daily_trades/
output/database/finance.db   THE single SQLite file
logs/                        backend / api / frontend daily log files
.env                         IBKR credentials (gitignored)
```

---

## Module — `backend/database/connection.py`

### Current State

- Single function `get_db_connection()` returns `sqlite3.Connection` with `row_factory = sqlite3.Row` (rows support `r[0]` and `r['col']`)
- Foreign keys enabled (`PRAGMA foreign_keys = ON`)
- DB path: `output/database/finance.db` (project root + `output/database/`)
- `init_database()` runs `executescript(schema.sql)` for first-time setup

### Change Log

- **2026-04-27** ([Epic A]) — refactored to centralized helper; removed legacy connection-per-file pattern in some scripts (e.g., ca_status.py fixed to use this).

---

## Module — `backend/api/routes/sync.py`

### Current State

- 5 endpoints under `/api/sync/`:
  - `POST /positions` — Flex pull → save_positions_ibkr only
  - `POST /transactions` — Flex pull → insert trades only + flag CA-orange + write import_logs
  - `POST /corporate-actions` — wraps `fetch_and_import_corporate_actions(incremental=True)`
  - `POST /splits` — wraps `apply_all_splits()`
  - `POST /full` — orchestrator: 1 shared Flex pull, 4 steps in sequence, returns per-step status
- Helper `_log_import(source_file, result)` — writes `import_logs` row with timezone-aware timestamp
- Helper `_flag_orange(symbols)` — sets CA status to 'orange' for newly-touched symbols

### Change Log

- **2026-04-28** ([Epic A SYNC-14]) — `_log_import` writes `import_date` explicitly with `datetime.now().astimezone().isoformat()` (was relying on schema default which was naive UTC).
- **2026-04-28** ([Epic A SYNC-13]) — Same timezone fix at the source for `positions_ibkr.last_updated`.
- **2026-04-28** ([Epic A SYNC-12]) — Restored `import_logs` writes (lost when `/api/transactions/flex-import` was deleted).
- **2026-04-27** ([Epic A SYNC-5..8]) — Created. Replaced the monolithic `/api/transactions/flex-import` route.

---

## Module — `backend/api/routes/positions.py`

### Current State

- Single endpoint `GET /api/positions`
- Returns raw `positions_ibkr` rows (no reconciliation)
- Sorted by absolute `position_value` descending
- Response shape: `{success, positions: [...], summary: {total_positions, last_updated}}`

### Change Log

- **2026-04-27** ([Epic A SYNC-2]) — Drop reconciliation; remove `qty_calculated`, `rec_status`, etc. from response. Drop `POST /api/positions/refresh` endpoint.

---

## Module — `backend/api/routes/transactions.py`

### Current State

- Endpoints:
  - `GET /api/transactions` — paginated list with filters: `symbol` (LIKE prefix), `date_from`, `date_to`, `side` (buy|sell maps to quantity sign)
  - `POST /api/transactions/upload` — CSV upload path
  - `DELETE /api/transactions/{transaction_id}` — single delete
  - `DELETE /api/transactions` — delete all
  - `POST /api/transactions/delete-batch` — batch delete
  - `GET /api/transactions/import-logs` — import history
  - `DELETE /api/transactions/import-logs` — clear history
  - `GET /api/transactions/securities` — distinct symbol list
  - `GET /api/transactions/export` — CSV export
  - `GET /api/transactions/adjusted` — split-adjusted view
  - `POST /api/transactions/apply-splits` — manually trigger apply_all_splits
- All `INSERT INTO import_logs` writes pass `import_date` explicitly with timezone offset

### Change Log

- **2026-04-28** ([Epic B STORY-B-2]) — `GET /api/transactions` accepts `date_from`, `date_to`, `side` query params.
- **2026-04-28** ([Epic A SYNC-14]) — All 3 `INSERT INTO import_logs` sites pass `import_date` explicitly.
- **2026-04-27** ([Epic A SYNC-10]) — Deleted `POST /api/transactions/flex-import` route (superseded by `/api/sync/*`).

---

## Module — `backend/api/routes/updated_transactions.py`

### Current State

- `GET /api/updated-transactions` — paginated list of split-adjusted transactions
- Filters: `symbol` (LIKE prefix), `date_from`, `date_to`, `ca_type`
- `DELETE /api/updated-transactions` — delete all
- `POST /api/updated-transactions/batch-delete` — batch delete
- Uses its own `get_db_connection()` (isolated from the global helper) — minor inconsistency but works

### Change Log

- **2026-04-28** ([Epic B STORY-B-3]) — Added `date_from`, `date_to`, `ca_type` filters; switched `symbol` from exact match to LIKE prefix.

---

## Module — `backend/api/routes/corporate_actions.py`

### Current State

- `GET /api/corporate-actions` — paginated list with filters: `ca_type`, `symbol` (LIKE), `date_from`, `date_to` (filter on `ex_date`)
- `POST /api/corporate-actions/refresh` — incremental yfinance fetch
- `POST /api/corporate-actions/fetch` — full re-fetch (bypasses incremental skip)
- `GET /api/corporate-actions/status` — per-symbol grey/green/orange
- `DELETE` and `POST /batch-delete`

### Change Log

- **2026-04-28** ([Epic B STORY-B-3]) — Added `date_from`, `date_to` filters on `ex_date`.

---

## Module — `backend/scripts/fetch_flex_trades.py`

### Current State

- `request_flex_query(token, query_id) → reference_code` — POST to IBKR Flex
- `fetch_flex_results(token, ref) → xml_content` — GET with retries
- `fetch_flex_response(query_type) → xml` — combined helper with env-var fallback (dedicated → unified)
- `parse_trades_from_xml(xml) → list[dict]` — XML → dicts
- `parse_positions_from_xml(xml) → list[dict]` — XML → dicts
- `insert_flex_trades(trades, source_file) → result` — DB writer with `INSERT OR IGNORE` (TODO: migrate to `ON CONFLICT` for portability if Supabase reconsidered)
- `save_positions_ibkr(positions) → result` — DELETE+INSERT pattern (positions are a snapshot)
- All timestamps via `datetime.now().astimezone().isoformat()`

### Change Log

- **2026-04-28** ([Epic A SYNC-13]) — All `datetime.now().isoformat()` → `datetime.now().astimezone().isoformat()` for timezone-aware writes.
- **2026-04-27** ([Epic A SYNC-4]) — Added `fetch_flex_response()` helper with dedicated/unified env-var fallback.
- **2026-04-27** ([Epic A SYNC-10]) — Removed `fetch_and_import_flex_trades()` (the old monolithic orchestrator function).

---

## Module — `backend/utils/ca_status.py`

### Current State

- Three functions: `set_ca_status(symbols, status)`, `get_ca_status(symbol=None)`, `delete_ca_status(symbols)`
- Uses centralized `get_db_connection()` (was previously a hardcoded path — fixed)
- All timestamps via `datetime.now().astimezone().isoformat()`

### Change Log

- **2026-04-27** ([Epic A SYNC-5..8]) — Bug fix: was opening its own connection to a hardcoded path, breaking test isolation. Routed through `get_db_connection()`.

---

## Module — `frontend/app/page.tsx`

### Current State

- 2200+ lines, top-level Dashboard component
- 3 top-level tabs: Positions / Transactions / Configuration
- Transactions has 3 sub-tabs: Original / Split-Adjusted / Corporate Actions
- Header: 🔄 Sync IBKR button + staleness pill + Connecté pill
- 4-card sync progress strip below header during sync
- Each Transactions sub-tab has a visible filter toolbar (Symbol / Date from / Date to / Side or CA Type)
- Positions tab: single "Open Positions" card (no recon UI)
- Calls `/api/sync/full` orchestrator via Sync IBKR button
- Inline styles throughout (NOT yet migrated to shadcn — that starts in Epic C)

### Known issues / debt

- File is huge (2200+ lines). Component extraction tracked under "Migrate existing tabs to shadcn/ui" — done as touched.
- Inline styles everywhere; no design tokens. Story C-1 introduces Tailwind+shadcn for new code; existing tabs migrate over time.

### Change Log

- **2026-04-28** ([Epic B STORY-B-3]) — Visible filter toolbars on Split-Adjusted + Corporate Actions sub-tabs; "Clear filters ✕" buttons.
- **2026-04-28** ([Epic B STORY-B-2]) — Visible filter toolbar on Original; backend filter params extended.
- **2026-04-28** ([Epic B STORY-B-1]) — Tab restructure (6 → 3 + sub-tabs); staleness badge; sync progress strip.
- **2026-04-27** ([Epic A SYNC-9]) — Sync IBKR button calls `/api/sync/full`; progress steps rendered from API response.
- **2026-04-27** ([Epic A SYNC-2]) — Drop recon UI: Position interface, summary cards, Qty Rec column, Recalculate Rec button.

---

## Data Flows

### Sync pipeline (full)

```
🔄 Sync IBKR (header) → POST /api/sync/full
├─ Step 1: fetch_flex_response("last_month") → ONE Flex XML
├─ Step 2: positions parse + save_positions_ibkr (and _sync_positions_to_universe in Epic C)
├─ Step 3: trades parse + insert_flex_trades + flag CA-orange + import_logs row
├─ Step 4: yfinance corp-actions refresh (per orange symbol)
├─ Step 5: apply_all_splits
└─ [Epic C+] Step 6: market-data sync; Step 7: indicators; Step 8: holding-signals; Step 9: tech analysis
```

### Holdings reads

```
Positions tab → GET /api/positions → SELECT FROM positions_ibkr ORDER BY position_value DESC
```

---

## Dependency Map

| Module | Depends on |
|---|---|
| `routes/sync.py` | `database/connection`, `scripts/fetch_flex_trades`, `scripts/fetch_corporate_actions`, `scripts/apply_splits`, `utils/ca_status` |
| `routes/positions.py` | `database/connection`, `utils/logger` |
| `routes/transactions.py` | `database/connection`, `scripts/parse_csv_trades`, `utils/ca_status` |
| `scripts/fetch_flex_trades.py` | `database/connection`, `utils/logger`, `requests`, `xml.etree.ElementTree` |
| `frontend/app/page.tsx` | Next.js proxy to FastAPI |

---

## Known Technical Debt

1. **`page.tsx` size (2200+ lines)** — addressed via Epic C+ as touched.
2. **`updated_transactions.py` has its own `get_db_connection()`** — inconsistent; should use `backend/database/connection.py` like the rest. Low priority.
3. **`INSERT OR IGNORE` in `fetch_flex_trades.py`** — SQLite-specific; would block a future Postgres migration. Tracked in the parked Supabase plan.
4. **Pre-existing test failures** in `test_database.py::test_database_initialization` (checks for non-existent `examples` table from a different project's template) and `test_api.py::test_health_endpoint` (asserts `status: healthy` but endpoint returns `ok`). Not in scope of any epic.

---

## Epic V — Dashboard & IA restructure (new modules)

| Module | Responsibility |
|---|---|
| `backend/api/routes/dashboard.py` | `GET /api/dashboard?window=` — aggregates net_worth, allocation, performance, movers, action queue, as_of/staleness, fx_rate into one payload |
| `backend/scripts/portfolio_history_compute.py` | `get_fx_rate(conn, on_date)`, `compute_history(conn, start)` — replays split-adjusted transactions × daily closes × FX into `portfolio_value_history` (CASH-excluded) |
| `backend/scripts/universe_seeders.py::seed_fx_symbols` | seeds `EURUSD=X` into `tracked_universe` (source `fx`) so FX ingests through the normal market-data path |
| `frontend/components/dashboard/` | Dashboard.tsx + NetWorthCard / AllocationDonut / PerformanceChart / ActionQueue / MoversCard / StalenessChips — hand-rolled SVG charts, last-request-wins fetch guard |
| `frontend/lib/dashboard.ts` | dashboard fetch + response types |
| `frontend/lib/journal.ts` | `visibleTransactions(rows, showCash)` — CASH/FX-leg filter shared by Journal |
| `frontend/lib/research.ts::GROUP_COLORS` | per-group accent colours for the ResearchGrid grouped header row |
| `frontend/components/security-detail/SecurityDetailSheet.tsx` | + Technical signals / ZigZag / Breakout card (consumes `technical`/`breakout`/`zigzag` blocks from `/api/security/{symbol}/detail`) |
| `frontend/e2e/dashboard_smoke.py` | Playwright headless smoke — Epic V surface assertions (run on the framework py3.10 that has Playwright) |

**New table:** `portfolio_value_history` (daily EUR/USD portfolio value snapshots).

**Dependency additions:** `routes/dashboard.py` → `database/connection`, `scripts/portfolio_history_compute`; `portfolio_history_compute` → `database/connection`, `pandas`; `routes/security.py` → `scripts/consolidation_core` (`calculate_zigzag`, `load_params`), `pandas`.

---

## Epic SH — Sync Hardening (new modules / changes)

| Module | Responsibility |
|---|---|
| `backend/database/connection.py` | `get_db_connection()` now opens with `timeout=30` + `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=30000` (concurrent read-during-write); `row_factory`/`foreign_keys` preserved |
| `frontend/lib/sync-context.tsx` | `SyncProvider` + `useSync()` — app-level sync orchestration (fundamentals/technical/compute/all/ibkr), `useRef` single-flight guard, `syncVersion` success counter. Exports `StepKey`, `StepState` |
| `frontend/app/providers.tsx` | `'use client'` wrapper mounting `SyncProvider` above the app |
| `frontend/app/layout.tsx` | wraps `{children}` in `<Providers>` |
| `frontend/components/research/SyncToolbar.tsx` | now consumes `useSync()` (no local state, no `onSynced` prop) — progress persists across tab switches |
| `frontend/components/dashboard/StalenessChips.tsx` | chips are actionable buttons wired to the provider (prices→technical, signals→compute, fundamentals→fundamentals, ibkr→ibkr) with per-chip syncing state |
| `frontend/components/dashboard/Dashboard.tsx` | "Sync all" button (runAll) beside the chips; refetches on `syncVersion` |

**Follow-up (logged):** `fetch_corporate_actions.py` + `routes/updated_transactions.py` open raw `sqlite3.connect()` — they inherit WAL (persistent file property) but lack the busy-timeout; route through `get_db_connection()` when next touched.

## 2026-07-13 — Trading-day-aware staleness chips

| Module | Responsibility |
|---|---|
| `backend/api/utils/trading_days.py` | `last_completed_trading_day(now)`, `close_of(day)` (22:00 UTC cutoff), `freshness_level(kind, data_date, checked_at, now)` → fresh/stale/unknown per chip; holidays unmodeled (amber for a day) |
| `backend/api/routes/dashboard.py` | `as_of` entries are now `{date, checked_at, level}`; `checked_at` = `MAX(sync_runs.finished_at)` per action (prices→market_data, signals→screen/analytics, fundamentals→fundamentals, ibkr→ibkr) |
| `frontend/lib/dashboard.ts` | `AsOfEntry` type; `shortDate()` + `relativeTime()` replace `relativeStaleness` (staleness level now comes from backend) |
| `frontend/components/dashboard/StalenessChips.tsx` | Option A two-line chips: data date + "checked Xh ago" subline; click-to-refresh and per-chip syncing state unchanged |

## 2026-07-13 — IBKR cash balances in net worth

| Module | Responsibility |
|---|---|
| `backend/database/schema.sql` → `cash_balances` | latest Flex CashReport snapshot per currency (DELETE+INSERT; empty report keeps last snapshot) |
| `backend/scripts/fetch_flex_trades.py` | `parse_cash_from_xml()` (skips BASE_SUMMARY, prefers endingSettledCash) + `save_cash_balances()` |
| `backend/api/routes/sync.py` | non-blocking `cash` step chained after `positions` in `/api/sync/ibkr` and `/api/sync/full` |
| `backend/api/routes/dashboard.py` | net worth = stocks + cash (EUR direct, USD via EURUSD); new `net_worth.cash_eur`; day-change % rebased on total incl. cash |
| `frontend/components/dashboard/NetWorthCard.tsx` | Cash cell shows the tracked amount (was "not tracked yet") |
