# Build Log

## 2026-04-29 — Epic H v1 complete: Security Detail Sheet

8 stories shipped. Click any symbol on Browse Universe (Configuration tab) or Positions tab → slide-in shadcn Sheet panel showing position info (held mode), latest indicators (all 11 values), transactions filtered by symbol, last 30 OHLCV bars.

**Endpoints added:**
- `GET /api/security/{symbol}/detail` — combined per-symbol response (universe + position + transactions + indicators + bars)

**Frontend additions:**
- shadcn `Sheet` component
- `frontend/components/security-detail/SecurityDetailSheet.tsx` — Sheet + Mode A/B branching + 4 cards (About, Position, Indicators, Transactions, Recent bars)
- Click handlers on Browse Universe rows (`hover:bg-secondary/40 cursor-pointer`)
- Click handlers on Positions tab rows (inline-styled to match existing tab)
- ESC / click-outside closes via Sheet's controlled `open` state

**Live smoke test:**
- `GET /api/security/NVDA/detail` → held=True, 26 transactions, MRSI +0.127, 30 bars
- `GET /api/security/AAPL/detail` → held=False, MRSI +0.028, 30 bars
- `GET /api/security/^GSPC/detail` → benchmark, sources=['benchmark']

**Out of scope (Epic H follow-up or merged into G/E/F as they ship):** mini price chart with MA overlays (Recharts), sell simulator (avg-cost realized P&L), buy/sell signal checklist (depends on Epic G), "Open in Tech Analysis" link (depends on Epic E), "Add to manual universe" CTA, yfinance Ticker.info stats card.

**Tests:** 4 new integration tests in `test_security_routes.py`. All passing.

**Commits:** STORY-H-1 through STORY-H-8 on branch `newstart`.

---

## 2026-04-28 — Epic D complete: indicators

7 stories shipped, end-to-end smoke test passed for indicators (CA step regression noted below).

**Subsystems delivered:**
- `indicators` table (composite PK on `(symbol, time)`, 11 indicator columns)
- Auto-seed of 4 benchmark symbols (`^GSPC`, `^FCHI`, `^GDAXI`, `^FTSE`) into `tracked_universe` with source `benchmark`
- Pure pandas indicator math: MA 50/100/150/200, BB(20, 2), RSI(14) Wilder, ATR(14), Volume MA(20), MRSI (Mansfield Relative Strength)
- Per-symbol orchestrator with benchmark resolution (USD→^GSPC, EUR→^FCHI, GBP→^FTSE)
- `POST /api/sync/indicators` endpoint, wired into `/api/sync/full` as the 5th step
- `GET /api/indicators/{symbol}` read endpoint

**Tests:** 16 new tests across 2 files (`test_indicators_compute.py` + `test_indicators_routes.py`). All passing.

**Live smoke test:**
- 18 symbols (14 IBKR positions + 4 benchmarks) fed market_data
- `compute_all` wrote 4,292 indicator rows for 17 symbols (one had insufficient history)
- Spot check NVDA: MA50=186.2, MA200=183.3 (uptrend), RSI(14)=69.9, **MRSI=+12.7** (NVDA outperforming S&P 500), BB width=0.27, ATR=5.93

**Known issue surfaced during smoke (NOT Epic D regression):** the `corporate_actions` step in `/api/sync/full` fails with "can't subtract offset-naive and offset-aware datetimes" — a side-effect of the SYNC-13 timezone work where `set_ca_status` stores tz-aware ISO timestamps but the CA fetcher's incremental logic compares against tz-naive `datetime.now()`. Indicators step does not run when CA fails because the chain stops. Fix tracked separately. Indicators sync works fine when called directly via `POST /api/sync/indicators`.

**Commits:** STORY-D-1 through STORY-D-6 on branch `newstart`.

---

## 2026-04-28 — Epic C complete: foundation (universe + market_data + design system)

