# CLAUDE.md — Stocks project (IBKR Portfolio Tracker)

Project-specific operating rules. The global `~/.claude/CLAUDE.md` methodology still applies.

## IBKR Flex API — NEVER over-query (hard rule)

The IBKR Flex Web Service throttles aggressively. Hammering it breaks the whole dashboard for hours.

- **Confirm with the user BEFORE firing any request at the IBKR Flex API** (SendRequest/GetStatement) — probing a query, running a sync, testing the token. Ask, then query. Never query IBKR to "just check."
- **Never loop or batch requests.** Space real API calls **≥ 5 minutes apart**, **max 2–3 attempts**, then stop.
- **A `1001 - Statement could not be generated` is a THROTTLE, not a config error.** Re-requesting the same query within minutes of a success returns 1001. Do NOT retry tightly — that escalates to **`1025 - Too many failed attempts`**, an account-level lock that bricks the query for *hours*.
- **Before diagnosing a Flex failure, read `sync_runs`** — a recent success on the same query means throttle, not a broken query.
- **Prefer non-API sources:** read the local DB (`output/database/finance.db`), or ask the user to use IBKR's **web-console "Run" button** (bypasses the API token entirely) and paste the XML.
- **Root-cause context (2026-07-22):** aggressive test-syncing during debugging tripped the 1001→1025 throttle and blocked all verification for the afternoon. See `workflow/ERRORS.md`.

## Local run — ports are per-app, wire them explicitly

Multiple projects run dev servers at once and collide on the generic defaults (backend 8000, frontend 3000).

- **Stocks pairing: frontend `3010` → backend `8010`.** (LMNP = 3000/8000, compta_sasu = 3001/8001 — leave those alone.)
- The frontend proxy (`frontend/app/api/proxy/[...path]/route.ts`) defaults to `http://localhost:8000` unless `BACKEND_URL` is set. **`frontend/.env.local` pins `BACKEND_URL=http://localhost:8010`** so Stocks can never proxy to another project's backend. (This file is gitignored — recreate it on a fresh checkout.)
- **Always run the port-conflict check before launching**, and **verify which backend the frontend actually hits before assuming a data bug** — a "wrong numbers" report is often a wiring/staleness issue, not bad logic.

## Two independent data feeds — don't confuse them

- **IBKR feed** (positions, cash, transactions) ← Flex API. Refreshed by the IBKR sync.
- **Price feed** (stock closes) ← yfinance. Refreshed by the market-data sync. **No throttle** — safe to run freely.
- Net worth = positions (priced by yfinance) + cash (from IBKR). If net worth looks off, check **which feed is stale** before touching code: `MAX(time) FROM market_data` for prices, `sync_runs WHERE action='ibkr'` for IBKR.

## Cash is a dedicated Flex query

Cash comes from its **own** query (`IBKR_QUERY_ID_cash`, currently `1579843`), separate from positions/trades (`1398454`). This is deliberate — bundling CashReport into the positions query made it too heavy for IBKR to generate reliably (chronic 1001). The cash step is best-effort: a cash failure must never block the positions/trades refresh. See `workflow/ADR.md`.
