# Research Unified View — Design Spec

**Date:** 2026-07-01
**Status:** Draft (awaiting user review)
**Author:** Louis + Claude
**Supersedes / merges:** the standalone Screener tab and the Browse Universe tab into one "Research" view.

## Problem

The app currently has two overlapping-but-divergent tabs that each hold *part* of a stock's picture, computed by different pipelines:

| | Browse Universe | Screener |
|---|---|---|
| Data source | `/api/security/{sym}/detail` + `/api/universe/coverage` | `/api/screener/overview` (the `screener_overview` DB view) |
| Columns | symbol, name, sources | symbol, score_total/tech/fund, gates_passed, momentum_60d, breakout_strength, consolidation_quality, roic, roe, gross_margin, verdict |
| Header buttons | market-data sync, analytics sync | export CSV |
| Row click | SecurityDetailSheet popup | (same popup) |
| Built by | Epic D (`indicators` table, per-bar MA/BB/RSI/MRSI/ATR) | Epic E (`screen_signals` + `consolidation_patterns` + `breakout_signals` + `fundamentals` + `screen_scores`) |

Consequences the user hit:
1. **No single clean per-stock dataset.** Tech indicators live in one pipeline (`indicators`), screener signals + fundamentals in another. Neither view shows the whole picture.
2. **Detail popup has no fundamentals.** Its cards are About / Position / Transactions / Indicators / Bars only.
3. **"Tech data missing / unreliable."** Root cause found: `consolidation_patterns` has **1 row / 561 symbols** despite a clean `screen` sync — the ZigZag/consolidation compute silently under-produces, and breakout depends on it, so 474/561 report `no_consolidation_patterns`. The ZigZag / support-resistance / consolidation columns are effectively empty for every stock.
4. **Fundamentals refresh doesn't rescore** — populating `fundamentals` leaves `score_fund=0` until scoring re-runs separately (see memory `gotcha_fundamentals_no_rescore`).
5. **Fundamentals refresh button is on the Configuration tab**, disconnected from where the data is consumed.

## Goals