9 stories shipped, end-to-end smoke test passed against real Wikipedia + yfinance + IBKR Flex.

**Subsystems delivered:**
- **Design system**: Tailwind v4 + shadcn/ui installed; first shadcn-styled UI section landed in Configuration tab. `frontend/components/ui/*` populated with button, card, input, label, badge, table, dialog, tabs, select, switch, sonner. `globals.css` migrated to v4 syntax with `@theme inline` design tokens.
- **Universe management**: `tracked_universe` (JSON `sources` column), `tracked_indices` tables. CRUD endpoints. S&P 500 + CAC 40 Wikipedia seeders (with User-Agent header to bypass 403). IBKR positions auto-tag into universe with source `ibkr_position`; sold positions un-tag and row deletes if no other source.
- **Market data ingestion**: `market_data` table (composite PK `(symbol, time)`). yfinance batched ingestor (50-symbol batches, threads, idempotent). `_yf_download` indirected for hermetic tests.

**Endpoints added:**
- `GET    /api/universe`                    list enabled tracked symbols
- `POST   /api/universe/manual`             add manual ticker (uppercases, idempotent)
- `DELETE /api/universe/manual/{symbol}`    remove manual tag
- `GET    /api/universe/indices`            list indices with status + count
- `POST   /api/universe/indices/{name}/toggle`
- `POST   /api/universe/indices/{name}/refresh`  re-scrape Wikipedia
- `POST   /api/sync/market-data`            yfinance ingest for enabled symbols
- `GET    /api/market-data/{symbol}`        OHLCV bars, optional date range

**Tests:** 19 new tests across 4 files (`test_universe_routes.py`, `test_universe_seeders.py`, `test_market_data_ingestor.py`, `test_market_data_routes.py`). All passing. SQLite via `temp_db` fixture; HTTP stubbed via `monkeypatch`.

**Live smoke test results:**
- S&P 500 refresh: 503 symbols inserted from Wikipedia
- CAC 40 refresh: 40 symbols inserted
- IBKR positions sync: 14 positions auto-tagged into universe (5 multi-source with sp500)
- Market data sync (capped to held positions): 14 symbols processed, **3276 OHLCV rows** inserted (~252 trading days each), 0 errors
- Total enabled universe after smoke: 552 symbols

**Bug fix bundled:** Wikipedia returns 403 to pandas' default User-Agent. Fix: fetch HTML via `requests` with a real UA, then `pd.read_html(StringIO(...))`.

**Commits:** STORY-C-1 through STORY-C-8 + bug fix on branch `newstart`.

---

## 2026-04-27 — Story A complete: sync pipeline restructured

Refactored the monolithic `/api/transactions/flex-import` endpoint into a 4-step decoupled sync pipeline at `/api/sync/*` plus a `/api/sync/full` orchestrator. Reconciliation feature dropped (`positions_calculated` table + recalc script + recon UI removed).

**Endpoints (all POST):**
- `/api/sync/positions` — Flex pull, write only positions_ibkr
- `/api/sync/transactions` — Flex pull, write only transactions, flag CA-orange
- `/api/sync/corporate-actions` — yfinance refresh
- `/api/sync/splits` — apply known splits → updated_transactions
- `/api/sync/full` — orchestrator with shared Flex call across positions+transactions

**Frontend:** Sync IBKR button wired to `/api/sync/full`. All recon UI removed (Recalculate Rec button, summary cards, Qty Rec column, Position interface fields).

**Env-var fallback** in `fetch_flex_response()`: dedicated `IBKR_QUERY_ID_positions` / `IBKR_QUERY_ID_trades_<type>` first, falls back to unified `IBKR_QUERY_ID_<type>`. No code change needed when dedicated queries are set up at IBKR.

**Tests:** 9 integration tests in `backend/tests/test_sync_routes.py`, all passing. Real DB via `temp_db` fixture, Flex HTTP stubbed via `stub_flex_http`.

