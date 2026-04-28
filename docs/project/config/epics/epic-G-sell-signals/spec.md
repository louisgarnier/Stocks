# Epic G — Sell Signals on Holdings

**Status:** [ ] Pending (no plan yet — written when Epic D ships)

## Goal

When the user opens the Positions tab, they see at a glance which of their holdings are flashing technical exit signals — without having to chart each one individually. This is the highest-frequency value-add of the whole tech analysis layer for a position-keeping use case.

## What this epic delivers

### Signal library (11 signal types)

| Signal type | Trigger |
|---|---|
| `ma50_break` | Latest close < MA50 |
| `ma100_break` | Latest close < MA100 |
| `ma150_break` | Latest close < MA150 |
| `ma200_break` | Latest close < MA200 |
| `death_cross` | MA50 crosses below MA150 today (was ≥ yesterday) |
| `volume_dryup` | 5-day avg volume < 50% of 20-day avg |
| `distribution_day` | Down day on volume > 1.5× 20-day avg |
| `rsi_weakness` | RSI(14) drops below 50 from above (was ≥ 50 yesterday) |
| `mrsi_flip` | MRSI crosses below 0 (was ≥ 0 yesterday) |
| `trailing_drawdown` | Latest close down configurable % from 30-day high (default 10%) |
| `stop_loss` | Latest close down configurable % from `cost_basis_price` (default 8%) |

Each signal is independently toggleable globally; per-position muting is a future enhancement.

### Storage

- `holding_signals` table: `(symbol, signal_type, fired BOOLEAN, value REAL, threshold REAL, last_evaluated_at TIMESTAMPTZ)`
- One row per `(symbol, signal_type)` — UPSERT on each evaluation
- Only symbols currently in `positions_ibkr` get rows; sold-out symbols' signals are deleted on next sync

### Compute

- `POST /api/sync/holding-signals` — recomputes all signals for current holdings
- Wired into `/api/sync/full` orchestrator after `indicators`
- Reads latest `indicators` row per held symbol + `cost_basis_price` from `positions_ibkr`
- Pure in-memory computation; ~10s for typical 15-position holding

### UI

- Positions tab gets a new "Signals" column with traffic light:
  - 🟢 0 signals fired
  - 🟡 1-2 signals fired
  - 🔴 3+ signals fired
- Click row → expand panel listing fired signals with current value vs threshold
  - Example: "MA50 break: ❌ Price $138.40 vs MA50 $145.20"
- Settings sub-section in Configuration tab to globally toggle signals (which ones to compute) and tune thresholds (`trailing_drawdown` %, `stop_loss` %)

### Endpoints

- `POST /api/sync/holding-signals`
- `GET /api/holding-signals` — all current signals across all holdings
- `GET /api/holding-signals/{symbol}` — signals for one symbol
- `POST /api/holding-signals/settings` — update thresholds + which signals are enabled

## In scope

- All 11 signal types
- Traffic-light column on Positions tab
- Click-to-expand details
- Configurable thresholds (per-signal globally) in Configuration tab

## Out of scope

- Per-position muting (future)
- Email / push notifications (future)
- Backtesting signal accuracy (future)
- Buy signals (those live in Epic H Mode B for non-held symbols)
- Custom user-defined signals beyond the 11 (future)

## Stories (provisional)

| ID | Title |
|---|---|
| **G-1** | Schema: `holding_signals` table + settings table for thresholds |
| **G-2** | Signal compute library (11 signal evaluators, pure functions) |
| **G-3** | `POST /api/sync/holding-signals` endpoint, wire into orchestrator |
| **G-4** | `GET /api/holding-signals` read endpoint |
| **G-5** | Positions tab Signals column + expand panel (shadcn Collapsible) |
| **G-6** | Configuration: signals settings sub-section (toggle + thresholds) |
| **G-7** | End-to-end smoke test |

## Acceptance criteria

- [ ] All 11 signals computed correctly against test fixtures (synthetic price series)
- [ ] Sold-out symbols have their signal rows deleted on next sync
- [ ] Positions tab traffic light renders correctly per holding
- [ ] Click-to-expand shows fired signals with values
- [ ] Threshold changes in Configuration take effect on next sync
- [ ] Sync time <10s for typical 15-holding portfolio

## Dependencies

- Epic C (positions_ibkr, market_data)
- Epic D (all indicators must be computed before signals can evaluate)

## Risks

| Risk | Mitigation |
|---|---|
| Signal threshold tuning is subjective; defaults may fire too often or too rarely | Defaults chosen from common practice; user can tune in Configuration |
| MRSI signal requires sufficient historical data; new IPOs won't have it | NULL-handling: signal returns "not enough data" and is treated as not-fired |
| `death_cross` and `mrsi_flip` are crossover events (yesterday vs today), not levels | Compute requires 2 latest indicator rows, not just 1 |
