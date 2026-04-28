# Active Work

> Current focus. Updated when an epic ships and the next one starts.

## Currently active

**Epic G — Sell Signals on Holdings**

- **Status:** [ ] Pending — plan not yet written
- **Spec:** [epic-G-sell-signals/spec.md](epic-G-sell-signals/spec.md)
- **Why now:** Epic D just shipped. Indicators are computed. Sell signals read from indicators + positions_ibkr — the natural next layer that surfaces actionable info on the Positions tab.

### What's needed before kicking off

- Write the implementation plan in `docs/plans/2026-04-28-story-g-sell-signals.md` per the spec
- Settle on the initial signal threshold defaults

## Up next (after Epic G ships)

**Epic H — Security Detail View** — universal modal triggered by symbol clicks. Held mode (chart + tx + sell sim + signal checklist) vs not-held mode (chart + buy signals + stats).

## Recently shipped

- **Epic D — Indicators** — `[STORY-D-1..6]`. MA/BB/RSI/MRSI/ATR/Vol MA, indicators table, per-symbol orchestrator, sync endpoint wired into `/api/sync/full`, read endpoint. Live smoke wrote 4,292 indicator rows for 17 of 18 symbols.
- **Epic C — Foundation** — `[STORY-C-1..8]` + bug fix + C-10 polish. Tailwind+shadcn, tracked_universe, market_data ingestion, S&P 500 + CAC 40 seeders.
- **Epic B — UX Polish** — tab restructure, staleness badge, sync progress strip, filter toolbars
- **Epic A — Sync Pipeline Restructure** — `/api/sync/*` 4-step pipeline + orchestrator

## Known issues

- **Corporate-actions step in `/api/sync/full` fails** with "can't subtract offset-naive and offset-aware datetimes" — pre-existing regression from SYNC-13 timezone work, surfaced during Epic D smoke test. Indicators sync works when called directly. Fix should restore CA fetcher's tz handling. Tracked as a follow-up bug fix before Epic G ships.

## Blockers

None for Epic G itself.

## Decisions awaiting user

None.
