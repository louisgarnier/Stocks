# Build Log

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
