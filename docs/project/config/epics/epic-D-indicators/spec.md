# Epic D — Indicators

**Status:** [ ] Pending (no plan yet — written when Epic C ships)
**Stories:** TBD when plan written

## Goal

Compute the technical indicators that downstream stories (G sell signals, H buy signals, E breakouts, F options) depend on. Incremental compute — only stale symbols, only new dates.

## What this epic delivers

### Indicators table

Single `indicators` table keyed by `(symbol, time)` with columns:

| Column | Indicator | Formula |
|---|---|---|
| `ma_50` | MA 50 | `close.rolling(50).mean()` |
| `ma_100` | MA 100 | `close.rolling(100).mean()` |
| `ma_150` | MA 150 | `close.rolling(150).mean()` |
| `ma_200` | MA 200 | `close.rolling(200).mean()` |
| `bb_upper_20` | Upper Bollinger Band | `MA(20) + 2 * stddev(close, 20)` |
| `bb_lower_20` | Lower Bollinger Band | `MA(20) - 2 * stddev(close, 20)` |
| `bb_width` | BB width | `(upper - lower) / MA(20)` |
| `rsi_14` | Relative Strength Index | standard 14-period RSI (0-100 scale) |
| `mrsi` | **Mansfield Relative Strength** | `((stock_close / benchmark_close) / MA(stock/benchmark, 252) - 1) * 100`. Centered at 0; positive = outperforming benchmark |
| `atr_14` | Average True Range | 14-period ATR |
| `volume_ma_20` | 20-day average volume | `volume.rolling(20).mean()` |

### MRSI specifics (the new one)

- **NOT regular RSI.** Different indicator.
- Per-symbol benchmark assigned at universe seed time:
  - Currency USD → benchmark `^GSPC` (S&P 500)
  - Currency EUR → benchmark `^FCHI` (CAC 40)
  - Currency GBP → benchmark `^FTSE` (FTSE 100)
  - Currency other → fallback to `^GSPC`
- Pre-req: benchmark symbols themselves must be in `tracked_universe` with market data ingested. Story D auto-seeds them.
- Formula: `RS = stock_close / benchmark_close` (point-in-time ratio); `RS_MA = MA(RS, 252)` (52-week trailing); `MRSI = ((RS / RS_MA) - 1) * 100`
- 252 trading days is approximate (varies by year due to holidays); acceptable.

### Endpoints

- `POST /api/sync/indicators` — incremental recompute
- `GET /api/indicators/{symbol}?from=&to=&limit=` — read latest indicator rows
- Wired into `/api/sync/full` orchestrator as a step after `market-data`

### Compute strategy

For each enabled symbol:
1. `SELECT MAX(time) FROM indicators WHERE symbol = ?` → latest computed
2. If missing or stale relative to `market_data`, pull bars from `market_data` starting at `latest_indicator_time - 200 days` (need pre-context for MA200 computation)
3. Compute all indicators via pandas rolling windows
4. `INSERT INTO indicators ... ON CONFLICT (symbol, time) DO UPDATE SET ...` for ALL the indicator columns (allows partial recomputes)
5. Special handling for MRSI: pull benchmark bars over the same date range, align by `time`, compute the ratio, then 252-day MA

## In scope

- All 11 indicator columns above
- Incremental compute (skip up-to-date symbols)
- Auto-seed benchmarks (`^GSPC`, `^FCHI`) into `tracked_universe` if not already present
- Wired into `/api/sync/full`

## Out of scope

- Advanced indicators (MACD, Stochastic, OBV, Ichimoku, etc.) — add later if a specific signal needs them
- Streaming / realtime indicator updates
- Per-symbol custom indicator parameters (MA window override, etc.)
- Multi-resolution (intraday, weekly) — daily only in v1

## Stories (provisional, refined when plan is written)

| ID | Title |
|---|---|
| **D-1** | Schema: `indicators` table |
| **D-2** | Auto-seed benchmark symbols (`^GSPC`, `^FCHI`, `^GDAXI`, `^FTSE`) into `tracked_universe` |
| **D-3** | Indicator compute service (MA + BB + RSI + ATR + Volume MA) |
| **D-4** | MRSI compute service (uses benchmark per symbol) |
| **D-5** | `POST /api/sync/indicators` endpoint, wire into `/api/sync/full` |
| **D-6** | `GET /api/indicators/{symbol}` read endpoint |
| **D-7** | End-to-end smoke test: full sync, verify indicators populated for held positions |

## Acceptance criteria

- [ ] All 11 indicator columns populated for every enabled symbol with sufficient `market_data` history
- [ ] MRSI requires ≥252 days of stock + benchmark data; for symbols with less history, MRSI is NULL (not zero)
- [ ] Symbols with insufficient data for MA200 (<200 days) have NULL for MA200 only; shorter MAs still computed
- [ ] Recompute is incremental — running twice doesn't change row count, only refreshes if `market_data` newer
- [ ] Sync time for full universe (~600 symbols) <60s after first run

## Dependencies

- Epic C (needs `tracked_universe`, `market_data`)

## Risks

| Risk | Mitigation |
|---|---|
| MRSI for non-USD stocks needs benchmark data; benchmark might be missing if user only enabled `sp500` | Auto-seed all 4 benchmarks regardless of which indices are enabled |
| Pandas rolling on 1.5M rows may be slow if not vectorized properly | Process per-symbol, smaller frames; reuse the existing `c_mma.py` pattern from tradingoff |
| Dividend-adjusted close vs raw close — which one for MA computation? | Use `adj_close` for MAs (matches yfinance convention, smooths splits/dividends) |

## Reference

- Existing tradingoff script for MA: `Claude/tradingoff/scripts/techanal/c_mma.py`
- Mansfield Relative Strength tutorial: see PRD §3 user story US-07
