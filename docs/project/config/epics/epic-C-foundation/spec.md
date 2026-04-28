# Epic C — Foundation: Universe + Market Data + Design System

**Status:** [→] Plan ready, not started
**Plan:** [docs/plans/2026-04-28-story-c-foundation.md](../../../../plans/2026-04-28-story-c-foundation.md)
**Stories:** 9

## Goal

Lay the data + design system foundation that every subsequent epic depends on. Three subsystems shipped together because they're all pre-requisites for indicators (D), sell signals (G), security detail (H), and tech analysis (E/F).

## What this epic delivers

### Subsystem 1 — Design system

- Tailwind v4 + shadcn/ui installed
- `app/globals.css` migrated to Tailwind v4 (`@import "tailwindcss"` + `@theme inline` design tokens)
- Initial shadcn components: Button, Card, Input, Label, Badge, Table, Dialog, Tabs, Select, Switch, Sonner
- `lib/utils.ts` `cn()` helper, `components.json` config
- Light mode default; neutral baseColor; tabular numerals utility

### Subsystem 2 — Universe management

- `tracked_universe` table with JSON `sources` column allowing same symbol to belong to multiple lists
- `tracked_indices` table (sp500/cac40/nasdaq100/dow30/dax40/ftse100); enabled flag + symbol_count + last_refreshed_at
- Universe CRUD endpoints:
  - `GET /api/universe` — list enabled symbols
  - `POST /api/universe/manual` — add manual ticker
  - `DELETE /api/universe/manual/{symbol}` — remove (drops 'manual' source; deletes row if no other source)
  - `GET /api/universe/indices` — list indices with enabled flag
  - `POST /api/universe/indices/{name}/toggle` — flip enabled
  - `POST /api/universe/indices/{name}/refresh` — re-scrape Wikipedia and upsert members
- Wikipedia seeders for **S&P 500** (`^GSPC` benchmark, USD currency) and **CAC 40** (`^FCHI` benchmark, EUR currency). Other indices listed but seeders unimplemented in Story C.
- IBKR positions auto-sync into universe with source `ibkr_position`. Sold positions un-tag, row deleted if no other source.

### Subsystem 3 — Market data ingestion

- `market_data` table (symbol, time, OHLCV, adj_close); composite PK `(symbol, time)`
- Batched yfinance ingestor (50-symbol batches with threads, idempotent via `INSERT OR IGNORE`)
- Per-symbol incremental: only fetches bars since latest stored `time`
- New first-time symbols pull last 365 days
- `POST /api/sync/market-data` step
- `GET /api/market-data/{symbol}` read endpoint with optional `date_from` / `date_to` / `limit`

### Subsystem 4 — UI

- Configuration tab (formerly "Load") gets a new shadcn-styled "Tracked Universe" card:
  - Index toggle list with refresh button per index
  - Manual ticker input (Add) + badge list with remove (×)
- Configuration tab gets a "Market Data" card with sync button

## In scope

- Everything above
- 1 live smoke test against real Wikipedia + yfinance + IBKR

## Out of scope

- Indicator computation → Epic D
- Detection (breakouts, S/R) → Epics E, F
- Security detail modal → Epic H
- Other index seeders (NASDAQ-100, DOW, DAX, FTSE) — UI lists them but seeder code not written
- Per-step manual buttons on every tab — only top-level Sync IBKR button + Configuration manual sync

## Stories

| ID | Title | Files touched |
|---|---|---|
| **C-1** | Install Tailwind v4 + shadcn/ui design system | `frontend/app/globals.css`, `frontend/components.json`, `frontend/lib/utils.ts`, `frontend/postcss.config.mjs`, `frontend/components/ui/*` |
| **C-2** | Schema: `tracked_universe`, `tracked_indices`, `market_data` tables | `backend/database/schema.sql` + apply to live DB |
| **C-3** | Universe CRUD endpoints | `backend/api/routes/universe.py`, `backend/api/main.py` |
| **C-4** | S&P 500 + CAC 40 seeders + refresh endpoint | `backend/scripts/universe_seeders.py`, `backend/api/routes/universe.py` |
| **C-5** | IBKR positions auto-sync into universe | `backend/api/routes/sync.py` (helper `_sync_positions_to_universe`) |
| **C-6** | yfinance batched market data ingestor | `backend/scripts/market_data_ingestor.py` |
| **C-7** | `/api/sync/market-data` + `GET /api/market-data/{symbol}` | `backend/api/routes/market_data.py`, `backend/api/routes/sync.py` |
| **C-8** | Configuration tab Universe section (shadcn UI) | `frontend/app/page.tsx` |
| **C-9** | End-to-end smoke test against real data | manual + build-log update |

## Acceptance criteria

- [ ] Tailwind v4 + shadcn/ui rendering correctly; sample shadcn component (Button) visible in app
- [ ] `tracked_universe` populated with at least: S&P 500 + IBKR positions
- [ ] Manual tickers add/remove works, persists across index refreshes
- [ ] `market_data` populated for all enabled symbols (one full year of bars)
- [ ] `/api/sync/full` is non-breaking (existing 4 steps + new market-data step or run separately)
- [ ] Configuration tab UI shadcn-styled, no inline styles in new sections
- [ ] All 13 backend tests pass (10 existing + 3+ new for universe/market-data)
- [ ] Frontend `npx tsc --noEmit` clean (no new errors)
- [ ] Live smoke test: refresh sp500 from Wikipedia, run market-data sync against held positions, verify counts in DB

## Dependencies

None — first foundational story.

## Risks

| Risk | Mitigation |
|---|---|
| Wikipedia table layout for S&P 500 / CAC 40 changes | Seeders use `pd.read_html` + tolerant column matching (`Symbol` or `Ticker`); test with real fetch in Task 4 |
| yfinance rate-limits on 600+ symbol batch | 50-symbol batches with `threads=True`; failures logged per batch, others continue |
| Existing inline-styled `page.tsx` (2200 lines) hard to inject shadcn into without full refactor | New section only; don't touch existing tabs in this story |

## Reference

- Existing tradingoff scripts: `Claude/tradingoff/scripts/techanal/b_grab_histo_data_up.py`
- Index sources: Wikipedia `List_of_S%26P_500_companies` and `CAC_40` pages
