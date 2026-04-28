# Brainstorm — IBKR Portfolio Tracker

> Stage 1 output. Source-of-truth for the project vision before requirements are detailed.
> Status: **GO**

---

## 0. Freeform Input

A solo investor who trades through Interactive Brokers (IBKR) keeps asking himself the same questions across separate tools: "What do I hold right now? What did I buy/sell? Are any of my positions about to break down? What looks interesting to enter? What did this stock do today?" Each question lives in a different tab — IBKR's own portal, a chart on TradingView, a yfinance script, a CSV from accounting. He wants ONE app that pulls his real holdings + transactions from IBKR, layers the technical analysis he actually uses, and surfaces actionable signals for his current positions and his watchlist.

Personal use, not multi-user. Local data, no cloud commitment. Already built: the IBKR sync pipeline (positions + trades + corporate actions + split-adjustments, all reconciled). What's missing: the analysis layer (price data, indicators, breakout/consolidation detection, sell signals on holdings, security detail drill-down) and a polished UI that doesn't look like a 2010 dashboard.

Future direction: technical analysis tab, fundamental analysis tab (port from old `Automated-Fundamental-Analysis` repo, finviz → yfinance), watchlist, FIFO lot tracking. Not building any of those today — just naming so we don't paint ourselves into a corner.

---

## 1. The One-Liner

**Stocks** is a local-first FastAPI + Next.js app that tracks an IBKR portfolio and surfaces technical analysis signals (breakouts, sell triggers, S/R levels) for the holdings + a configurable universe.

---

## 2. The Problem

