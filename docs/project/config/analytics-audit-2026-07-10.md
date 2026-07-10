# Analytics Audit — 2026-07-10

**Data as-of:** prices/indicators/signals = **2026-07-09 close** (by design the ingestor never stores today's bar during the session — a partial intraday bar would poison EOD analytics; the 07-10 bar lands at the next sync after US close). Fundamentals fetched **2026-07-10 14:21 UTC**. All computes re-run **2026-07-10 ~18:05 UTC** after the fixes below.

**Cross-check guidance:** compare against TradingView/Yahoo values **as of the 2026-07-09 daily close**. Live intraday tools include today's partial bar and will drift slightly. MAs/BB/RSI here are computed on **adjusted close** (split+dividend); TradingView default chart is split-adjusted only — expect small deviations on dividend payers, none on non-payers (PLTR, NVDA pay ~0).

---

## 0. Trust status — what was broken, what was fixed today

| # | Problem | Status |
|---|---------|--------|
| 1 | **Stale-join MA verdicts** — signals computed 07-01 against ~7-week-old indicators; AAPL "All Bearish" on a bullish stack; 317/561 wrong | ✅ Fixed: 7-day freshness guard at read + recompute. Now 0 mismatches, signal_date == indicator_date for 561/561 |
| 2 | **No recompute chaining** — indicator syncs never refreshed signals (9-day drift) | ✅ Fixed: screen chain runs after every indicators recompute (Technical & IBKR full sync) |
| 3 | **Breakout vs consolidation column mixing** — "breakout detected" next to empty consolidation columns | ✅ Fixed: breakout rows now expose their own support/resistance/range/duration (`breakout_*` columns) |
| 4 | **Split-artifact corruption** — CRWD (4:1), CVNA (5:1), KLAC (10:1), DD (1:3 reverse) had mixed pre/post-split history; DD showed fake +185.9% momentum | ✅ Repaired: purged + re-fetched clean history. ⚠️ Prevention (auto-refetch on split) not yet implemented — see Recommendations |
| 5 | **ZigZag quality detector detects nothing** — 0/561 patterns at default gates (R-2 proved 236/561 at loosened gates) | ⚠️ Open finding: the analytic is effectively OFF until gates are calibrated (tuning panel exists) |
| 6 | **Sync freezes the API** — long syncs blocked every request (looked like backend crash) | ✅ Fixed: fundamentals/screen/analytics/full run in threadpool; verified /health responsive mid-sync |
| 7 | **Scores are coarse buckets** — score_tech takes ~5 distinct values across 561 stocks | ⚠️ Known: provisional scoring, calibration = Epic S Phase 2 |

---

## 1. Analytics registry

Sync buttons (Browse Universe → Research header): **Fundamentals** = fetch + auto-rescore · **Technical** = prices + indicators + *(now)* signals/consolidation/breakout/scores · **Compute signals** = signals/consolidation/breakout/scores only · **Run all** = Technical → Fundamentals → Compute.

### 1.1 Price & bars

| Analytic | Definition | Source | UI | Refresh needed | Button | Reliability |
|---|---|---|---|---|---|---|
| `price` | Latest stored close | yfinance → `market_data.close` (via `market_data_ingestor.py`) | Research grid; detail sheet "Recent bars" | Daily after US close (~22:05 CET) | Technical / Run all | ✅ Good. Today's bar deliberately excluded until complete. ⚠️ No auto-repair after splits (see Rec-1) |
| OHLCV bars | Daily open/high/low/close/adj_close/volume, 730d lookback | same | Detail sheet (last 30 bars) | Daily | Technical | ✅ Good after today's split repair |

### 1.2 Trend & volatility indicators (`indicators_compute.py` → `indicators`; shown in Research grid "Indicators" group + detail sheet Indicators card)

| Analytic | Definition | Refresh | Button | Reliability |
|---|---|---|---|---|
| `ma_50/100/150/200` | Simple rolling mean of **adj_close** | Daily | Technical | ✅ Standard SMA. Note: adjusted-close basis (tiny deviation vs TradingView on dividend payers) |
| `bb_upper_20 / bb_lower_20 / bb_width` | MA20 ± 2σ; width = (upper−lower)/MA20 | Daily | Technical | ✅ Standard |
| `rsi_14` | Wilder smoothing (EWM α=1/14) | Daily | Technical | ✅ Matches TradingView RSI convention |
| `atr_14` | Wilder ATR on raw OHLC | Daily | Technical | ✅ Standard |
| `volume_ma_20` | Rolling mean of volume (includes last bar) | Daily | Technical | ✅ Note: screener's `avg_volume_20` **excludes** the last bar → the two differ slightly, by design |
| `mrsi` | Mansfield RS: (stock/bench) ÷ MA252(stock/bench) − 1; benchmark by currency (USD→^GSPC, EUR→^FCHI, GBP→^FTSE) | Daily | Technical | ✅ Needs 252d of overlapping history — NULL for recent listings. ⚠️ 9/14 IBKR holdings have NULL currency → default ^GSPC (fine for US names) |

### 1.3 Momentum & screener signals (`screen_signals_compute.py` → `screen_signals`; Research grid "Momentum" group)

| Analytic | Definition | Reliability |
|---|---|---|
| `momentum_5d/20d/60d` | % change vs close 5/20/60 **trading days** ago (raw close) | ✅ After split repair. ⚠️ raw-close basis (vs indicators' adj_close) — Rec-2 |
| `multi_factor_momentum` | 0.4×m5 + 0.3×m20 + 0.3×m60 | ✅ |
| `above_ma50/100/150/200` | last close > MA (1/0) | ✅ Now guarded: only joins indicators ≤7 days older than the price bar |
| `ma_cross_status` | Ordering of **MA50/100/150 only** — price not involved: 50>100>150 "All Bullish"; 50>150 "Mostly Bullish"; 50<100<150 "All Bearish"; 50<150 "Mostly Bearish" | ✅ Verified 0 mismatches vs current MAs. NB: a stock can be *below* MA50 and still "All Bullish" (see NVDA) |
| `trend_aligned` | price > MA50 > MA150 **and** price within +1%..+10% above MA50 | ✅ |
| `is_8d_consec` | MA50 rose in ≥6 of the last 8 day-over-day steps | ✅ |
| `volume_spike` | volume > 1.5 × avg of prior 20 bars (excl. today) | ✅ |
| `high_52w / low_52w / dist_from_52w_high / near_52w_high` | 252-bar high/low; near = within 5% of high | ✅ |
| Refresh: daily; **Compute signals** or chained into **Technical** | | |

### 1.4 ZigZag consolidation — quality detector (`consolidation_compute.py` + `consolidation_core.py` → `consolidation_patterns`; grid "Consolidation" group)

| Analytic | Definition |
|---|---|
| `consolidation_quality` (0–100) | Composite of tightness/touches/duration/volume/freshness scores |
| `support_level / resistance_level` | Channel bounds from hybrid channel+ZigZag detection |
| `consolidation_range_pct / timeframe` | Channel width %; best of 15/30/60-day windows |
| ZigZag core | Swings ≥ **6%** deviation (`zigzag_deviation`), ≥2 days apart; channel needs ≥2 touches/level, ≥3 bounces, ≥70% bars in channel, ≥4 boundary touches, ≥85% closes in channel |

**Reliability: ⚠️ currently produces 0/561 patterns at default gates** — the strict thresholds (70%/4/85%) rarely co-occur in this universe. All params are tunable in the **consolidation tuning panel** (Research header → tuning): R-2 testing showed loosened gates yield 236/561. Until calibrated, treat `consolidation_quality/support_level/resistance_level` as **empty by configuration, not by bug**. Refresh: daily via Compute/Technical; re-run after tuning via "Save & re-run".

### 1.5 Breakout detector (`breakout_compute.py` → `breakout_signals`; grid "Breakout" group)

Independent of §1.4 — runs its **own** strict consolidation pass on 40-day windows (3 cases: breakout day = today / yesterday / day before), then checks ±1.5% beyond bounds for a breakout. Shares ZigZag math (6% deviation).

| Analytic | Definition | Reliability |
|---|---|---|
| `breakout_status` | breakout_detected / consolidation_found_no_breakout / no_consolidation_patterns | ✅ |
| `breakout_direction / strength / volume_ratio` | bullish if close ≥ resistance×1.015 (strength = % beyond level); volume vs 20d avg | ✅ |
| `breakout_support / breakout_resistance / breakout_range_pct / breakout_duration_days` | Bounds of the consolidation this detector found (NEW columns — previously missing) | ✅ Now stored for both fired and non-fired consolidations |
| Internal gates | range 5–30%, ≥14d duration, price inside zone ±2%, ≥95% closes in zone, ≥70% highs/lows in zone | strict by design |
| Refresh: daily via Compute/Technical | | |

### 1.6 Fundamentals (`fundamentals_fetch.py` → `fundamentals`; detail sheet Fundamentals card + grid "Fundamentals" group)

| Analytic | Definition | Reliability |
|---|---|---|
| `gross_margin, roe, market_cap, trailing_pe, …` | Straight from yfinance `Ticker.info` | ✅ As reliable as Yahoo; refreshed today 14:21 UTC |
| `roic` | NOPAT ÷ (debt+equity−cash); fallback pre-tax ROCE | ✅ method recorded in `roic_method` |
| `levered_fcf_margin` | FCF ÷ revenue | ✅ |
| `interest_cover` | EBIT ÷ interest expense | ⚠️ NULL when no interest expense reported (e.g. PLTR) |
| `eps_5y_growth` | CAGR of annual diluted EPS series | ⚠️ NULL if <2 positive EPS years (e.g. PLTR); yfinance provides ~4y not 5 |
| `gates_passed`/7 | Gates: GM>60%, ROE>15%, ROIC>10%, FCF margin>20%, interest cover>3, EPS growth>10%, FCF>0 | ✅ **Missing metric = failed gate** (conservative, by design) |
| Refresh needed: weekly, or after earnings. Button: **Fundamentals** (~14 min for 561, auto-rescores after) | | |

### 1.7 Scores & verdict (`scoring_compute.py` → `screen_scores`; grid "Score" group)

score_tech = weighted checks (above_ma50 ×10, above_ma200 ×10, volume_spike ×7, momentum_60d>0 ×10, near_52w_high ×5, bullish breakout ×12, consolidation quality≥50 ×10) ÷ max ×100. score_fund = gates/7 ×100. score_total = average. Verdict: ≥75 strong_buy / ≥60 buy / ≥45 watch / ≥30 neutral / <30 avoid.

**Reliability: ⚠️ provisional (is_provisional=1).** Only 7 binary tech inputs → coarse buckets; the consolidation input is currently always false (§1.4) and breakout rarely true, so effective ceiling is lower than 100. Calibration = Epic S Phase 2. Refresh: chained after Fundamentals and Compute.

### Wireframe map (current, pre-Phase-B)

| Screen | Data shown |
|---|---|
| **Positions tab** | IBKR positions + holding signals (`holding_signals_compute`) |
| **Transactions tab** | IBKR transactions, corporate actions sub-tab, splits |
| **Browse Universe tab = Research view** | ResearchGrid (all §1 analytics, configurable columns), SyncToolbar, consolidation TuningPanel |
| **Configuration tab** | Universe management (indices, manual tickers), IBKR sync |
| **Detail sheet** (click any row) | About / Position / Indicators / Transactions / Recent bars / Fundamentals cards |

---

## 2. Cross-check: PLTR & NVDA (as of 2026-07-09 close)

### PLTR — Palantir Technologies

| Analytic | Value | | Analytic | Value |
|---|---|---|---|---|
| Close 07-09 | **129.04** | | RSI(14) | **50.31** |
| MA50 | **133.55** | | MRSI vs ^GSPC | **−0.263** (underperforming) |
| MA100 | **139.09** | | ATR(14) | **6.94** |
| MA150 | **149.59** | | Vol MA20 | **44.49M** |
| MA200 | **157.07** | | BB(20,2) | **108.18 – 142.00** (width 0.270) |
| Momentum 5d | **+2.63%** | | above MA 50/100/150/200 | **0/0/0/0** |
| Momentum 20d | **−2.29%** | | MA cross | **All Bearish** (133.55<139.09<149.59 ✓) |
| Momentum 60d | **−2.52%** | | trend_aligned / 8d-consec / vol-spike | **0 / 0 / 0** |
| Multi-factor | **−0.39** | | Volume 07-09 | 35.16M vs avg 44.66M → no spike |
| 52w high/low | **207.52 / 106.37** | | dist from high | **−37.8%** (near-high: no) |
| Breakout | **no_consolidation_patterns** | | ZigZag quality pattern | none (detector at defaults) |

ZigZag swings, 40d window (verify on chart): peak 06-01 @ 163.70 → trough 06-11 @ 127.17 → peak 06-17 @ 136.10 → trough 06-26 @ 108.47 → peak 07-06 @ 134.07.

Fundamentals (fetched 07-10): gross margin **84.1%**, ROE **32.6%**, ROIC **22.5%** (NOPAT), FCF margin **33.6%**, FCF **$1.75B**, interest cover **n/a**, EPS-5y **n/a** → gates **5/7** (2 missing = failed). Mkt cap **$305.7B**, trailing P/E **143.3**, forward P/E **60.9**, analyst mean target **183.12** (27 analysts, "buy"), beat rate 4/4.

Scores: tech **0.0** (no flags fire), fund **71.4**, total **35.7** → **neutral**.

### NVDA — Nvidia

| Analytic | Value | | Analytic | Value |
|---|---|---|---|---|
| Close 07-09 | **202.78** | | RSI(14) | **49.71** |
| MA50 | **209.12** | | MRSI vs ^GSPC | **−0.021** (≈ market) |
| MA100 | **197.37** | | ATR(14) | **7.02** |
| MA150 | **193.03** | | Vol MA20 | **147.31M** |
| MA200 | **191.49** | | BB(20,2) | **190.02 – 212.83** (width 0.113) |
| Momentum 5d | **+2.63%** | | above MA 50/100/150/200 | **0/1/1/1** |
| Momentum 20d | **−2.60%** | | MA cross | **All Bullish** (209.12>197.37>193.03 ✓ — price below MA50 yet stack bullish: status measures MA ordering, not price) |
| Momentum 60d | **+7.12%** | | trend_aligned / 8d-consec / vol-spike | **0 / 0 / 0** |
| Multi-factor | **+2.41** | | Volume 07-09 | 131.65M vs avg 149.78M → no spike |
| 52w high/low | **236.54 / 161.16** | | dist from high | **−14.3%** |
| Breakout | **no_consolidation_patterns** | | ZigZag quality pattern | none |

ZigZag swings, 40d window: peak 05-14 @ 236.54 → trough 05-28 @ 211.22 → peak 06-01 @ 224.87 → trough 06-10 @ 199.92 → peak 06-22 @ 213.99 → trough 06-29 @ 189.80 → peak 07-08 @ 205.16.

Fundamentals: gross margin **74.1%**, ROE **114.3%**, ROIC **76.3%**, FCF margin **18.3%**, interest cover **547**, EPS-5y CAGR **+204%/yr**, FCF **$46.3B** → gates **6/7** (fails FCF margin 18.3% < 20%). Mkt cap **$5.008T**, trailing P/E **31.7**, forward **16.2**, dividend yield 0.49%, mean target **301.62** (58 analysts, "strong_buy"), beat rate 4/4.

Scores: tech **31.2** (flags: above_ma200, momentum_60d_positive), fund **85.7**, total **58.5** → **watch**.

---

## 3. Trigger examples (2026-07-09 data — verify against real charts)

| Signal | Fires for (count in universe) | Examples with numbers |
|---|---|---|
| **volume_spike** (10) | AES 26.45M vs 8.04M avg = **3.29×** · CINF 2.20M vs 0.94M = **2.33×** · PSKY 18.87M vs 8.45M = **2.23×** |
| **is_8d_consec** MA50 rising (291) | A (MA50 124.60) · AAPL (296.87) · ABBV (222.92) — MA50 up ≥6 of last 8 days |
| **trend_aligned** (160) | AAPL 316.22 > MA50 296.87 (+6.5%) > MA150 275.00 · ABNB 146.89 > 138.23 (+6.3%) > 133.41 · AC.PA 48.66 > 46.09 (+5.6%) > 45.73 |
| **near_52w_high** (113) | EA −0.01% from 206.59 · EXPD −0.02% from 170.65 · MPC −0.13% from 283.68 |
| **All Bullish** (233) | AAPL: 296.87 > 278.57 > 275.00 |
| **Mostly Bullish** (67) | ABBV: MA50 222.92 > MA150 219.55, but MA100 218.97 < MA150 |
| **All Bearish** (~183) | ABT: 89.18 < 97.19 < 104.37 (also PLTR above) |
| **Mostly Bearish** (75) | A: MA50 124.60 > MA100 120.86 but < MA150 126.72 |
| **MRSI outperformance** | SNDK **+1.96** · MU **+1.37** · DELL **+1.32** (vs ^GSPC, 252d basis) |
| **Top momentum 60d** | DDOG **+144.4%** · DELL **+137.2%** · MU **+132.5%** (DD's former +185.9% was a split artifact — repaired) |
| **breakout_detected** (6 on 07-09) | **MPC bullish** +3.04% above 272.40 resistance (support 240.68, 40d base, vol 1.02×) · **REGN bullish** +4.05% above 649.93 (support 604.70, 49d) · **FCX bearish** −1.68% below 58.49 (49d, vol 1.39×) · KER.PA bearish · MOS bearish · **PSKY bearish** −3.91% below 9.71 on 2.10× volume |
| **consolidation_found_no_breakout** (60 on 07-09) | OR.PA in **369.90–395.02** (6.8%, 39d) · CSGP 28.82–30.80 (6.9%, 14d) · JCI 138.94–148.78 (7.1%, 21d) · CHD 93.19–100.03 (7.3%, 41d) · LOW 212.24–228.07 (7.5%, 21d) |
| **ZigZag quality pattern** (0) | none — detector produces nothing at default gates (see §1.4); PLTR/NVDA swing lists above show the ZigZag core itself works |

---

## 4. Recommendations (next fixes, in priority order)

1. **Split auto-repair (Rec-1, HIGH):** when corporate_actions records a new split for a tracked symbol, purge + re-fetch its market_data and indicators. Until then the day-ratio scan in ERRORS.md is the manual guard.
2. **Adjustment-basis standardization (Rec-2, MEDIUM):** indicators use adj_close, momentum/signals use raw close. Standardize (recommend adj_close everywhere) so price-vs-MA comparisons are same-basis.
3. **ZigZag gate calibration (HIGH, product decision):** defaults produce 0 patterns. Either adopt the loosened R-2 preset (236/561) with quality-score ranking, or tune per-timeframe. The tuning panel already supports this — needs your target hit-rate.
4. **Score calibration (Epic S Phase 2):** replace binary-weight tech score with graded contributions; include MRSI/RSI.
5. **Staleness surfacing in UI:** show data-age chips (price date, signal date, fundamentals age) in the Research header — the audit's freshness contract should be visible, not implicit.
6. **Phase B wireframe audit + dashboard** (agreed next step).
