# Screener Integration — Design Spec

- **Status:** Draft (awaiting user review)
- **Date:** 2026-07-01
- **Author:** Louis + Claude
- **Related roadmap:** Epic E (Tech Analysis) / Epic F (Options & polish) — this design *is* Epic E, built on proven legacy logic.

---

## 1. Context & Goal

The existing project is an **IBKR portfolio tracker** (FastAPI + Next.js + SQLite `finance.db`)
that ingests trades, tracks holdings, computes indicators, and fires **sell/exit signals**
on positions held. It answers *"should I sell what I hold?"*

This project adds the opposite, buy-side capability: a **stock screener** that answers
*"what should I buy?"* — a three-tier funnel:

1. **Broad analytics (all stocks):** fetch technical + fundamental analytics for a large,
   expandable universe. Cheap, runs over the whole universe.
2. **Screener (the filter):** score/rank the whole universe from those analytics to surface
   a shortlist of candidates worth investigating.
3. **Deep-dive (narrow):** for stocks that pass the screen (plus a manual watchlist), build
   richer per-stock analysis — exit strategy, risk/reward, position sizing.

Plus a **watchlist**: pin specific stocks to always score and always deep-analyze, even if
the screener never flags them.

A reference design (`STOCK_SCREENER_PIPELINE.md`) proposed a standalone parquet/file pipeline.
We **reject the file-pipeline architecture** and instead reuse the existing DB + sync
infrastructure, lifting only the genuinely-new pieces. Prior-art legacy scripts
(`d_breakout_detector_3.py`, `g_consolidation.py`, `f_watch.py`, `e_watch.py`) provide the
**exact buy-signal logic** we will port.

### Goal in one line
Broad cheap analytics → screen → narrow expensive analysis, on the existing SQLite DB,
wired as new `/api/sync/*` steps and a new Screener tab. **Data first, calibrate second.**

## 2. Non-Goals

- No parquet / file-based data layer. All persistence stays in SQLite (`finance.db`), raw SQL.
- No second yfinance fetcher that duplicates `market_data_ingestor.py` — reuse it.
- No AI/LLM in the screening logic. Pure quantitative rules.
- Options data / max-pain (Epic F) — out of scope here.
- Finalized scoring weights and filter thresholds — deliberately deferred to Phase 2 (see §9).

## 3. Locked Decisions (from brainstorming)

| # | Decision |
|---|---|
| Universe | **Indices, expandable.** Start S&P500 + CAC40 (existing `tracked_universe`); design universe as switchable index seeders (NASDAQ100, DAX, STOXX600…). |
| Fundamentals storage | **Latest snapshot, weekly refresh.** One row/symbol, overwritten with `fetched_at`. Decoupled sync step + on-demand button. |
| Signal placement | **Broad layer feeds the score.** Momentum/MA/volume/52w flags AND the base/breakout engines run nightly over the whole universe as scoring inputs. |
| Buy-signal engine | **Exact legacy logic, ported verbatim** — `g_consolidation` (base quality 0–100) + `d_breakout` (breakout event) + `f_watch` momentum. Math preserved; only I/O rewired. |
| R/R inputs | **Config setting, editable in UI.** `screener_settings` holds account_size (default PEA), risk_pct_per_trade, default stop method. R/R + sizing both computed. |
| Storage model | SQLite, raw SQL, `(symbol, time)` time-series grain — same as `indicators`. |
| Build sequencing | **Phased. Data first, then calibrate §2/§3, then deep-dive.** (see §9) |

## 4. Architecture Overview

```
        ┌───────────────── BROAD (all ~540+ symbols, nightly) ──────────────────┐
tracked_universe → market_data (exists) → indicators (exists) ─┐
   (indices,        fundamentals (NEW, weekly) ────────────────┤
   expandable)                                                 ▼
                    screen_signals (NEW, f_watch) ─┐   consolidation_patterns (NEW, g)
                    support_resistance (NEW) ──────┤   breakout_signals (NEW, d)
                                                   ▼
                                        scoring engine (NEW) → screen_scores (NEW)
                                        score_tech + score_fund + verdict + rank
                                                   │
        ┌──── NARROW (passers + watchlist, ~20) ──┴────┐
        │  trade_plans (NEW): stop · targets · R/R ·   │◄── screener results + watchlist (NEW)
        │  position sizing                             │
        └──────────────────────────────────────────────┘
                                                   │
     FRONTEND: new "Screener" tab (raw grid → calibrated list) + Watchlist
               + deep-dive in existing SecurityDetailSheet
```

