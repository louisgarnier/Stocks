# Product Requirements — IBKR Portfolio Tracker

> Stage 2 output. Source-of-truth for goals, users, and requirements.
> Status: **Locked** (2026-04-28). Amendments dated at the bottom.

---

## 1. Project Summary

| Field | Value |
|---|---|
| **Project name** | Stocks (IBKR Portfolio Tracker) |
| **One-liner** | A local-first FastAPI + Next.js app that tracks an IBKR portfolio and surfaces technical analysis signals (breakouts, sell triggers, S/R levels) for the holdings + a configurable universe. |
| **Owner** | Louis Garnier |
| **Target completion** | All 8 epics by mid-2026-Q3 (no fixed deadline; ships story-by-story) |
| **Tech stack** | FastAPI + Python 3.10 + SQLite + yfinance + pandas (backend); Next.js 16 + React 19 + Tailwind v4 + shadcn/ui + Recharts + lightweight-charts (frontend) |

---

## 2. Goals

### Primary goals

1. **Single source of truth for the portfolio.** IBKR positions + transactions + corporate actions + applied splits, all synced and consistent, accessible at a glance.
2. **Sell-signal awareness on holdings.** Surface technical exit signals (MA breaks, volume dryup, MRSI flip, etc.) on the Positions tab so no holding silently breaks down without noticing.
3. **Universal security drill-down.** Click any symbol anywhere → modal with chart + history + sell simulator (held) or buy-signal checklist (not held). Same UX for everything.
4. **Tech-Analysis screener for the broader universe.** Range/Trend breakouts, consolidation patterns, technical + options-based S/R.
5. **Local-first, no cloud commitment.** Single SQLite file, run on demand on the user's Mac. No accounts, no subscriptions.

### Anti-goals (explicitly out of scope)

- Multi-user / sharing / collaboration
- Real-time price streaming (snapshot data is enough)
- Order execution / placing trades from within the app
- Tax / accounting reports
- Mobile app (web on desktop is sufficient)

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| **US-01** | solo investor | one-click sync IBKR data | I always see today's holdings and trades without manual upload |
| **US-02** | position holder | see at a glance which of my holdings are flashing exit signals | I can act on weak positions before they break down further |
| **US-03** | trader | click any symbol and see a unified detail view | I don't context-switch between IBKR/TradingView/spreadsheets |
| **US-04** | trader holding a stock | simulate a sell at a specific quantity and price | I know the realized P&L before I click sell at IBKR |
| **US-05** | trader scanning for opportunities | filter the broader universe by breakout/consolidation signals | I find candidates without manually screening hundreds of charts |
| **US-06** | technical analyst | see both swing-based and options-based S/R on the same chart | I can confirm levels via two independent methods |
| **US-07** | trader using relative strength | see MRSI (Mansfield) for each holding vs its benchmark | I know which positions are leading vs lagging the market |
| **US-08** | user managing the universe | toggle which indices to track and add custom tickers | I'm not stuck with a hardcoded watchlist |
| **US-09** | future: tax-aware trader | see FIFO-matched lot P&L on the sell simulator | I know which tax lots I'm closing |
| **US-10** | future: fundamental investor | see fundamental grades vs sector for any symbol | I confirm technicals match underlying business quality |

US-09 and US-10 are documented for completeness but parked (FIFO module + Fundamental Analysis epic in Future).

---

## 4. Functional Requirements

### Already shipped (Epics A + B)

| ID | Requirement |
|---|---|
| **FR-A1** | One-click `/api/sync/full` orchestrator runs 4 steps (positions / transactions / corporate-actions / splits) sharing a single Flex Query response between positions and transactions |
| **FR-A2** | Each pipeline step is independently runnable via `/api/sync/<step>` |
| **FR-A3** | `import_logs` table records each sync with timezone-aware timestamps |
| **FR-A4** | Reconciliation feature dropped — positions and transactions are both sourced from IBKR Flex and trusted |
| **FR-B1** | Three top-level tabs (Positions / Transactions / Configuration); Transactions has 3 sub-tabs (Original / Split-Adjusted / Corporate Actions) |
| **FR-B2** | Header staleness badge (green <6h, amber <24h, red >24h since last sync) |
| **FR-B3** | Per-step sync progress strip (4 cards lighting ✅/❌ during sync, auto-hide 5s after) |
| **FR-B4** | Always-visible filter toolbar on each Transactions sub-tab (Symbol / Date from / Date to / Side or CA Type) |

### Foundation (Epic C — queued)

| ID | Requirement |
|---|---|
| **FR-C1** | Tailwind v4 + shadcn/ui design system installed; new UI built with components, existing UI migrates as touched |
| **FR-C2** | `tracked_universe` table with JSON `sources` column allowing same symbol to belong to multiple lists (sp500 + ibkr_position + manual) |
| **FR-C3** | Universe seeders for S&P 500 + CAC 40 from Wikipedia (other indices listed as toggles, seeders unimplemented) |
| **FR-C4** | IBKR positions auto-tag into universe with source `ibkr_position`; sold positions un-tag and delete row if no other source |
| **FR-C5** | Manual ticker add/remove (source `manual`) persists across index refreshes |
| **FR-C6** | `market_data` table (PK on symbol+time) populated by yfinance batched download (50-symbol batches, threads, idempotent) |
| **FR-C7** | Configuration tab "Tracked Universe" + "Market Data" sections, shadcn-styled |

