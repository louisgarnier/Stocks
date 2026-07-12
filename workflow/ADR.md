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