Every engine is a pure, independently-testable module mirroring the existing
`indicators_compute.py` / `holding_signals_compute.py` convention. Thin route wrappers.
Each sync step logs to `sync_runs`.

## 5. Data Model (new tables)

All SQLite, raw SQL, added to `backend/database/schema.sql` + migrations. Time-series tables
use `PRIMARY KEY (symbol, <date>)` like `indicators`. Columns below are the intended shape;
final DDL lands in the implementation plan.

### 5.1 `fundamentals` (1 row/symbol, snapshot)
Snake-cased `ticker.info` fields, overwritten on refresh. `fetched_at` timestamp.
- **Identity:** symbol (PK), long_name, sector, industry, country, currency, exchange, quote_type
- **Valuation:** trailing_pe, forward_pe, price_to_book, price_to_sales, ev_to_ebitda
- **Growth:** revenue_growth, earnings_growth, earnings_quarterly_growth
- **Profitability:** gross_margins, operating_margins, profit_margins, roe, roa
- **Health:** debt_to_equity, current_ratio, quick_ratio, total_cash, total_debt, free_cashflow
- **Market:** market_cap, beta, fifty_two_week_high, fifty_two_week_low, dividend_yield, payout_ratio
- **Analyst:** recommendation_mean, recommendation_key, number_of_analyst_opinions,
  target_mean_price, target_high_price, target_low_price
- **EPS:** trailing_eps, forward_eps
- **Meta:** fetched_at, fetch_error (nullable)

### 5.2 `screen_signals` (symbol + date) — from `f_watch`
Holds only what `indicators` lacks (no duplication; scoring JOINs `indicators` for
ma_50/100/150/200, rsi_14, mrsi, atr_14, volume_ma_20, bb_*):
- momentum_5d, momentum_20d, momentum_60d, multi_factor_momentum (0.4·m5 + 0.3·m20 + 0.3·m60)
- vs_benchmark (uses `indicators.mrsi`; optional vs-SPY momentum retained for parity with f_watch)
- price_vs_ma50, above_ma50, above_ma100, above_ma150, above_ma200
- ma_cross_status (All Bullish / Mostly Bullish / … / Mixed), trend_aligned (Price>MA50>MA150 & 1–10% above MA50)
- is_8d_consec (MA50 rising ≥6 of last 8 — exact f_watch threshold)
- volume, avg_volume_20, volume_spike (volume > 1.5× avg_vol_20)
- high_52w, low_52w, dist_from_52w_high, dist_from_52w_low, near_52w_high

### 5.3 `consolidation_patterns` (symbol + date) — from `g_consolidation` (EXACT)
Best pattern per symbol/date (all patterns optional via `is_best` flag):
- timeframe (15d/30d/60d), detection_method
- support_level, resistance_level, range_pct, duration_days
- quality_score (0–100), tightness_score (/25), touch_score (/25), duration_score (/20),
  volume_score (/20), freshness_score (/10)
- total_touches, zigzag_swings, boundary_touches, pct_closes_in_channel
- volume_trend, volume_decline_pct, price_position_pct, position_desc
- current_price, is_best

### 5.4 `breakout_signals` (symbol + date) — from `d_breakout` (EXACT)
- breakout_status (breakout_detected / consolidation_found_no_breakout / no_consolidation)
- breakout_direction (bullish/bearish/none), breakout_day (0/1/2), breakout_strength, breakout_volume_ratio
- consolidation_bottom, consolidation_top, consolidation_range_pct, consolidation_duration_days
- rejection_reason
- (per-case detail day0/day1/day2 retained for parity/debug — optional columns or JSON blob)

### 5.5 `support_resistance` (symbol + date) — shared ZigZag zone core
- zone_type (support/resistance), center_price, zone_bottom, zone_top, min_price, max_price
- touches, strength

