# Epic E — Tech Analysis Tab v1

**Status:** [ ] Pending (no plan yet — written when Epic H ships)

## Goal

Add a new top-level "Tech Analysis" tab where the user screens the broader universe (S&P 500 + CAC 40 + held + manual additions) for actionable trading signals: range breakouts, trend breakouts, consolidations, and key support/resistance levels (technical method; options method in Epic F).

## What this epic delivers

### Pattern detection — TWO distinct breakout signals

The user explicitly requested both. Different mental models, different traders use them differently.

| Signal | Trigger |
|---|---|
| **Range Breakout** | Price breaks above ZigZag-defined consolidation zone with volume confirmation. Port of `d_breakout_detector_3.py`. |
| **Trend Breakout** | All four conditions: Price > MA150 AND MA50 sloping up AND Price > MA50 AND volume > 1.5× 20-day avg. Stan-Weinstein-style sustained-uptrend confirmation. |

Both write to `breakout_signals` table with a `signal_type` column (`range` / `trend`).

### Consolidation detection

| Pattern | Logic |
|---|---|
| **ZigZag consolidation** | Multi-timeframe (15d / 30d / 60d) ZigZag-based S/R + quality scoring. Port of `g_consolidation.py`. |
| **Bollinger Band Squeeze** | BB width = `(upper - lower) / MA20`; flag when at multi-month low (lowest in 6 months). Volatility-based; complements ZigZag's price-zone-based detection. |

NR7 + VCP **explicitly punted** to a future story (per user decision).

Both patterns write to `consolidation_patterns` table with a `pattern_type` column.

### Support & Resistance — technical method

(Options method is Epic F.)

`support_resistance` table with `method` column. Multiple methods stored side-by-side:

| Method | Source |
|---|---|
| `zigzag_swing` | ZigZag-detected swing high/low zones (already from breakout/consolidation logic) |
| `ma` | Dynamic levels at MA50 / MA100 / MA150 / MA200 |
| `round_number` | Psychological levels at round prices ($50, $100, $150, $200, $250...) within ±20% of current price |
| `volume_profile` | Historical price levels with most trading volume — proxy for "where retail stops cluster" |

Each level has: `(symbol, method, price, type='support'/'resistance', strength_score, valid_from, valid_until)`.

### Tech Analysis tab UI

New top-level tab "Tech Analysis", shadcn-styled.

- **Top filter bar:**
  - Universe scope: all enabled / S&P 500 / CAC 40 / held only / manual only
  - Signal type multi-select: Range / Trend / ZigZag / BB Squeeze
  - Date range
- **Tab section:** "Breakouts" | "Consolidations" | "All signals"
- **Signal rows:**
  - Symbol (clickable → opens Epic H Security Detail modal)
  - Signal type badge
  - Fired date
  - Current price
  - Key metric per signal type:
    - Range: zone-broken + breakout %
    - Trend: how many of 4 conditions met
    - ZigZag consolidation: range tightness % + quality score
    - BB Squeeze: BB width as % of historical
  - Confidence/quality score
- Sort by: most recent / highest quality / symbol
- Row click → opens Epic H modal

### Drill-down per-symbol detail page

New route `/tech-analysis/{symbol}` — full-page interactive chart using **lightweight-charts** (TradingView's library):

- Full chart with all MAs as overlay lines
- Detected swing highs/lows annotated
- Active consolidation zone highlighted
- Active breakout zone highlighted with break direction
- Volume bars with avg overlay
- Optional: BB bands shaded
- Sidebar: full analyzer output (port of `analyze_lmt_patterns.py`) — every detected zone, every swing, with strict bi-directional validation commentary

### Configurable parameters

New "Detection settings" sub-section in Configuration tab:

| Param | Default |
|---|---|
| ZigZag deviation | 5% |
| Min consolidation days | 10 |
| Volume confirmation multiplier | 1.5× |
| Volume lookback days | 20 |
| BB Squeeze lookback (months) | 6 |
| Trailing-drawdown threshold for trend invalidation | 8% |

### Endpoints

- `POST /api/sync/breakouts` — run both range + trend detectors over enabled symbols
- `POST /api/sync/consolidations` — run ZigZag + BB Squeeze
- `POST /api/sync/support-resistance` — compute technical S/R for all enabled symbols
- All wired into `/api/sync/full` orchestrator
- `GET /api/tech-analysis/breakouts?signal_type=&date_from=&...` — filtered list
- `GET /api/tech-analysis/consolidations?pattern_type=&...`
- `GET /api/tech-analysis/support-resistance/{symbol}`
- `GET /api/tech-analysis/{symbol}/detail` — full output for the drill-down route (chart bars, all detected zones, analyzer commentary)

## In scope

- Both breakout signals
- ZigZag + BB Squeeze consolidation
- Technical S/R (4 methods)
- Tech Analysis tab UI with filters + 3 tab sections
- Drill-down `/tech-analysis/{symbol}` route
- Configurable parameters in Configuration

## Out of scope

- Options-based S/R → Epic F
- NR7 / VCP / wedges / cup-and-handle / flags / pennants → future
- Backtesting historical signal accuracy → future
- Auto-alerts when signals fire → future
- User-defined custom signals → future

## Stories (provisional)

| ID | Title |
|---|---|
| **E-1** | Schema: `breakout_signals`, `consolidation_patterns`, `support_resistance` tables |
| **E-2** | Range Breakout detector (port `d_breakout_detector_3.py`) |
| **E-3** | Trend Breakout detector (4-condition Stan-Weinstein-style) |
| **E-4** | ZigZag Consolidation detector (port `g_consolidation.py`) |
| **E-5** | BB Squeeze detector |
| **E-6** | Technical S/R: zigzag_swing + ma methods |
| **E-7** | Technical S/R: round_number + volume_profile methods |
| **E-8** | Sync endpoints + orchestrator wiring |
| **E-9** | Tech Analysis tab UI (filter bar + 3 tab sections + clickable rows) |
| **E-10** | Drill-down `/tech-analysis/{symbol}` route with lightweight-charts |
| **E-11** | Configurable detection parameters in Configuration tab |
| **E-12** | End-to-end smoke test against real data |

## Acceptance criteria

- [ ] Range Breakout detector finds known historical breakouts (verify against ATRA / NVDA / etc. in DB)
- [ ] Trend Breakout 4-condition logic correct (test with synthetic series for each true/false combination)
- [ ] BB Squeeze flags symbols with width at multi-month low
- [ ] Tech Analysis tab loads and renders in <500ms after data is synced
- [ ] Click on signal row opens Epic H modal
- [ ] Drill-down chart renders correctly with all overlays
- [ ] Configurable params take effect on next sync

## Dependencies

- Epic C (universe, market_data)
- Epic D (indicators)
- Epic H (clickable rows need somewhere to land)

## Risks

| Risk | Mitigation |
|---|---|
| ZigZag false positives | Reuse the existing strict bi-directional validation from `analyze_lmt_patterns.py` |
| Compute time scales with universe × timeframes (60d for 600 symbols × 3 timeframes) | Profile after Story C; optimize via vectorized pandas + multiprocessing if needed |
| lightweight-charts has a learning curve vs Recharts | Recharts can be the v1 fallback if tight on time; lightweight-charts in v2 |

## Reference

- `Claude/tradingoff/scripts/techanal/d_breakout_detector_3.py`
- `Claude/tradingoff/scripts/techanal/g_consolidation.py`
- `Claude/tradingoff/scripts/techanal/analyze_lmt_patterns.py`
- `Claude/tradingoff/scripts/techanal/y_consolidation_config.py` (parameter defaults)