**Smoke test:** real IBKR sync via `/api/sync/full` succeeded — 14 positions refreshed, 25 split-adjusted transactions confirmed across ATRA/AVGO/CHPT/NFLX/NOW/NVDA.

**Bug fix bundled:** `backend/utils/ca_status.py` was opening its own hardcoded SQLite connection, bypassing the connection module's `DB_FILE` and breaking test isolation. Routed through `get_db_connection()`.

**Commits:** SYNC-1 through SYNC-10 on branch `newstart`.

---

## 2026-07-12 — Epic V complete: Global Dashboard + IA restructure

Shipped the 11-task Dashboard & Information-Architecture restructure (`[STORY-V-1..11]`, commits `8da2bc5..0b66e5c` on `newstart`), executed via subagent-driven development (implementer → task review → fix loop per task).

**What shipped:**
- **New Dashboard tab (default landing)** — EUR net-worth hero (FX-combined), allocation donut (Sector / Position / Currency toggle), portfolio-vs-^GSPC performance line, top/flop movers, action queue merging holding sell-signals + screener buy verdicts, staleness chips, single "Sync IBKR". All charts hand-rolled SVG (`components/dashboard/`).
- **Backend aggregate** — `GET /api/dashboard?window=` (`routes/dashboard.py`); daily `portfolio_value_history` snapshots (`scripts/portfolio_history_compute.py`) replaying split-adjusted transactions × closes × FX, CASH-excluded; `EURUSD=X` FX ingest via `universe_seeders.seed_fx_symbols`; snapshot chained into syncs, isolated so it can't 500 an ingest.
- **Research tab pruned** — Market Data panel + old Browse-Universe list retired; one grid remains, with a colour-coded grouped header row (IDENTITY/PRICE/INDICATORS/MOMENTUM/CONSOLIDATION/BREAKOUT/FUNDAMENTALS/SCORE).
- **Transactions → Journal** — trades-first filter (CASH/EUR.USD hidden by default), guarded delete demoted to a danger-zone action.
- **Configuration → Settings**, and a full French → English UI sweep.
- **Detail popup** — new Technical signals card (momentum + MA-cross), ZigZag swing block, and conditional Breakout block (`security.py` + `SecurityDetailSheet.tsx`); zigzag compute isolated so a messy symbol can't 500 the popup.

**Test evidence:**
- Backend: `210 passed` (`backend/venv/bin/python -m pytest backend/tests/ -q`).
- Frontend: `80/80` across 13 suites (`cd frontend && npx jest`).
- **E2E smoke** (`frontend/e2e/dashboard_smoke.py`, headless Chromium vs live :3010/:8010) — all 18 assertions green, 0 console errors:
  ```
  Dashboard: NET WORTH · EUR (€117,850), donut + performance SVGs, ACTION QUEUE
             with SELL SIGNALS + BUY CANDIDATES, movers  — PASS
  Mover click → detail sheet with Technical signals + ZigZag (Task 9)  — PASS
  Browse Universe: exactly one grid, "Market Data" absent (Task 6),
             grouped header row, colSpans 13 == visible cols 13 (Task 10)  — PASS
  Journal: EUR.USD FX leg hidden by default (Task 7)  — PASS
  Console: 0 errors  — PASS
  SMOKE PASSED — all assertions green.
  ```
  Screenshots: `e2e_1_dashboard.png` … `e2e_4_journal.png` (session scratchpad).

**Notable fixes caught in review:** same-day trades dropped by reindex (Task 2); snapshot failure could 500 an ingest (Task 3); fetch race/unmount guard on Dashboard (Task 5); zigzag ZeroDivision/Type errors 500-ing the detail popup + untested breakout aliasing (Task 9); group-header fallback border referenced an undefined `var(--border)` under Tailwind v4 `@theme inline` → concrete `#e8eaed` (Task 10).