### 5.6 `screen_scores` (symbol + date)
- score_tech, score_fund, score_total (0–100 normalized)
- verdict (strong_buy ≥75 / buy ≥60 / watch ≥45 / neutral / avoid <30) — **provisional**
- tech_flags (csv), fund_flags (csv), multi_factor_momentum
- passed (bool vs filter), fail_reasons (csv) — **provisional**
- is_provisional (bool: true until Phase-2 calibration sign-off)

### 5.7 `trade_plans` (1 row/symbol, latest) — from doc Script 5 (deep-dive)
- entry_price, stop_recommended, stop_risk_pct, stop_methods (JSON: atr_2x, ma50_5pct, pct_8…)
- target_1 (rr 1:1), target_2 (rr 1:2), target_3 (rr 1:3), rr_ratio
- position_shares, position_value, position_pct_of_account, dollar_risk, risk_per_share
- computed_at, account_size_used, risk_pct_used

### 5.8 `watchlist` (symbol + note)
- symbol (PK), note, added_at

### 5.9 `screener_settings` (key/value, category)
Mirrors `signal_settings` pattern. Categories:
- **scoring_weights** (JSON) — doc's technical + fundamental + bonus weights
- **thresholds** (JSON) — min_score_total/tech/fund, min_rr_ratio, max_rsi, min_market_cap, profiles
- **consolidation_params** (JSON) — `g`/`d` legacy defaults: zigzag_deviation 6.0,
  lookback_days 40, min_days_between_swings 2, breakout_confirmation_pct 1.5, volume_lookback 20,
  timeframes [15,30,60], max_consolidation_range_pct 5.0, min_consolidation_duration, grouping tolerances…
- **account** — account_size (default 13596 EUR / PEA), risk_pct_per_trade (1.0), default_stop_method

## 6. The Five Components

### 6.1 Fundamentals (`fundamentals_fetch.py`)
New fetcher hits `yf.Ticker(symbol).info` for all enabled universe symbols, snake-cases the
FIELDS set, writes/overwrites `fundamentals`. Weekly cadence, decoupled sync step + on-demand
button. Reuses the failure-tracking discipline from the OBS epic (per-symbol errors → `fetch_error`).

### 6.2 Scoring / verdict engine (`scoring_compute.py`)
Pure module. Reads `indicators` + `screen_signals` + `consolidation_patterns` +
`breakout_signals` + `fundamentals`. Applies the doc's weighted scheme (config-driven from
`screener_settings.scoring_weights` + `thresholds`). Writes `screen_scores` as a daily
time-series, **storing all sub-scores + raw inputs** so distributions are inspectable.
Weights + verdict thresholds are **provisional** (Phase 2 calibration).

### 6.3 Buy-side signals — EXACT legacy logic
- `consolidation_core.py` — shared ZigZag + validated support/resistance zone construction
  (deduplicated from `d` and `g`, behavior-identical).
- `consolidation_compute.py` — `g_consolidation` multi-timeframe quality scoring → `consolidation_patterns`.
- `breakout_compute.py` — `d_breakout` consolidation→breakout event detection → `breakout_signals`.
- `screen_signals_compute.py` — `f_watch` momentum/MA/volume/52w → `screen_signals`.

**Exact-logic contract:** every threshold and validation step preserved verbatim
(ZigZag deviation 6.0, min 2 days between swings, bi-directional zone validation, grouping
tolerance 2.5%, consolidation range 5–30%, ≥95% closes in zone, ≥70% highs/lows in range,
≥14d duration, 3-day breakout window, 1.5% confirmation + volume ratio; g's timeframes
15/30/60d and quality weights 25/25/20/20/10). Only rewired: `moving_averages` → `indicators`;
watchlist/sector CSVs → `tracked_universe` + `watchlist`; CSV output → DB tables. Params come
from `screener_settings.consolidation_params` with legacy defaults.

### 6.4 R/R + position sizing (`trade_plan_compute.py`) — deep-dive
Doc Script-5 logic. ATR-based & MA-based stops (2×ATR, 1.5×ATR, MA50−5%, etc.), recommended
stop = most conservative, R/R targets 1:1/1:2/1:3, position sizing from
`screener_settings.account`. Runs for passers + watchlist only → `trade_plans`.

### 6.5 Watchlist
`watchlist` table. Pinned symbols are always scored and always get a `trade_plan`, regardless
of screen result. Managed from the UI.