### Indicators (Epic D — queued)

| ID | Requirement |
|---|---|
| **FR-D1** | MA 50, MA 100, MA 150, MA 200 computed incrementally per symbol |
| **FR-D2** | Bollinger Bands (period 20, std 2): upper, lower, width |
| **FR-D3** | RSI(14) — standard 14-period Relative Strength Index |
| **FR-D4** | **MRSI — Mansfield Relative Strength**: `RS = stock_close / benchmark_close`, normalized via 252-day MA, centered at 0 |
| **FR-D5** | ATR(14) — Average True Range |
| **FR-D6** | Volume MA(20) |
| **FR-D7** | Per-symbol benchmark assigned at universe seed time (`^GSPC` for US, `^FCHI` for FR, etc.); benchmark symbols themselves auto-seeded into universe |
| **FR-D8** | `/api/sync/indicators` step in orchestrator; recomputes only stale symbols |

### Sell signals on holdings (Epic G — queued)

| ID | Signal | Trigger |
|---|---|---|
| **FR-G1** | `ma50_break` | Latest close < MA50 |
| **FR-G2** | `ma100_break` | Latest close < MA100 |
| **FR-G3** | `ma150_break` | Latest close < MA150 |
| **FR-G4** | `ma200_break` | Latest close < MA200 |
| **FR-G5** | `death_cross` | MA50 crosses below MA150 today |
| **FR-G6** | `volume_dryup` | 5-day avg volume < 50% of 20-day avg |
| **FR-G7** | `distribution_day` | Down day on volume > 1.5× 20-day avg |
| **FR-G8** | `rsi_weakness` | RSI(14) drops below 50 from above |
| **FR-G9** | `mrsi_flip` | MRSI crosses below 0 (was ≥ 0 yesterday) |
| **FR-G10** | `trailing_drawdown` | Latest close down configurable % from 30-day high (default 10%) |
| **FR-G11** | `stop_loss` | Latest close down configurable % from `cost_basis_price` (default 8%) |
| **FR-G12** | Positions tab Signals column with traffic light (🟢 / 🟡 / 🔴) + click-to-expand panel |

### Security Detail View (Epic H — queued)

| ID | Requirement |
|---|---|
| **FR-H1** | Universal modal triggered by clicking any symbol anywhere |
| **FR-H2** | Mode A (held): mini chart with MAs + buy/sell markers, transaction history, sell simulator (qty + price → realized P&L using `cost_basis_price`), sell signal checklist |
| **FR-H3** | Mode B (not held): mini chart with MAs, buy signal checklist (price > MA150, MA50↑, MRSI > 0, RSI in 40-65, volume picking up), quick stats (market cap, sector, 52w range) |
| **FR-H4** | Endpoint `GET /api/security/{symbol}/detail` returns all data for the modal in one call |
| **FR-H5** | All checks rendered as independent toggleable cards (slot for future fundamental cards) |
| **FR-H6** | "Open in Tech Analysis" link in modal → dedicated full-page view |

### Tech Analysis tab v1 (Epic E — queued)

| ID | Requirement |
|---|---|
| **FR-E1** | Range Breakout detector: ZigZag-defined consolidation broken with volume confirmation (port of `d_breakout_detector_3.py`) |
| **FR-E2** | Trend Breakout detector: price > MA150 AND MA50 sloping up AND price > MA50 AND volume > 1.5× 20-day avg |
| **FR-E3** | ZigZag Consolidation detector: multi-timeframe (15d/30d/60d) with quality scoring (port of `g_consolidation.py`) |
| **FR-E4** | BB Squeeze detector: BB width at multi-month low |
| **FR-E5** | Technical S/R: zigzag swings + MA dynamic levels + round numbers + volume profile, stored with `method` column |
| **FR-E6** | Tech Analysis tab UI: filter bar (universe scope + signal type) + tab section (Breakouts / Consolidations / All) + clickable rows opening Story H modal |
| **FR-E7** | Drill-down `/tech-analysis/{symbol}` route with full chart (lightweight-charts) and analyzer output (port of `analyze_lmt_patterns.py`) |
| **FR-E8** | Configurable parameters in Configuration: ZigZag deviation, min consolidation days, volume confirmation multiplier, BB squeeze lookback |

### Options S/R + polish (Epic F — queued)

