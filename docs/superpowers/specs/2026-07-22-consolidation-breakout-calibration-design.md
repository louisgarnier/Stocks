# Consolidation / Breakout / S-R Calibration — Design Spec

**Date:** 2026-07-22
**Status:** Draft — awaiting user review
**Epic:** S Phase 2 (Screener calibration), consolidation/breakout track
**Author:** brainstormed with user 2026-07-22

---

## 1. Context & problem

The Research (Browse Universe) grid exposes a family of ~14 consolidation / support-resistance / breakout columns. In the live DB they are almost entirely empty:

- `consolidation_patterns` table: **1 row for 1 symbol out of 562.** The standalone ZigZag detector is effectively off — the Consolidation columns (`consolidation_quality`, `support_level`, `resistance_level`, `consolidation_range_pct`, `consolidation_timeframe`) are 100% blank.
- `breakout_signals` table: runs (2,760 rows / 561 symbols) but is downstream of consolidation detection, so most detail columns (`breakout_strength`, `breakout_volume_ratio`, and the base bounds `breakout_support/resistance/range/duration`) are only populated on the ~38 stocks actually breaking out.

Root cause (established during Epic R-2): **not a code bug — conservative default parameters.** Recorded proof: default params detect 1/561; loosened detect 236/561. But loosening blindly trades one failure (finds nothing) for another (finds low-quality noise). The real fix is **evidence-based calibration**: build the ability to measure whether a detected setup actually precedes a move, then tune to that measurement.

This spec designs that capability end-to-end.

## 2. Goals / non-goals

**Goals**
1. A **walk-forward backtest harness** that scores any detection ruleset by forward **excess return vs each stock's home index** over 20/60/180/360-day horizons. This is the "scale" everything else is tuned against.
2. A rebuilt **multi-source Support/Resistance** engine (Layer 2) — the foundation all higher layers read.
3. A **structure/regime classifier** (Layer 3): flat base, uptrend/downtrend channel, ascending/descending/symmetric triangle, VCP, extended/choppy.
4. A **breakout trigger** (Layer 4) that fires on a daily close outside a valid structure, with direction + strength.
5. **Calibrated parameters** chosen by the harness, persisted via the existing settings mechanism.
6. The clean outputs **wired back into the existing grid columns** so the empty fields fill with trustworthy data.

**Non-goals (this round)**
- Options-based S/R (no data, not backtestable) — deferred to a later live-overlay phase.
- Intraday timeframes — we are daily-only.
- Changes to fundamentals, scoring verdict weights, or sell-side holding signals.
- A UI charting view of patterns (separate future story).

## 3. Architecture — one bottom-up stack

```
  LAYER 4  BREAKOUT TRIGGER        close outside a valid structure -> signal (dir + strength)
             ^ reads
  LAYER 3  STRUCTURE CLASSIFIER    shape of the S/R lines: base / channel / triangle / VCP / extended
             ^ reads
  LAYER 2  SUPPORT / RESISTANCE    horizontal price zones, merged from multiple sources (confluence)
             ^ reads
  LAYER 1  RAW DATA                daily OHLCV (have it) + home-index series (have it)

  LAYER 0  BACKTEST HARNESS        replays L2->L4 walk-forward over history, scores signals vs home index.
                                    Built FIRST; runs LAST. The scale we tune against.
```

**Runtime order** (per symbol, each refresh): data -> S/R -> structure -> breakout.
**Build order**: harness (0) -> S/R (2) -> structure (3) -> breakout (4) -> calibrate -> grid wiring -> options overlay (later).

Each layer is an independently testable unit with a pure-function core (`df -> result`) and a thin DB read/write wrapper, mirroring the existing `backend/scripts/*_compute.py` pattern.

## 4. Data foundation & constraints

- **Price history:** `market_data` daily OHLCV, 2024-05-06 -> 2026-07-21 (~2.2y, ~550 bars/symbol), 562 enabled symbols.
- **Home-index benchmarks:** `^GSPC` (S&P 500), `^FCHI` (CAC 40), `^FTSE` (FTSE 100), `^GDAXI` (DAX) all present. Mapping via `tracked_universe.benchmark` (503 -> ^GSPC, 40 -> ^FCHI, 19 null). **Task:** backfill the 19 nulls from `currency`/`exchange` (USD->^GSPC, EUR->^FCHI unless exchange says DAX, GBP->^FTSE); default ^GSPC.
- **CRITICAL constraint — benchmark history is short:** index series only start **2025-04-28** (~15 months). Excess-return scoring requires benchmark data over `[T, T+h]`, so:
  - **20d / 60d horizons:** well-covered (hundreds of origination dates).
  - **180d:** partial (origination dates through ~2026-01).
  - **360d:** sparse — only signals originating 2025-04-28 .. ~2025-07-26 have a full forward window (~3 months of origination dates). **Treat 360d as directional-only, report sample counts, never calibrate primarily on it.**
- **`consolidation_patterns` is snapshot-only** (PK = symbol, one row each). The harness does NOT read it; it recomputes detections walk-forward from `market_data`. The snapshot tables are for live-grid display only.

