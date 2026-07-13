# ERRORS.md — known error patterns and prevention rules

## 2026-07-10 — Split-artifact corruption: incremental ingest + INSERT OR IGNORE never re-adjusts history

**Symptom:** absurd momentum values (DD momentum_60d = +185.9%) and fake price discontinuities at *sync-gap boundaries* (not at the split date): DD jumped 3.25× on 2026-05-05 in our data, while the actual 1-for-3 reverse split was 2026-06-24.

**Root cause:** yfinance retro-adjusts ALL history when a split occurs, but our ingest is incremental (`start = last bar + 1`) with `INSERT OR IGNORE` — existing bars are never updated. Bars stored before the split stay on the old price basis; bars fetched after are on the new basis. Every price-derived analytic (momentum, MAs, 52w, consolidation, breakout) is then wrong for that symbol. Affected & repaired 2026-07-10: CRWD (4:1, 07-02), CVNA (5:1, 05-08), KLAC (10:1, 06-12), DD (1:3, 06-24) — purged market_data+indicators for those symbols and re-fetched clean 730d history.

**How to detect:** `close/LAG(close)` day-ratio scan — ratios >1.6 or <0.55 that don't match a real one-day move; cross-check `yf.Ticker(sym).splits`.

**Prevention rule (not yet implemented):** when corporate_actions records a new split for a tracked symbol, purge and re-fetch that symbol's market_data (and indicators) instead of trusting stored history. Until then, re-run the day-ratio scan after any split announcement.

**Related caveat:** indicators (MA/BB/RSI) compute on `adj_close` (split+dividend adjusted) while screen signals/momentum use raw `close` (split-adjusted only) — a small mixed-basis bias for dividend payers; standardization tracked in the analytics audit.

## 2026-07-10 — Stale-join: screen_signals stored wrong MA verdicts ("All Bearish" on a bullish stack)

**Symptom:** research_overview showed incoherent analytics — e.g. AAPL price > MA50 > MA100 > MA150 (textbook bullish) yet `ma_cross_status = "All Bearish"`, `trend_aligned = 0`. 56/561 symbols had a bullish stack labeled Bearish; only 244/561 stored statuses matched current indicators.

