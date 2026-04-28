# Architecture — IBKR Portfolio Tracker

> Stage 3 output. Source-of-truth for technical decisions.
> Status: **Locked** (2026-04-28). Mid-project changes require updating this doc first.

---

## 1. Tech Stack

### Backend

| Category | Choice | Notes |
|---|---|---|
| **Language** | Python 3.10 (framework Python at `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3`) | NOT homebrew Python — uvicorn / pandas / yfinance installed against framework Python |
| **API framework** | FastAPI | async-first, OpenAPI auto-gen, TestClient for integration tests |
| **DB driver** | sqlite3 stdlib | Engine-aware migration to psycopg2 evaluated and parked |
| **Database** | SQLite 3 (file at `output/database/finance.db`) | ~12 MB today; ~250 MB at full universe scope |
| **External data** | yfinance (price data, corp actions, options chains) | free, snapshot-only |
| **External data** | IBKR Flex Query API (positions + trades) | XML response; token + query ID via `.env` |
| **External data** | `pd.read_html` from Wikipedia (index constituents) | S&P 500 + CAC 40 in v1 |
| **DataFrame ops** | pandas | indicator math, rolling windows, ZigZag, etc. |
| **Server** | uvicorn (development) | port 8000 |

### Frontend

| Category | Choice | Notes |
|---|---|---|
| **Framework** | Next.js 16 (App Router) | port 3000 |
| **UI library** | React 19 | |
| **Styling** | Tailwind CSS v4 | `@theme inline` design tokens; light mode default |
| **Component library** | shadcn/ui | copy-in approach, owned in `components/ui/` |
| **Icons** | lucide-react | ships with shadcn |
| **Charts (mini)** | Recharts | declarative, used inside Security Detail modal |
| **Charts (full-page)** | lightweight-charts (TradingView's library) | used on `/tech-analysis/{symbol}` route — Story F |
| **Toasts** | sonner (via shadcn) | replaces inline upload-result divs |

### Testing

| Layer | Tool |
|---|---|
| **Backend integration** | pytest + FastAPI TestClient + monkeypatch for HTTP stubs |
| **Backend test fixtures** | `temp_db` (SQLite tempfile, monkey-patched DB_FILE) at `backend/tests/conftest.py` |
| **Frontend** | jest + @testing-library/react (set up but minimally used) |
| **Type-check** | `npx tsc --noEmit` (excludes pre-existing `__tests__` errors) |

### Infrastructure

| Aspect | Choice |
|---|---|
| **Hosting** | None — local only |
| **Deployment** | Manual `git push` to GitHub for backup |
| **Secrets** | `.env` file (gitignored) for IBKR Flex token + query IDs |

---

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User (browser)                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
                ┌──────────▼───────────┐
                │  Next.js (port 3000) │
                │  - app/page.tsx      │
                │  - components/ui/    │
                │  - api/proxy → :8000 │
                └──────────┬───────────┘
                           │ /api/proxy/*
                ┌──────────▼───────────┐
                │  FastAPI (port 8000) │
                │  - routes/sync.py    │
                │  - routes/positions  │
                │  - routes/transactions│
                │  - routes/corporate-actions│
                │  - routes/updated-transactions│
                │  - routes/universe (C)│
                │  - routes/market-data (C)│
                │  - routes/indicators (D)│
                │  - routes/holding-signals (G)│
                │  - routes/security (H)│
                │  - routes/tech-analysis (E,F)│
                └──┬─────────────┬──────┘
                   │             │
        ┌──────────▼───┐ ┌───────▼───────────────────────┐
        │  SQLite DB   │ │  External APIs                 │
        │  (finance.db)│ │  - IBKR Flex Query (XML)       │
        │              │ │  - yfinance (prices, options)  │
        │              │ │  - Wikipedia (index lists)     │
        └──────────────┘ └────────────────────────────────┘
```

---

## 3. Component Breakdown

### Backend modules (`backend/`)

| Module | Responsibility |
|---|---|
| `api/main.py` | FastAPI app, CORS, router registration, lifespan |
| `api/routes/sync.py` | Pipeline orchestrator + 4 step endpoints |
| `api/routes/positions.py` | `GET /api/positions` (raw IBKR snapshot) |
| `api/routes/transactions.py` | List, upload, delete, export trades; CSV path |
| `api/routes/corporate_actions.py` | CRUD + status + refresh endpoints for CAs |
| `api/routes/updated_transactions.py` | Split-adjusted transactions view |
| `api/routes/universe.py` *(Story C)* | `tracked_universe` CRUD + index toggles + refresh |
| `api/routes/market_data.py` *(Story C)* | Read-only access to OHLCV |
| `api/routes/indicators.py` *(Story D)* | Read-only access to indicator values |
| `api/routes/holding_signals.py` *(Story G)* | Sell signal computation + read |
| `api/routes/security.py` *(Story H)* | Unified `/api/security/{symbol}/detail` endpoint |
| `api/routes/tech_analysis.py` *(Stories E, F)* | Breakouts + consolidations + S/R |
| `api/utils/logger.py` | Centralized logger with emoji conventions per CLAUDE.md |
| `database/connection.py` | `get_db_connection()` returning sqlite3.Connection with row_factory |
| `database/schema.sql` | Single source of truth for table definitions |
| `scripts/fetch_flex_trades.py` | IBKR Flex API client + parsers + DB writers |
| `scripts/fetch_corporate_actions.py` | yfinance corporate actions fetcher |
| `scripts/apply_splits.py` | Apply known splits → `updated_transactions` rows |
| `scripts/parse_csv_trades.py` | CSV upload path (manual ingestion) |
| `scripts/universe_seeders.py` *(Story C)* | Wikipedia scrapers per index |
| `scripts/market_data_ingestor.py` *(Story C)* | Batched yfinance OHLCV downloader |
| `scripts/indicators_compute.py` *(Story D)* | Incremental indicator computation |
| `scripts/breakout_detector.py` *(Story E)* | Range Breakout (port of `d_breakout_detector_3`) |
| `scripts/trend_breakout.py` *(Story E)* | Trend Breakout (4-condition setup) |
| `scripts/consolidation_detector.py` *(Story E)* | ZigZag + BB squeeze |
| `scripts/sr_technical.py` *(Story E)* | Technical S/R computation |
| `scripts/options_ingestor.py` *(Story F)* | yfinance options chain → DB |
| `scripts/sr_options.py` *(Story F)* | Max pain + call/put walls |
| `utils/ca_status.py` | CA status grey/green/orange management |

### Frontend (`frontend/`)

| Module | Responsibility |
|---|---|
| `app/page.tsx` | Top-level Dashboard with 3 tabs (Positions / Transactions / Configuration). 2200+ lines today; component extraction happens as touched. |
| `app/api/proxy/[...path]/route.ts` | Next.js proxy → FastAPI backend |
| `components/ui/*` *(Story C)* | shadcn/ui copies (Button, Card, Dialog, Table, Tabs, Badge, Input, Select, Switch, Sonner) |
| `components/security-detail/*` *(Story H)* | Security Detail Modal — Mode A / Mode B |
| `components/tech-analysis/*` *(Stories E, F)* | Tech Analysis tab + filter bar + drill-down |
| `lib/utils.ts` *(Story C)* | shadcn `cn()` helper |
| `app/globals.css` | Tailwind v4 + theme tokens |

---

## 4. Data Model

### Core tables (current state — pre-Story-C)

| Table | Purpose |
|---|---|
| `transactions` | Raw IBKR trades; PK `id` (auto), UNIQUE `transaction_id` |
| `import_logs` | Audit trail of every sync; PK `id` |
| `corporate_actions` | Splits / dividends / etc., UNIQUE `(sec_id, ca_type, ex_date)` |
| `corporate_actions_status` | Per-symbol status (grey/green/orange); PK `sec_id` |
| `updated_transactions` | Split-adjusted overlay; FK to `transactions` and `corporate_actions` |
| `transactions_adjusted` (view) | LEFT JOIN of `transactions` + `updated_transactions` with COALESCE; excludes Forex (`%.%`) |
| `positions_ibkr` | IBKR snapshot of open positions; PK `symbol` |

### New tables (Story C)

| Table | Purpose |
|---|---|
| `tracked_universe` | Symbols we ingest market data for; PK `symbol`; JSON `sources` column for multi-source membership |
| `tracked_indices` | Index list metadata (sp500/cac40/etc.); PK `name`; enabled flag + last_refreshed_at + symbol_count |
| `market_data` | OHLCV bars; composite PK `(symbol, time)` |

### New tables (Stories D, G, H, E, F)

| Story | Table | Purpose |
|---|---|---|
| D | `indicators` | Per-(symbol, time) MA50/100/150/200, BB upper/lower, RSI, MRSI, ATR, Vol MA |
| G | `holding_signals` | Per-(symbol, signal_type) latest fired status + threshold + value |
| E | `breakout_signals` | Per-(symbol, signal_type='range'/'trend', date) detection |
| E | `consolidation_patterns` | Per-(symbol, pattern_type='zigzag'/'bb_squeeze', date) detection |
| E, F | `support_resistance` | Per-(symbol, method='zigzag_swing'/'ma'/'round_number'/'volume_profile'/'options_max_pain'/'options_call_wall'/'options_put_wall') zone + price + score |
| F | `options_snapshots` | Per-(symbol, expiry, snapshot_at, strike, type) OI + volume + IV |

### JSON column conventions

- `tracked_universe.sources`: JSON array of strings; values from `{sp500, cac40, nasdaq100, dow30, dax40, ftse100, ibkr_position, manual}`. Allows a symbol to belong to multiple sources; row deleted only when ALL sources are removed.

### Idempotency strategy

- All ingestion uses `INSERT ... ON CONFLICT (cols) DO NOTHING` (or `DO UPDATE SET ...` for replace-style writes). SQLite 3.24+ supports `ON CONFLICT` syntax — same as Postgres. SQLite-specific `INSERT OR IGNORE/REPLACE` avoided so the codebase stays portable if Supabase migration is reconsidered.

---

## 5. Data Flow

### Sync pipeline (one user click → 4 steps)

```
User clicks "🔄 Sync IBKR" in header
  ↓
POST /api/sync/full
  ↓
  Step 1: fetch_flex_response("last_month") → ONE Flex Query XML
  ↓
  Step 2: parse_positions_from_xml + save_positions_ibkr
  ↓        + _sync_positions_to_universe (auto-tag held symbols with source 'ibkr_position')
  ↓
  Step 3: parse_trades_from_xml + insert_flex_trades
  ↓        + set CA-status 'orange' for affected symbols
  ↓        + write import_logs row
  ↓
  Step 4: fetch_and_import_corporate_actions(incremental=True)  [yfinance per affected symbol]
  ↓
  Step 5: apply_all_splits  [updates updated_transactions table]
  ↓
  *(Story C+):* sync_market_data + sync_indicators + sync_holding_signals
  ↓
Return per-step status to UI → progress strip lights ✅/❌ per step
```

### Indicator computation (Story D)

```
POST /api/sync/indicators
  ↓
Read enabled symbols from tracked_universe
  ↓
For each symbol: SELECT MAX(time) from indicators (latest computed row)
  ↓
Pull ALL bars for symbol with time > latest_indicator_time (+ 150 days back for MA windows)
  ↓
Compute MA50/100/150/200 + BB(20,2) + RSI(14) + ATR(14) + Volume MA(20) via pandas rolling
  ↓
Compute MRSI: pull benchmark bars, divide closes, normalize via 252-day MA
  ↓
INSERT new rows into indicators table (idempotent on (symbol, time))
```

### Sell signal evaluation (Story G)

```
POST /api/sync/holding-signals
  ↓
Read symbols from positions_ibkr (only currently held)
  ↓
For each symbol: pull latest indicators row + cost_basis_price
  ↓
Run all FR-G1..FR-G11 signal checks
  ↓
UPSERT (symbol, signal_type) → holding_signals with fired flag + value + threshold
  ↓
Positions tab UI fetches /api/holding-signals → renders traffic light per row
```

---

## 6. Folder Structure

```
Stocks/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/         (one file per logical group)
│   │   ├── utils/
│   │   └── middleware/
│   ├── database/
│   │   ├── connection.py
│   │   └── schema.sql
│   ├── scripts/            (ingestion + computation scripts)
│   ├── tests/              (pytest, conftest.py with temp_db fixture)
│   ├── utils/              (ca_status, logger config)
│   └── requirements.txt
├── frontend/
│   ├── app/                (Next.js App Router pages + proxy route)
│   ├── components/
│   │   └── ui/             (shadcn components — Story C onward)
│   ├── lib/                (utils, helpers)
│   ├── tailwind.config (n/a — Tailwind v4 is CSS-first)
│   ├── postcss.config.mjs
│   └── package.json
├── docs/
│   ├── project/
│   │   ├── config/         (brainstorm, prd, architecture, logging, codebase, build-log, epics/)
│   │   └── requirements/   (1-BRAINSTORM through 7-CODEBASE templates — read-only)
│   ├── plans/              (per-story implementation plans + ROADMAP.md)
│   ├── workflow/
│   ├── guides/
│   └── implementation/
├── input/                  (CSV uploads, daily_trades/)
├── output/
│   └── database/finance.db (THE single SQLite file)
├── logs/                   (backend / api / frontend daily log files)
└── .env                    (gitignored — IBKR credentials)
```

---

## 7. Environment Variables

| Var | Purpose | Where set |
|---|---|---|
| `IBKR_FLEX_TOKEN` | IBKR Flex Query API token | `.env` |
| `IBKR_QUERY_ID_last_year` | Flex query ID for full-year pull | `.env` |
| `IBKR_QUERY_ID_last_month` | Flex query ID for incremental pull | `.env` |
| `IBKR_QUERY_ID_positions` *(future)* | Optional dedicated positions-only query | `.env` if user creates one at IBKR |
| `IBKR_QUERY_ID_trades_last_year` *(future)* | Optional dedicated trades-only query | `.env` if user creates one |
| `IBKR_QUERY_ID_trades_last_month` *(future)* | Optional dedicated trades-only query | `.env` if user creates one |

The `fetch_flex_response()` helper uses dedicated query IDs if set, falls back to unified — no code change when user adds dedicated queries.

---

## 8. Key Technical Decisions

| Decision | Rationale |
|---|---|
| **SQLite, not Postgres/Supabase** | Solo-user local app. Performance is microseconds vs 50-100ms over network. Free vs free-tier-but-eventually-paid. Migration plan exists but parked. |
| **`INSERT ... ON CONFLICT`, not `INSERT OR IGNORE`** | Portable across SQLite (3.24+) and Postgres without code changes. |
| **JSON `sources` column on `tracked_universe`** | Same symbol can belong to multiple lists. JSON is overkill for a list of ~6 known values BUT lets us use `LIKE '%"sp500"%'` filters cheaply and avoids a join table. |
| **Indicators in their own `indicators` table, not denormalized into `market_data`** | Independent compute lifecycle, can recompute without touching OHLCV. |
| **Sell signals on holdings only, not on the universe** | Universe-wide sell signals = noise. Holdings are personal context. Universe-wide signals are buy/breakout, not sell. |
| **MRSI requires benchmark in `tracked_universe`** | Auto-seed `^GSPC`, `^FCHI`, etc. as universe members so their `market_data` is ingested. Pre-req for any MRSI calc. |
| **Two breakout signals (range + trend), separate rows in `breakout_signals`** | Different mental models, different traders use them differently. Don't conflate. |
| **Two S/R methods (technical + options), `method` column** | Comparison view is the value proposition. Storing as separate rows lets UI layer-toggle and find agreement zones. |
| **Use lightweight-charts only on dedicated full-page chart** | Heavy library; Recharts is plenty for mini-charts inside modals. |
| **Light mode default, dark mode optional later** | User preference. shadcn's neutral palette covers both, swappable via `[data-theme]`. |
| **No realtime / streaming** | Snapshot data on manual sync is sufficient. Adding streaming = ws/SSE infrastructure for marginal value. |
| **Sell simulator uses weighted-avg cost basis in v1** | FIFO matching requires lot-level tracking. The FIFO module is parked. UX surfaces this limitation in the modal. |

---

## 9. Performance Assumptions

| Operation | Target | Strategy |
|---|---|---|
| Full sync (`/api/sync/full`) | <30s | Single Flex call (~5s) + 50-symbol yfinance batches with threads + idempotent DB writes |
| Indicator recompute | <60s for 600 symbols | Incremental: only stale symbols, only new dates, batch INSERT via executemany |
| Sell signal eval | <10s for 15 holdings | Read latest indicators (1 query per symbol), compute in-memory, batch UPSERT |
| API read endpoints (`/api/positions`, `/api/transactions`) | <100ms | SQLite local, indexes on hot columns, no joins beyond `transactions_adjusted` view |
| Frontend tab switch | <500ms first paint | shadcn components are static; data fetches are async + cached in React state |

---

## 10. Out of Scope

- Real-time price streaming
- Order execution
- Multi-user / sharing
- Mobile native apps
- Cloud hosting / Supabase / Postgres
- Auth / user accounts
- Tax reports
- Email / push notifications when signals fire
- Historical options chain (paid feed required)
