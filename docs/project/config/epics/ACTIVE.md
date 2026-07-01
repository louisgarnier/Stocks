# Active Work

> Current focus. Updated when an epic ships and the next one starts.

## Currently active

**Epic R — Research Unified View** (correction — do now)

- **Status:** [→] In Progress
- **Spec:** [epic-R-research-unified/spec.md](epic-R-research-unified/spec.md) · full design: [`docs/superpowers/specs/2026-07-01-research-unified-view-design.md`](../../../superpowers/specs/2026-07-01-research-unified-view-design.md)
- **Why now:** The Screener (Epic S) and Browse Universe drifted into two divergent per-stock pipelines — indicators in one, screener signals + fundamentals in the other; detail popup has no fundamentals; and `consolidation_patterns` writes only 1 row / 561 (ZigZag/S-R effectively empty). Correct the data model before resuming G → E → F.

### Progress

- ✅ **R-1** Unified `research_overview` view (+ latest indicators) + `/api/research/overview` json/csv. 4 TDD tests green; live DB migrated (52 cols, 561 rows).
- ✅ **R-2 backend** Root cause = 3 hardcoded consolidation gates (70%/4/85%), not a bug. Parameterized them (conservative defaults) + `GET/PUT /api/screener/settings/{key}`. Live proof: default=1/561, loosened=236/561. TDD green.
- ⏳ **R-2/R-3 frontend** Tuning panel (edit consolidation params + reset-to-recommended) + re-run — **needs UI mockup approval first**.
- ⏳ **R-3** Merged Research UI: Screener grid into Browse Universe, 3+1 sync buttons (Fundamentals auto-rescore · Technical · Compute · Run all), column show/hide + persistence, retire Screener tab — **needs UI mockup approval first**.
- ⏳ **R-4** Fundamentals card in the Security Detail popup (`/api/security/{sym}/detail` extension).

## Up next (after Epic R ships)

1. **Epic G — Sell Signals frontend.** Backend done (G-1..G-5). Remaining: **G-6** signals settings sub-section, **G-7** E2E smoke, bonus signals card in the detail sheet.
2. **Epic S Phase 2 — Screener calibration.** Turn provisional gate/tech weights into tuned verdicts.
3. **Epic E (remaining) — Tech Analysis drill-down chart** `/tech-analysis/{symbol}` (lightweight-charts). Signals/S-R/consolidation already delivered by Epic S.
4. **Epic F — Options S/R + polish.**

## Recently shipped

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
