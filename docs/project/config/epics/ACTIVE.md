# Active Work

> Current focus. Updated when an epic ships and the next one starts.

## Currently active

**Epic D — Indicators**

- **Status:** [ ] Pending — plan not yet written
- **Spec:** [epic-D-indicators/spec.md](epic-D-indicators/spec.md)
- **Why now:** Epic C just shipped the foundation (`tracked_universe` + `market_data`). Indicators are the next layer everything else depends on (Stories G, H, E all read from the indicators table).

### What's needed before kicking off

- Write the implementation plan in `docs/plans/2026-04-28-story-d-indicators.md` per the spec
- Decide story breakdown (~7 stories per spec: schema, benchmark auto-seed, MA/BB/RSI/ATR/Volume MA compute, MRSI compute, sync endpoint wiring, read endpoint, smoke test)

## Up next (after Epic D ships)

**Epic G — Sell Signals on Holdings** — 11 signal types (FR-G1..FR-G11) with traffic-light Signals column on Positions tab.

## Recently shipped

- **Epic C — Foundation** — `[STORY-C-1..8]` + bug fix. Tailwind+shadcn, tracked_universe, market_data ingestion, S&P 500 + CAC 40 seeders. Live smoke: 552 universe symbols, 3276 OHLCV rows for 14 IBKR positions.
- **Epic B — UX Polish** — `[STORY-B-1..3]` — tab restructure, staleness badge, sync progress strip, filter toolbars
- **Epic A — Sync Pipeline Restructure** — `[SYNC-1..14]` — `/api/sync/*` 4-step pipeline + orchestrator

## Blockers

None.

## Decisions awaiting user

None — all design decisions logged in `docs/plans/ROADMAP.md` Decision Log + epic specs.
