# Project Review — IBKR Portfolio Tracker

**Date:** 2026-04-27
**Scope:** Functional + code review of the three pillars: Holdings, Transactions, Reconciliation.
**Goal:** Identify what works, what's broken, and concrete optimization targets.

---

## 1. Holdings

The "source of truth" side: the IBKR position snapshot, stored locally and displayed in the Positions tab.

### 1.1 Data flow

```
IBKR Flex Query API (XML)
  └─> parse_positions_from_xml()        backend/scripts/fetch_flex_trades.py:207
        └─> save_positions_ibkr()       backend/scripts/fetch_flex_trades.py:253
              └─> positions_ibkr table  schema.sql:149
                    └─> GET /api/positions  routes/positions.py:13
                          └─> Positions tab  app/page.tsx:1932
```

A single Flex Query response carries **both trades AND open positions**. They're parsed in one pass and saved into two separate tables. The IBKR snapshot is **wiped + reinserted** on every import (`DELETE FROM positions_ibkr` then `INSERT`).

### 1.2 What's stored

`positions_ibkr` (per symbol): `quantity`, `cost_basis_money`, `cost_basis_price`, `mark_price`, `position_value`, `unrealized_pnl`, `currency`, `asset_category`, `last_updated`.

Pulled directly from IBKR Flex XML attributes — no derivation, no transformation.

### 1.3 Current state

- 15 open positions in DB.
- All 15 reconcile clean on quantity (0.00 diff).
- IBKR cost basis values are loaded but **never compared** against locally-computed cost.

### 1.4 Findings

**F1.1 — "Refresh holdings" is conflated with "import trades."**
There is no endpoint that re-fetches *only* the IBKR position snapshot. To update holdings, you must run a full Flex import which also re-ingests trades. If positions move intraday but no new trades happened, the snapshot still goes stale until the next trade-import cycle. Two options: (a) call Flex with a positions-only query ID, (b) accept the coupling and rename the UI to make it clear ("Sync from IBKR" rather than implying granular control). [`fetch_flex_trades.py:739-744`](../../../backend/scripts/fetch_flex_trades.py#L739-L744)

**F1.2 — DELETE+INSERT loses history.**
Each Flex sync wipes `positions_ibkr` entirely. There's no time-series of holdings — you can never answer "what did I hold on March 12?" Even if not needed today, the destructive overwrite forecloses any future P&L-over-time chart. Cheap fix: append-with-timestamp instead of replace, or keep current table as "latest" and add a `positions_ibkr_history` snapshot table on each sync. [`fetch_flex_trades.py:270`](../../../backend/scripts/fetch_flex_trades.py#L270)

**F1.3 — `last_updated` is per-row but always identical.**
Every row gets the same `now` timestamp because the whole table is rewritten in one transaction. The column adds no information — the table-level "last sync time" would be cleaner as a single row in a `sync_status` table or a constant returned from the API.

**F1.4 — No Holdings refresh independent of recalc.**
The Positions tab has one button: "🔄 Recalculate Rec" → hits `/api/positions/refresh` → recalculates `positions_calculated` from existing transactions. Nothing in the UI re-fetches the IBKR snapshot. Users have to go to the Load tab and run a Flex import. This is non-obvious. [`page.tsx:1944-1962`](../../../frontend/app/page.tsx#L1944-L1962), [`routes/positions.py:112-129`](../../../backend/api/routes/positions.py#L112-L129)

**F1.5 — Position-value math is IBKR's, not ours.**
`mark_price`, `position_value`, `unrealized_pnl` come straight from IBKR's XML at sync time. They're frozen at sync. The UI displays them as if live. Either: (a) re-mark from a price feed (yfinance is already a dependency for corporate actions), or (b) label timestamps clearly so a user knows they're looking at a snapshot, not a live quote.

**F1.6 — No cost-basis reconciliation.**
[`positions.py:60-71`](../../../backend/api/routes/positions.py#L60-L71) computes `qty_diff` only. `positions_ibkr.cost_basis_money` is never compared to `positions_calculated.total_cost`. Quantity matching is necessary but not sufficient — splits applied with the wrong ratio, or fee/proceeds drift, would show qty-match but cost-basis-drift. **This is the single highest-leverage optimization for correctness.**

**F1.7 — Forex positions silently dropped.**
The view filters `symbol NOT LIKE '%.%'` which excludes Forex pairs from the calculated side. But IBKR may include them in `positions_ibkr`. If you ever held a forex position, it would appear on the IBKR side with no matching calculated row → reconciliation flagged as "error" by accident. None today (15/15 reconcile), but a latent bug. [`schema.sql:133`](../../../backend/database/schema.sql#L133), [`calculate_and_save_positions.py:45`](../../../backend/scripts/calculate_and_save_positions.py#L45)

**F1.8 — Currency is ignored in reconciliation.**
USD, EUR, GBP positions are mixed in the reconciliation summary and sort. Position values aren't FX-converted to a base currency. If you have €100k EUR and $20k USD, "total portfolio value" cannot be derived from this data. Future feature.

**F1.9 — Stale DB file confuses tooling.**
Two SQLite files exist: `backend/database/finance.db` (empty, leftover) and `output/database/finance.db` (real, 582 trades). The connection module ([`connection.py:14`](../../../backend/database/connection.py#L14)) correctly points at `output/`, but ad-hoc scripts run from `backend/` could open the wrong one. **Delete the stale file** and ensure it can't be recreated.

### 1.5 Code observations

- [`fetch_flex_trades.py`](../../../backend/scripts/fetch_flex_trades.py) is 763 lines doing trades + positions + corp-actions parsing + DB writes. Should split into `flex_client.py` (HTTP), `flex_parser.py` (XML→dict), and `flex_storage.py` (dict→DB).
- [`positions.py`](../../../backend/api/routes/positions.py) is 129 lines with two endpoints, well-scoped — fine as is.
- The Positions tab block in [`page.tsx`](../../../frontend/app/page.tsx) spans lines 1932–~2200. Inline styles, no extraction. With the rest of `page.tsx` at 2163 total lines, this whole file is the #1 frontend refactor target.

### 1.6 Optimization priorities (Holdings)

| # | Item | Effort | Value |
|---|---|---|---|
| 1 | Add cost-basis reconciliation alongside qty (F1.6) | S | High |
| 2 | Delete stale `backend/database/finance.db` file (F1.9) | XS | Med (foot-gun removal) |
| 3 | Snapshot history table for time-series (F1.2) | M | Med (unlocks future) |
| 4 | Surface "last IBKR sync" timestamp clearly + dedicated re-sync button (F1.1, F1.4) | S | Med (UX) |
| 5 | Extract Positions tab from `page.tsx` into a component | M | Med (debt) |
| 6 | Re-mark prices from yfinance for live position values (F1.5) | M | Low-Med |

---

## 2. Transactions

*Pending review.*

---

## 3. Reconciliation

*Pending review.*
