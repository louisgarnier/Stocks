# Roadmap

Single source of truth for what's done, in flight, and queued. Each story has its own plan file in `docs/plans/`. Specs live below — design intent is captured here even before the implementation plan is written.

---

## Shipped

| Epic | Commits | Highlights |
|---|---|---|
| **A — Sync pipeline restructure** | `c6386de..3d8b6a8` (SYNC-1..14) | Drop reconciliation, build `/api/sync/*` 4-step pipeline + `/api/sync/full` orchestrator, fix import_logs writes, fix timezone handling |
| **B — UX polish** | `212f1c6`, `09605e4`, `9fa1d56` (STORY-B-1..3) | Tab restructure (3 top-level + sub-tabs), staleness badge, sync progress strip, visible filter toolbars on all 3 Transactions sub-tabs |

---

## Queued (in priority order)

| # | Epic | Plan file | Spec |
|---|---|---|---|
| ✅ | **C — Foundation: Universe + Market Data + Design System** | `2026-04-28-story-c-foundation.md` | [§ Story C](#story-c--foundation) |
| ✅ | **D — Indicators** | `2026-04-28-story-d-indicators.md` | [§ Story D](#story-d--indicators) |
| 1 | **H — Security Detail View popup** | not yet | [§ Story H](#story-h--security-detail-view) |
| 2 | **G — Sell signals on holdings** | not yet | [§ Story G](#story-g--sell-signals-on-holdings) |
| 3 | **E — Tech Analysis tab v1** | not yet | [§ Story E](#story-e--tech-analysis-tab-v1) |
| 4 | **F — Options S/R + polish** | not yet | [§ Story F](#story-f--options-based-sr--polish) |

> **Reordering note (2026-04-29):** H moved ahead of G. Building more detection layers without an inspector to verify them is flying blind. Epic H gives every symbol a click-to-inspect view that validates D's indicators (and every future epic's data) per-symbol.

---

## Story specs

These are the design-intent specs for each queued story. The implementation plan (in `docs/plans/`) gets written from this when the story is up next.

### Story C — Foundation

**Goal:** Lay the data + design system foundation that everything else builds on. Plan written: `docs/plans/2026-04-28-story-c-foundation.md`.

**In scope:**
- Tailwind v4 + shadcn/ui design system installed; first shadcn-styled UI section in the Configuration tab
- `tracked_universe` table (symbol, name, sector, currency, exchange, benchmark, sources JSON array, enabled, added_at, last_synced_at)
- `tracked_indices` table (name, enabled, last_refreshed_at, symbol_count) — seeded with sp500/cac40/nasdaq100/dow30/dax40/ftse100
- `market_data` table (symbol, time, OHLCV, adj_close) with composite PK (symbol, time)
- Universe CRUD endpoints: `GET /api/universe`, `POST/DELETE /api/universe/manual/{symbol}`, `GET /api/universe/indices`, `POST /api/universe/indices/{name}/toggle`, `POST /api/universe/indices/{name}/refresh`
- S&P 500 + CAC 40 seeders via `pd.read_html` from Wikipedia (other indices are listed but unimplemented seeders for now)
- IBKR positions auto-sync into `tracked_universe` (source: `ibkr_position`); sold positions have the source removed; row deleted if no other source remains
- yfinance batched market data ingestor (port of `b_grab_histo_data_up.py`, 50-symbol batches with threads, idempotent via `INSERT OR IGNORE`)
- `/api/sync/market-data` endpoint + `GET /api/market-data/{symbol}`
- Configuration tab "Tracked Universe" section: index toggles + per-index refresh button + custom-ticker input + manual ticker badge list
- Configuration tab "Market Data" card with sync button

**Out of scope (deferred to D):** indicator computation. Story C just gets the OHLCV bars; Story D layers indicators on top.

**Universe seeding strategy:** S&P 500 + CAC 40 + IBKR positions + manual = ~560 unique symbols default. Other indices (NASDAQ-100, DOW30, DAX 40, FTSE 100) are listed as toggles but seeder code is unimplemented; user can enable later when they want the symbols.

**Dependencies:** none (first foundational story).

---

### Story D — Indicators

**Goal:** Compute the technical indicators we'll use everywhere downstream (sell signals, breakout detection, security detail checklist).

**In scope:**
- New `indicators` table or per-indicator tables — TBD when plan written. Likely: `(symbol, time, ma_50, ma_100, ma_150, ma_200, bb_upper_20, bb_lower_20, rsi_14, mrsi, atr_14, volume_ma_20)` — one row per (symbol, date)
- **Moving Averages: MA 50, MA 100, MA 150, MA 200** — `close.rolling(N).mean()`. Port + extend `c_mma.py` from tradingoff.
- **Bollinger Bands (20, 2):** `MA(close, 20) ± 2 * stddev(close, 20)`. Both upper and lower stored.
- **RSI(14):** standard 14-period RSI via pandas-ta or hand-rolled. Range 0-100.
- **MRSI — Mansfield Relative Strength** (NOT regular RSI):
  - Formula: `RS = stock_close / benchmark_close`; `RS_MA = MA(RS, 252)` (52 weeks ≈ 252 trading days); `MRSI = ((RS / RS_MA) - 1) * 100`
  - Centered around 0: positive = outperforming benchmark, negative = underperforming
  - Benchmark per symbol = `tracked_universe.benchmark` (e.g. `^GSPC` for US, `^FCHI` for FR). Set when symbol is seeded.
  - **Pre-req:** benchmark symbols (`^GSPC`, `^FCHI`, `^GDAXI`, `^FTSE`) must themselves be in `tracked_universe` with market data ingested. Story D adds this auto-seed.
- **ATR(14):** Average True Range, 14-period. Used for stop-loss placement and signal context.
- **Volume MA(20):** 20-day average volume — used for "above-avg volume" comparisons throughout.

**Computation:** incremental — only process symbols where the latest indicator date < latest market_data date. Reuse the same monkeypatch-friendly indirection pattern as `_yf_download` in Story C so tests can stub.

**Endpoints:**
- `POST /api/sync/indicators` — recompute incrementally for all enabled symbols
- `GET /api/indicators/{symbol}` — return latest indicator row(s) for a symbol
- Wired into `/api/sync/full` orchestrator as a step after market-data sync

**Out of scope:** advanced indicators (MACD, Stochastic, etc.) — add later only if we need them for a specific signal.

**Dependencies:** Story C (needs `tracked_universe` + `market_data`).

---

### Story G — Sell signals on holdings

**Goal:** When you click into the Positions tab, you can see at a glance which of your holdings are flashing technical exit signals.

**In scope:**
- New `holding_signals` table: `(symbol, signal_type, fired, value, threshold, last_evaluated_at)` — one row per (symbol, signal_type)
- Signal library — each toggleable per user (settings in a future Configuration sub-section):
  | Signal type | Trigger |
  |---|---|
  | `ma50_break` | Latest close < MA50 |
  | `ma100_break` | Latest close < MA100 |
  | `ma150_break` | Latest close < MA150 |
  | `ma200_break` | Latest close < MA200 |
  | `death_cross` | MA50 crosses below MA150 today |
  | `volume_dryup` | 5-day avg volume < 50% of 20-day avg |
  | `distribution_day` | Down day with volume > 1.5× 20-day avg |
  | `rsi_weakness` | RSI(14) drops below 50 from above |
  | `mrsi_flip` | MRSI crosses below 0 (was ≥ 0 yesterday) |
  | `trailing_drawdown` | Latest close down X% from 30-day high (configurable, default 10%) |
  | `stop_loss` | Latest close down Y% from `cost_basis_price` (configurable, default 8%) |
- `POST /api/sync/holding-signals` — recompute for every symbol in `positions_ibkr`. Wired into `/api/sync/full` after indicators.
- `GET /api/holding-signals` — return all current signals
- Positions tab UI:
  - New "Signals" column with traffic light: 🟢 (none fired) / 🟡 (1-2 fired) / 🔴 (3+ fired)
  - Click row → expanded panel listing fired signals with current value vs threshold
  - Per-signal mute toggle (global) and per-position mute (later)

**Out of scope:**
- Buy signals (those live in Story H Mode B — for non-held symbols)
- Email/push notifications when signals fire — manual check-in for now
- Backtesting signal accuracy — future module

**Dependencies:** Story C (needs market_data), Story D (needs MA / RSI / MRSI / volume MA).

---

### Story H — Security Detail View

**Goal:** Universal modal/side-panel that opens when clicking any symbol anywhere in the app. Adapts based on whether you hold the security.

**Trigger:** click symbol in Positions tab, Transactions tab, Tech Analysis screener results, etc.

**Mode A — Held position:**
- Mini price chart (last 6-12 months) with overlays: MA50/100/150/200, BB bands, your buy/sell markers as dots on the chart
- Position summary: quantity held, avg cost (`cost_basis_price`), market value (`position_value`), unrealized P&L (`unrealized_pnl`)
- Transaction history: filtered list of `transactions` rows for this symbol with date / qty / price / side
- **Sell simulator:**
  - Inputs: quantity to sell (defaults to all), target sell price (or "current market")
  - Output: gross realized P&L = `qty * (sell_price - cost_basis_price)`, fees-adjusted P&L (estimate), remaining position, % return
  - **v1 limitation: uses weighted avg cost basis (`cost_basis_price`).** Lot-level FIFO simulation requires the FIFO module (parked). Document the limitation in the modal.
- Sell signal checklist (from Story G): each signal as a card with ✅/❌ + current value vs threshold
  - Example: "Price > MA50: ✅ ($145.20 vs MA50 $138.40)" / "Volume above 20-day avg: ❌ (5d avg 1.2M vs 20d avg 2.1M)"

**Mode B — Not held:**
- Same mini price chart with MA overlays
- **Buy signal checklist** — entry-side flip of the indicator framework:
  - Price > MA150 (long-term uptrend): ✅/❌
  - MA50 sloping up (short-term trend): ✅/❌
  - Above breakout zone resistance (when Story E ships): ✅/❌
  - MRSI > 0 (outperforming benchmark): ✅/❌
  - RSI(14) in 40-65 (not overbought, not oversold): ✅/❌
  - Volume picking up: ✅/❌
- Quick stats card: market cap, sector, currency, 52-week range, distance from MA200 %
- Optional "Add to manual universe" button if not yet tracked

**Common to both modes:**
- All checks are independent toggleable cards. Future fundamental indicators (P/E vs sector, ROE vs sector, etc.) slot in as additional cards alongside technical ones.
- Modal closes via X / ESC / click-outside
- "Open in Tech Analysis" button → navigates to dedicated full-page view (uses analyze_lmt_patterns.py port)

**Implementation notes:**
- shadcn `<Dialog>` or `<Sheet>` (right-side slide-in panel — fits more info)
- Recharts for mini chart in v1; lightweight-charts for the dedicated full page in Story E/F
- New endpoint `GET /api/security/{symbol}/detail` returns all data for the modal in one call (positions row if held, transactions, indicators, signals)

**Out of scope:**
- FIFO-based sell simulation (parked)
- Fundamental indicator cards (separate future epic)
- Real-time price streaming during the modal session — uses last sync data

**Dependencies:** Story C (universe + market_data), Story D (indicators), Story G (sell signals for Mode A).

---

### Story E — Tech Analysis tab v1

**Goal:** A new top-level "Tech Analysis" tab where you screen the broad universe for trading signals — breakouts, consolidations, key S/R levels.

**In scope:**

**Pattern detection — TWO distinct breakout signals:**

| Signal | Trigger | Logic source |
|---|---|---|
| **Range Breakout** | Price breaks above ZigZag-defined consolidation zone with volume confirmation | Port of `d_breakout_detector_3.py` |
| **Trend Breakout** | Price > MA150 **AND** MA50 sloping up **AND** Price > MA50 **AND** volume > 1.5× 20-day avg | New, user-specified Stan-Weinstein-style |

Both write to a new `breakout_signals` table with a `signal_type` column (`range` / `trend`).

**Consolidation detection:**

| Pattern | Logic |
|---|---|
| **ZigZag consolidation** | Port `g_consolidation.py` — multi-timeframe (15d/30d/60d) ZigZag-based S/R + quality score |
| **Bollinger Band Squeeze** | BB width = (upper - lower)/MA20; flag when at multi-month low (e.g., lowest in 6 months). Different signal from ZigZag — volatility-based, not zone-based. |

**NR7 and VCP punted** to a future story per user preference (BB Squeeze is the highest-value addition in v1).

Both write to `consolidation_patterns` table with a `pattern_type` column.

**Support & Resistance — technical method (options method is Story F):**
- New `support_resistance` table with `method` column
- Methods stored as separate rows so UI can layer/toggle:
  - `zigzag_swing` — ZigZag-detected swing high/low zones (already from breakout/consolidation logic)
  - `ma` — dynamic levels at MA50/100/150/200
  - `round_number` — psychological levels at $50/$100/$150/etc. relative to current price
  - `volume_profile` — historical price levels with most trading volume (proxy for "where pain lives")

**Tech Analysis tab UI (shadcn-styled):**
- Top: filter bar (universe scope: all enabled / S&P 500 / CAC 40 / held only / manual; signal type multi-select)
- Tab section: "Breakouts" | "Consolidations" | "All signals"
- Each row = one symbol-signal hit, with: symbol (clickable → opens Story H modal), signal type, fired date, current price, key metric (zone touched, BB width %, etc), confidence/quality score
- Sort by: most recent / highest quality / symbol
- Row click → opens Story H Security Detail View

**Endpoints:**
- `POST /api/sync/breakouts` — run both range + trend detectors
- `POST /api/sync/consolidations` — run ZigZag + BB squeeze
- `POST /api/sync/support-resistance` — compute technical S/R for all enabled symbols
- `GET /api/tech-analysis/breakouts?signal_type=&date_from=...`
- `GET /api/tech-analysis/consolidations?...`
- `GET /api/tech-analysis/support-resistance/{symbol}`
- All wired into `/api/sync/full` orchestrator

**Drill-down view:** when user clicks "Open in Tech Analysis" from Story H modal → dedicated `/tech-analysis/{symbol}` route shows full chart with zones, swings, all detected patterns. Uses lightweight-charts for full-screen interactive chart. Port of `analyze_lmt_patterns.py` for the underlying detection.

**Configurable parameters** (settings sub-page in Configuration):
- ZigZag deviation (default 5%)
- Min consolidation days (default 10)
- Volume confirmation multiplier (default 1.5×)
- Volume lookback days (default 20)
- BB squeeze lookback (default 6 months)

**Dependencies:** Story C, Story D (indicators), Story H (clicks need somewhere to land).

**Out of scope:**
- Options-based S/R → Story F
- NR7 / VCP / wedges / cup-and-handle / flags → future
- Backtesting historical signal accuracy → future
- Auto-alerts when signals fire → future

---

### Story F — Options-based S/R + polish

**Goal:** Add the second method of S/R detection — what market makers actually defend, based on options open interest. Plus chart polish on the Tech Analysis tab.

**In scope:**

**Options data ingestion:**
- yfinance: `Ticker.option_chain(expiry)` returns calls + puts with `strike`, `openInterest`, `volume`, `impliedVolatility`
- New `options_snapshots` table: `(symbol, expiry, snapshot_at, strike, type, open_interest, volume, iv)` — one row per strike per expiry per snapshot
- Snapshot is current state only — yfinance doesn't provide historical chains (caveat: backtesting chain-based signals not possible without paid feed)
- Refresh frequency: nightly via `/api/sync/options` (manual button + part of `/api/sync/full`)

**Options S/R computation:**
- Add to `support_resistance` table with new methods:
  - `options_max_pain` — strike where total option intrinsic value is min for the nearest expiry. Magnet level near expiration.
  - `options_call_wall` — top N call OI strikes per expiry → resistance
  - `options_put_wall` — top N put OI strikes per expiry → support
- Per-expiry granularity: monthly + nearest weekly

**UI:**
- Tech Analysis chart layers: toggle technical S/R / options S/R / both
- Comparison highlight: where technical and options S/R agree → high-confidence zone (visual emphasis)
- Per-symbol detail page: list options walls per expiry, max pain by expiry table

**Polish:**
- Migrate Tech Analysis tab v1 chart from Recharts → lightweight-charts (TradingView-style) for the full-screen view
- Annotate breakout/consolidation zones on the chart
- Add "show technical S/R" / "show options S/R" / "show both" toggle layers
- Persist user's filter+chart preferences to localStorage

**Caveats acknowledged in UI:**
- Options data is delayed (yfinance free); show "Last refreshed Xh ago" prominently
- Liquid US names only — international names (CAC 40) often have thin/no options data on yfinance. Show "no options data" gracefully.

**Endpoints:**
- `POST /api/sync/options` — ingest current chains for all enabled symbols (with options data available)
- `GET /api/options/{symbol}/walls?expiry=` — call/put wall list
- `GET /api/options/{symbol}/max-pain?expiry=` — max pain per expiry

**Dependencies:** Story E (Tech Analysis tab exists), Story D (indicators for chart overlays).

**Out of scope:**
- Gamma exposure / GEX calculation (deeper math, future)
- Historical options data (requires paid feed)
- Greeks calculations (delta/gamma/vega per strike)

---

## Future (parked, no plan)

- **FIFO module** — lot-level cost basis tracking. Reads from `transactions_adjusted` view (split-adjusted lots). Upgrades the Story H sell simulator from avg-cost to lot-aware (FIFO/LIFO). Standalone module that can be added without breaking other stories.
- **Fundamental Analysis tab** — port `Automated-Fundamental-Analysis` (https://github.com/louisgarnier/Automated-Fundamental-Analysis) methodology: per-sector outlier-trimmed avgs, ±std/3 grade buckets, A+→F letter grades. **Swap data source from finviz scraping (fragile) to yfinance** — `Ticker.info` covers ~80% of the 32 metrics; `Ticker.financials` covers the rest. Adds fundamental cards to Story H modal checklist.
- **Watchlist tab** — saved screens / candidate tracking; integrates with Story H via "Add to watchlist" button.
- **Auto-scheduling** — cron-style runs of `/api/sync/full` (originally Phase 5). Once the manual flow is stable, schedule daily at market close.
- **Migrate existing tabs (Positions/Transactions) to shadcn/ui** — done as touched in later stories, no dedicated story.
- **Historical positions snapshots** — `positions_ibkr_history` table keyed by sync date for time-series of holdings (P&L over time chart).
- **M — Migrate to Supabase** — plan written but parked due to cost/dependency concerns. See `docs/plans/2026-04-28-story-m-supabase-migration.md` if reconsidering.

---

## Decision log

- **2026-04-27** — Drop reconciliation. Both `positions_ibkr` and `transactions` come from the same Flex response so they're inherently consistent; recon was catching nothing real.
- **2026-04-27** — Keep split-adjustment chain (`updated_transactions`, `corporate_actions`) because future FIFO module depends on split-adjusted lots.
- **2026-04-28** — Light mode default. Tailwind v4 + shadcn/ui as design system foundation. Recharts for mini charts, lightweight-charts (TradingView's library) for the full-page Tech Analysis chart in F.
- **2026-04-28** — MRSI = Mansfield Relative Strength (NOT regular RSI). Stock vs benchmark relative strength, normalized via 252-day MA, centered at 0. Per-symbol benchmark assigned at universe seed time.
- **2026-04-28** — Two breakout signals (NOT one): Range Breakout (existing ZigZag-based) + Trend Breakout (price>MA150 + MA50↑ + price>MA50 + high vol). Distinct signals, distinct rows in `breakout_signals`.
- **2026-04-28** — Build BOTH S/R methods: technical (Story E: swing/MA/round/volume profile) + options-based (Story F: max pain + call/put walls via yfinance). Stored side-by-side with a `method` column so UI can compare; agreement = high-confidence zone.
- **2026-04-28** — Universe scope: S&P 500 + CAC 40 + benchmarks + IBKR positions + manual additions. Other indices (NASDAQ-100, DOW, DAX, FTSE) listed as toggles but seeders unimplemented in Story C.
- **2026-04-28** — Manual ticker placeholder: `sources` JSON column allows the same symbol to belong to multiple sources (e.g., AAPL is both `sp500` AND `manual`). Removing one source doesn't delete the row if others remain.
- **2026-04-28** — BB Squeeze yes (volatility-based companion to ZigZag's price-zone-based detection). NR7 + VCP punted to future.
- **2026-04-28** — Cost-basis reconciliation rejected — user is position-tracking, not cost-analyzing; IBKR's `cost_basis_money` is authoritative.
- **2026-04-28** — Forex transactions (`%.%` symbols) intentionally excluded from `transactions_adjusted` view — they're FX conversions, not stock holdings.
- **2026-04-28** — Sell simulator in Story H uses weighted-avg cost basis in v1; FIFO upgrade comes when FIFO module ships.
- **2026-04-28** — Considered Supabase migration; **rejected** for cost/dependency concerns. Staying on local SQLite. Plan kept in `docs/plans/` if reconsidering later.
