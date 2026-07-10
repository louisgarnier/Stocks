# Wireframe Audit — 2026-07-10 (Phase B)

Screenshots: `docs/project/config/wireframe-audit/` (live app, real data, 2026-07-10 evening).

## A. Current state — screen inventory

### Header (all screens)
Sync IBKR button · "Last sync: 11h ago" chip · "Connecté" status. **Language mix** (Connecté / Précédent / Quantité vs English everywhere else).

### 1. Positions tab (default landing) — `wf_1_positions.png`
- Summary cards: Open Positions (18) · Holdings with sell signals (15 of 18)
- Positions table: Symbol, Qty, Avg Cost, Market Value, Unrealized P&L, Signals pill (▶ expandable "N fired")
- Totals split per currency (USD $117,481.83 / EUR €15,281.64) — **never combined into one net worth**
- Data: `positions_ibkr` + `holding_signals`. As-of labels present (good).

### 2. Transactions tab — `wf_2_transactions.png` + sub-tabs
- Sub-tabs: Original · Split-Adjusted · Corporate Actions
- Raw IBKR ledger, 575 rows, 23 pages — **first page dominated by EUR.USD forex conversions**, actual stock trades buried
- Prominent red **"Delete All Transactions"** destructive button at top right
- Data: `transactions` / `updated_transactions` / `corporate_actions`.

### 3. Browse Universe tab ("Research") — `wf_3_research.png`
**Three stacked sections, ~4 screens tall:**
1. **Research grid** — "one row = all technical + fundamental data" (R-3). Toolbar (Fundamentals · Technical · Compute · Run all), filter chips, Columns picker, CSV export, Tune parameters.
2. **Market Data panel** — coverage stats + **"Sync market data" and "Recompute analytics" buttons that duplicate the toolbar's Technical button** (and are the pre-R-3 generation of it).
3. **Old Browse Universe grid** — a SECOND 561-row table (Symbol, Sources, Cur, Bars, Last close, MA50, RSI, MRSI) — **~80% column overlap with the Research grid above it**. R-3 retired the Screener tab but not this list.

### 4. Detail sheet (row click) — `wf_4_detail_sheet.png`
About · Position · Indicators (as-of date ✓) · Fundamentals · Transactions · Recent bars. Well-structured, honest dating. Best screen in the app.

### 5. Configuration tab — `wf_5_configuration.png`
Tracked Universe (index toggles + custom tickers) · Fundamentals cadence panel (**another** "Refresh fundamentals" button) · DB status card · CSV import / Flex queries / Export · Sync Runs log (excellent, hidden here).

## B. Data-to-screen matrix

| Data family | Source table | Shown in | Issue |
|---|---|---|---|
| Positions + P&L | positions_ibkr | Positions | No %-return, no weight, no combined net worth, no realized P&L |
| Sell signals (holdings) | holding_signals | Positions (pills) | Invisible anywhere else; not on dashboard-level |
| Transactions | transactions/updated_transactions | Transactions | Forex noise buries trades; no per-symbol grouping/realized P&L |
| Corporate actions / splits | corporate_actions | Transactions sub-tab | OK |
| Prices/indicators | market_data, indicators | Research grid, old universe grid, detail sheet | **Duplicated across two grids in the same tab** |
| Screener signals/momentum | screen_signals | Research grid (columns) | OK (many off by default — fine) |
| Consolidation/breakout | consolidation_patterns, breakout_signals | Research grid | ZigZag columns empty at default gates (audit Rec) |
| Fundamentals + gates | fundamentals | Research grid + detail sheet | OK |
| Scores/verdict (buy-side) | screen_scores | Research grid | **Buy candidates never surfaced outside the grid** |
| Sync status/history | sync_runs | Config (log), header (IBKR only), Market Data panel | Fragmented across 3 places |
| Universe membership | tracked_universe | Config (manage) + old universe grid (browse) | Same entity in two tabs |

**Sync entry points: 9 buttons in 4 locations** (header Sync IBKR · toolbar ×4 · Market Data panel ×2 · Config fundamentals refresh + per-index refresh). Post-Phase-A chaining makes most redundant.

## C. Findings (ranked)

1. **No portfolio overview exists.** Nothing answers "how am I doing?" — no net worth (currencies never combined), no allocation, no performance vs benchmark, no top/flop. This is the gap your Holistic/Finanzfluss references fill.
2. **Browse Universe tab is three generations of UI stacked.** Research grid (new) + Market Data panel (old) + Browse Universe list (old) = two 561-row tables and duplicate sync buttons on one page. Retire the two old sections.
3. **Buy-side and sell-side never meet.** Sell signals live on Positions; buy verdicts live in the Research grid. No single "what should I act on today?" surface — the core buy/sell strategy view is missing.
4. **Transactions is a raw ledger, not a journal.** Forex conversions drown trades; no realized P&L per trade/symbol (FIFO module planned); "Delete All" is one click from data loss.
5. **Sync UX is fragmented.** 9 buttons / 4 places / 3 status displays; Sync Runs log (the best diagnostic) is buried in Configuration.
6. **Universe management is split** between Configuration (manage) and Browse Universe (browse-lite duplicate).
7. **Language mix** French/English across all screens.
8. **No staleness surfacing** beyond Positions/detail-sheet as-of labels (audit Rec-5).

## D. Proposed target IA (brief for Phase C)

```
┌────────────────────────────────────────────────────────┐
│ 1 DASHBOARD (new, default)                              │
│   Net worth (combined ccy, FX-converted) + day change   │
│   Allocation donut (position / sector / currency)       │
│   Perf line: portfolio vs ^GSPC (needs value history)   │
│   Top/Flop movers today (held)                          │
│   ACTION QUEUE: sell signals fired (holdings)           │
│              + top buy candidates (score/verdict)       │
│   Sync health chip (last sync per data family)          │
├────────────────────────────────────────────────────────┤
│ 2 PORTFOLIO  = today's Positions + weight%, return%,    │
│   cost basis, realized P&L (FIFO later), signals detail │
├────────────────────────────────────────────────────────┤
│ 3 RESEARCH   = ResearchGrid + toolbar + tuning ONLY     │
│   (kill Market Data panel + old universe list)          │
├────────────────────────────────────────────────────────┤
│ 4 JOURNAL    = Transactions, trades-first (forex behind │
│   filter), per-symbol grouping, CA sub-tab, realized    │
│   P&L when FIFO ships                                   │
├────────────────────────────────────────────────────────┤
│ 5 SETTINGS   = universe mgmt, tuning defaults, sync     │
│   runs log, CSV import/export, destructive ops gated    │
└────────────────────────────────────────────────────────┘
```

**New data requirements for the Dashboard** (backend work, small):
- **Portfolio value history** — daily snapshot table (positions × close, FX-converted); backfillable from existing bars + transactions
- **FX rates** for EUR/USD consolidation (yfinance `EURUSD=X`, already feasible)
- Realized P&L → planned FIFO module (out of scope for v1 dashboard; show unrealized only)

**Migration is mostly deletion + one new screen:** Dashboard (new) · Positions→Portfolio (enrich) · Research (prune two sections) · Transactions→Journal (filter default) · Configuration→Settings (unchanged + gate destructive ops).

## E. Next step (Phase C)
Interactive HTML mockup of the Dashboard (+ pruned Research) in the Holistic/Finanzfluss aesthetic — dark, modern financial app — for approval before any code.
