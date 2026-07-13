# Active Work

> Current focus. Updated when an epic ships and the next one starts.

## Currently active

**Epic SH — Sync Hardening**

- **Status:** [✓] Complete — SH-1..SH-5 shipped 2026-07-13 (commits `545933e..` on `newstart`). Backend 214 green, frontend 89 green (16 suites), tsc clean, E2E smoke all-green (0 console errors). See build-log 2026-07-13 + ADR-4.
- **Plan:** [`docs/superpowers/plans/2026-07-13-sync-hardening.md`](../../../superpowers/plans/2026-07-13-sync-hardening.md)
- **Why:** hands-on Epic V testing surfaced three sync-subsystem failures sharing one root (fragile tab-scoped state over a rollback-journal DB): dashboard froze during a sync, sync lost on tab-switch, refresh buttons on a different tab from the chips.
- **Shipped:** SQLite WAL + busy-timeout (reads don't block writes) · app-level `SyncProvider` (survives navigation, single-flight guard) · `SyncToolbar` consumes it · Dashboard sync hub (actionable chips + "Sync all").
- **Next:** Epic S Phase 2 — evidence-based verdict calibration (brainstorm parked; decisions banked: fundamentals judgment-only, primary metric excess-vs-^GSPC with risk-adjusted secondary lens).

**Epic V — Global Dashboard & IA restructure**

- **Status:** [✓] Complete — V-1..V-11 all shipped 2026-07-12 (commits `8da2bc5..0b66e5c` on `newstart`). Backend 210 green, frontend 80 green, E2E smoke 18/18 (0 console errors). See build-log 2026-07-12 + ADR-3.
- **Plan:** [`docs/superpowers/plans/2026-07-10-dashboard-ia-restructure.md`](../../../superpowers/plans/2026-07-10-dashboard-ia-restructure.md)
- **Shipped:** Dashboard landing (EUR net-worth hero, allocation donut, portfolio-vs-^GSPC line, movers, action queue, staleness chips) · `GET /api/dashboard` + `portfolio_value_history` + `EURUSD=X` FX · Research grid pruned to one view with colour-coded grouped headers · Transactions→Journal (trades-first) · Configuration→Settings · English-only UI · Technical/ZigZag/Breakout card in the detail popup.
- **Next focus:** Epic G frontend, then Epic S Phase 2 (see "Up next").

**Epic R — Research Unified View** (correction — done)

- **Status:** [✓] Complete — R-1..R-4 all shipped (frontend merged 2026-07-03)
- **Spec:** [epic-R-research-unified/spec.md](epic-R-research-unified/spec.md) · full design: [`docs/superpowers/specs/2026-07-01-research-unified-view-design.md`](../../../superpowers/specs/2026-07-01-research-unified-view-design.md)
- **Why now:** The Screener (Epic S) and Browse Universe drifted into two divergent per-stock pipelines — indicators in one, screener signals + fundamentals in the other; detail popup has no fundamentals; and `consolidation_patterns` writes only 1 row / 561 (ZigZag/S-R effectively empty). Correct the data model before resuming G → E → F.

### Progress

- ✅ **R-1** Unified `research_overview` view (+ latest indicators) + `/api/research/overview` json/csv. 4 TDD tests green; live DB migrated (52 cols, 561 rows).
- ✅ **R-2 backend** Root cause = 3 hardcoded consolidation gates (70%/4/85%), not a bug. Parameterized them (conservative defaults) + `GET/PUT /api/screener/settings/{key}`. Live proof: default=1/561, loosened=236/561. TDD green.
- ✅ **R-2/R-3 frontend** `TuningPanel` — all numeric consolidation params as labeled inputs (recommended captions), Reset-to-recommended, Save & re-run (`PUT settings` → `POST /sync/screen`). Collapsible under the Research header.
- ✅ **R-3** Merged Research UI: `ResearchGrid` (configurable columns + localStorage persistence `research.columns.v1`, sort, filter chips, CSV export) + `SyncToolbar` (Fundamentals · Technical · Compute · Run all) mounted in Browse Universe; standalone Screener tab + orphaned `ScreenerGrid` retired. 8 TDD tests green.
- ✅ **R-4** Fundamentals card in the Security Detail popup (`/api/security/{sym}/detail` extension). Verified live (SPG: ROE 113.6% · ROIC 18.9% · gates 7/7 · P/E 15.4).

**E2E evidence (2026-07-03, headless Chromium against live backend):** Research grid renders 561/561 real rows; toolbar + tuning (recommended max range = 5) present; MA200 column toggles on; row-click → detail sheet with Fundamentals card; **0 console errors**. Screenshots in session scratchpad.

## Up next (Epic R + V shipped)

1. **Epic G — Sell Signals frontend.** Backend done (G-1..G-5). Remaining: **G-6** signals settings sub-section, **G-7** E2E smoke, bonus signals card in the detail sheet.
2. **Epic S Phase 2 — Screener calibration.** Turn provisional gate/tech weights into tuned verdicts.
3. **Epic E (remaining) — Tech Analysis drill-down chart** `/tech-analysis/{symbol}` (lightweight-charts). Signals/S-R/consolidation already delivered by Epic S.
4. **Epic F — Options S/R + polish.**

## Recently shipped

- **Epic SH — Sync Hardening** — `[STORY-SH-1..5]`. SQLite WAL + busy-timeout (sync no longer blocks the dashboard read), app-level `SyncProvider` (sync survives tab navigation + single-flight guard), `SyncToolbar` consumes it, Dashboard sync hub (actionable staleness chips + "Sync all"). Found by hands-on Epic V testing. E2E smoke green, 0 console errors.
- **Epic V — Global Dashboard & IA restructure** — `[STORY-V-1..11]`. New Dashboard landing tab (EUR net-worth hero, allocation donut, portfolio-vs-^GSPC performance, movers, action queue merging sell-signals + buy verdicts, staleness chips, single Sync), `GET /api/dashboard` aggregate + daily `portfolio_value_history` snapshots + `EURUSD=X` FX ingest, Research pruned to one grid with colour-coded grouped headers, Transactions→Journal (trades-first), Configuration→Settings, English-only UI, Technical/ZigZag/Breakout card in the detail popup. Charts hand-rolled SVG (no chart lib). E2E smoke `frontend/e2e/dashboard_smoke.py` 18/18 green.
- **Epic R — Research Unified View** — `[STORY-R-1..4]`. Unified `research_overview` view + `/api/research/overview`, parameterized consolidation gates + `TuningPanel`, merged `ResearchGrid` (Screener retired), Fundamentals card in the detail popup.
- **Epic S Phase 1 — Screener** — `[E-1]` commits (16 tasks). Fundamentals fetch + quality gates, `screen_signals`, ZigZag consolidation, breakout + S/R, provisional scoring, Screener grid + CSV. Tracked in `docs/superpowers/`; now registered as Epic S. **Live fix 2026-07-01:** fundamentals table was empty → fetched 555 symbols + rescored (verdicts spread 3 strong_buy / 55 buy / 129 watch / 193 neutral / 181 avoid).
- **Epic H v1 — Security Detail Sheet** — `[STORY-H-1..8]`. Click any symbol → slide-in panel with position / transactions / indicators / bars. Bandaid version: chart + sell simulator + signal checklist deferred to follow-up or later epics.
- **Epic D — Indicators** — `[STORY-D-1..9]`. MA / BB / RSI / MRSI / ATR / Vol MA, MRSI scaled to ±1 ratio range.
- **Epic C — Foundation** — Tailwind+shadcn, tracked_universe, market_data ingestion, S&P 500 + CAC 40 seeders.
- **Epic B — UX Polish** — tab restructure, staleness badge, sync progress strip, filter toolbars.
- **Epic A — Sync Pipeline Restructure** — `/api/sync/*` 4-step pipeline + orchestrator.

## Known issues / loose ends

- **Consolidation under-production (→ Epic R-2)** — `consolidation_patterns` writes only 1 row / 561 symbols despite a clean `screen` sync; breakout depends on it so 474/561 report `no_consolidation_patterns`. ZigZag / S-R effectively empty. Root cause TBD (seed-drift params / ZigZag port I/O / retention prune).
- **Fundamentals refresh doesn't rescore (→ Epic R-3)** — `POST /api/sync/fundamentals` only fetches; `score_fund` stays 0 until `scoring_compute` runs. R-3 chains a rescore into the button.
- **Corporate-actions step in `/api/sync/full` fails** with timezone error — pre-existing regression from SYNC-13. Indicators sync still works directly. Fix tracked as a follow-up.
- **Currency back-fill from positions_ibkr** — 9 of 14 IBKR holdings have NULL currency in tracked_universe (default to ^GSPC, correct for US stocks but brittle). Small fix to `_sync_positions_to_universe`.
- **Lookback bump for MRSI history** — yfinance fetch is 365d, gives ~252 trading days. MRSI rolls on 252-day window so only the very last bar gets a value. Bump default lookback to 730d for a meaningful MRSI time series. Cheap fix in `market_data_ingestor.py`.

## Blockers

None for Epic R. Design spec approved; ready to write the R-1 implementation plan.