## 7. Sync Steps (added to `/api/sync/*`, composable into `full`)

- `POST /api/sync/fundamentals` — weekly snapshot; on-demand button.
- `POST /api/sync/screen` — nightly: `screen_signals` + `consolidation_patterns` +
  `breakout_signals` + `support_resistance` → scoring engine → `screen_scores`.
- `POST /api/sync/trade-plans` — deep-dive for passers + watchlist.
- Each logged to `sync_runs`. `full` orchestrator gains these steps (fundamentals gated to weekly).

## 8. Frontend

- **New "Screener" tab.** Phase 1: a **raw diagnostic data grid** — every signal value
  (momentum, MA cross, consolidation quality + sub-scores, breakout direction/strength,
  fundamentals), sortable/filterable, CSV export, provisional score shown but clearly labeled
  *uncalibrated*. Phase 2: becomes a polished ranked candidate list with verdict + filters
  (min score, verdict, sector, in-portfolio, watchlist-only).
- **Watchlist.** Pin/unpin from any symbol; a filter within the Screener tab. (Top-level tab TBD — user preference.)
- **Deep-dive.** Extend existing `SecurityDetailSheet` (Epic H) — score breakdown, base-quality +
  breakout detail, stop/targets/R-R, position sizing.
- **Configuration.** `screener_settings` editor + fundamentals-refresh button.
- API calls via existing `frontend/app/api/proxy/[...path]`.

## 9. Phasing (build order)

### Phase 1 — Data + raw signals, made visible (**the concrete first build**)
Get everything flowing into the app as raw, inspectable numbers, **no finalized scoring/filter**:
- `fundamentals` fetched for the universe
- `screen_signals`, `consolidation_patterns`, `breakout_signals`, `support_resistance` computed
  (exact legacy logic)
- Scoring engine built but writing **provisional** scores + all raw inputs
- Screener tab as a **raw data grid** + CSV export
- Goal: *look at the data, sanity-check coherence* — momentum vs chart, consolidation coverage
  (5 vs 300 stocks?), MRSI centering, fundamentals sanity.

### Phase 2 — Calibrate & finalize scoring/filtering (§2 + §3 tuning)
With real distributions visible: tune `g`/`d` params for sane coverage; calibrate scoring
weights + verdict thresholds + `min_score` filter; flip `screen_scores.is_provisional` → false.
Config tuning in `screener_settings` + re-run `/api/sync/screen`, not code churn.

### Phase 3 — Deep-dive on winners (§4 + watchlist)
`trade_plans` (R/R + sizing), watchlist, deep-dive panel in `SecurityDetailSheet`.

## 10. Testing Approach

- **Unit (TDD):** each `*_compute.py` module tested in isolation with fixture OHLCV/fundamentals.
  For the exact-logic ports, **golden-value tests**: run the legacy script and the new module on
  the same symbols/data, assert identical outputs (the fidelity contract is testable).
- **Coverage/coherence checks (Phase 1):** run over the real universe, eyeball distributions
  (how many consolidations/breakouts fire, momentum ranges, fundamental completeness).
- **Contract tests:** yfinance `ticker.info` response shape (extend OBS-epic pattern).
- **E2E (Phase 1):** Screener tab renders the raw grid; CSV export works.

## 11. Open Items (deferred to Phase 2, intentionally)

- Final scoring weights and verdict thresholds.
- Final `min_score` / R-R / RSI / market-cap filter cutoffs.
- Final `g`/`d` consolidation parameters (calibrated to real coverage).
- Whether Watchlist is also a top-level tab vs. Screener-tab filter only.
- Whether to keep the vs-SPY momentum alongside MRSI, or standardize on MRSI.

## 12. Module Inventory (new files)

Backend (`backend/scripts/`): `fundamentals_fetch.py`, `screen_signals_compute.py`,
`consolidation_core.py`, `consolidation_compute.py`, `breakout_compute.py`,
`scoring_compute.py`, `trade_plan_compute.py`.
Routes (`backend/api/routes/`): `screener.py` (results/raw grid), `fundamentals.py`,
`watchlist.py`; new steps in `sync.py`.
Schema: new tables in `schema.sql` + migration.
Frontend: `Screener` tab + components; watchlist controls; settings editor; deep-dive additions.