## 5. Layer 0 — Backtest harness & evaluation metric (BUILD FIRST)

**Module:** `backend/scripts/backtest_harness.py`

**Pure evaluation contract.** Given a list of signals `[(symbol, date, direction), ...]`:
- `forward_return(S, T, h) = close[T+h] / close[T] - 1` (h in trading days: 20, 60, 180, 360)
- `bench_return(S, T, h) = idx_close[T+h] / idx_close[T] - 1`, idx = home benchmark of S
- `excess(S, T, h) = forward_return - bench_return`
- Signals with incomplete forward or missing benchmark data at horizon h are excluded from that horizon's stats (counted separately).

**Aggregate report** per horizon: `n_signals`, `hit_rate` (% excess>0), `avg_excess`, `median_excess`, `avg_absolute_return`. Also **absolute** return alongside excess (user asked to see both).

**Null baseline (overfitting guard):** alongside the signal cohort, score a **random-entry cohort** — same symbols, random dates, equal count. A ruleset only "works" if signal `avg_excess` beats the random baseline by a meaningful margin, not just >0. (Rising markets make almost any long look positive; the benchmark subtraction plus the random baseline are the two defenses.)

**Walk-forward / no look-ahead (non-negotiable):** a detection dated T may use only bars with `time <= T`. The harness drives detection as-of each candidate date on the trailing window. A dedicated test asserts detection output is identical whether or not future bars are present in the input frame.

**Calibration primary metric:** `avg_excess @ 60d`, subject to `n_signals >= MIN_SIGNALS` (guard, e.g. 40) and `signal avg_excess - random avg_excess >= MIN_EDGE`. 20d is a secondary confirmation; 180/360d are reported for context.

**Cross-validation:** split the scoreable window into two halves (and separately US vs EU cohorts); prefer parameter sets that hold up on both over a set that wins on one. Guards against fitting to a single market regime.

**Output tables:**
- `backtest_runs (run_id PK, params_hash, created_at, universe_size, notes)`
- `backtest_results (run_id, cohort, horizon, n_signals, hit_rate, avg_excess, median_excess, avg_return)` — cohort in {signal, random, us, eu}.

## 6. Layer 2 — Support / Resistance (multi-source confluence)

**Module:** `backend/scripts/sr_levels.py`. Pure core: `detect_sr_zones(df, params) -> List[SRZone]`.

**Sources** (each proposes candidate horizontal levels over the trailing `lookback` window, default 120 trading days):
1. **Swing pivots** — ZigZag highs/lows (`zigzag_deviation`); a level is a pivot price with a touch count.
2. **Volume-by-price** — bin the window's price range into N bins; accumulate each bar's volume across its high-low span; peak bins = High-Volume Nodes.
3. **Dynamic MAs** — current MA50 / MA200 values (marked as dynamic, lower base weight).
4. **Reference levels** — 52w high/low, recent swing extremes, round numbers near price.

**Merge into zones:** cluster candidate levels within `merge_tolerance_pct` (default 1.0%). Each `SRZone`:
- `price` (volume/touch-weighted center), `kind` (support if below last close, else resistance)
- `strength` = f(number of distinct sources, touch count, volume at zone) -> 0..100
- `sources` (list), `touches`

**Output:** ordered zone list + the **active** pair: nearest support below price, nearest resistance above. Persisted latest-per-symbol to `sr_zones (symbol, date, price, kind, strength, sources_json, touches)` for display; the harness uses the in-memory result.

## 7. Layer 3 — Structure / regime classifier

**Module:** `backend/scripts/structure_classify.py`. Pure core: `classify_structure(df, sr_zones, params) -> Structure`.

Fit a **support line** and **resistance line** over the window (regression on swing lows / swing highs, anchored to active zones). Compute descriptors:
- `support_slope`, `resistance_slope` (normalized % per day)
- `width_pct` (channel height / price), `tightness` (% of closes inside the channel)
- `contraction` (is width shrinking over the window? early vs late width ratio)
- `volume_trend` (declining => dry-up)
- `dist_from_ma`, volatility (ATR%) for extended/choppy detection

**Classification** (thresholds are calibrated params):

| Regime | Condition |
|---|---|
| **flat base / rectangle** | both slopes ~ 0, width tight, high tightness |
| **ascending triangle** | support_slope > 0, resistance ~ flat |
| **descending triangle** | resistance_slope < 0, support ~ flat |
| **symmetric triangle** | support up + resistance down (converging) |
| **uptrend channel** | both slopes > 0, roughly parallel |
| **downtrend channel** | both slopes < 0 |
| **extended / choppy** | none of the above / high volatility / far from MA |

**VCP flag** is an overlay (co-occurs with base/triangle): `contraction` present AND `volume_trend` declining -> the "coiled" setup. Output: `regime`, `pattern`, numeric descriptors, `quality` score (0..100 from tightness x touches x contraction).

