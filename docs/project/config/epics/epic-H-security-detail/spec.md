# Epic H — Security Detail View

**Status:** [ ] Pending (no plan yet — written when Epic G ships)

## Goal

Universal modal/side-panel that opens when clicking any symbol anywhere in the app (Positions, Transactions, Tech Analysis screener results, Configuration manual ticker badge). Adapts based on whether the user holds the security: held → Mode A, not held → Mode B. The single drill-down UX for everything.

## What this epic delivers

### Mode A — Held position

User clicks a symbol in `positions_ibkr`. Modal shows:

- **Mini price chart** (last 6-12 months) using Recharts
  - Overlays: MA50, MA100, MA150, MA200
  - Optional: Bollinger Bands shaded region
  - User's buy/sell trades plotted as dots on the chart (green/red, sized by qty)
- **Position summary card** (read from `positions_ibkr`):
  - Quantity held, avg cost (`cost_basis_price`), market value, unrealized P&L
- **Transaction history table** (read from `transactions` filtered by symbol):
  - Date / qty / price / side / source_file
- **Sell simulator card:**
  - Inputs: quantity (number input, default = held qty), target price (number, default = `mark_price`)
  - Output: gross realized P&L = `qty * (sell_price - cost_basis_price)`, fees-adjusted P&L estimate (subtract `cost_basis_price * 0.001` per share as IBKR-style commission), remaining position
  - **v1 limitation footnote:** "Uses weighted-average cost basis. Lot-level FIFO simulation will arrive with the FIFO module."
- **Sell signal checklist** (from Epic G):
  - Each signal as a card with ✅/❌ + current value vs threshold
  - Example: "MA50 break: ❌ ($138.40 vs MA50 $145.20)"
  - Muted signals shown grayed out
- **Open in Tech Analysis** button → routes to `/tech-analysis/{symbol}` (full chart, Epic E)

### Mode B — Not held

User clicks a symbol that's NOT in `positions_ibkr` (e.g., from screener results, manual universe, search). Modal shows:

- **Mini price chart** with same MA overlays as Mode A (no trade markers, no BB bands by default)
- **Buy signal checklist** — entry-side flip of indicator framework:
  - Price > MA150 (long-term uptrend): ✅/❌
  - MA50 sloping up (short-term trend): ✅/❌
  - Price > MA50 (short-term confirmation): ✅/❌
  - Above breakout zone resistance (when Epic E ships): ✅/❌ — surfaces if active range/trend breakout signal
  - MRSI > 0 (outperforming benchmark): ✅/❌
  - RSI(14) in 40-65 (not overbought, not oversold): ✅/❌
  - Volume picking up (latest > volume_ma_20): ✅/❌
- **Quick stats card:**
  - Market cap (from yfinance Ticker.info), sector, currency, 52-week range, distance from MA200 (%), distance from 52w high (%)
- **Add to manual universe** button (if not already tracked) — calls `POST /api/universe/manual`
- **Open in Tech Analysis** button → `/tech-analysis/{symbol}`

### Common to both modes

- All checks rendered as **independent toggleable cards**
- Future fundamental cards (P/E vs sector, ROE vs sector, etc.) slot in alongside as additional cards — Epic placeholder for fundamental analysis future module
- Modal closes via X / ESC / click-outside
- shadcn `<Sheet>` (right-side slide-in) for desktop; full-screen on smaller windows
- One backend call: `GET /api/security/{symbol}/detail` returns ALL data needed for the modal

### New endpoint

```
GET /api/security/{symbol}/detail
{
  "symbol": "AAPL",
  "is_held": true,
  "position": { ... } | null,           // positions_ibkr row if held
  "transactions": [ ... ],              // filtered transactions table
  "indicators_latest": { ... },         // latest indicators row
  "signals": [ ... ],                   // holding_signals rows for held symbols
  "buy_signals": { ... },               // computed at request time for non-held
  "stats": { market_cap, sector, ... }, // yfinance Ticker.info subset
  "chart": { bars: [...], buy_markers: [...], sell_markers: [...] }
}
```

## In scope

- Both Mode A and Mode B
- Single modal component, mode-switched by `is_held` flag
- Triggered from any symbol click in the app
- shadcn Sheet/Dialog
- Recharts for mini chart
- Sell simulator with avg-cost (v1 limitation explicit)
- All buy signal checks listed above
- "Add to manual universe" CTA in Mode B if symbol not tracked

## Out of scope

- Lot-level FIFO sell simulation → future FIFO module
- Fundamental signal cards → future Fundamental Analysis epic
- Real-time price streaming during modal session — uses last sync data
- Trade execution from modal (not building any order routing)
- Custom chart annotations / drawing tools
- Multi-symbol comparison (compare AAPL vs MSFT side-by-side)

## Stories (provisional)

| ID | Title |
|---|---|
| **H-1** | `GET /api/security/{symbol}/detail` endpoint (combines positions / transactions / indicators / signals into one response) |
| **H-2** | yfinance Ticker.info → `stats` cache table (avoid hitting yfinance per modal open) |
| **H-3** | Modal component skeleton (shadcn Sheet) with mode switching |
| **H-4** | Mode A: position summary + transaction history + sell signal checklist |
| **H-5** | Mode A: sell simulator |
| **H-6** | Mode A: mini chart with MAs + trade markers (Recharts) |
| **H-7** | Mode B: buy signal checklist + quick stats card |
| **H-8** | Mode B: chart (no trade markers, no BB bands by default) |
| **H-9** | "Open in Tech Analysis" link (placeholder route, full implementation in Epic E) |
| **H-10** | "Add to manual universe" CTA in Mode B |
| **H-11** | Wire modal to symbol clicks throughout app (Positions, Transactions, Configuration badge list) |
| **H-12** | End-to-end smoke test |

## Acceptance criteria

- [ ] Click any symbol anywhere → modal opens within 500ms
- [ ] Mode A vs Mode B detection automatic based on `positions_ibkr` membership
- [ ] Sell simulator P&L matches manual calculation
- [ ] Buy signal checklist accurate against indicator values
- [ ] Mini chart renders with MA overlays
- [ ] Modal closes via X / ESC / click-outside
- [ ] No layout shift while data loads (skeleton states)
- [ ] Backend endpoint `GET /api/security/{symbol}/detail` returns complete payload in <300ms

## Dependencies

- Epic C (positions, transactions, market_data)
- Epic D (indicators)
- Epic G (sell signals for Mode A; buy signals for Mode B reuse indicator data directly)

## Risks

| Risk | Mitigation |
|---|---|
| Modal data payload large (especially chart bars) | Limit chart to 6-12 months by default; user can expand later |
| yfinance Ticker.info is slow + rate-limited | Cache in `stats` table, refresh weekly via sync step |
| Sell simulator confusion: avg-cost vs FIFO | Explicit footnote + tooltip; FIFO upgrade path documented |
| "Open in Tech Analysis" requires Epic E to be useful | Epic E ships next (or H delivers a placeholder route) |

## Reference

- Stan Weinstein-style trend setup (informs buy signal criteria): see Epic E spec for the 4-condition Trend Breakout
- Existing sell-simulator math: gross P&L = `qty * (sell - cost_basis_price)`; fees ≈ 0.1% of notional (IBKR commission ballpark)