- **Who has this problem?** Solo IBKR account holders who manage their own portfolio and use technical analysis to time entries/exits but find IBKR's UI minimal and external TA tools disconnected from their actual holdings.
- **How are they solving it today?** Manually flipping between IBKR portal (positions + trades), TradingView/yfinance (charts + indicators), spreadsheets (P&L tracking), various Python scripts (breakout detectors, sector rotation). No single place ties their actual holdings to the technical signals affecting them.
- **Why is the current solution inadequate?** Disconnected: a breakout signal on AAPL means nothing if you can't immediately see whether you hold AAPL, what your cost basis is, and what you'd realize if you sold today. Sell signals get missed because nobody's actively running an MA50-break check against your specific holdings every day.
- **How often does this problem occur?** Daily during active trading windows. Position-management blind spots compound over weeks (e.g., a slow MA-break that crosses while you're not looking).

---

## 3. The Solution

### Core workflow (user's journey)

1. **Sync** — One-click "🔄 Sync IBKR" pulls latest trades + positions from IBKR Flex API, refreshes corporate actions from yfinance, applies splits to historical transactions, ingests price bars for the tracked universe, recomputes indicators, and refreshes signals.
2. **Holdings view** — Positions tab shows current holdings with reconciled qty/value/P&L straight from IBKR + a Signals column flagging which holdings are flashing exit signals (price < MA50, volume drying up, MRSI flipping negative, etc).
3. **Click any symbol** — Security Detail modal opens. If held: chart with MAs, transaction history, sell simulator (realized P&L per qty/price), sell-signal checklist. If not held: chart, buy-signal checklist, quick stats.
4. **Tech Analysis tab** — Screen the broader universe (S&P 500 + CAC 40 + held + manual additions) for range breakouts, trend breakouts, consolidations, and S/R levels (technical + options-based). Click a row → detail modal.
5. **Configuration tab** — Toggle which indices to track, add custom tickers, run individual sync steps, view import logs.

### What makes this different from alternatives

- **Holdings ⇄ Signals are first-class** — most TA tools show signals for the whole market and leave you to filter; this one runs sell-signal checks on the symbols you ACTUALLY hold and surfaces them on the page you live in (Positions).
- **Two breakout signals, not one** — Range Breakout (range-broken-with-volume) for setups that just released, AND Trend Breakout (price > MA150 + MA50↑ + price > MA50 + high vol) for sustained-uptrend confirmation. Different mental models, both useful.
- **Two S/R methods compared side-by-side** — Technical (swing zones / MAs / round numbers / volume profile) AND Options-derived (max pain / call walls / put walls). When they agree → high-confidence zone; when they disagree → instructive.
- **MRSI (Mansfield Relative Strength)** baked in as a first-class indicator — a stock vs benchmark relative-strength score, NOT regular RSI. Tells you whether a holding is leading or lagging the market.
- **Sell simulator on every holding** — pick qty + price, see realized P&L instantly. v1 uses weighted avg cost; FIFO upgrade comes when the FIFO module ships.
- **No cloud lock-in** — local SQLite, all data on the user's Mac, no account required.

---

## 4. Assumptions & Risks

| Assumption | Risk if Wrong | Mitigation |
|---|---|---|
| IBKR Flex Query API stays available + the user's token doesn't expire | Sync breaks; fall back to CSV upload | Already built CSV upload path; surface clear errors when Flex 401s |
| yfinance remains free and stable for OHLCV + corporate actions + options chains | All TA depends on yfinance; rate limits or shutdown breaks everything | Cache aggressively, backoff on errors. Switch to paid feed (Polygon, Tiingo) if yfinance becomes unreliable. |
| Wikipedia tables for index constituents (S&P 500, CAC 40) stay stable | Universe seeders break | Seeders are isolated; can swap to alternate source (iShares ETF holdings CSV) without touching the rest |
| Solo-user, single-machine, single-DB | No multi-user / cloud requirements bite us | Doc'd as out-of-scope. Migration plan to Supabase exists if reconsidered. |
| Cost-basis from IBKR is authoritative; no need to re-derive | If IBKR cost basis is wrong, we surface the wrong P&L | Trust IBKR's `cost_basis_money` for now; FIFO module will provide an independent verification path |
| 252 trading days/year is close enough for MRSI normalization | Minor MRSI calibration error for holiday-heavy years | Acceptable; signal is direction-of-trend, not precise threshold |
| Technical S/R + options S/R complement each other | If they disagree systematically, comparison view gives noise | Worth shipping; agreement filter is the high-confidence layer |

---

## 5. Feasibility Check

| Dimension | Assessment | Notes |
|---|---|---|
| **Technical complexity** | Medium-high | Most components solved by existing scripts in `Claude/tradingoff/scripts/` (breakout, consolidation, ZigZag, MAs); main work is integration + UX. |
| **Time estimate (MVP)** | ~2-3 weeks of evening sessions, broken across 6 epics (C/D/G/H/E/F) | Each epic is 1-3 days of work + tests + smoke verification. |
| **Dependencies / blockers** | yfinance, Wikipedia, IBKR Flex (existing) | All free. No paid feed required for v1. |
| **Skills gap** | None major — TypeScript/React, Python/FastAPI, SQL all well-trodden | Tailwind v4 + shadcn/ui is new but well-documented. |
| **Maintenance burden** | Low | No realtime streaming, no auth, no multi-tenancy, no cloud hosting. Local app run on demand. |

---

## 6. Go / No-Go Decision

### What does success look like?

- **Minimum (MVP done):** Story C (Foundation) + Story D (Indicators) + Story G (Sell signals) + Story H (Security Detail) shipped. User can: click any holding → see chart + transactions + sell simulator + signal checklist. Sell signals visible at a glance on Positions tab.
- **Full success:** All 8 epics shipped (A through H). Tech Analysis tab + Options S/R + drill-down detail page. Daily workflow: open app → glance at Positions/Signals column → click anything red → decide → done.
- **Failure looks like:** signals fire incorrectly often enough that user stops trusting them; OR ingestion is so slow that sync becomes a chore; OR the UI still looks like a 2010 dashboard after a story-B-style polish pass.

### Decision

**[x] GO** — All 8 epics scoped. Foundations (A, B) already shipped. Architecture works. Risks all have mitigation paths. Investment of 2-3 weeks of evenings is in line with the value (replacing 4-5 disconnected tools with one).

### Rationale

The disconnect between "what I hold" and "what the technicals say about it" is the real productivity loss. Building this internally also doubles as a learning vehicle — every component I implement myself I understand, vs paying for TradingView + IBKR's portal + spreadsheets and still having to glue them mentally.

---

*→ Proceed to `2-PRD.md` → `config/prd.md`*