Persist latest-per-symbol to `structure_state (symbol, date, regime, pattern, support_slope, resistance_slope, width_pct, tightness, contraction, volume_trend, vcp_flag, quality)`.

## 8. Layer 4 — Breakout trigger

**Module:** rework `backend/scripts/breakout_compute.py`. Pure core: `detect_breakout(df, structure, sr_zones, params) -> Breakout | None`.

- **Active only** when regime has a defined boundary (base, triangle, channel).
- **Trigger:** latest daily **close** beyond the active resistance (up) or support (down) by `breakout_confirmation_pct`.
- **Strength:** distance beyond level normalized by ATR.
- **Volume confirmation:** `breakout_volume_ratio` = breakout-day volume / 20d avg; optional `min_volume_surge` gate (calibrated).
- **Direction:** up / down.
- **Primary buy signal** = up breakout from a **flat base** or **ascending triangle**. Others are recorded with their type but not treated as the buy trigger.

Writes to existing `breakout_signals` (time-keyed) — the harness reads its walk-forward equivalent in memory.

## 9. Calibration loop

Parameter surface (persisted in `consolidation_params` settings key, extended):
`zigzag_deviation`, `lookback`, `merge_tolerance_pct`, min sources/touches for a valid zone, base tightness threshold, triangle slope thresholds, VCP contraction + volume-dryup thresholds, `breakout_confirmation_pct`, `min_volume_surge`.

Procedure:
1. Define a search space (sensible ranges per param).
2. For each candidate param set: run the harness walk-forward across the universe, produce `backtest_results`.
3. Rank by `avg_excess @ 60d` with the guards (min signals, beat-random edge, cross-validation stability).
4. Select, persist to settings, record the winning `run_id`.
5. Re-run the live compute (`consolidation_compute` / `structure` / `breakout`) so the snapshot tables + grid reflect calibrated params.

Search starts as a coarse grid / random search (not a heavy optimizer) to keep it debuggable; can be tightened later.

## 10. Grid integration — closing the field-walk loop

Map calibrated outputs onto the **existing** grid columns (fills today's empty fields):

| Grid column | New source |
|---|---|
| `consolidation_quality` | `structure_state.quality` |
| `support_level` / `resistance_level` | active S/R zone prices (Layer 2) |
| `consolidation_range_pct` | `structure_state.width_pct` |
| `consolidation_timeframe` | repurpose to `regime` / `pattern` label (rename column label to "Structure") |
| `breakout_status` / `direction` / `strength` / `volume_ratio` / `date` | Layer 4 |
| `breakout_support/resistance/range/duration` | the structure bounds that were broken |

New optional columns to expose (parity test auto-covers): `pattern`, `vcp_flag`, zone `strength`. Column curation (defaults) decided at the end of the broader field walk.

## 11. Testing strategy

- **Per-layer unit tests on synthetic series with known answers:** S/R on a series with hand-placed levels; classifier on synthetic base/triangle/channel/VCP shapes; breakout on a synthetic close-cross.
- **No-look-ahead test:** detection at T identical with/without future bars appended.
- **Harness test:** tiny synthetic dataset with one known-good and one known-bad signal -> asserts excess/hit-rate math and random-baseline wiring.
- **Benchmark-mapping test:** each symbol resolves to a home index; nulls backfilled deterministically.
- **Regression:** existing `test_research_overview.py` + column parity tests stay green after the grid re-wire.

## 12. Data model changes (summary)

New: `sr_zones`, `structure_state`, `backtest_runs`, `backtest_results`. Reuse: `breakout_signals`, `consolidation_patterns` (may fold into `structure_state` or keep as the base-bounds snapshot). Extend `consolidation_params` settings. Backfill `tracked_universe.benchmark`. All view changes require the drop+recreate migration on the live DB (`research_overview`), per the known gotcha.

## 13. Build sequence (stories)

1. **CB-0** Backtest harness + evaluation metric + benchmark backfill + null-baseline + no-look-ahead test. (Foundation — nothing tunable is trustworthy without it.)
2. **CB-1** Layer 2 S/R engine (multi-source + merge) + unit tests + `sr_zones` table.
3. **CB-2** Layer 3 structure classifier + `structure_state` table + tests.
4. **CB-3** Layer 4 breakout rework + tests.
5. **CB-4** Calibration loop -> pick params -> persist -> live recompute.
6. **CB-5** Grid re-wire (map outputs to columns) + parity/regression tests + E2E screenshot.
7. **CB-6 (later, optional)** Options-wall overlay on the S/R display (US-only, live snapshot, outside calibration).

## 14. Risks & open questions

- **Short benchmark history** caps long-horizon calibration; 360d is directional-only. Accept and report sample counts.
- **Regime overfit:** 15 months is one market regime. Cross-validation + random baseline + preference for simple/robust params are the mitigations; we should stay skeptical of any param set that only wins on one half.
- **Volume-by-price from daily OHLC** is approximate (no intraday distribution). Acceptable for zone-finding; documented.
- **`consolidation_timeframe` repurpose** changes a column's meaning — confirm the rename to a "Structure" label is acceptable vs adding a new column.
