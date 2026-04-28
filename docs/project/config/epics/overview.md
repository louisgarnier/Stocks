# Epics Overview

> Top-level work breakdown. Each epic has its own folder with `spec.md` (and stories below).
> Status: `[ ] Pending` | `[→] In Progress` | `[x] Done` | `[~] Blocked` | `[ ] Parked`

| ID | Epic | Status | Stories | Focus |
|---|---|---|---|---|
| **A** | [Sync Pipeline Restructure](epic-A-sync-pipeline/spec.md) | [x] Done | 14 | `/api/sync/*` decoupled steps + orchestrator, drop reconciliation |
| **B** | [UX Polish](epic-B-ux-polish/spec.md) | [x] Done | 3 | Tab restructure, staleness badge, sync progress strip, filter toolbars |
| **C** | [Foundation: Universe + Market Data + Design System](epic-C-foundation/spec.md) | [x] Done | 9 | Tailwind+shadcn, `tracked_universe`, `market_data` ingestion |
| **D** | [Indicators](epic-D-indicators/spec.md) | [x] Done | 7 | MA / BB / RSI / **MRSI (Mansfield)** / ATR / Volume MA |
| **G** | [Sell Signals on Holdings](epic-G-sell-signals/spec.md) | [ ] Pending | TBD | Positions tab Signals column with traffic light + 11 signal types |
| **H** | [Security Detail View](epic-H-security-detail/spec.md) | [ ] Pending | TBD | Universal modal — Mode A (held: chart + tx + sell sim + signals) / Mode B (not held: chart + buy signals + stats) |
| **E** | [Tech Analysis Tab v1](epic-E-tech-analysis/spec.md) | [ ] Pending | TBD | Range + Trend Breakouts, ZigZag + BB Squeeze consolidation, technical S/R |
| **F** | [Options S/R + Polish](epic-F-options-sr/spec.md) | [ ] Pending | TBD | yfinance options chain → max pain + call/put walls, chart polish |

## Execution order

Already shipped: A, B.
Queued in priority: **C → D → G → H → E → F**.

Stories C through H ship sequentially, each builds on the previous. Story F can technically slot anywhere after E ships, but ordered last as enrichment.

## Story numbering convention

Within each epic, stories number `<EPIC>-<N>`. Commit prefixes: `[STORY-<EPIC>-<N>]`.

Examples already shipped:
- `[STORY-A-1..14]` (committed as `[SYNC-1..14]` historically — same epic)
- `[STORY-B-1..3]`

Going forward (Story C onward), commits use `[STORY-C-1]`, `[STORY-D-1]`, etc.

## Future (parked, no spec)

| Topic | Notes |
|---|---|
| **FIFO Module** | Lot-level cost basis tracking. Reads `transactions_adjusted` view. Upgrades Story H sell simulator from avg-cost to FIFO/LIFO matching. |
| **Fundamental Analysis Tab** | Port `Automated-Fundamental-Analysis` methodology, swap finviz → yfinance. Adds fundamental cards to Story H modal. |
| **Watchlist Tab** | Saved screens / candidate tracking; integrates with Story H "Add to watchlist". |
| **Auto-scheduling** | Cron-style runs of `/api/sync/full`. Once manual flow is stable. |
| **Historical positions snapshots** | `positions_ibkr_history` for time-series of holdings (P&L over time chart). |
| **Existing tab migration to shadcn/ui** | Done as touched in later stories, no dedicated epic. |
| **Supabase migration** | Plan written but parked due to cost concerns. See `docs/plans/2026-04-28-story-m-supabase-migration.md`. |

## Cross-cutting concerns

| Concern | How handled |
|---|---|
| **Tests** | Per-story TDD; integration tests in `backend/tests/`; real SQLite via `temp_db` fixture; HTTP stubbed via monkeypatch. |
| **Logging** | Per-component logger from `backend/api/utils/logger.py`. Existing emoji conventions (📥📤✅❌⚠️🗄️🚀). See `config/logging.md`. |
| **Build log** | Updated after every story in `config/build-log.md`. |
| **Codebase doc** | Updated after every story in `config/codebase.md`. |
| **Roadmap (quick-reference)** | `docs/plans/ROADMAP.md` — flat index alongside this hierarchical epic structure. |