| ID | Requirement |
|---|---|
| **FR-F1** | Options chain ingestion via `Ticker.option_chain(expiry)` → `options_snapshots` table |
| **FR-F2** | Max pain calculation per expiry → `support_resistance` with method `options_max_pain` |
| **FR-F3** | Top-N call OI strikes per expiry → method `options_call_wall` (resistance) |
| **FR-F4** | Top-N put OI strikes per expiry → method `options_put_wall` (support) |
| **FR-F5** | Tech Analysis chart: toggle layers (technical / options / both); agreement zones visually emphasized |
| **FR-F6** | Caveats surfaced in UI: data delay, no historical options chains, thin coverage for non-US names |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | `/api/sync/full` completes in <30s for ~600 symbols (90% on yfinance latency). Indicator recompute incremental only — full universe shouldn't exceed 60s. |
| **Idempotency** | All ingestion endpoints idempotent — re-running a sync doesn't duplicate rows. `INSERT ... ON CONFLICT` everywhere (works in SQLite 3.24+). |
| **Test coverage** | Per-story TDD; integration tests against real DB (no DB mocks); HTTP-to-yfinance/IBKR stubbed via monkeypatch for hermeticity. |
| **Reliability** | Sync failures stop the chain at the failing step; earlier successful steps remain committed. Per-step error returned in API response. |
| **Observability** | Every sync writes a row to `import_logs` with timezone-aware timestamp. Backend log file under `logs/` (per global CLAUDE.md). |
| **Latency for UI interactions** | Click → result < 500ms for all cached data. Full sync waits acceptable; UI shows progress strip. |

---

## 6. Data Requirements

### Inputs

| Source | Data | Frequency |
|---|---|---|
| **IBKR Flex Query API** | trades + open positions snapshot (XML) | manual sync (typically daily) |
| **yfinance** | OHLCV bars per symbol | manual sync (per universe) |
| **yfinance** | corporate actions (dividends, splits) | manual sync (per affected symbol) |
| **yfinance** | options chains | manual sync (Story F) |
| **Wikipedia tables** | index constituents (S&P 500, CAC 40) | manual refresh per index |
| **User input** | manual ticker additions, signal threshold tuning | as needed |

### Persistent storage

Single SQLite file at `output/database/finance.db`. ~12 MB current; estimated ~250 MB after full universe ingestion (1.5M market_data rows + indicators + signals).

### Data retention

Indefinite. No automated archival. Manual backup is the user's responsibility (a copy of `finance.db` to a Drive folder).

---

## 7. UI / UX Requirements

| ID | Requirement |
|---|---|
| **UX-01** | Light mode default. (Dark mode optional future polish.) |
| **UX-02** | shadcn/ui components throughout new UI; consistent neutral baseColor + radius `0.5rem` |
| **UX-03** | Tabular numerals (`font-variant-numeric: tabular-nums`) on every price/percentage cell |
| **UX-04** | Color semantics: green = positive/healthy, amber = caution, red = negative/breakdown — used consistently across signals/badges/charts |
| **UX-05** | All long-running actions (sync, refresh) show progress + disabled state |
| **UX-06** | All numbers in user's local timezone with offset visible (no naive timestamps) |

---

## 8. Interfaces & Integrations

| Integration | Direction | Notes |
|---|---|---|
| **IBKR Flex Query API** | Read | XML response. Token + Query ID via `.env` (`IBKR_FLEX_TOKEN`, `IBKR_QUERY_ID_last_year/last_month`). Future: dedicated `IBKR_QUERY_ID_positions` / `IBKR_QUERY_ID_trades_*` env vars optional. |
| **yfinance (Yahoo Finance)** | Read | Free, no auth. Rate-limit-tolerant via batching. |
| **Wikipedia (pd.read_html)** | Read | Plain HTML scraping. Stable for major indices. |
| **GitHub** | Push | `git push origin newstart` — manual user trigger. |

---

## 9. Constraints

- **Solo user, single machine.** No multi-tenancy, no auth.
- **No paid data feeds in v1.** yfinance is free with rate-limits accepted.
- **Local SQLite only.** Supabase migration evaluated and parked due to cost/dependency concerns.
- **No mobile / no web hosting.** Web app, runs locally.

---

## 10. Open Questions

| Q | Resolution |
|---|---|
| Will yfinance options chain coverage be sufficient for non-US holdings (CAC 40)? | Defer to Story F implementation; if thin, surface "no options data" gracefully. |
| Should NR7 / VCP be added to consolidation detection? | Punted to future. BB Squeeze ships in v1 because it's volatility-based (different from ZigZag). NR7 is too short-horizon, VCP too noisy. |
| Will the FIFO module be needed before Story H (Security Detail) ships? | No. Story H sell simulator uses weighted-avg cost basis (`cost_basis_price`) in v1; FIFO upgrade comes when the FIFO module ships independently. |
| Should we build a watchlist tab, or is "manual tickers" sufficient? | Manual tickers in Story C cover MVP. A dedicated Watchlist tab with saved screens is parked. |

---

## 11. Definition of Done

A story is done when:
1. All acceptance criteria in its epic spec are met.
2. Per-story integration tests pass against real SQLite (`pytest backend/tests/`).
3. Frontend type-check is clean (`npx tsc --noEmit`, excluding pre-existing test-file errors).
4. Live smoke test executed against real data (yfinance / Wikipedia / IBKR).
5. `build-log.md` and `codebase.md` updated.
6. Commit messages prefixed `[STORY-<X>-<N>]`.

---

## Amendments

*(No amendments yet. Add dated entries here when locked content changes.)*
