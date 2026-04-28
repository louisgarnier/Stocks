# Roadmap

Single source of truth for what's done, in flight, and queued. Each story has its own plan file in `docs/plans/`.

## Shipped

| Epic | Commits | Highlights |
|---|---|---|
| **A — Sync pipeline restructure** | `c6386de..3d8b6a8` (SYNC-1..14) | Drop reconciliation, build `/api/sync/*` 4-step pipeline + `/api/sync/full` orchestrator, fix import_logs writes, fix timezone handling |
| **B — UX polish** | `212f1c6`, `09605e4`, `9fa1d56` (STORY-B-1..3) | Tab restructure (3 top-level + sub-tabs), staleness badge, sync progress strip, visible filter toolbars on all 3 Transactions sub-tabs |

## Queued (in priority order)

| # | Epic | Plan file | Status |
|---|---|---|---|
| 1 | **M — Migrate to Supabase** | `docs/plans/2026-04-28-story-m-supabase-migration.md` | 📋 plan ready |
| 2 | **C — Foundation: Universe + Market Data + Design System** | `docs/plans/2026-04-28-story-c-foundation.md` | 📋 plan ready (built on Postgres post-M) |
| 3 | **D — Indicators** | not yet planned | MA/BB/RSI/MRSI/ATR/Volume MA — once C ships |
| 4 | **G — Sell signals on holdings** | not yet planned | Positions tab Signals column — depends on D |
| 5 | **H — Security Detail View popup** | not yet planned | Click any symbol → modal w/ chart + transactions + sell sim + signal checklist |
| 6 | **E — Tech Analysis tab v1** | not yet planned | Range/Trend Breakouts + Consolidation + technical S/R |
| 7 | **F — Options S/R + polish** | not yet planned | yfinance options chain → max pain + call/put walls |

## Future (parked, no plan)

- **FIFO module** — lot-level cost basis tracking. Upgrades the sell simulator from avg-cost to lot-aware.
- **Fundamental Analysis tab** — port `Automated-Fundamental-Analysis` methodology, swap data source from finviz to yfinance.
- **Watchlist tab** — saved screens / candidate tracking.
- **Auto-scheduling** — cron-style runs of `/api/sync/full` (originally Phase 5).
- **Migrate existing tabs (Positions/Transactions) to shadcn/ui** — done as touched in later stories, no dedicated story.
- **Historical positions snapshots** — `positions_ibkr_history` table for time-series of holdings (P&L over time chart).

## Decision log

- **2026-04-27** — Drop reconciliation. Both `positions_ibkr` and `transactions` come from the same Flex response so they're inherently consistent; recon was catching nothing real. ([review.md](../project/config/review.md) F1.6 superseded.)
- **2026-04-27** — Keep split-adjustment chain (`updated_transactions`, `corporate_actions`) because future FIFO module depends on split-adjusted lots.
- **2026-04-28** — Light mode default. Tailwind v4 + shadcn/ui as design system foundation.
- **2026-04-28** — MRSI = Mansfield Relative Strength (NOT regular RSI). Stock vs benchmark relative strength, normalized via 252-day MA.
- **2026-04-28** — Two breakout signals (NOT one): Range Breakout (existing ZigZag-based) + Trend Breakout (price>MA150 + MA50↑ + price>MA50 + high vol).
- **2026-04-28** — Build BOTH S/R methods: technical (swing/MA/round/volume profile) + options-based (max pain + call/put walls via yfinance).
- **2026-04-28** — Migrate to Supabase BEFORE Story C. Smaller migration surface (7 tables vs 17+), establishes pattern early, all future stories build on the right foundation.
