# Active Work

> Current focus. Updated when an epic ships and the next one starts.

## Currently active

**Epic C — Foundation (Universe + Market Data + Design System)**

- **Status:** Plan ready, not started
- **Spec:** [epic-C-foundation/spec.md](epic-C-foundation/spec.md)
- **Plan:** [docs/plans/2026-04-28-story-c-foundation.md](../../../plans/2026-04-28-story-c-foundation.md)
- **Why now:** Foundational. Stories D / G / H / E / F all depend on `tracked_universe` + `market_data` + the design system.

### Next 3 stories

1. **C-1** — Install Tailwind v4 + shadcn/ui design system
2. **C-2** — Add `tracked_universe`, `tracked_indices`, `market_data` tables
3. **C-3** — Universe CRUD endpoints (`GET /api/universe`, `POST/DELETE /api/universe/manual/{symbol}`, `GET /api/universe/indices`, `POST /api/universe/indices/{name}/toggle`)

(Full 9-task list in plan.)

## Up next (after Epic C ships)

**Epic D — Indicators** — MA 50/100/150/200, BB(20,2), RSI(14), **MRSI (Mansfield)**, ATR(14), Volume MA(20). Builds on Story C's `market_data`.

## Recently shipped

- **Epic B — UX Polish** — `[STORY-B-1..3]` committed as `212f1c6`, `09605e4`, `9fa1d56`
- **Epic A — Sync Pipeline Restructure** — `[SYNC-1..14]` (historical prefix; same epic)

## Blockers

None.

## Decisions awaiting user

None — all design decisions logged in `docs/plans/ROADMAP.md` Decision Log.
