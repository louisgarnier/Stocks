# ADR.md — architectural decision records

## 2026-07-10 — ADR-1: Pipeline freshness contract (indicators → screen signals)

**Context:** market_data, indicators, and screen_signals are synced by independent endpoints/buttons. Signals computed on 2026-07-01 joined fresh prices with ~7-week-stale MAs and were never invalidated, poisoning research_overview (see ERRORS.md stale-join entry).

**Decision:**
1. **Read-time guard** — `screen_signals_compute` only accepts an indicators row dated within 7 calendar days at-or-before the last market_data bar (`INDICATOR_FRESHNESS_DAYS`). Stale ⇒ MA-derived fields are NULL, never silently wrong.
2. **Write-time chaining** — every endpoint that recomputes indicators (`/api/sync/analytics`, `/api/sync/full`) chains `_step_screen()` (signals → consolidation → breakout → scoring → prune) afterwards. `/api/sync/screen` remains standalone for post-tuning recompute.
3. Long-running sync endpoints are plain `def` (FastAPI threadpool), never `async def`, so the event loop stays responsive (`/analytics`, `/full`, `/screen`, `/fundamentals`).

**Consequence:** `signal_date` can no longer drift from `indicator_date` through normal UI use; a stale join degrades to honest NULLs instead of wrong verdicts.

## 2026-07-10 — ADR-2: Two consolidation detectors coexist, columns labeled by source

**Context:** `breakout_compute.py` embeds its own strict 40-day consolidation detection (verbatim port of `d_breakout_detector_3.py` — contractually not to be refactored), independent of `consolidation_compute.py` (ZigZag quality scoring → `consolidation_patterns`, port of `g_consolidation.py`). research_overview mixed columns from both, so `breakout_detected` rows showed empty consolidation columns — read as data corruption.

**Decision:** keep both detectors (they answer different questions: tradeable-breakout setup vs. consolidation quality screening), but every breakout row now exposes the bounds of the consolidation that produced it as distinct view columns: `breakout_support`, `breakout_resistance`, `breakout_range_pct`, `breakout_duration_days`. The ZigZag detector keeps `consolidation_quality` / `support_level` / `resistance_level`. No algorithm changes.

**Rejected alternative:** making breakout read `consolidation_patterns` — would alter the verbatim-ported detection semantics and couple two deliberately separate signals.

**Follow-up (Phase B wireframe audit):** decide how the UI presents the two sources so they aren't mistaken for one detector.

## 2026-07-12 — ADR-3: Dashboard valuation, FX, and hand-rolled charts (Epic V)

**Context:** Epic V added a global Dashboard tab needing a single EUR net-worth figure, a portfolio-vs-benchmark performance line, and allocation/movers/action-queue cards, on a stack with no charting library and a mixed USD/EUR book.

**Decisions:**
1. **FX as a first-class tracked symbol** — EUR base currency is derived from an `EURUSD=X` bar series ingested through the normal market-data path, seeded via `tracked_universe` source `fx` (`universe_seeders.seed_fx_symbols`). `get_fx_rate(conn, on_date)` reads the at-or-before close, so historical snapshots convert at period-correct rates rather than today's spot.
2. **Valuation excludes CASH legs** — `portfolio_history_compute` replays split-adjusted transactions × daily closes × FX into `portfolio_value_history`, deliberately excluding CASH-category legs (they are settlement artifacts, not marketable value). The Journal applies the same CASH-free filter (`visibleTransactions`) so trades-first view and net-worth agree.
3. **Charts are hand-rolled SVG — no chart package.** The allocation donut and performance line are authored as raw `<svg>` in `components/dashboard/`, consistent with the existing SVG sparklines. Adding a charting dependency was rejected: the visuals are simple, and a new package needs architecture.md approval and ships client weight for no gain.
4. **Snapshot compute is isolated from ingest** — chaining `portfolio_value_history` hydration into a sync must never 500 a successful IBKR pull; a snapshot failure returns 200 with a `portfolio_history.error` field (see Task 3).

**Consequence:** net worth, performance, and allocation all trace to the same replayed-transaction + FX source; a missing price or FX bar degrades to a logged warning, not a wrong or crashing figure.

## 2026-07-13 — ADR-4: Sync concurrency (WAL) + app-level sync orchestration (Epic SH)

**Context:** Testing Epic V surfaced three failures that shared one root — sync was built as fragile, tab-scoped UI state over a rollback-journal database: (a) a running analytics sync blocked the dashboard read (stuck "Loading dashboard…"); (b) leaving the Browse Universe tab lost all sync progress and risked double-starts; (c) the refresh buttons lived on a different tab from the staleness chips.

**Decisions:**
1. **SQLite runs in WAL mode with a 30s busy-timeout**, set on every connection from `get_db_connection()`. WAL lets a reader (the dashboard) see the last committed snapshot while a writer (a sync) holds an open transaction — reads no longer block behind writes. WAL is a persistent file property, so even the few call sites that still open `sqlite3.connect()` directly (`fetch_corporate_actions.py`, `updated_transactions.py`) inherit WAL; they only lack the busy-timeout (tracked follow-up).
2. **Sync orchestration lives in an app-level React context (`SyncProvider`), mounted above the tabs in `layout.tsx`** — not in tab-scoped component state. A running sync's awaited fetch and its progress survive tab navigation; a synchronous `useRef` single-flight guard (checked in the event handler, not a `setState` updater — StrictMode-safe) prevents overlapping runs; `syncVersion` increments on success so the dashboard and research grid refetch only when data actually changed.
3. **The Dashboard is the sync hub:** the staleness chips are actionable buttons (prices→Technical, signals→Compute, fundamentals→Fundamentals, IBKR→ibkr) and a "Sync all" runs the analytics chain (Technical→Fundamentals→Compute). The header's existing IBKR/Flex button is deliberately untouched (always mounted, richer flow).

**Consequence:** the dashboard stays live during a sync, a sync can't be silently abandoned or double-started by navigation, and refresh happens where the staleness is shown. Live-verified: dashboard rendered net worth while a signals recompute wrote, and "Syncing…" persisted across a tab round-trip (E2E smoke, 0 console errors).

## 2026-07-13 — Freshness is a server-side, trading-day contract (staleness chips)

**Context:** the chips showed "prices 4d" on a Monday even though Friday's bar was the freshest completed trading day and syncs had just succeeded — a wall-clock delta over a date-only string can't distinguish "data is old" from "markets were closed", nor "data as-of" from "last checked".

**Decisions:**
1. **`as_of` is a rich contract, not a string:** each chip gets `{date, checked_at, level}` — `date` = newest data, `checked_at` = last relevant `sync_runs.finished_at`, `level` computed server-side.
2. **Freshness compares against the last completed trading day** (`backend/api/utils/trading_days.py`, single 22:00 UTC all-markets-closed cutoff, weekends rolled back). fresh = expected bar present AND verified by a sync after that day's close. Holidays deliberately unmodeled (YAGNI): one amber day, honest-but-conservative.
3. **The frontend renders, it doesn't reason:** chips display the date and a relative "checked Xh ago"; the old client-side `relativeStaleness` heuristic is deleted so there's exactly one freshness authority.

**Consequence:** weekend/premarket states read green with the true data date; a chip can now honestly say "data is current but nobody has checked since Friday" (amber). Regression-tested in `test_trading_days.py` + dashboard route tests.