- **One canonical per-symbol dataset** = the single source of truth for the grid, the CSV export, and the detail popup.
- **One merged "Research" view** (Screener grid UI, kept as-is — it's the nicer one) living in the Browse Universe window; standalone Screener tab retired.
- **Add/remove columns** in the grid; default column set = union of today's Screener + Browse Universe columns; choice persists in the browser.
- **Explicit, idempotent sync pipeline**: 3 independent buttons + a "Run all", grouped in a top toolbar, each with last-run / stale badges.
- **Reliable tech data** — fix the consolidation under-production so ZigZag / support-resistance / consolidation actually populate.
- **Detail popup shows everything** — keep current technical cards, add a Fundamentals card.

## Non-goals (YAGNI)

- No new signal types beyond what already exists (momentum, MA flags, ZigZag, S/R, breakout, consolidation, fundamentals, score).
- No score-weight recalibration (that is the separate Phase-2 calibration work).
- No user-defined *computed* columns — "add/remove columns" means show/hide from the available set, not authoring new formulas.
- No changes to the IBKR/positions/transactions pipeline.

## Architecture

### 1. Unified data view — single source of truth

Extend the existing `screener_overview` view (rename to **`research_overview`**, keep `screener_overview` as a thin alias for backward-compat during transition) to additionally LEFT JOIN the **latest indicator row per symbol** from `indicators` (Epic D):

- New joined columns: `ma_50, ma_100, ma_150, ma_200, bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20`, plus the indicator `time` as `indicator_date`.
- Latest-per-symbol via correlated subquery `AND i.time = (SELECT MAX(time) FROM indicators i2 WHERE i2.symbol = u.symbol)` — same pattern the view already uses for `breakout_signals` and `screen_scores`.

Everything reads from this one view:
- `GET /api/research/overview?format=json|csv` (new; `/api/screener/overview` kept as alias, same handler).
- The merged grid.
- The detail popup's new Fundamentals card (fundamentals fields are already in the view).

### 2. Sync pipeline — 3 buttons + Run all

A toolbar at the top of the merged Research window. Each endpoint already mostly exists; wiring:

| Button | Action | Endpoint(s) | Notes |
|---|---|---|---|
| **① Fundamentals** | fetch yfinance fundamentals **then rescore** | `POST /api/sync/fundamentals` → chain `scoring_compute.compute_all` | Fixes the no-rescore gotcha. |
| **② Technical** | price bars + base indicators | `POST /api/sync/market-data` → indicators compute | Feeds the `indicators` table + raw prices. |
| **③ Compute signals** | momentum / MA-flags / ZigZag / S-R / breakout / consolidation / score | `POST /api/sync/screen` | Existing orchestrator; consolidation step fixed (Phase 2). |
| **④ Run all** | chain in dependency order | ② → ① → ③ | Prices first, then fundamentals, then compute. |

- Each button: idempotent, disabled+spinner while running, toast on start/finish, and a **last-run + stale badge** (reuse the fundamentals `/status` cadence pattern; add equivalent `/status` for technical & compute if missing).
- Buttons sit next to the existing market-data / analytics buttons already in the Browse Universe header.

### 3. Merged UI — Research grid

- Move `ScreenerGrid` (unchanged look) into the Browse Universe tab; **retire the standalone `screener` tab** from `TabType` and the tab bar.
- **Column visibility control**: a "Columns" menu (checkbox list of all available fields). Default visible set = union of current Screener columns (score_total, score_tech, score_fund, gates_passed, momentum_60d, breakout_strength, consolidation_quality, roic, roe, gross_margin, verdict) + Browse Universe columns (symbol, name, sources). Selection persisted to `localStorage` under a versioned key.
- Preserve existing Screener grid features: sort, filter chips (min-score / gates / breakout), CSV export.
- CSV export streams the **full** unified dataset (all columns), independent of which columns are visible.

### 4. Detail popup — add Fundamentals

- `SecurityDetailSheet` keeps its current cards (About / Position / Transactions / Indicators / Bars).
- Add a **Fundamentals** card: gross margin, ROE, ROIC, levered FCF margin, interest cover, EPS 5y growth, quality gates (x/7), market cap, trailing P/E.
- Source: extend `GET /api/security/{symbol}/detail` (in `backend/api/routes/security.py`) to include a `fundamentals` block read from the `fundamentals` table (or from `research_overview`). Popup renders the card only when the block is present.

### 5. Reliability fix — consolidation under-production (debugging spike)

- **Symptom:** `consolidation_patterns` = 1 row / 561 symbols after a clean `screen` sync (0 failures). `breakout_signals` = 560 rows but 474 = `no_consolidation_patterns` because breakout depends on consolidation.
- **Approach:** systematic-debugging. Hypotheses to test in order: (a) consolidation params seeded too strict / seed-drift (`min_touches_per_level`, `min_range_size_pct`, `min_bounces_in_channel`, `channel_test_tolerance` — see memory `gotcha_screener_settings_seed_drift`); (b) the verbatim ZigZag port has an I/O rewire bug (wrong lookback / wrong price series / silent empty result); (c) the compute writes but a retention prune deletes (sync summary shows `pruned 1+0` — investigate).
- **Definition of done:** consolidation patterns + support/resistance populate for a meaningful fraction of the universe, and a regression test asserts >1 symbol produces a pattern on representative data.

## Data flow

```
② Technical ──> market_data (prices) ──> indicators (MA/BB/RSI/MRSI/ATR)
① Fundamentals ─> fundamentals ──(auto)──> scoring_compute
③ Compute ─────> screen_signals, consolidation_patterns, breakout_signals ──> scoring_compute ──> screen_scores
                                   │
                                   ▼
                        research_overview  (VIEW: universe ⨝ latest indicators ⨝ signals ⨝ consolidation ⨝ breakout ⨝ fundamentals ⨝ latest score)
                                   │
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
        Research grid        CSV export         Detail popup (Fundamentals card)
```

## Testing

- **Backend:** view returns indicator columns joined (unit test against `temp_db`); `/api/research/overview` json+csv parity; `/api/sync/fundamentals` triggers rescore (score_fund changes); consolidation regression test (>1 pattern on seeded data); `/api/security/{sym}/detail` includes fundamentals block.
- **Frontend:** jest for column show/hide + localStorage persistence; grid renders union columns; detail popup renders Fundamentals card when present.
- **E2E (webapp-testing):** open Research tab → run "Run all" (stubbed) → grid populates → toggle a column → click a row → Fundamentals card visible.

## Build order (phased, each shippable)

1. **Phase 1 — Unified view + CSV.** `research_overview` view w/ indicators; `/api/research/overview`; CSV. (Backend only, no UI change yet.)
2. **Phase 2 — Consolidation reliability fix.** Debugging spike + regression test.
3. **Phase 3 — Merged UI.** Screener grid into Browse Universe; 3+1 button toolbar (Fundamentals auto-rescore, Run all chain); column show/hide + persistence; retire Screener tab.
4. **Phase 4 — Detail popup.** Fundamentals card + `/api/security/{sym}/detail` extension.

## Open questions

None blocking. Defaults locked: column choice persists in localStorage; standalone Screener tab is removed; sync buttons live in the merged window's top toolbar.
