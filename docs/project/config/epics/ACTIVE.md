# Active Work

> Current focus. Updated when an epic ships and the next one starts.

## Currently active

**Epic H — Security Detail View**

- **Status:** [ ] Pending — plan not yet written
- **Spec:** [epic-H-security-detail/spec.md](epic-H-security-detail/spec.md)
- **Why now (re-prioritized 2026-04-29 ahead of Epic G):** every backend epic so far has put data into the database without giving the user a way to inspect it per-symbol. Epic H is the universal detail view — click any symbol anywhere → see its data. This validates Epic D's indicators (MRSI, MAs, RSI) per-symbol and gives every later epic (G, E, F) a place to surface its information. Building more detection on top of unverified data layers is flying blind.

### Plan strategy

- Strip Story H to v1: open modal, show held/not-held mode, indicator card, transactions list (held mode), basic stats (not-held mode). Skip chart + sell simulator + signal checklist for now (signal checklist needs Epic G).
- Add chart + sell simulator + signals as Epic H follow-ups OR fold into G/F as they ship.

## Up next (after Epic H ships)

**Epic G — Sell Signals on Holdings.** With Epic H in place, signals will surface both as a Positions tab Signals column AND a card inside the Security Detail modal.

## Recently shipped

- **Epic D — Indicators** — `[STORY-D-1..9]`. MA/BB/RSI/MRSI/ATR/Vol MA, indicators table, per-symbol orchestrator, sync endpoint wired into `/api/sync/full`, read endpoint, Browse Universe table, MRSI scaled to ±1 ratio range.
- **Epic C — Foundation** — `[STORY-C-1..8]` + bug fix + C-10 polish. Tailwind+shadcn, tracked_universe, market_data ingestion, S&P 500 + CAC 40 seeders.
- **Epic B — UX Polish** — tab restructure, staleness badge, sync progress strip, filter toolbars
- **Epic A — Sync Pipeline Restructure** — `/api/sync/*` 4-step pipeline + orchestrator

## Known issues / loose ends

- **Corporate-actions step in `/api/sync/full` fails** with "can't subtract offset-naive and offset-aware datetimes" — pre-existing regression from SYNC-13 timezone work. Indicators sync still works directly. Fix tracked as a follow-up.
- **Currency back-fill from positions_ibkr** — 9 of 14 IBKR holdings have NULL currency in tracked_universe (so they default to ^GSPC for MRSI, which happens to be correct for US stocks but is brittle). Small fix to `_sync_positions_to_universe` to copy currency from `positions_ibkr` row.
- **Lookback bump for MRSI history** — yfinance fetch is 365d, gives ~252 trading days. MRSI needs ≥252 days of context, so it only fires on the very last bar. Bumping default lookback to 730d would give a meaningful MRSI time series. Cheap fix in `market_data_ingestor.py`.

## Blockers

None for Epic H itself.

## Decisions awaiting user

- Build full Epic H (12 stories, charts + sell simulator) or stripped v1 (~6 stories, no chart/simulator)?