**Root cause (two layers):**
1. `screen_signals_compute.compute_for_symbol` joined the LAST market_data bar (fresh) with the LATEST `indicators` row *regardless of its date*. On 2026-07-01 the indicators table was ~7 weeks stale (AAPL's latest row ≤ 2026-05-13, when the stack genuinely was bearish), so fresh prices were joined with May MAs and stored.
2. Nothing ever recomputed signals: `/api/sync/analytics` and `/api/sync/full` refresh indicators but never chained the screen compute, so `signal_date` (06-30) drifted 9 days behind `indicator_date` (07-09) with no invalidation and no UI staleness cue.

**Fix:** (a) `screen_signals_compute` now only joins indicators dated within `INDICATOR_FRESHNESS_DAYS` (7) **before or at** the last market bar; stale MAs → MA-derived fields stored as NULL/0 (honest) while price-only signals still compute. Regression tests: `test_stale_indicators_are_not_joined`, `test_fresh_indicators_within_tolerance_are_joined`. (b) `_step_screen()` is chained after indicators in `/api/sync/analytics` and `/api/sync/full` so the dates can't drift; endpoints converted to plain `def` (threadpool) per the 2026-07-10 event-loop entry below.

**Prevention rule:** any compute that JOINS two independently-synced tables must enforce a freshness contract (date-match with tolerance) at read time, AND the sync orchestration must chain dependents after their inputs. Never trust "latest row" semantics across pipeline stages.

## 2026-07-10 — Multiple projects share localhost ports: 8000 is NOT the Stocks backend

**Symptom:** POST to `localhost:8000/api/sync/...` returns 404; `/health` returns `{"status":"healthy"}` (Stocks returns `{"status":"ok", "database": ...}`).

**Root cause:** three dev stacks run side by side: **Stocks = frontend 3010 / backend 8010**; LMNP = 3000/8000; compta_sasu = 3001/8001. The Stocks frontend proxy defaults to `BACKEND_URL=http://localhost:8000` unless the env var overrides it at launch.

**Prevention rule:** before hitting or restarting "the backend", verify identity: `lsof -p <pid> | grep cwd` and `curl /health` (Stocks health includes `database_path` with `/Claude/Stocks/`). Stocks lives on 3010/8010.

**Related artifact:** a 0-byte `backend/database/finance.db` appeared 2026-07-10 16:24 (something ran with a wrong cwd/path). The real DB is `output/database/finance.db` (~67 MB); `connection.py` resolves it absolutely. The 0-byte file is inert — safe to delete.

## 2026-07-10 — "Erreur de connexion / Cannot connect to API" while backend is alive

**Symptom:** Frontend shows the connection-error screen (`frontend/app/page.tsx:1287` / `:461`) even though the backend process is up and listening.

**Root cause:** `POST /api/sync/fundamentals` runs **synchronously on the request path**. While it fetches fundamentals for the ~560-symbol universe via yfinance (~14 min), the backend answers no other request — `/health` times out, so the UI concludes the API is down. The process is NOT crashed; it recovers by itself when the sync finishes.

**How to diagnose:** `lsof -nP -iTCP:<backend-port> -sTCP:LISTEN` shows the process alive; backend log shows `🏦 Sync step: fundamentals` with no completion line yet; `curl /health` times out even at 90s.

**Prevention rule:** Before restarting a "dead" backend, check the log for an in-flight fundamentals sync — killing it discards the sync.

**FIXED 2026-07-10:** `sync_fundamentals` in `backend/api/routes/sync.py` changed from `async def` to plain `def`, so FastAPI runs it in its threadpool and the event loop stays free. Regression test: `test_sync_fundamentals_does_not_block_other_requests` in `backend/tests/test_sync_fundamentals.py`. Live-verified: /health answered in ~5ms while a real 561-symbol sync was in flight.

**Watch out — same latent bug elsewhere:** other sync endpoints (`/api/sync/screen`, `/api/sync/analytics`, `/api/sync/market-data`, …) are still `async def` running blocking work directly; they block the loop for their duration (seen: 15s during analytics). Apply the same `def` fix if any of them grows long enough to matter.

## 2026-07-13 — Dashboard stuck on "Loading dashboard…" during a sync

**Symptom:** Starting a prices/signals sync makes the Dashboard hang on "Loading dashboard…" until the sync finishes.

**Root cause:** SQLite was in `delete` (rollback-journal) mode. A writer holds an EXCLUSIVE lock for its whole transaction, so the dashboard's read (`GET /api/dashboard`) is blocked (then errors after the busy-timeout) while a 561-symbol analytics sync writes.

**Prevention rule:** All connections go through `get_db_connection()`, which sets `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=30000` (Epic SH, ADR-4). WAL allows concurrent read-during-write. NEVER open `sqlite3.connect()` directly — you skip the busy-timeout (and, before the DB was ever put in WAL, would skip WAL too). Regression test: `backend/tests/test_connection_wal.py`.

## 2026-07-13 — Sync appears to stop when leaving the Browse Universe tab

**Symptom:** Start a sync from the Research toolbar, switch tabs, come back — the progress is gone and the toolbar looks idle, as if the sync stopped.

**Root cause:** Sync progress lived in `SyncToolbar`'s local `useState`, and the toolbar was conditionally rendered (`{activeTab === 'browse-universe' && …}`) so it unmounted on tab switch — destroying the progress state and orphaning the awaited fetch chain. The backend `sync_runs` table existed but was never used for live status.

**Prevention rule:** Long-running operations belong in the app-level `SyncProvider` (mounted above the tabs in `layout.tsx`), never in a conditionally-rendered tab component. The provider owns the fetch + progress (survives navigation) and a `useRef` single-flight guard (prevents double-start). Regression test: the persistence case in `frontend/__tests__/synctoolbar.test.tsx`.

## 2026-07-13 — Staleness chips called fresh Friday data "4d stale" on Monday

**Symptom:** user refreshed prices + indicators Monday midday; syncs succeeded ("562 symbols · 0 new bars") but the dashboard chip still showed amber "● prices 4d".

**Root cause:** the chip conflated two facts (data date vs last check) into one wall-clock delta. `relativeStaleness` parsed the bare bar date `2026-07-10` as midnight UTC and diffed against now → Monday 14:49 CEST is ~85h → `round(85/24)` = "4d", amber because >24h — even though Friday's bar was the freshest completed trading day possible (weekend + US market not yet closed Monday).

**Fix:** backend `as_of` entries are now `{date, checked_at, level}` — `checked_at` from `sync_runs.finished_at` per action, `level` computed by `backend/api/utils/trading_days.py` against the last *completed* trading day (22:00 UTC cutoff, weekends rolled back; holidays unmodeled → amber for a day, honest-but-conservative). Frontend chips show the data date + "checked Xh ago" subline. Regression tests: `backend/tests/test_trading_days.py` (Monday-premarket/weekend cases), `test_dashboard_as_of_entries_are_rich_objects`.

**Prevention rule:** freshness UI for market data must compare against the last completed trading day, never a wall-clock delta from a date-only string; and always display "data as-of" separately from "last checked" — a single relative age can't express both.
