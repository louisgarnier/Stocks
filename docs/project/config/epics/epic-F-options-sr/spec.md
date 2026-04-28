# Epic F — Options S/R + Polish

**Status:** [ ] Pending (no plan yet — written when Epic E ships)

## Goal

Add the second method of S/R detection — what market makers actually defend, derived from options open interest. Plus chart polish on the Tech Analysis tab. The "agreement zone" between technical S/R (Epic E) and options S/R (this epic) becomes the high-confidence layer.

## What this epic delivers

### Options data ingestion

- yfinance `Ticker.option_chain(expiry)` returns `calls` + `puts` DataFrames with: `strike`, `lastPrice`, `bid`, `ask`, `openInterest`, `volume`, `impliedVolatility`
- New `options_snapshots` table:
  - `(symbol, expiry, snapshot_at, strike, type, open_interest, volume, iv, last_price)`
  - One row per strike per expiry per snapshot_at
- **Snapshot only** — yfinance doesn't provide historical chains. Caveat surfaced in UI.
- Refresh: `POST /api/sync/options` (manual button + part of `/api/sync/full`)
- Refresh frequency: nightly typical; daily acceptable (quotes are 15-min delayed regardless)

### Options-based S/R computation

Adds three new methods to the existing `support_resistance` table (from Epic E):

| Method | Computation |
|---|---|
| `options_max_pain` | Strike where total option intrinsic value is min for the nearest expiry. Magnet-toward-this-level near expiration. Formula: for each strike, total pain = sum over all calls/puts of intrinsic value × OI; pick min. |
| `options_call_wall` | Top-N call OI strikes per expiry. Each strike → resistance level. Configurable N (default 3). |
| `options_put_wall` | Top-N put OI strikes per expiry. Each strike → support level. |

Per-expiry granularity:
- Nearest weekly expiry (most reactive)
- Nearest monthly expiry (third Friday standard)
- Optional: long-dated (LEAPS) for big-picture levels

### UI on Tech Analysis tab

- Chart layer toggles in `/tech-analysis/{symbol}`:
  - ☐ Technical S/R (Epic E)
  - ☐ Options S/R (this epic)
  - ☐ Both (default)
- **Agreement highlight:** when a technical level and an options level are within ±2% of each other → render as a thicker band with a "🎯 confluence" badge
- Per-symbol detail panel: expandable section listing
  - Options walls per expiry (table: expiry / strike / OI / call vs put)
  - Max pain per expiry (table)

### Chart polish (the "polish" part of this epic)

- Migrate Tech Analysis full-page chart from Recharts (Epic E v1) → **lightweight-charts** (TradingView-style)
- Annotate breakout/consolidation zones on the chart
- Show all S/R levels as horizontal lines with method-color encoding:
  - Technical zigzag: solid line
  - Technical MA: dashed line
  - Round number: dotted line
  - Volume profile: thick translucent band
  - Options call wall: red dashed
  - Options put wall: green dashed
  - Max pain: orange diamond marker
- Persist user's filter + chart layer preferences to `localStorage`

### Caveats surfaced in UI

| Caveat | UX |
|---|---|
| Options data 15-min delayed (free yfinance) | "Last refreshed Xh ago" prominent |
| No historical options chains | Tooltip on max-pain history view: "Showing current snapshot only — historical options data requires paid feed" |
| Thin or missing options for non-US names | Show "No options data available" gracefully; CAC 40 names often skip |

### Endpoints

- `POST /api/sync/options` — ingest current chains for all enabled symbols with options
- `GET /api/options/{symbol}/walls?expiry=` — call/put wall list
- `GET /api/options/{symbol}/max-pain?expiry=` — max pain per expiry

## In scope

- Options chain ingestion via yfinance (snapshot)
- Max pain + call/put wall computation
- New methods added to existing `support_resistance` table
- Tech Analysis chart polish (lightweight-charts + layer toggles + agreement highlight)
- Caveats surfaced in UI

## Out of scope

- Gamma exposure / GEX calculation — deeper math, future
- Historical options chains — requires paid feed (Polygon, ORATS, etc.)
- Greeks calculation per strike (delta, gamma, vega) — future
- Options strategy P&L visualization — future
- Direct order routing for options trades — never (out of project scope)

## Stories (provisional)

| ID | Title |
|---|---|
| **F-1** | Schema: `options_snapshots` table |
| **F-2** | yfinance options chain ingestor (per-symbol, all enabled symbols with options data) |
| **F-3** | Max pain computation per expiry |
| **F-4** | Call/put wall computation per expiry (top-N OI strikes) |
| **F-5** | Add to `support_resistance` write path: `options_max_pain` / `options_call_wall` / `options_put_wall` methods |
| **F-6** | `POST /api/sync/options` endpoint, wire into `/api/sync/full` |
| **F-7** | `GET /api/options/{symbol}/walls` and `/max-pain` read endpoints |
| **F-8** | Migrate Tech Analysis full-page chart to lightweight-charts |
| **F-9** | Layer toggles + agreement highlight |
| **F-10** | Per-symbol options detail panel (walls per expiry, max pain table) |
| **F-11** | localStorage persistence for chart layer preferences |
| **F-12** | End-to-end smoke test: AAPL/NVDA/SPY (high-OI names guaranteed to have options data) |

## Acceptance criteria

- [ ] Options sync completes for ~50 high-liquidity US symbols in <60s
- [ ] Max pain per expiry matches manual calculation
- [ ] Call/put walls correctly identified as top-N OI
- [ ] `support_resistance` table contains all 7 method types after Epic E + Epic F
- [ ] Tech Analysis chart with layer toggles renders correctly
- [ ] Agreement zones (technical + options within 2%) visually emphasized
- [ ] CAC 40 / non-liquid symbols handle "no options data" gracefully

## Dependencies

- Epic C (universe, market_data)
- Epic E (Tech Analysis tab + `support_resistance` table + drill-down chart)

## Risks

| Risk | Mitigation |
|---|---|
| yfinance options data quality (occasional NaN OI, missing strikes) | Filter NaN, log per-symbol failures |
| Snapshot-only data limits backtesting | Documented in PRD constraints; paid feed migration path noted |
| OI of all 0s for thin names → degenerate max pain | Skip symbols with total OI < threshold (e.g., 1000) |
| lightweight-charts library has a learning curve | Allocate 1-2 stories to chart migration; keep Recharts as fallback path if blocked |

## Reference

- yfinance docs: https://github.com/ranaroussi/yfinance/wiki
- Max pain methodology: standard options theory (sum of put OI below strike + sum of call OI above strike, weighted by distance)
- TradingView lightweight-charts docs: https://tradingview.github.io/lightweight-charts/
