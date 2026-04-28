# Build Log

## 2026-04-28 — Epic D complete: indicators

7 stories shipped, end-to-end smoke test passed for indicators (CA step regression noted below).

**Subsystems delivered:**
- `indicators` table (composite PK on `(symbol, time)`, 11 indicator columns)
- Auto-seed of 4 benchmark symbols (`^GSPC`, `^FCHI`, `^GDAXI`, `^FTSE`) into `tracked_universe` with source `benchmark`
- Pure pandas indicator math: MA 50/100/150/200, BB(20, 2), RSI(14) Wilder, ATR(14), Volume MA(20), MRSI (Mansfield Relative Strength)
- Per-symbol orchestrator with benchmark resolution (USD→^GSPC, EUR→^FCHI, GBP→^FTSE)
- `POST /api/sync/indicators` endpoint, wired into `/api/sync/full` as the 5th step
- `GET /api/indicators/{symbol}` read endpoint

**Tests:** 16 new tests across 2 files (`test_indicators_compute.py` + `test_indicators_routes.py`). All passing.

**Live smoke test:**
- 18 symbols (14 IBKR positions + 4 benchmarks) fed market_data
- `compute_all` wrote 4,292 indicator rows for 17 symbols (one had insufficient history)
- Spot check NVDA: MA50=186.2, MA200=183.3 (uptrend), RSI(14)=69.9, **MRSI=+12.7** (NVDA outperforming S&P 500), BB width=0.27, ATR=5.93

**Known issue surfaced during smoke (NOT Epic D regression):** the `corporate_actions` step in `/api/sync/full` fails with "can't subtract offset-naive and offset-aware datetimes" — a side-effect of the SYNC-13 timezone work where `set_ca_status` stores tz-aware ISO timestamps but the CA fetcher's incremental logic compares against tz-naive `datetime.now()`. Indicators step does not run when CA fails because the chain stops. Fix tracked separately. Indicators sync works fine when called directly via `POST /api/sync/indicators`.

**Commits:** STORY-D-1 through STORY-D-6 on branch `newstart`.

---

## 2026-04-28 — Epic C complete: foundation (universe + market_data + design system)

9 stories shipped, end-to-end smoke test passed against real Wikipedia + yfinance + IBKR Flex.

**Subsystems delivered:**
- **Design system**: Tailwind v4 + shadcn/ui installed; first shadcn-styled UI section landed in Configuration tab. `frontend/components/ui/*` populated with button, card, input, label, badge, table, dialog, tabs, select, switch, sonner. `globals.css` migrated to v4 syntax with `@theme inline` design tokens.
- **Universe management**: `tracked_universe` (JSON `sources` column), `tracked_indices` tables. CRUD endpoints. S&P 500 + CAC 40 Wikipedia seeders (with User-Agent header to bypass 403). IBKR positions auto-tag into universe with source `ibkr_position`; sold positions un-tag and row deletes if no other source.
- **Market data ingestion**: `market_data` table (composite PK `(symbol, time)`). yfinance batched ingestor (50-symbol batches, threads, idempotent). `_yf_download` indirected for hermetic tests.

**Endpoints added:**
- `GET    /api/universe`                    list enabled tracked symbols
- `POST   /api/universe/manual`             add manual ticker (uppercases, idempotent)
- `DELETE /api/universe/manual/{symbol}`    remove manual tag
- `GET    /api/universe/indices`            list indices with status + count
- `POST   /api/universe/indices/{name}/toggle`
- `POST   /api/universe/indices/{name}/refresh`  re-scrape Wikipedia
- `POST   /api/sync/market-data`            yfinance ingest for enabled symbols
- `GET    /api/market-data/{symbol}`        OHLCV bars, optional date range

**Tests:** 19 new tests across 4 files (`test_universe_routes.py`, `test_universe_seeders.py`, `test_market_data_ingestor.py`, `test_market_data_routes.py`). All passing. SQLite via `temp_db` fixture; HTTP stubbed via `monkeypatch`.

**Live smoke test results:**
- S&P 500 refresh: 503 symbols inserted from Wikipedia
- CAC 40 refresh: 40 symbols inserted
- IBKR positions sync: 14 positions auto-tagged into universe (5 multi-source with sp500)
- Market data sync (capped to held positions): 14 symbols processed, **3276 OHLCV rows** inserted (~252 trading days each), 0 errors
- Total enabled universe after smoke: 552 symbols

**Bug fix bundled:** Wikipedia returns 403 to pandas' default User-Agent. Fix: fetch HTML via `requests` with a real UA, then `pd.read_html(StringIO(...))`.

**Commits:** STORY-C-1 through STORY-C-8 + bug fix on branch `newstart`.

---

## 2026-04-27 — Story A complete: sync pipeline restructured

Refactored the monolithic `/api/transactions/flex-import` endpoint into a 4-step decoupled sync pipeline at `/api/sync/*` plus a `/api/sync/full` orchestrator. Reconciliation feature dropped (`positions_calculated` table + recalc script + recon UI removed).

**Endpoints (all POST):**
- `/api/sync/positions` — Flex pull, write only positions_ibkr
- `/api/sync/transactions` — Flex pull, write only transactions, flag CA-orange
- `/api/sync/corporate-actions` — yfinance refresh
- `/api/sync/splits` — apply known splits → updated_transactions
- `/api/sync/full` — orchestrator with shared Flex call across positions+transactions

**Frontend:** Sync IBKR button wired to `/api/sync/full`. All recon UI removed (Recalculate Rec button, summary cards, Qty Rec column, Position interface fields).

**Env-var fallback** in `fetch_flex_response()`: dedicated `IBKR_QUERY_ID_positions` / `IBKR_QUERY_ID_trades_<type>` first, falls back to unified `IBKR_QUERY_ID_<type>`. No code change needed when dedicated queries are set up at IBKR.

**Tests:** 9 integration tests in `backend/tests/test_sync_routes.py`, all passing. Real DB via `temp_db` fixture, Flex HTTP stubbed via `stub_flex_http`.

**Smoke test:** real IBKR sync via `/api/sync/full` succeeded — 14 positions refreshed, 25 split-adjusted transactions confirmed across ATRA/AVGO/CHPT/NFLX/NOW/NVDA.

**Bug fix bundled:** `backend/utils/ca_status.py` was opening its own hardcoded SQLite connection, bypassing the connection module's `DB_FILE` and breaking test isolation. Routed through `get_db_connection()`.

**Commits:** SYNC-1 through SYNC-10 on branch `newstart`.
