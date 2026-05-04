# Active Work

> Current focus. Updated when an epic ships and the next one starts.

## Currently active

**Epic G — Sell Signals on Holdings**

- **Status:** [~] Backend complete (G-1, G-2, G-3+G-4 merged); frontend pending
- **Spec:** [epic-G-sell-signals/spec.md](epic-G-sell-signals/spec.md)
- **Why now:** Epic H v1 just shipped. Click-to-inspect works for any symbol. Now we surface signals on the Positions tab Signals column AND inside the Security Detail Sheet (a new "Signals" card alongside Position / Indicators / Transactions / Bars).

### Progress

- ✅ **G-1** schema: `holding_signals` + `signal_settings` tables, defaults seeded
- ✅ **G-2** 11 sell-signal evaluators + `compute_all_signals` orchestrator
- ✅ **G-3** API routes (sync + reads + settings GET/POST) and wired into `/api/sync/full`. (G-4 read endpoint absorbed into G-3.)
- ✅ **G-5** Positions tab Signals column + inline expand panel. Implementation complete (type-check + 23 jest tests green; backend smoke 143 signals across 14 holdings). Visual UI confirmation pending user.
- ⏳ **G-6** Configuration: signals settings sub-section (toggle + thresholds)
- ⏳ **G-7** End-to-end smoke test (will fold into G-6 ship)
- ⏳ Bonus: signals card inside the Security Detail Sheet for held symbols

## Up next (after Epic G ships)

**Epic E — Tech Analysis tab v1.** Range + Trend Breakouts, ZigZag + BB Squeeze consolidation, technical S/R. Drill-down chart at `/tech-analysis/{symbol}` (full lightweight-charts). Click rows → opens Security Detail Sheet (already in place from Epic H v1).

## Recently shipped

- **Epic H v1 — Security Detail Sheet** — `[STORY-H-1..8]`. Click any symbol → slide-in panel with position / transactions / indicators / bars. Bandaid version: chart + sell simulator + signal checklist deferred to follow-up or later epics.
- **Epic D — Indicators** — `[STORY-D-1..9]`. MA / BB / RSI / MRSI / ATR / Vol MA, MRSI scaled to ±1 ratio range.
- **Epic C — Foundation** — Tailwind+shadcn, tracked_universe, market_data ingestion, S&P 500 + CAC 40 seeders.
- **Epic B — UX Polish** — tab restructure, staleness badge, sync progress strip, filter toolbars.
- **Epic A — Sync Pipeline Restructure** — `/api/sync/*` 4-step pipeline + orchestrator.

## Known issues / loose ends

- **Corporate-actions step in `/api/sync/full` fails** with timezone error — pre-existing regression from SYNC-13. Indicators sync still works directly. Fix tracked as a follow-up.
- **Currency back-fill from positions_ibkr** — 9 of 14 IBKR holdings have NULL currency in tracked_universe (default to ^GSPC, correct for US stocks but brittle). Small fix to `_sync_positions_to_universe`.
- **Lookback bump for MRSI history** — yfinance fetch is 365d, gives ~252 trading days. MRSI rolls on 252-day window so only the very last bar gets a value. Bump default lookback to 730d for a meaningful MRSI time series. Cheap fix in `market_data_ingestor.py`.

## Blockers

None for Epic G itself.