**Deferred (backlog):** split auto-refetch prevention; ZigZag gate calibration (0/561 patterns — product decision); score calibration (Epic S Phase 2); Journal select-all still spans hidden CASH rows; detail popup Breakout mini-chart (mockup §⑥) not built (textual stats only).

---

## 2026-07-13 — Epic SH complete: Sync Hardening

Fixed three related sync-subsystem failures found by hands-on Epic V testing (`[STORY-SH-1..5]`, commits `545933e..` on `newstart`), via subagent-driven development (implementer → review → fix per task).

**Root cause (shared):** sync was fragile, tab-scoped UI state over a rollback-journal database.

**What shipped:**
- **SH-1 — WAL + busy-timeout** (`connection.py`): SQLite runs `journal_mode=WAL` + `busy_timeout=30000`, so a running sync no longer blocks the dashboard read. Real read-during-write concurrency test.
- **SH-2 — `SyncProvider`** (`lib/sync-context.tsx` + `providers.tsx` + `layout.tsx`): app-level context above the tabs owns sync orchestration; a `useRef` single-flight guard (StrictMode-safe) blocks double-starts; `syncVersion` bumps on success.
- **SH-3 — `SyncToolbar`** consumes the provider (no local state); the research grid refetches on `syncVersion`. Progress now persists across tab switches (regression-tested via unmount/remount).
- **SH-4 — Dashboard sync hub:** staleness chips are actionable buttons + a "Sync all" button; per-chip syncing state; dashboard refetches on completion.
- **SH-5 — this:** E2E smoke extended + docs (ADR-4, two ERRORS entries).

**Test evidence:**
- Backend `214 passed`; frontend `89 passed` across 16 suites; `tsc --noEmit` clean.
- **E2E smoke** (`frontend/e2e/dashboard_smoke.py`, headless Chromium vs live :3010/:8010) — all assertions green, 0 console errors, including:
  ```
  Sync hub: Dashboard has 'Sync all' + actionable prices/signals chips  — PASS
  Sync survives navigation + dashboard stays live (WAL):
    started a signals recompute, left to Browse Universe, returned mid-sync
    → dashboard still rendered net worth (not stuck on "Loading…")        — PASS
    (info) 'Syncing…' still visible after round-trip: True
  Console: 0 errors                                                        — PASS
  ```
  Screenshot `e2e_5_sync_hub.png`: signals chip "… syncing", "Syncing…" button active, full dashboard rendered during the write — the WAL + provider win, visually confirmed.

**Note:** `layout.tsx` carries a "check with user before modifying" banner; the modification (wrapping `{children}` in `<Providers>`) was explicitly named in the user-approved plan.

**Follow-up (logged, backlog):** two raw `sqlite3.connect()` call sites lack the busy-timeout (inherit WAL); route through `get_db_connection()` when next touched.

## 2026-07-13 — Epic G complete (G-6 signal settings + G-7 E2E)

**G-6 — Sell Signals settings card** (Settings tab, approved mockup): 11 signal toggles in 3 groups (Trend breaks / Volume & momentum / Risk), %-threshold inputs for trailing_drawdown & stop_loss (display % ↔ stored fraction, clamped 1–95), immediate save with "✓ Saved" hint + optimistic revert on failure, "↻ Recompute signals now" → POST /api/sync/holding-signals. Backend endpoints pre-existed (G-1..G-4).

**G-7 — E2E smoke** `frontend/e2e/signals_smoke.py`: ALL GREEN — card renders (11 switches, badge matches API), toggle + threshold round-trip through the API and restore, recompute advances last_evaluated_at, Positions pills + expand panel work, 0 console errors.

**Test evidence:** frontend 101 passed (18 suites) + tsc clean; E2E 18/18 PASS.

Also today (out-of-epic): trading-day-aware staleness chips; IBKR cash balances in net worth + allocation donut (see codebase.md 2026-07-13 entries).
