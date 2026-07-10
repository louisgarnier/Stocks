# Dashboard & IA Restructure Implementation Plan (Epic V)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the approved Dashboard (net worth EUR, allocation, perf vs ^GSPC, movers, action queue, staleness chips) and restructure the app to 5 tabs (Dashboard / Portfolio / Research / Journal / Settings), English-only.

**Architecture:** Backend gains an FX symbol (`EURUSD=X`) flowing through the existing market-data ingest, a `portfolio_value_history` daily snapshot (replayed from split-adjusted transactions × closes × FX), and one `GET /api/dashboard` endpoint that assembles every card's payload. Frontend gains a `components/dashboard/` family (plain SVG donut + line — **no new packages**) and prunes/renames existing tabs. Approved mockup: `.superpowers/brainstorm/41440-1783714071/content/dashboard-v1.html`; wireframe brief: `docs/project/config/wireframe-audit-2026-07-10.md`.

**Tech Stack:** FastAPI + SQLite (backend/venv, pytest) · Next.js + Jest (frontend, tests in `frontend/__tests__/`) · plain SVG charts.

## Global Constraints

- All UI copy in **English** (finding #7). Base currency **EUR** (user decision 2026-07-10).
- No new npm/pip packages (charts = hand-rolled SVG; project rule: packages need architecture.md approval).
- Commit format: `[STORY-V-n] type: description`, branch `newstart`.
- Backend tests: `backend/venv/bin/python -m pytest backend/tests/ -q` must stay green (197 baseline).
- Frontend tests: `cd frontend && npx jest` must stay green.
- Long-running sync endpoints stay plain `def` (threadpool — see workflow/ADR.md ADR-1 §3).
- Every dashboard number must carry its as-of date (staleness contract, analytics-audit Rec-5).

---

### Task 1: FX symbol ingest (EURUSD=X)

**Files:**
- Modify: `backend/scripts/universe_seeders.py` (add `seed_fx_symbols`)
- Modify: `backend/api/main.py` (call seeder at startup, next to existing benchmark seeding)
- Test: `backend/tests/test_fx_ingest.py` (create)

**Interfaces:**
- Produces: `tracked_universe` row `('EURUSD=X', sources=["fx"], currency='USD', enabled=1)`; after any market-data sync, `market_data` rows for `EURUSD=X`. Helper `get_fx_rate(conn, on_date=None) -> float | None` in `backend/scripts/portfolio_history_compute.py` (defined in Task 2; this task only guarantees the data exists).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fx_ingest.py
import sqlite3


def test_seed_fx_symbols_inserts_eurusd(temp_db):
    from backend.scripts.universe_seeders import seed_fx_symbols
    from backend.database.connection import get_db_connection

    conn = get_db_connection()
    seed_fx_symbols(conn)
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    row = conn.execute(
        "SELECT enabled, sources, currency FROM tracked_universe WHERE symbol='EURUSD=X'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 1
    assert "fx" in row[1]


def test_seed_fx_symbols_idempotent(temp_db):
    from backend.scripts.universe_seeders import seed_fx_symbols
    from backend.database.connection import get_db_connection

    conn = get_db_connection()
    seed_fx_symbols(conn)
    seed_fx_symbols(conn)
    n = conn.execute(
        "SELECT COUNT(*) FROM tracked_universe WHERE symbol='EURUSD=X'"
    ).fetchone()[0]
    conn.close()
    assert n == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/venv/bin/python -m pytest backend/tests/test_fx_ingest.py -v`
Expected: FAIL with `ImportError: cannot import name 'seed_fx_symbols'`

- [ ] **Step 3: Implement `seed_fx_symbols`**

Copy the pattern of the existing benchmark seeder in `universe_seeders.py` (search `benchmark` in that file):

```python
FX_SYMBOLS = [("EURUSD=X", "EUR/USD", "USD")]


def seed_fx_symbols(conn) -> int:
    """Seed FX rate symbols so they flow through the normal market-data ingest.

    Source tag 'fx' (like 'benchmark') — INSERT OR IGNORE keeps it idempotent.
    """
    import json
    n = 0
    for symbol, name, currency in FX_SYMBOLS:
        cur = conn.execute(
            "INSERT OR IGNORE INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
            "VALUES (?, ?, ?, ?, 1, datetime('now'))",
            (symbol, name, currency, json.dumps(["fx"])),
        )
        n += cur.rowcount
    conn.commit()
    return n
```

In `backend/api/main.py`, find where benchmark symbols are seeded at startup (search `seed_benchmark`) and add directly below it:

```python
from backend.scripts.universe_seeders import seed_fx_symbols
seed_fx_symbols(conn)  # same conn/startup block as the benchmark seeding
```

- [ ] **Step 4: Run tests to verify pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_fx_ingest.py backend/tests/test_universe_seeders.py -v`
Expected: all PASS

- [ ] **Step 5: Live check + commit**

```bash
curl -s -X POST http://localhost:8010/api/sync/market-data | python3 -m json.tool | head -5
sqlite3 output/database/finance.db "SELECT COUNT(*), MAX(time) FROM market_data WHERE symbol='EURUSD=X'"
# expect ~500 rows after the first sync that includes the new symbol (backend restart needed to seed)
git add backend/scripts/universe_seeders.py backend/api/main.py backend/tests/test_fx_ingest.py
git commit -m "[STORY-V-1] feat: seed EURUSD=X fx symbol through market-data ingest"
```

---

### Task 2: `portfolio_value_history` snapshot compute

**Files:**
- Modify: `backend/database/schema.sql` (new table)
- Create: `backend/scripts/portfolio_history_compute.py`
- Test: `backend/tests/test_portfolio_history.py`

**Interfaces:**
- Consumes: `updated_transactions`-aware transaction reads (use `COALESCE(updated_quantity, quantity)`), `market_data` closes, `EURUSD=X` closes (Task 1).
- Produces: table `portfolio_value_history(date TEXT PK, value_eur REAL, value_usd_leg REAL, value_eur_leg REAL, fx_rate REAL, computed_at TEXT)`; functions `get_fx_rate(conn, on_date=None) -> float | None` and `compute_history(conn, start=None) -> dict` (returns `{"days_written": int}`).

- [ ] **Step 1: Add table to schema.sql** (next to the other CREATE TABLE blocks)

```sql
-- Daily portfolio valuation (Epic V dashboard). Rebuilt by
-- portfolio_history_compute.compute_history; safe to delete and recompute.
CREATE TABLE IF NOT EXISTS portfolio_value_history (
    date TEXT PRIMARY KEY,
    value_eur REAL NOT NULL,
    value_usd_leg REAL,
    value_eur_leg REAL,
    fx_rate REAL,
    computed_at TEXT
);
```

Apply live: `sqlite3 output/database/finance.db "CREATE TABLE IF NOT EXISTS portfolio_value_history (date TEXT PRIMARY KEY, value_eur REAL NOT NULL, value_usd_leg REAL, value_eur_leg REAL, fx_rate REAL, computed_at TEXT)"`

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_portfolio_history.py
import json
import sqlite3


def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    # one USD stock bought 2026-01-05 (10 sh @100), one fx series, 3 trading days
    conn.execute("INSERT INTO tracked_universe (symbol, currency, sources, enabled, added_at) "
                 "VALUES ('TEST', 'USD', ?, 1, datetime('now'))", (json.dumps(["test"]),))
    conn.execute(
        "INSERT INTO transactions (transaction_id, asset_category, currency, symbol, trade_date, quantity, t_price) "
        "VALUES ('t1', 'STK', 'USD', 'TEST', '2026-01-05', 10, 100.0)")
    for d, px, fx in (("2026-01-05", 100.0, 1.10), ("2026-01-06", 110.0, 1.10), ("2026-01-07", 120.0, 1.20)):
        conn.execute("INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES ('TEST', ?, ?, ?, ?, ?, 1000)", (d, px, px, px, px))
        conn.execute("INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES ('EURUSD=X', ?, ?, ?, ?, ?, 0)", (d, fx, fx, fx, fx))
    conn.commit(); conn.close()


def test_compute_history_values_and_fx(temp_db):
    from backend.scripts.portfolio_history_compute import compute_history
    from backend.database.connection import get_db_connection

    _seed(temp_db)
    conn = get_db_connection()
    result = compute_history(conn)
    conn.close()
    assert result["days_written"] == 3

    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT date, value_eur, fx_rate FROM portfolio_value_history ORDER BY date").fetchall()
    conn.close()
    # day1: 10*100/1.10 ≈ 909.09 ; day3: 10*120/1.20 = 1000.0
    assert abs(rows[0][1] - 909.09) < 0.1
    assert abs(rows[2][1] - 1000.0) < 0.01
    assert rows[2][2] == 1.20


def test_forex_and_cash_transactions_excluded(temp_db):
    from backend.scripts.portfolio_history_compute import compute_history
    from backend.database.connection import get_db_connection

    _seed(temp_db)
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO transactions (transaction_id, asset_category, currency, symbol, trade_date, quantity, t_price) "
        "VALUES ('fx1', 'CASH', 'USD', 'EUR.USD', '2026-01-05', 1773.76, 1.18)")
    conn.commit(); conn.close()

    conn = get_db_connection()
    compute_history(conn)
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    v = conn.execute("SELECT value_eur FROM portfolio_value_history WHERE date='2026-01-05'").fetchone()[0]
    conn.close()
    assert abs(v - 909.09) < 0.1  # CASH row must not change the valuation


def test_get_fx_rate_latest_and_dated(temp_db):
    from backend.scripts.portfolio_history_compute import get_fx_rate
    from backend.database.connection import get_db_connection

    _seed(temp_db)
    conn = get_db_connection()
    assert get_fx_rate(conn) == 1.20
    assert get_fx_rate(conn, on_date="2026-01-06") == 1.10
    conn.close()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `backend/venv/bin/python -m pytest backend/tests/test_portfolio_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.scripts.portfolio_history_compute'`

- [ ] **Step 4: Implement `portfolio_history_compute.py`**

```python
"""Daily portfolio valuation from split-adjusted transactions × closes × FX.

Rebuild-from-scratch each run (dataset is small: ~550 trading days × 1 row).
CASH / forex-pair transactions are excluded — only stock legs are valued.
"""
import logging
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)

FX_SYMBOL = "EURUSD=X"
STOCK_CATEGORIES = ("STK", "Stocks")


def get_fx_rate(conn, on_date: str | None = None):
    """Latest EURUSD close at-or-before on_date (or overall latest). None if absent."""
    if on_date:
        row = conn.execute(
            "SELECT close FROM market_data WHERE symbol=? AND time<=? ORDER BY time DESC LIMIT 1",
            (FX_SYMBOL, on_date)).fetchone()
    else:
        row = conn.execute(
            "SELECT close FROM market_data WHERE symbol=? ORDER BY time DESC LIMIT 1",
            (FX_SYMBOL,)).fetchone()
    return float(row[0]) if row else None


def compute_history(conn, start: str | None = None) -> dict:
    tx = pd.read_sql_query(
        f"SELECT symbol, currency, trade_date, COALESCE(updated_quantity, quantity) AS qty "
        f"FROM transactions WHERE asset_category IN {STOCK_CATEGORIES} AND symbol NOT LIKE '%.%'",
        conn)
    if tx.empty:
        return {"days_written": 0}

    symbols = sorted(tx["symbol"].unique())
    px = pd.read_sql_query(
        "SELECT symbol, time, close FROM market_data WHERE symbol IN (%s) ORDER BY time"
        % ",".join("?" * len(symbols)), conn, params=symbols)
    if px.empty:
        return {"days_written": 0}
    closes = px.pivot(index="time", columns="symbol", values="close").ffill()

    fx = pd.read_sql_query(
        "SELECT time, close FROM market_data WHERE symbol=? ORDER BY time",
        conn, params=[FX_SYMBOL]).set_index("time")["close"]

    # cumulative shares held per symbol per day
    qty = (tx.pivot_table(index="trade_date", columns="symbol", values="qty", aggfunc="sum")
             .reindex(closes.index).fillna(0.0).cumsum())

    ccy = dict(tx.drop_duplicates("symbol")[["symbol", "currency"]].values)
    values = closes * qty
    usd_cols = [s for s in values.columns if (ccy.get(s) or "USD") == "USD"]
    eur_cols = [s for s in values.columns if ccy.get(s) == "EUR"]

    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for day, row in values.iterrows():
        if start and day < start:
            continue
        usd_leg = float(row[usd_cols].sum()) if usd_cols else 0.0
        eur_leg = float(row[eur_cols].sum()) if eur_cols else 0.0
        rate = float(fx.reindex([day]).ffill().iloc[-1]) if not fx.empty else None
        rate = rate or (float(fx.loc[:day].iloc[-1]) if not fx.loc[:day].empty else None)
        if rate is None:
            continue  # no FX yet for this day — skip rather than guess
        conn.execute(
            "INSERT INTO portfolio_value_history (date, value_eur, value_usd_leg, value_eur_leg, fx_rate, computed_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(date) DO UPDATE SET value_eur=excluded.value_eur, "
            "value_usd_leg=excluded.value_usd_leg, value_eur_leg=excluded.value_eur_leg, "
            "fx_rate=excluded.fx_rate, computed_at=excluded.computed_at",
            (day, usd_leg / rate + eur_leg, usd_leg, eur_leg, rate, now))
        written += 1
    conn.commit()
    logger.info(f"✅ [PortfolioHistory] wrote {written} days")
    return {"days_written": written}
```

Note the `symbol NOT LIKE '%.%'` guard also drops `EUR.USD` symbols that were miscategorized; European tickers like `AC.PA` are NOT in transactions (IBKR positions are US) — if that changes, switch the guard to `symbol NOT LIKE '%.USD'`.

- [ ] **Step 5: Run tests to verify pass**

Run: `backend/venv/bin/python -m pytest backend/tests/test_portfolio_history.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/database/schema.sql backend/scripts/portfolio_history_compute.py backend/tests/test_portfolio_history.py
git commit -m "[STORY-V-2] feat: portfolio_value_history daily snapshot compute"
```

---

### Task 3: chain snapshot into syncs

**Files:**
- Modify: `backend/api/routes/sync.py` (add `_step_portfolio_history`, chain into `/market-data`, `/ibkr`, `/analytics`)
- Test: `backend/tests/test_sync_routes.py` (extend)

**Interfaces:**
- Consumes: `compute_history(conn)` from Task 2.
- Produces: sync responses include a `portfolio_history` step; `/api/sync/analytics` step list becomes `["indicators", "holding_signals", "screen", "portfolio_history"]`.

- [ ] **Step 1: Extend the analytics step-list test** in `backend/tests/test_sync_routes.py` — in `test_sync_analytics_runs_only_compute_steps`, change the final assert to:

```python
    assert [s["name"] for s in body["steps"]] == [
        "indicators", "holding_signals", "screen", "portfolio_history"]
```

Also in `test_sync_full_runs_all_five_steps` and `test_sync_full_includes_indicators_step` append `"portfolio_history"` to the expected list.

- [ ] **Step 2: Run to verify fail** — `backend/venv/bin/python -m pytest backend/tests/test_sync_routes.py -k "analytics or full" -v` → FAIL (list mismatch)

- [ ] **Step 3: Implement** in `backend/api/routes/sync.py`, below `_step_screen()`:

```python
def _step_portfolio_history() -> dict:
    from backend.scripts.portfolio_history_compute import compute_history
    conn = get_db_connection()
    try:
        return compute_history(conn)
    finally:
        conn.close()
```

Chain it: in `sync_analytics` and `sync_full` add `_run(steps, "portfolio_history", _step_portfolio_history)` after the `screen` step. In `sync_market_data`, after the ingest result, add a snapshot refresh (market data moved → valuations moved):

```python
        conn = get_db_connection()
        try:
            from backend.scripts.portfolio_history_compute import compute_history
            result["portfolio_history"] = compute_history(conn)
        finally:
            conn.close()
```

- [ ] **Step 4: Run full sync tests** — `backend/venv/bin/python -m pytest backend/tests/test_sync_routes.py backend/tests/test_sync_screen.py -q` → all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/sync.py backend/tests/test_sync_routes.py
git commit -m "[STORY-V-3] feat: chain portfolio_value_history snapshot into syncs"
```

---

### Task 4: `GET /api/dashboard` endpoint

**Files:**
- Create: `backend/api/routes/dashboard.py`
- Modify: `backend/api/main.py` (register router: `app.include_router(dashboard.router)`)
- Test: `backend/tests/test_dashboard_route.py`

**Interfaces:**
- Consumes: `positions_ibkr`, `market_data`, `fundamentals.sector`, `holding_signals`, `research_overview` (verdict/score), `portfolio_value_history`, `get_fx_rate` (Task 2), `sync_runs`.
- Produces JSON shape (frontend Task 5 relies on these exact keys):

```json
{
  "as_of": {"prices": "2026-07-09", "signals": "2026-07-09", "fundamentals": "2026-07-10T14:21:05Z", "ibkr": "2026-07-10T09:09:48Z"},
  "fx_rate": 1.14,
  "net_worth": {"value_eur": 118339.0, "day_change_eur": 614.0, "day_change_pct": 0.52,
                 "unrealized_pnl_eur": 29911.0, "positions": 18, "usd_exposure_pct": 87.1},
  "allocation": {"sector": [{"label": "Technology", "value_eur": 57815.0, "pct": 48.9}],
                  "position": [{"label": "PLTR", "value_eur": 35656.0, "pct": 30.1}],
                  "currency": [{"label": "USD", "value_eur": 103054.0, "pct": 87.1}]},
  "performance": {"portfolio": [{"date": "2026-01-02", "value": 100.0}],
                   "benchmark": [{"date": "2026-01-02", "value": 100.0}]},
  "movers": [{"symbol": "SOFI", "close": 18.62, "prev_close": 17.73, "change_pct": 5.02, "day_pnl_eur": 573.0}],
  "actions": {"sell": [{"symbol": "RGTI", "quantity": 29, "return_pct": -57.9, "fired": ["stop_loss", "ma50_break"], "n_fired": 6}],
               "buy": [{"symbol": "SPG", "name": "Simon Property Group", "verdict": "strong_buy", "score_total": 77.3, "gates_passed": 7}]}
}
```

Performance series are both normalized to 100 at the window start; endpoint takes `?window=1M|3M|6M|1Y|MAX` (default `6M`).

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_dashboard_route.py
import json
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
                 "VALUES ('TEST', 10, 100.0, 'USD')")
    conn.execute("INSERT INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
                 "VALUES ('TEST','Test Corp','USD',?,1,datetime('now'))", (json.dumps(["test"]),))
    for d, px, fx in (("2026-07-08", 110.0, 1.10), ("2026-07-09", 121.0, 1.10)):
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('TEST',?,?,?,?,?,1000)", (d, px, px, px, px))
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('EURUSD=X',?,?,?,?,?,0)", (d, fx, fx, fx, fx))
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('^GSPC',?,?,?,?,?,0)", (d, 7500.0, 7500.0, 7500.0, 7500.0))
        conn.execute("INSERT INTO portfolio_value_history (date, value_eur) VALUES (?, ?)",
                     (d, 10 * px / fx))
    conn.execute("INSERT INTO fundamentals (symbol, sector) VALUES ('TEST', 'Technology')")
    conn.execute("INSERT INTO holding_signals (symbol, signal_type, fired, last_evaluated_at) "
                 "VALUES ('TEST','stop_loss',1,datetime('now'))")
    conn.commit(); conn.close()


def test_dashboard_net_worth_and_day_change(temp_db):
    _seed(temp_db)
    r = client.get("/api/dashboard")
    assert r.status_code == 200, r.text
    b = r.json()
    assert abs(b["net_worth"]["value_eur"] - 1100.0) < 0.1          # 10*121/1.10
    assert abs(b["net_worth"]["day_change_eur"] - 100.0) < 0.1      # vs 10*110/1.10
    assert b["net_worth"]["positions"] == 1


def test_dashboard_allocation_and_actions(temp_db):
    _seed(temp_db)
    b = client.get("/api/dashboard").json()
    assert b["allocation"]["sector"][0]["label"] == "Technology"
    assert abs(b["allocation"]["sector"][0]["pct"] - 100.0) < 0.1
    sell = b["actions"]["sell"]
    assert sell and sell[0]["symbol"] == "TEST" and "stop_loss" in sell[0]["fired"]


def test_dashboard_performance_normalized(temp_db):
    _seed(temp_db)
    b = client.get("/api/dashboard?window=MAX").json()
    assert b["performance"]["portfolio"][0]["value"] == 100.0
    assert b["performance"]["benchmark"][0]["value"] == 100.0
    assert abs(b["performance"]["portfolio"][-1]["value"] - 110.0) < 0.1  # 1100/1000
```

- [ ] **Step 2: Run to verify fail** — `backend/venv/bin/python -m pytest backend/tests/test_dashboard_route.py -v` → FAIL 404

- [ ] **Step 3: Implement `backend/api/routes/dashboard.py`**

```python
"""Dashboard aggregate endpoint (Epic V). One call = every card's payload."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from backend.database.connection import get_db_connection
from backend.scripts.portfolio_history_compute import get_fx_rate

router = APIRouter(prefix="/api", tags=["dashboard"])

WINDOWS = {"1M": 30, "3M": 91, "6M": 182, "1Y": 365, "MAX": 100000}


def _latest_two_closes(conn, symbol):
    rows = conn.execute(
        "SELECT close FROM market_data WHERE symbol=? ORDER BY time DESC LIMIT 2",
        (symbol,)).fetchall()
    c0 = rows[0][0] if rows else None
    c1 = rows[1][0] if len(rows) > 1 else None
    return c0, c1


@router.get("/dashboard")
def get_dashboard(window: str = Query("6M")):
    conn = get_db_connection()
    try:
        fx = get_fx_rate(conn) or 1.0

        positions = conn.execute(
            "SELECT p.symbol, p.quantity, p.cost_basis_price, COALESCE(p.currency,'USD') AS ccy, "
            "       f.sector, u.name "
            "FROM positions_ibkr p "
            "LEFT JOIN fundamentals f ON f.symbol=p.symbol "
            "LEFT JOIN tracked_universe u ON u.symbol=p.symbol "
            "WHERE p.quantity > 0").fetchall()

        holdings, total_eur, prev_total_eur, cost_eur, usd_eur = [], 0.0, 0.0, 0.0, 0.0
        for sym, qty, cost, ccy, sector, name in positions:
            c0, c1 = _latest_two_closes(conn, sym)
            if c0 is None:
                continue
            rate = fx if ccy == "USD" else 1.0
            mv = qty * c0 / rate
            holdings.append({"symbol": sym, "name": name, "qty": qty, "close": c0,
                             "prev_close": c1, "ccy": ccy, "sector": sector or "Other",
                             "mv_eur": mv, "cost_eur": (qty * cost / rate) if cost else None})
            total_eur += mv
            prev_total_eur += qty * (c1 if c1 is not None else c0) / rate
            if cost:
                cost_eur += qty * cost / rate
            if ccy == "USD":
                usd_eur += mv

        day_change = total_eur - prev_total_eur
        net_worth = {
            "value_eur": round(total_eur, 2),
            "day_change_eur": round(day_change, 2),
            "day_change_pct": round(day_change / prev_total_eur * 100, 2) if prev_total_eur else 0.0,
            "unrealized_pnl_eur": round(total_eur - cost_eur, 2) if cost_eur else None,
            "positions": len(holdings),
            "usd_exposure_pct": round(usd_eur / total_eur * 100, 1) if total_eur else 0.0,
        }

        def _bucket(key_fn):
            agg = {}
            for h in holdings:
                agg[key_fn(h)] = agg.get(key_fn(h), 0.0) + h["mv_eur"]
            return sorted(
                ({"label": k, "value_eur": round(v, 2),
                  "pct": round(v / total_eur * 100, 1) if total_eur else 0.0}
                 for k, v in agg.items()),
                key=lambda x: -x["value_eur"])
        allocation = {"sector": _bucket(lambda h: h["sector"]),
                      "position": _bucket(lambda h: h["symbol"]),
                      "currency": _bucket(lambda h: h["ccy"])}

        cutoff = (datetime.now() - timedelta(days=WINDOWS.get(window, 182))).date().isoformat()
        hist = conn.execute(
            "SELECT date, value_eur FROM portfolio_value_history WHERE date >= ? ORDER BY date",
            (cutoff,)).fetchall()
        bench = conn.execute(
            "SELECT time, close FROM market_data WHERE symbol='^GSPC' AND time >= ? ORDER BY time",
            (cutoff,)).fetchall()

        def _normalize(series):
            if not series or not series[0][1]:
                return []
            base = series[0][1]
            return [{"date": d, "value": round(v / base * 100, 2)} for d, v in series]
        performance = {"portfolio": _normalize(hist), "benchmark": _normalize(bench)}

        movers = sorted(
            ({"symbol": h["symbol"], "close": h["close"], "prev_close": h["prev_close"],
              "change_pct": round((h["close"] / h["prev_close"] - 1) * 100, 2),
              "day_pnl_eur": round(h["qty"] * (h["close"] - h["prev_close"])
                                   / (fx if h["ccy"] == "USD" else 1.0), 2)}
             for h in holdings if h["prev_close"]),
            key=lambda m: -abs(m["change_pct"]))

        sell = []
        for h in holdings:
            fired = [r[0] for r in conn.execute(
                "SELECT signal_type FROM holding_signals WHERE symbol=? AND fired=1",
                (h["symbol"],)).fetchall()]
            if fired:
                ret = (round((h["mv_eur"] / h["cost_eur"] - 1) * 100, 1)
                       if h.get("cost_eur") else None)
                sell.append({"symbol": h["symbol"], "quantity": h["qty"],
                             "return_pct": ret, "fired": fired, "n_fired": len(fired)})
        sell.sort(key=lambda s: -s["n_fired"])

        buy = [dict(r) for r in conn.execute(
            "SELECT symbol, name, verdict, score_total, gates_passed FROM research_overview "
            "WHERE verdict IN ('strong_buy','buy') ORDER BY score_total DESC LIMIT 6")]

        def _one(sql):
            row = conn.execute(sql).fetchone()
            return row[0] if row else None
        as_of = {
            "prices": _one("SELECT MAX(time) FROM market_data"),
            "signals": _one("SELECT MAX(date) FROM screen_signals"),
            "fundamentals": _one("SELECT MAX(fetched_at) FROM fundamentals"),
            "ibkr": _one("SELECT MAX(finished_at) FROM sync_runs WHERE action='ibkr'"),
        }

        return {"as_of": as_of, "fx_rate": fx, "net_worth": net_worth,
                "allocation": allocation, "performance": performance,
                "movers": movers, "actions": {"sell": sell, "buy": buy}}
    finally:
        conn.close()
```

Register in `backend/api/main.py` next to the other routers: `from backend.api.routes import dashboard` + `app.include_router(dashboard.router)`.

- [ ] **Step 4: Run tests** — `backend/venv/bin/python -m pytest backend/tests/test_dashboard_route.py -v` → 3 PASS; then full suite `-q` → green.

- [ ] **Step 5: Live smoke + commit**

```bash
# restart backend first (kill uvicorn on 8010, relaunch backend/venv/bin/uvicorn backend.api.main:app --port 8010)
curl -s "http://localhost:8010/api/dashboard" | python3 -m json.tool | head -30
git add backend/api/routes/dashboard.py backend/api/main.py backend/tests/test_dashboard_route.py
git commit -m "[STORY-V-4] feat: GET /api/dashboard aggregate endpoint"
```

---

### Task 5: Dashboard frontend (components + default tab)

**Files:**
- Create: `frontend/components/dashboard/Dashboard.tsx` (container, fetches `/api/proxy/api/dashboard`)
- Create: `frontend/components/dashboard/NetWorthCard.tsx`, `AllocationDonut.tsx`, `PerformanceChart.tsx`, `ActionQueue.tsx`, `MoversCard.tsx`, `StalenessChips.tsx`
- Modify: `frontend/app/page.tsx` — `TabType` gains `'dashboard'`, becomes the default `useState<TabType>('dashboard')`, tab bar gets Dashboard first, `{activeTab === 'dashboard' && <Dashboard onSelectSymbol={setSelectedSymbol} />}`
- Test: `frontend/__tests__/dashboard.test.tsx`

**Interfaces:**
- Consumes: the Task 4 JSON verbatim (`net_worth.value_eur`, `allocation.sector[]`, `performance.portfolio[]`, `movers[]`, `actions.sell[]/buy[]`, `as_of`).
- Produces: `<Dashboard onSelectSymbol={(sym: string) => void} />` — clicking any symbol opens the existing detail sheet.

Visual spec = approved mockup `dashboard-v1.html`: dark cards (use the app's existing card/token classes, not hard-coded hex), donut and line as inline SVG (donut: `stroke-dasharray` circles, exactly as the mockup; line: `<path>` from normalized series), EUR formatting via `Intl.NumberFormat('en-IE', {style:'currency', currency:'EUR', maximumFractionDigits:0})`.

- [ ] **Step 1: Write failing test**

```tsx
// frontend/__tests__/dashboard.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { Dashboard } from '@/components/dashboard/Dashboard';

const payload = {
  as_of: { prices: '2026-07-09', signals: '2026-07-09', fundamentals: '2026-07-10T14:21:00Z', ibkr: '2026-07-10T09:09:00Z' },
  fx_rate: 1.1,
  net_worth: { value_eur: 118339, day_change_eur: 614, day_change_pct: 0.52, unrealized_pnl_eur: 29911, positions: 18, usd_exposure_pct: 87.1 },
  allocation: { sector: [{ label: 'Technology', value_eur: 57815, pct: 48.9 }], position: [], currency: [] },
  performance: { portfolio: [{ date: '2026-01-02', value: 100 }, { date: '2026-07-09', value: 118.4 }], benchmark: [{ date: '2026-01-02', value: 100 }, { date: '2026-07-09', value: 111.2 }] },
  movers: [{ symbol: 'SOFI', close: 18.62, prev_close: 17.73, change_pct: 5.02, day_pnl_eur: 573 }],
  actions: { sell: [{ symbol: 'RGTI', quantity: 29, return_pct: -57.9, fired: ['stop_loss'], n_fired: 6 }], buy: [{ symbol: 'SPG', name: 'Simon Property Group', verdict: 'strong_buy', score_total: 77.3, gates_passed: 7 }] },
};

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => payload }) as jest.Mock;
});

test('renders net worth, action queue and movers from the API', async () => {
  render(<Dashboard onSelectSymbol={() => {}} />);
  await waitFor(() => expect(screen.getByText(/€118,339/)).toBeInTheDocument());
  expect(screen.getByText('RGTI')).toBeInTheDocument();
  expect(screen.getByText('SPG')).toBeInTheDocument();
  expect(screen.getByText('SOFI')).toBeInTheDocument();
  expect(screen.getByText(/Technology/)).toBeInTheDocument();
});

test('clicking a mover calls onSelectSymbol', async () => {
  const onSelect = jest.fn();
  render(<Dashboard onSelectSymbol={onSelect} />);
  await waitFor(() => screen.getByText('SOFI'));
  screen.getByText('SOFI').click();
  expect(onSelect).toHaveBeenCalledWith('SOFI');
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && npx jest __tests__/dashboard.test.tsx` → FAIL (module not found)

- [ ] **Step 3: Implement components.** `Dashboard.tsx` fetches once on mount (`/api/proxy/api/dashboard?window=` + selected window state), holds the payload in state, renders the grid layout from the mockup (row 1: NetWorthCard · AllocationDonut · PerformanceChart; row 2: ActionQueue · MoversCard; StalenessChips in a header strip). Every sub-component is a pure render of its payload slice — copy the mockup's structure translating inline styles to the app's Tailwind classes (`bg-card`, `border`, `rounded-xl`, `text-muted-foreground`, `tabular-nums`). AllocationDonut takes `{data, mode, onMode}` with the three pills switching `sector | position | currency`. PerformanceChart maps the two normalized series to SVG paths:

```tsx
const toPath = (pts: { value: number }[], w = 400, h = 120) => {
  if (pts.length < 2) return '';
  const vals = pts.map(p => p.value);
  const [lo, hi] = [Math.min(...vals), Math.max(...vals)];
  const y = (v: number) => h - ((v - lo) / (hi - lo || 1)) * (h - 16) - 8;
  const x = (i: number) => (i / (pts.length - 1)) * w;
  return pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ');
};
```

ActionQueue renders `actions.sell` (top 3 by `n_fired` + "+N more → open Portfolio") and `actions.buy` (grid of verdict chips); all symbols clickable → `onSelectSymbol(sym)`.

- [ ] **Step 4: Run tests** — `cd frontend && npx jest` → all green (existing 8 + new 2)

- [ ] **Step 5: Wire the tab.** In `frontend/app/page.tsx`: extend `TabType`, default `'dashboard'`, add the tab button first in the tab bar (same styling as the others, label `Dashboard`), render block `{activeTab === 'dashboard' && <Dashboard onSelectSymbol={setSelectedSymbol} />}`. Verify manually at http://localhost:3010.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/dashboard/ frontend/__tests__/dashboard.test.tsx frontend/app/page.tsx
git commit -m "[STORY-V-5] feat: Dashboard tab — net worth, allocation, performance, action queue, movers"
```

---

### Task 6: Prune the Research tab

**Files:**
- Modify: `frontend/app/page.tsx` — inside `{activeTab === 'browse-universe' && ...}` (starts line ~1418): **keep** the Research block (`<h2>Research</h2>` through `<ResearchGrid …/>`, lines ~1420-1439), **delete** the entire `Market Data` Card (starts at comment `{/* Market data sync … */}` line ~1441) and the old `Browse Universe` Card below it (search `Browse Universe` heading inside the same tab block — delete through its closing `</Card>`). Also delete now-unused state/handlers flagged by ESLint: `marketDataStatus`, `fetchMarketDataStatus`, `handleSyncMarketData`, `handleSyncAnalytics`, `marketDataSyncing`, `analyticsSyncing`, `universeCoverage`, `fetchUniverseCoverage` and the `fetchUniverseCoverage()/fetchMarketDataStatus()` calls in the tab's `onClick` (line ~1377).

**Interfaces:** none new — SyncToolbar already covers sync; coverage stats surface via Dashboard staleness chips.

- [ ] **Step 1: Delete the two sections + dead code** as described.
- [ ] **Step 2: Lint + tests** — `cd frontend && npx eslint app/page.tsx && npx jest` → clean, green.
- [ ] **Step 3: Visual check** — Research tab shows only header + toolbar + tuning + grid, http://localhost:3010.
- [ ] **Step 4: Commit** — `git add frontend/app/page.tsx && git commit -m "[STORY-V-6] refactor: Research tab = grid+toolbar only; retire Market Data panel and old universe list"`

---

### Task 7: Journal (trades-first Transactions + guarded delete)

**Files:**
- Modify: `frontend/app/page.tsx` — tab label `Transactions` → `Journal`; add a `Show cash & forex` toggle (default **off**) that filters the rendered rows: hide rows where `asset_category === 'CASH'` (the EUR.USD conversions); guard `Delete All Transactions` behind `window.confirm` requiring the literal word: `prompt('Type DELETE to remove all 575 transactions')` → proceed only when input === 'DELETE'; demote the button style from red-primary to a small text-danger link at the bottom.
- Test: `frontend/__tests__/journal-filter.test.tsx` — render the transactions table component (or the filter helper) with two rows (`asset_category: 'CASH'` and `'STK'`) and assert only STK shows by default, both with the toggle on. If the table isn't extractable as a component, extract the filter as `frontend/lib/journal.ts`:

```ts
export interface TxRow { asset_category: string | null }
export function visibleTransactions<T extends TxRow>(rows: T[], showCash: boolean): T[] {
  return showCash ? rows : rows.filter(r => r.asset_category !== 'CASH');
}
```

with test:

```ts
import { visibleTransactions } from '@/lib/journal';
test('hides CASH rows by default, shows with toggle', () => {
  const rows = [{ asset_category: 'CASH' }, { asset_category: 'STK' }, { asset_category: null }];
  expect(visibleTransactions(rows, false)).toHaveLength(2);
  expect(visibleTransactions(rows, true)).toHaveLength(3);
});
```

- [ ] **Step 1: Write the filter test** (above) → run `npx jest __tests__/journal-filter.test.tsx` → FAIL
- [ ] **Step 2: Implement `frontend/lib/journal.ts`** (above) → test PASS
- [ ] **Step 3: Wire into page.tsx** — apply `visibleTransactions(transactions, showCash)` where the table maps rows; add the toggle checkbox next to the existing filters; rename the tab label; guard + demote the delete button.
- [ ] **Step 4: Lint, jest, visual check, commit** — `git commit -m "[STORY-V-7] feat: Journal — trades-first filter, guarded delete"`

---

### Task 8: Settings rename + English-only sweep

**Files:**
- Modify: `frontend/app/page.tsx` (and any component containing French copy)

- [ ] **Step 1: Rename** tab label `Configuration` → `Settings` (the `TabType` value `'configuration'` may stay — label-only change keeps the diff minimal).
- [ ] **Step 2: Sweep French copy.** `grep -rn "Connecté\|Quantité\|Précédent\|Suivant\|Afficher\|Prix\|Frais\|Base de données\|Connectée" frontend/app frontend/components --include='*.tsx'` and replace: Connecté→Connected · Connectée→Connected · Quantité→Qty · Prix→Price · Frais→Fees · Précédent→Previous · Suivant→Next · Afficher→Show · Base de données→Database. Re-run the grep → zero hits.
- [ ] **Step 3: Jest + visual check + commit** — `git commit -m "[STORY-V-8] refactor: Settings rename + English-only UI copy"`

---

### Task 9: Technical signals card in the detail popup

**Files:**
- Modify: `backend/api/routes/security.py` (extend `/api/security/{symbol}/detail` with `technical` + `zigzag` blocks)
- Modify: `frontend/components/security-detail/SecurityDetailSheet.tsx` (new card between Indicators and Fundamentals)
- Test: `backend/tests/test_security_routes.py` (extend) + `frontend/__tests__/detail-technical.test.tsx`

**Interfaces:**
- Consumes: `screen_signals` row, latest `breakout_signals` row (incl. `consolidation_bottom/top/range_pct/duration_days`), `consolidation_core.calculate_zigzag` + `load_params` over the last 41 market_data bars.
- Produces detail-response additions:

```json
{
  "technical": {"momentum_5d": 2.63, "momentum_20d": -2.6, "momentum_60d": 7.12,
                 "multi_factor_momentum": 2.41, "ma_cross_status": "All Bullish",
                 "trend_aligned": 0, "volume_spike": 0, "near_52w_high": 0,
                 "dist_from_52w_high": -14.3, "mrsi": -0.021, "signal_date": "2026-07-09"},
  "breakout": {"status": "no_consolidation_patterns", "direction": "none", "strength": null,
                "volume_ratio": null, "support": null, "resistance": null,
                "range_pct": null, "duration_days": null, "date": "2026-07-09"},
  "zigzag": {"deviation_pct": 6.0, "window_days": 40,
              "swings": [{"date": "2026-05-14", "price": 236.54, "type": "peak"}]}
}
```

- [ ] **Step 1: Write failing backend test** — in `backend/tests/test_security_routes.py` add:

```python
def test_detail_includes_technical_breakout_zigzag(temp_db):
    """Detail response carries screen signals, latest breakout (with bounds) and
    zigzag swings so the popup can render the Technical signals card."""
    _seed_security(temp_db, "NVDA")  # reuse/extend the file's existing seed helper:
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO screen_signals (symbol, date, momentum_5d, momentum_60d, ma_cross_status) "
                 "VALUES ('NVDA','2026-07-09', 2.63, 7.12, 'All Bullish')")
    conn.execute("INSERT INTO breakout_signals (symbol, date, breakout_status, breakout_direction, "
                 "consolidation_bottom, consolidation_top) "
                 "VALUES ('NVDA','2026-07-09','breakout_detected','bullish', 190.0, 200.0)")
    conn.commit(); conn.close()

    resp = client.get("/api/security/NVDA/detail")
    body = resp.json()
    assert body["technical"]["ma_cross_status"] == "All Bullish"
    assert body["breakout"]["support"] == 190.0
    assert isinstance(body["zigzag"]["swings"], list)  # may be empty on short seeds
```

- [ ] **Step 2: Run to verify fail** → KeyError/assert fail on `technical`
- [ ] **Step 3: Implement** in `security.py`: read the `screen_signals` row (`SELECT momentum_5d, momentum_20d, momentum_60d, multi_factor_momentum, ma_cross_status, trend_aligned, volume_spike, near_52w_high, dist_from_52w_high, vs_benchmark AS mrsi, date FROM screen_signals WHERE symbol=?`), the latest `breakout_signals` row aliasing `consolidation_bottom AS support` etc., and compute swings:

```python
from backend.scripts.consolidation_core import calculate_zigzag, load_params
params = load_params(conn)
df = pd.read_sql_query("SELECT time, high, low, close FROM market_data WHERE symbol=? ORDER BY time ASC", conn, params=[symbol])
swings = []
if len(df) >= 20:
    df["time"] = pd.to_datetime(df["time"])
    pts = calculate_zigzag(df.tail(41).iloc[:-1].copy(), params) or []
    swings = [{"date": str(p["date"].date()), "price": round(float(p["price"]), 2), "type": p["type"]} for p in pts]
detail["technical"] = {...}   # keys exactly as the Interfaces block
detail["breakout"] = {...}
detail["zigzag"] = {"deviation_pct": params["zigzag_deviation"], "window_days": params["lookback_days"], "swings": swings}
```

- [ ] **Step 4: Backend tests pass** → full suite green
- [ ] **Step 5: Frontend card** — in `SecurityDetailSheet.tsx` add a `Technical signals` card (grid of the 9 metrics, color semantics: green >0 / red <0), a `ZigZag swings` block (SVG polyline over `zigzag.swings` + monospace swing list) and, when `breakout.status !== 'no_consolidation_patterns'`, a `Breakout` block (support→resistance, strength, volume ratio) — per approved mockup v2 section ⑥. Jest test `detail-technical.test.tsx`: mock the detail payload, assert 'All Bullish', '+7.12%', and the swing list render.
- [ ] **Step 6: Commit** — `git commit -m "[STORY-V-9] feat: Technical signals + ZigZag + Breakout cards in detail popup"`

---

### Task 10: Grouped, color-coded columns in ResearchGrid

**Files:**
- Modify: `frontend/lib/research.ts` (add `GROUP_COLORS`), `frontend/components/research/ResearchGrid.tsx` (grouped header row)
- Test: `frontend/__tests__/research-grid.test.tsx` (extend)

**Interfaces:** consumes the existing `COLUMNS[].group` field (`Identity/Price/Indicators/Momentum/Consolidation/Breakout/Fundamentals/Score`).

- [ ] **Step 1: Failing test** — render ResearchGrid with rows and assert a group header row exists: `expect(screen.getByText('Momentum')).toBeInTheDocument()` alongside existing column labels, and that the group cell spans its visible columns (query `th[colspan]`).
- [ ] **Step 2: Implement** — in `research.ts`: `export const GROUP_COLORS: Record<string,string> = { Momentum:'#5b9bd5', Indicators:'#8f7ee8', Breakout:'#d9a441', Consolidation:'#4fd08d' }` (others default muted). In `ResearchGrid.tsx`, above the existing `<th>` row add a first header row grouping consecutive visible columns by `group`, `colSpan` = run length, `borderBottom: 2px solid GROUP_COLORS[group] ?? 'var(--border)'`.
- [ ] **Step 3: Jest green, visual check, commit** — `git commit -m "[STORY-V-10] feat: grouped color-coded column headers in ResearchGrid"`

---

### Task 11: E2E smoke + docs close-out

**Files:**
- Create: `frontend/e2e/dashboard_smoke.py` (Playwright, pattern of `scratchpad/walk_app.py` from the Phase B walk)
- Modify: `docs/project/config/build-log.md`, `docs/project/config/codebase.md`, `docs/project/config/epics/ACTIVE.md`, `workflow/ADR.md`

- [ ] **Step 1: Write the smoke script** — headless Chromium against http://localhost:3010: assert Dashboard is the landing tab and contains `Net worth`, an SVG donut, `Action queue`, ≥1 sell row and ≥1 buy row; click a mover symbol → detail sheet opens; switch to Research → exactly one grid (assert the string `Market Data` is absent); Journal → no `EUR.USD` row visible by default; zero console errors. Screenshot each screen to the session scratchpad.
- [ ] **Step 2: Run it** — `python3 frontend/e2e/dashboard_smoke.py` → all assertions pass. Paste output into the story evidence.
- [ ] **Step 3: Docs** — build-log entry (Epic V summary + evidence), codebase.md (new modules: `portfolio_history_compute`, `routes/dashboard.py`, `components/dashboard/`), ACTIVE.md (Epic V shipped; next = Epic G frontend / Epic S Phase 2), ADR entry (FX via tracked_universe source `fx`; valuation excludes CASH legs; charts hand-rolled SVG — no chart package).
- [ ] **Step 4: Commit** — `git commit -m "[STORY-V-11] test+docs: dashboard E2E smoke + Epic V close-out"`

E2E additions for Tasks 9-10: detail popup shows `Technical signals` card with momentum values; Research grid header shows the color-coded group row.

---

## Self-Review

- **Spec coverage:** finding 1 → Tasks 2/4/5 · finding 2 → Task 6 · finding 3 → Task 4-5 action queue · finding 4 → Task 7 · finding 5 → Dashboard "Sync all" chip strip (Task 5, StalenessChips + SyncToolbar reuse) + Sync Runs stays in Settings · finding 6 → universe management already only in Settings after Task 6 removes the browse duplicate · finding 7 → Task 8 · finding 8 → StalenessChips (Task 5) fed by `as_of` (Task 4). EUR base + English confirmed by user.
- **Placeholder scan:** none — every code step has concrete code; Task 5 Step 3 references the approved mockup file for pixel-level details (exists in repo).
- **Type consistency:** `get_fx_rate(conn, on_date)` (T2→T4), `compute_history(conn, start)` (T2→T3), dashboard JSON keys (T4→T5 test payload matches endpoint shape), `visibleTransactions` (T7).
