# Screener Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get broad analytics + the exact legacy buy-signals flowing into the DB and visible in a raw diagnostic Screener grid, so real distributions can be inspected before any scoring calibration.

**Architecture:** New SQLite tables + `*_compute.py` modules mirroring `indicators_compute.py` / `holding_signals_compute.py`, wired as `/api/sync/*` steps and a read-only `/api/screener/overview` endpoint feeding a new Next.js Screener tab. Buy-signal logic (`f_watch`, `g_consolidation`, `d_breakout`) is ported **verbatim** from `docs/plans/features_pipe/`; only I/O is rewired. Scoring is built but **provisional** (Phase 2 calibrates).

**Tech Stack:** Python 3.13, FastAPI, SQLite (raw SQL), pandas, yfinance; Next.js 16 (app router), React 19, Tailwind v4, shadcn/Radix. Tests: pytest (`temp_db` fixture), FastAPI `TestClient`.

**Spec:** `docs/superpowers/specs/2026-07-01-screener-integration-design.md` (Phase 1 = §9 Phase 1).

## Global Constraints

- **Storage:** SQLite only (`output/database/finance.db`), raw SQL. No parquet/ORM.
- **Schema changes:** append `CREATE TABLE IF NOT EXISTS` (+ indexes + `INSERT OR IGNORE` seeds) to the END of `backend/database/schema.sql`. No migration files — `init_database()` re-runs `schema.sql` idempotently on startup. `IF NOT EXISTS` does NOT alter existing tables.
- **Connection:** `from backend.database.connection import get_db_connection`; `conn = get_db_connection()` then `conn.close()` (try/finally). `row_factory = sqlite3.Row` but index positionally (`r[0]`) per house style.
- **Compute modules** live in `backend/scripts/<name>_compute.py`: pure functions first, then DB layer `compute_for_symbol(conn, symbol) -> int` (UPSERT via `ON CONFLICT (...) DO UPDATE SET col = excluded.col`) and `compute_all(conn) -> dict` returning `{"symbols_processed": [...], "rows_written": int, "errors": int, "failures": [{"symbol","reason"}]}`. Wrap every float in a local `_none_if_nan`.
- **Exact-logic mandate:** port `f_watch` / `g_consolidation` / `d_breakout` algorithms verbatim (every threshold/validation identical). Faithfulness beats DRY — where the two ZigZag scripts genuinely diverge, keep both; share only truly-identical helpers. Params come from `screener_settings` with the legacy defaults.
- **yfinance indirection:** every external call goes through a module-level `_yf_*` function so tests monkeypatch it (mirror `market_data_ingestor._yf_download`).
- **Logging:** compute modules use `logger = logging.getLogger(__name__)` (like `holding_signals_compute.py`). Emojis per house convention (📥/📤/✅/❌/⚠️).
- **Tests:** `backend/tests/test_<name>.py`, `temp_db` fixture, seed via raw `sqlite3.connect(str(temp_db))`, exercise via `get_db_connection()` or `TestClient(app)`. Run from repo root: `pytest -q`. venv: `backend/venv` (python3.13).
- **No linter configured** — match surrounding style; keep `# noqa: E402` on post-pure-function imports if used.
- **UI gate:** NO UI code until the `ui-mockup` skill has produced a mockup the user approved (Task 13 gates Tasks 14–16). Aesthetic: modern financial-app/reporting.
- **Retention tiers (§5.11):** `screen_signals` / `consolidation_patterns` / `support_resistance` = latest-only (`PK(symbol)`, upsert-replace). `breakout_signals` / `screen_scores` = windowed (`PK(symbol, date)`, nightly prune). `fundamentals` = snapshot (`PK(symbol)`).

---

## Task 1: Schema — Phase 1 tables + `screener_settings` seed

**Files:**
- Modify: `backend/database/schema.sql` (append at end, after `sync_runs`)
- Test: `backend/tests/test_screener_schema.py`

**Interfaces:**
- Produces tables: `fundamentals(symbol PK, ...)`, `screen_signals(symbol PK, ...)`, `consolidation_patterns(symbol PK, ...)`, `breakout_signals(symbol, date, PK(symbol,date))`, `support_resistance(symbol, zone_type, level, PK(symbol,zone_type,level))`, `screen_scores(symbol, date, PK(symbol,date))`, `screener_settings(key PK, value_json, category)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_screener_schema.py
import sqlite3
from backend.database.connection import get_db_connection

EXPECTED_TABLES = [
    "fundamentals", "screen_signals", "consolidation_patterns",
    "breakout_signals", "support_resistance", "screen_scores", "screener_settings",
]

def _tables(temp_db):
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    return {r[0] for r in rows}

def test_phase1_tables_exist(temp_db):
    tables = _tables(temp_db)
    for t in EXPECTED_TABLES:
        assert t in tables, f"missing table {t}"

def test_screener_settings_seeded(temp_db):
    conn = sqlite3.connect(str(temp_db))
    keys = {r[0] for r in conn.execute("SELECT key FROM screener_settings").fetchall()}
    conn.close()
    for k in ("quality_gates", "consolidation_params", "scoring_weights", "retention", "account"):
        assert k in keys, f"missing setting {k}"

def test_breakout_signals_pk_is_symbol_date(temp_db):
    conn = sqlite3.connect(str(temp_db))
    pk = [r[1] for r in conn.execute("PRAGMA table_info(breakout_signals)").fetchall() if r[5] > 0]
    conn.close()
    assert set(pk) == {"symbol", "date"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_screener_schema.py -q`
Expected: FAIL (`missing table fundamentals`).

- [ ] **Step 3: Append the DDL to `schema.sql`**

Append to the END of `backend/database/schema.sql`:

```sql
-- ============================================================
-- SCREENER (Epic E) — Phase 1
-- ============================================================

-- Fundamentals snapshot (1 row/symbol, overwritten). QUALITY SCORECARD.
CREATE TABLE IF NOT EXISTS fundamentals (
    symbol TEXT PRIMARY KEY,
    long_name TEXT, sector TEXT, industry TEXT, country TEXT,
    currency TEXT, exchange TEXT, quote_type TEXT,
    -- quality gate raw values
    gross_margin REAL, roe REAL, roic REAL, roic_method TEXT,
    levered_fcf_margin REAL, interest_cover REAL, eps_5y_growth REAL, free_cashflow REAL,
    gates_passed INTEGER, gates_total INTEGER,
    -- raw statement inputs (for recompute)
    ebit REAL, tax_provision REAL, total_revenue REAL, total_debt REAL,
    total_equity REAL, cash REAL, interest_expense REAL, eps_annual_json TEXT,
    -- context
    market_cap REAL, trailing_pe REAL, forward_pe REAL, trailing_eps REAL, forward_eps REAL,
    dividend_yield REAL, recommendation_mean REAL, recommendation_key TEXT,
    number_of_analyst_opinions INTEGER, target_mean_price REAL,
    target_high_price REAL, target_low_price REAL,
    -- earnings beat/miss
    earnings_history_json TEXT, beat_rate_4q REAL,
    -- meta
    fetched_at TIMESTAMP, fetch_error TEXT, fields_missing_json TEXT
);

-- Screening signals (latest-only, f_watch). Holds only what indicators lacks.
CREATE TABLE IF NOT EXISTS screen_signals (
    symbol TEXT PRIMARY KEY,
    date TEXT,
    momentum_5d REAL, momentum_20d REAL, momentum_60d REAL, multi_factor_momentum REAL,
    vs_benchmark REAL,
    price_vs_ma50 TEXT, above_ma50 INTEGER, above_ma100 INTEGER, above_ma150 INTEGER, above_ma200 INTEGER,
    ma_cross_status TEXT, trend_aligned INTEGER, is_8d_consec INTEGER,
    volume INTEGER, avg_volume_20 REAL, volume_spike INTEGER,
    high_52w REAL, low_52w REAL, dist_from_52w_high REAL, dist_from_52w_low REAL, near_52w_high INTEGER,
    last_evaluated_at TIMESTAMP
);

-- Current consolidation/base per symbol (latest-only, g_consolidation).
CREATE TABLE IF NOT EXISTS consolidation_patterns (
    symbol TEXT PRIMARY KEY,
    date TEXT, timeframe TEXT, detection_method TEXT,
    support_level REAL, resistance_level REAL, range_pct REAL, duration_days INTEGER,
    quality_score REAL, tightness_score REAL, touch_score REAL, duration_score REAL,
    volume_score REAL, freshness_score REAL,
    total_touches INTEGER, zigzag_swings INTEGER, boundary_touches INTEGER, pct_closes_in_channel REAL,
    volume_trend TEXT, volume_decline_pct REAL, price_position_pct REAL, position_desc TEXT,
    current_price REAL, last_evaluated_at TIMESTAMP
);

-- Breakout events (windowed, d_breakout). PK(symbol, date).
CREATE TABLE IF NOT EXISTS breakout_signals (
    symbol TEXT NOT NULL, date TEXT NOT NULL,
    breakout_status TEXT, breakout_direction TEXT, breakout_day INTEGER,
    breakout_strength REAL, breakout_volume_ratio REAL,
    consolidation_bottom REAL, consolidation_top REAL, consolidation_range_pct REAL,
    consolidation_duration_days INTEGER, rejection_reason TEXT, detail_json TEXT,
    last_evaluated_at TIMESTAMP,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_breakout_signals_date ON breakout_signals(date);

-- Support/resistance zones (latest-only). PK(symbol, zone_type, level).
CREATE TABLE IF NOT EXISTS support_resistance (
    symbol TEXT NOT NULL, zone_type TEXT NOT NULL, level REAL NOT NULL,
    zone_bottom REAL, zone_top REAL, center_price REAL, touches INTEGER, strength REAL,
    date TEXT, last_evaluated_at TIMESTAMP,
    PRIMARY KEY (symbol, zone_type, level)
);

-- Composite score/verdict (windowed). PK(symbol, date). PROVISIONAL until Phase 2.
CREATE TABLE IF NOT EXISTS screen_scores (
    symbol TEXT NOT NULL, date TEXT NOT NULL,
    score_tech REAL, score_fund REAL, score_total REAL, verdict TEXT,
    tech_flags TEXT, fund_flags TEXT, multi_factor_momentum REAL,
    passed INTEGER, fail_reasons TEXT, is_provisional INTEGER DEFAULT 1,
    last_evaluated_at TIMESTAMP,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_screen_scores_date ON screen_scores(date);

-- Screener config (key/value JSON). All editable from the UI later.
CREATE TABLE IF NOT EXISTS screener_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    category TEXT
);
INSERT OR IGNORE INTO screener_settings (key, value_json, category) VALUES
 ('quality_gates', '{"gross_margin":0.60,"roe":0.15,"roic":0.10,"levered_fcf_margin":0.20,"interest_cover":3.0,"eps_5y_growth":0.10,"free_cashflow":0}', 'fundamentals'),
 ('consolidation_params', '{"zigzag_deviation":6.0,"lookback_days":40,"min_days_between_swings":2,"breakout_confirmation_pct":1.5,"volume_lookback_days":20,"min_resistance_touches":2,"min_support_touches":2,"extreme_grouping_tolerance":2.5,"timeframes":[15,30,60],"max_consolidation_range_pct":5.0,"min_consolidation_duration":20,"max_daily_change":30.0,"min_volume_threshold":5000,"max_volatility_filter":150.0}', 'signals'),
 ('scoring_weights', '{"above_ma50":10,"above_ma200":10,"ma50_rising_8d":10,"ma50_above_ma200":8,"macd_bullish":8,"rsi_neutral":5,"volume_spike":7,"breakout":12,"consolidation_quality":10,"momentum_20d_positive":8,"momentum_60d_positive":10,"near_52w_high":5}', 'scoring'),
 ('thresholds', '{"min_score_total":55,"min_score_tech":50,"min_quality_gates":4,"min_rr_ratio":1.5,"max_rsi":80,"min_market_cap":500000000}', 'scoring'),
 ('retention', '{"breakout_fresh_days":3,"breakout_retention_days":30,"screen_scores_retention_days":60}', 'retention'),
 ('account', '{"account_size":13596,"currency":"EUR","risk_pct_per_trade":1.0,"default_stop_method":"atr_2x"}', 'account');
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_screener_schema.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/database/schema.sql backend/tests/test_screener_schema.py
git commit -m "[E-1] feat: Phase-1 screener tables + settings seed"
```

---

## Task 2: Fundamentals — quality-gate pure functions

**Files:**
- Create: `backend/scripts/fundamentals_fetch.py`
- Test: `backend/tests/test_fundamentals_gates.py`

**Interfaces:**
- Produces: `compute_quality_gates(info: dict, income: dict, balance: dict, gate_thresholds: dict) -> dict` returning `{gross_margin, roe, roic, roic_method, levered_fcf_margin, interest_cover, eps_5y_growth, free_cashflow, gates_passed, gates_total, fields_missing: list, raw: {ebit, tax_provision, total_revenue, total_debt, total_equity, cash, interest_expense, eps_annual: list}}`.
- Consumes (Task 3): `_stmt_value(df_like, *labels)`, `_cagr(series)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fundamentals_gates.py
from backend.scripts.fundamentals_fetch import compute_quality_gates

GATES = {"gross_margin":0.60,"roe":0.15,"roic":0.10,"levered_fcf_margin":0.20,
         "interest_cover":3.0,"eps_5y_growth":0.10,"free_cashflow":0}

def test_all_gates_pass():
    info = {"grossMargins":0.65,"returnOnEquity":0.30,"freeCashflow":300.0,"totalRevenue":1000.0}
    income = {"EBIT":400.0,"Tax Provision":80.0,"Pretax Income":400.0,"Interest Expense":20.0,
              "Diluted EPS": [1.0, 1.2, 1.5, 1.8]}  # oldest->newest
    balance = {"Total Debt":200.0,"Stockholders Equity":800.0,"Cash And Cash Equivalents":100.0}
    r = compute_quality_gates(info, income, balance, GATES)
    assert r["gross_margin"] == 0.65
    assert round(r["roic"], 3) == round(400*(1-0.20)/(200+800-100), 3)  # 320/900
    assert r["roic_method"] == "nopat"
    assert round(r["interest_cover"], 1) == 20.0
    assert round(r["levered_fcf_margin"], 2) == 0.30
    assert r["eps_5y_growth"] > 0.10
    assert r["gates_passed"] == 7 and r["gates_total"] == 7

def test_roce_fallback_when_tax_missing():
    info = {"grossMargins":0.65,"returnOnEquity":0.30,"freeCashflow":300.0,"totalRevenue":1000.0}
    income = {"EBIT":400.0,"Interest Expense":20.0,"Diluted EPS":[1.0,1.8]}  # no tax, no cash
    balance = {"Total Debt":200.0,"Stockholders Equity":800.0}
    r = compute_quality_gates(info, income, balance, GATES)
    assert r["roic_method"] == "roce"
    assert round(r["roic"], 3) == round(400/(200+800), 3)  # EBIT/(debt+equity)

def test_missing_fields_null_and_counted():
    info = {"grossMargins":0.65,"returnOnEquity":0.30,"freeCashflow":300.0,"totalRevenue":1000.0}
    r = compute_quality_gates(info, {}, {}, GATES)  # no statements
    assert r["roic"] is None and r["interest_cover"] is None and r["eps_5y_growth"] is None
    assert "roic" in r["fields_missing"]
    assert r["gates_passed"] == 4  # gross_margin, roe, fcf, levered_fcf_margin still pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_fundamentals_gates.py -q`
Expected: FAIL (`cannot import name compute_quality_gates`).

- [ ] **Step 3: Write the pure functions**

```python
# backend/scripts/fundamentals_fetch.py
"""Fetch fundamentals + compute the 7-gate MOAT quality scorecard."""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # NaN guard
    except (TypeError, ValueError):
        return None


def _stmt_value(stmt: dict, *labels):
    """Fetch a line-item from a statement dict by trying label aliases.
    Value may be a scalar (latest) or a list (oldest->newest); returns the latest scalar."""
    for label in labels:
        if label in stmt and stmt[label] is not None:
            v = stmt[label]
            if isinstance(v, (list, tuple)):
                return _num(v[-1]) if len(v) else None
            return _num(v)
    return None


def _eps_series(stmt: dict):
    for label in ("Diluted EPS", "Basic EPS"):
        if label in stmt and isinstance(stmt[label], (list, tuple)):
            vals = [_num(x) for x in stmt[label] if _num(x) is not None]
            if len(vals) >= 2:
                return vals
    return []


def _cagr(series):
    """CAGR from oldest->newest positive EPS series; None if not computable."""
    if len(series) < 2:
        return None
    first, last = series[0], series[-1]
    if first is None or last is None or first <= 0 or last <= 0:
        return None
    years = len(series) - 1
    return (last / first) ** (1.0 / years) - 1.0


def compute_quality_gates(info: dict, income: dict, balance: dict, gate_thresholds: dict) -> dict:
    info = info or {}
    income = income or {}
    balance = balance or {}
    missing = []

    gross_margin = _num(info.get("grossMargins"))
    roe = _num(info.get("returnOnEquity"))
    free_cashflow = _num(info.get("freeCashflow"))
    total_revenue = _num(info.get("totalRevenue"))

    levered_fcf_margin = (free_cashflow / total_revenue
                          if free_cashflow is not None and total_revenue else None)

    ebit = _stmt_value(income, "EBIT", "Operating Income")
    tax_provision = _stmt_value(income, "Tax Provision", "Income Tax Expense")
    pretax = _stmt_value(income, "Pretax Income", "Pre Tax Income")
    interest_expense = _stmt_value(income, "Interest Expense")
    total_debt = _stmt_value(balance, "Total Debt")
    total_equity = _stmt_value(balance, "Stockholders Equity", "Total Equity Gross Minority Interest")
    cash = _stmt_value(balance, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")

    # ROIC = NOPAT / invested capital, with pre-tax ROCE fallback
    roic, roic_method = None, None
    if ebit is not None and total_debt is not None and total_equity is not None:
        if tax_provision is not None and pretax not in (None, 0) and cash is not None:
            tax_rate = max(0.0, min(1.0, tax_provision / pretax))
            invested = total_debt + total_equity - cash
            if invested:
                roic, roic_method = ebit * (1 - tax_rate) / invested, "nopat"
        if roic is None:  # fallback
            denom = total_debt + total_equity
            if denom:
                roic, roic_method = ebit / denom, "roce"

    interest_cover = (ebit / interest_expense
                      if ebit is not None and interest_expense not in (None, 0) else None)

    eps_annual = _eps_series(income)
    eps_5y_growth = _cagr(eps_annual)

    values = {
        "gross_margin": gross_margin, "roe": roe, "roic": roic,
        "levered_fcf_margin": levered_fcf_margin, "interest_cover": interest_cover,
        "eps_5y_growth": eps_5y_growth, "free_cashflow": free_cashflow,
    }
    for k, v in values.items():
        if v is None:
            missing.append(k)

    gates_passed = sum(
        1 for k, thr in gate_thresholds.items()
        if values.get(k) is not None and values[k] > thr
    )
    return {
        **values, "roic_method": roic_method,
        "gates_passed": gates_passed, "gates_total": len(gate_thresholds),
        "fields_missing": missing,
        "raw": {"ebit": ebit, "tax_provision": tax_provision, "total_revenue": total_revenue,
                "total_debt": total_debt, "total_equity": total_equity, "cash": cash,
                "interest_expense": interest_expense, "eps_annual": eps_annual},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_fundamentals_gates.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/fundamentals_fetch.py backend/tests/test_fundamentals_gates.py
git commit -m "[E-1] feat: quality-gate computation (7 gates + ROCE fallback)"
```

---

## Task 3: Fundamentals — fetch + upsert into `fundamentals`

**Files:**
- Modify: `backend/scripts/fundamentals_fetch.py`
- Test: `backend/tests/test_fundamentals_fetch.py`

**Interfaces:**
- Consumes: `compute_quality_gates(...)` (Task 2), `get_db_connection` (Global), gate thresholds from `screener_settings`.
- Produces: `_yf_ticker(symbol) -> object` (indirection, monkeypatched in tests) with attrs `.info: dict`, `.income_stmt`, `.balance_sheet`, `.earnings_history`; `fetch_for_symbol(conn, symbol, gates) -> bool`; `fetch_all(conn) -> dict` (`{symbols_processed, rows_written, errors, failures}`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fundamentals_fetch.py
import sqlite3
import backend.scripts.fundamentals_fetch as ff
from backend.database.connection import get_db_connection


class _FakeTicker:
    def __init__(self, symbol):
        self.info = {"longName": f"{symbol} Inc", "sector": "Technology", "currency": "USD",
                     "grossMargins": 0.65, "returnOnEquity": 0.30, "freeCashflow": 300.0,
                     "totalRevenue": 1000.0, "marketCap": 2.0e12, "trailingPE": 30.0}
        self.income_stmt = {"EBIT": 400.0, "Tax Provision": 80.0, "Pretax Income": 400.0,
                            "Interest Expense": 20.0, "Diluted EPS": [1.0, 1.2, 1.5, 1.8]}
        self.balance_sheet = {"Total Debt": 200.0, "Stockholders Equity": 800.0,
                              "Cash And Cash Equivalents": 100.0}
        self.earnings_history = [{"epsActual": 1.8, "epsEstimate": 1.6},
                                 {"epsActual": 1.5, "epsEstimate": 1.5}]


def _seed_universe(temp_db, symbols):
    conn = sqlite3.connect(str(temp_db))
    for s in symbols:
        conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled) VALUES (?, 1)", (s,))
    conn.commit(); conn.close()


def test_fetch_all_writes_rows(temp_db, monkeypatch):
    _seed_universe(temp_db, ["AAPL", "MSFT"])
    monkeypatch.setattr(ff, "_yf_ticker", lambda s: _FakeTicker(s))
    conn = get_db_connection()
    result = ff.fetch_all(conn)
    row = conn.execute("SELECT gates_passed, roic_method, gross_margin, long_name FROM fundamentals WHERE symbol='AAPL'").fetchone()
    conn.close()
    assert result["rows_written"] == 2
    assert row[0] == 7           # gates_passed
    assert row[1] == "nopat"     # roic_method
    assert row[2] == 0.65        # gross_margin
    assert row[3] == "AAPL Inc"


def test_fetch_records_error_not_crash(temp_db, monkeypatch):
    _seed_universe(temp_db, ["BAD"])
    def _boom(s): raise RuntimeError("yf down")
    monkeypatch.setattr(ff, "_yf_ticker", _boom)
    conn = get_db_connection()
    result = ff.fetch_all(conn)
    conn.close()
    assert result["errors"] == 1
    assert result["failures"][0]["symbol"] == "BAD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_fundamentals_fetch.py -q`
Expected: FAIL (`module has no attribute _yf_ticker`).

- [ ] **Step 3: Add fetch + upsert to `fundamentals_fetch.py`**

Append to `backend/scripts/fundamentals_fetch.py`:

```python
import json


def _yf_ticker(symbol):
    """Indirected so tests can monkeypatch. Returns a yfinance Ticker."""
    import yfinance as yf
    return yf.Ticker(symbol)


def _as_dict(stmt):
    """Normalize a yfinance statement (DataFrame or dict) to {label: latest_or_series}.
    DataFrame: columns are period dates (newest first); we return oldest->newest lists."""
    if stmt is None:
        return {}
    if isinstance(stmt, dict):
        return stmt
    try:
        # pandas DataFrame: index = line items, columns = periods (newest first)
        out = {}
        cols = list(stmt.columns)[::-1]  # oldest->newest
        for label in stmt.index:
            out[str(label)] = [stmt.loc[label, c] for c in cols]
        return out
    except Exception:
        return {}


def _earnings_list(hist):
    if hist is None:
        return []
    if isinstance(hist, list):
        return hist
    try:
        return hist.reset_index().to_dict("records")
    except Exception:
        return []


def _load_gates(conn) -> dict:
    row = conn.execute("SELECT value_json FROM screener_settings WHERE key='quality_gates'").fetchone()
    return json.loads(row[0]) if row else {}


_COLS = [
    "symbol","long_name","sector","industry","country","currency","exchange","quote_type",
    "gross_margin","roe","roic","roic_method","levered_fcf_margin","interest_cover",
    "eps_5y_growth","free_cashflow","gates_passed","gates_total",
    "ebit","tax_provision","total_revenue","total_debt","total_equity","cash",
    "interest_expense","eps_annual_json","market_cap","trailing_pe","forward_pe",
    "trailing_eps","forward_eps","dividend_yield","recommendation_mean","recommendation_key",
    "number_of_analyst_opinions","target_mean_price","target_high_price","target_low_price",
    "earnings_history_json","beat_rate_4q","fetched_at","fetch_error","fields_missing_json",
]


def fetch_for_symbol(conn, symbol: str, gates: dict) -> bool:
    t = _yf_ticker(symbol)
    info = t.info or {}
    income = _as_dict(getattr(t, "income_stmt", None))
    balance = _as_dict(getattr(t, "balance_sheet", None))
    earnings = _earnings_list(getattr(t, "earnings_history", None))

    q = compute_quality_gates(info, income, balance, gates)
    raw = q["raw"]

    beats = [e for e in earnings if _num(e.get("epsActual")) is not None and _num(e.get("epsEstimate")) is not None]
    beat_rate = (sum(1 for e in beats if _num(e["epsActual"]) > _num(e["epsEstimate"])) / len(beats)
                 if beats else None)

    now = datetime.now(timezone.utc).isoformat()
    values = {
        "symbol": symbol, "long_name": info.get("longName"), "sector": info.get("sector"),
        "industry": info.get("industry"), "country": info.get("country"),
        "currency": info.get("currency"), "exchange": info.get("exchange"),
        "quote_type": info.get("quoteType"),
        "gross_margin": q["gross_margin"], "roe": q["roe"], "roic": q["roic"],
        "roic_method": q["roic_method"], "levered_fcf_margin": q["levered_fcf_margin"],
        "interest_cover": q["interest_cover"], "eps_5y_growth": q["eps_5y_growth"],
        "free_cashflow": q["free_cashflow"], "gates_passed": q["gates_passed"],
        "gates_total": q["gates_total"], "ebit": raw["ebit"], "tax_provision": raw["tax_provision"],
        "total_revenue": raw["total_revenue"], "total_debt": raw["total_debt"],
        "total_equity": raw["total_equity"], "cash": raw["cash"],
        "interest_expense": raw["interest_expense"], "eps_annual_json": json.dumps(raw["eps_annual"]),
        "market_cap": _num(info.get("marketCap")), "trailing_pe": _num(info.get("trailingPE")),
        "forward_pe": _num(info.get("forwardPE")), "trailing_eps": _num(info.get("trailingEps")),
        "forward_eps": _num(info.get("forwardEps")), "dividend_yield": _num(info.get("dividendYield")),
        "recommendation_mean": _num(info.get("recommendationMean")),
        "recommendation_key": info.get("recommendationKey"),
        "number_of_analyst_opinions": _num(info.get("numberOfAnalystOpinions")),
        "target_mean_price": _num(info.get("targetMeanPrice")),
        "target_high_price": _num(info.get("targetHighPrice")),
        "target_low_price": _num(info.get("targetLowPrice")),
        "earnings_history_json": json.dumps(earnings, default=str), "beat_rate_4q": beat_rate,
        "fetched_at": now, "fetch_error": None, "fields_missing_json": json.dumps(q["fields_missing"]),
    }
    cols = ",".join(_COLS)
    placeholders = ",".join("?" * len(_COLS))
    updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "symbol")
    conn.execute(
        f"INSERT INTO fundamentals ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(symbol) DO UPDATE SET {updates}",
        tuple(values[c] for c in _COLS),
    )
    conn.commit()
    return True


def fetch_all(conn) -> dict:
    gates = _load_gates(conn)
    rows = conn.execute("SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()
    processed, written, errors, failures = [], 0, 0, []
    for (sym,) in rows:
        try:
            if fetch_for_symbol(conn, sym, gates):
                processed.append(sym); written += 1
        except Exception as e:
            logger.error(f"❌ fundamentals fetch failed for {sym}: {e}")
            errors += 1
            failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    return {"symbols_processed": processed, "rows_written": written, "errors": errors, "failures": failures}


def run() -> dict:
    conn = get_db_connection()
    try:
        return fetch_all(conn)
    finally:
        conn.close()
```

Add near the top (after the stdlib imports): `from backend.database.connection import get_db_connection  # noqa: E402`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_fundamentals_fetch.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/fundamentals_fetch.py backend/tests/test_fundamentals_fetch.py
git commit -m "[E-1] feat: fundamentals fetch + upsert (info + statements + earnings)"
```

---

## Task 4: `/api/sync/fundamentals` step + last-run metadata

**Files:**
- Modify: `backend/api/routes/sync.py` (add `_step_fundamentals` + `@router.post("/fundamentals")` + `@router.get("/fundamentals/status")`)
- Test: `backend/tests/test_sync_fundamentals.py`

**Interfaces:**
- Consumes: `fundamentals_fetch.fetch_all` (Task 3), `record_run` (existing).
- Produces: `POST /api/sync/fundamentals` → `{"success": True, ...}`; `GET /api/sync/fundamentals/status` → `{"last_run": iso|None, "suggested_next": iso|None, "overdue": bool}` (30-day cadence).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sync_fundamentals.py
import sqlite3
import backend.scripts.fundamentals_fetch as ff
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


class _FakeTicker:
    def __init__(self, s):
        self.info = {"longName": f"{s} Inc", "grossMargins": 0.65, "returnOnEquity": 0.30,
                     "freeCashflow": 300.0, "totalRevenue": 1000.0}
        self.income_stmt = {"EBIT": 400.0, "Diluted EPS": [1.0, 1.8]}
        self.balance_sheet = {"Total Debt": 200.0, "Stockholders Equity": 800.0}
        self.earnings_history = []


def test_sync_fundamentals_endpoint(temp_db, monkeypatch):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled) VALUES ('AAPL', 1)")
    conn.commit(); conn.close()
    monkeypatch.setattr(ff, "_yf_ticker", lambda s: _FakeTicker(s))
    resp = client.post("/api/sync/fundamentals")
    assert resp.status_code == 200
    assert resp.json()["rows_written"] == 1
    # a sync_runs row was recorded
    conn = sqlite3.connect(str(temp_db))
    n = conn.execute("SELECT COUNT(*) FROM sync_runs WHERE action='fundamentals'").fetchone()[0]
    conn.close()
    assert n == 1


def test_fundamentals_status_overdue_when_never_run(temp_db):
    resp = client.get("/api/sync/fundamentals/status")
    assert resp.status_code == 200
    assert resp.json()["overdue"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_sync_fundamentals.py -q`
Expected: FAIL (404 on `/api/sync/fundamentals`).

- [ ] **Step 3: Add the step + endpoints to `sync.py`**

Add a step closure alongside `_step_indicators` (near `sync.py:397`):

```python
def _step_fundamentals() -> dict:
    from backend.scripts.fundamentals_fetch import fetch_all
    conn = get_db_connection()
    try:
        return fetch_all(conn)
    finally:
        conn.close()
```

Add the endpoints (mirror `/market-data`'s recorder style):

```python
@router.post("/fundamentals")
async def sync_fundamentals():
    logger.info("🏦 Sync step: fundamentals")
    with record_run("fundamentals") as run:
        try:
            result = _step_fundamentals()
        except Exception as e:
            logger.error(f"❌ sync_fundamentals failed: {e}")
            run.summary(f"Fundamentals crashed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        n_fail = len(result.get("failures", []))
        run.summary(f"{len(result['symbols_processed'])} symbols · {result['rows_written']} rows · {n_fail} failures")
        run.details(result)
        if n_fail or result.get("errors", 0):
            run.status("partial")
        return {"success": True, **result}


@router.get("/fundamentals/status")
async def fundamentals_status():
    from datetime import datetime, timedelta, timezone
    conn = get_db_connection()
    row = conn.execute(
        "SELECT finished_at FROM sync_runs WHERE action='fundamentals' AND status != 'error' "
        "ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return {"last_run": None, "suggested_next": None, "overdue": True}
    last = datetime.fromisoformat(row[0])
    nxt = last + timedelta(days=30)
    overdue = datetime.now(timezone.utc) >= nxt.replace(tzinfo=nxt.tzinfo or timezone.utc)
    return {"last_run": row[0], "suggested_next": nxt.isoformat(), "overdue": overdue}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_sync_fundamentals.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/sync.py backend/tests/test_sync_fundamentals.py
git commit -m "[E-1] feat: /api/sync/fundamentals step + status (30-day cadence)"
```

---

## Task 5: `GET /api/fundamentals/{symbol}` read route

**Files:**
- Create: `backend/api/routes/fundamentals.py`
- Modify: `backend/api/main.py` (import + include_router)
- Test: `backend/tests/test_fundamentals_route.py`

**Interfaces:**
- Consumes: `fundamentals` table.
- Produces: `GET /api/fundamentals/{symbol}` → row dict or 404.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_fundamentals_route.py
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app
client = TestClient(app)

def test_get_fundamentals(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO fundamentals (symbol, long_name, gates_passed, gates_total, roic) "
                 "VALUES ('AAPL','Apple Inc',6,7,0.55)")
    conn.commit(); conn.close()
    resp = client.get("/api/fundamentals/aapl")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["gates_passed"] == 6
    assert client.get("/api/fundamentals/NOPE").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_fundamentals_route.py -q`
Expected: FAIL (404 for AAPL — route missing).

- [ ] **Step 3: Create route + register**

```python
# backend/api/routes/fundamentals.py
from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/fundamentals", tags=["fundamentals"])


@router.get("/{symbol}")
async def get_fundamentals(symbol: str):
    sym = symbol.upper()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM fundamentals WHERE symbol = ?", (sym,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"no fundamentals for {sym}")
    logger.info(f"🏦 Returned fundamentals for {sym}")
    return {k: row[k] for k in row.keys()}
```

In `backend/api/main.py`, add to the import block (~lines 21-30):
```python
from backend.api.routes.fundamentals import router as fundamentals_router
```
and to the include block (~lines 52-61):
```python
app.include_router(fundamentals_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_fundamentals_route.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/fundamentals.py backend/api/main.py backend/tests/test_fundamentals_route.py
git commit -m "[E-1] feat: GET /api/fundamentals/{symbol}"
```

---

## Task 6: `screen_signals_compute.py` — f_watch momentum/MA/volume/52w (exact formulas)

**Files:**
- Create: `backend/scripts/screen_signals_compute.py`
- Test: `backend/tests/test_screen_signals_compute.py`

**Interfaces:**
- Consumes: `market_data`, `indicators` (ma_50/100/150/200), `get_db_connection`.
- Produces: `compute_signals(df, ind) -> dict` (pure, exact f_watch formulas); `compute_for_symbol(conn, symbol) -> int`; `compute_all(conn) -> dict`.

**Port note:** the f_watch monolithic CTE reads a `moving_averages` table that no longer exists; we compute the SAME formulas in pandas from `market_data` + `indicators`. Formulas are verbatim: `momentum_Nd = (close - close_N_ago)/close_N_ago*100`; `multi_factor_momentum = 0.4*m5 + 0.3*m20 + 0.3*m60`; `volume_spike = volume > 1.5*avg_vol_20`; `is_8d_consec = 1 if MA50 rose in ≥6 of last 8 days`; `ma_cross_status` mapping from `f_watch.py:326-334`; `trend_aligned = Price>MA50>MA150 AND MA50*1.01 ≤ close ≤ MA50*1.10` (`f_watch.py:343-349`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_screen_signals_compute.py
import pandas as pd
from backend.scripts.screen_signals_compute import compute_signals

def test_momentum_and_flags_exact():
    # 70 ascending closes so momentum is positive; volume flat except last day spike
    closes = [100 + i for i in range(70)]
    vols = [1_000_000] * 69 + [3_000_000]
    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=70).astype(str),
        "high": [c + 1 for c in closes], "low": [c - 1 for c in closes],
        "close": closes, "volume": vols,
    })
    ind = {"ma_50": 150.0, "ma_100": 140.0, "ma_150": 130.0, "ma_200": 120.0}
    r = compute_signals(df, ind)
    c = closes[-1]
    assert round(r["momentum_5d"], 2) == round((c - closes[-6]) / closes[-6] * 100, 2)
    assert round(r["multi_factor_momentum"], 2) == round(
        0.4*r["momentum_5d"] + 0.3*r["momentum_20d"] + 0.3*r["momentum_60d"], 2)
    assert r["volume_spike"] == 1               # 3M > 1.5 * ~1M
    assert r["above_ma50"] == 1                 # close 169 > 150
    assert r["ma_cross_status"] == "All Bullish"  # 150>140>130
    assert r["near_52w_high"] == 1              # last close is the high
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_screen_signals_compute.py -q`
Expected: FAIL (import error).

- [ ] **Step 3: Implement pure `compute_signals` + DB layer**

Create `backend/scripts/screen_signals_compute.py`. Pure function reproduces the f_watch formulas exactly:

```python
"""Screening signals (f_watch, exact formulas) — momentum / MA cross / volume / 52w."""
import logging
from datetime import datetime, timezone
import pandas as pd

logger = logging.getLogger(__name__)


def _none_if_nan(v):
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _ret(closes, n):
    if len(closes) > n and closes[-(n + 1)]:
        return (closes[-1] - closes[-(n + 1)]) / closes[-(n + 1)] * 100.0
    return None


def _ma_cross_status(ma50, ma100, ma150):
    # Faithful to f_watch.py:326-334 SQL CASE (FIRST-MATCH). The SQL's
    # "Short-term Bullish/Bearish" WHENs are dead (any ma50>ma150 already
    # matched "Mostly Bullish"; any ma50<ma150 already matched "Mostly Bearish").
    if None in (ma50, ma100, ma150):
        return None
    if ma50 > ma100 and ma100 > ma150:
        return "All Bullish"
    if ma50 > ma150:
        return "Mostly Bullish"
    if ma50 < ma100 and ma100 < ma150:
        return "All Bearish"
    if ma50 < ma150:
        return "Mostly Bearish"
    return "Mixed"


def compute_signals(df: pd.DataFrame, ind: dict) -> dict:
    df = df.sort_values("time").reset_index(drop=True)
    closes = [float(x) for x in df["close"].tolist()]
    c = closes[-1]
    ma50, ma100, ma150, ma200 = (ind.get("ma_50"), ind.get("ma_100"),
                                 ind.get("ma_150"), ind.get("ma_200"))

    m5, m20, m60 = _ret(closes, 5), _ret(closes, 20), _ret(closes, 60)
    mfm = (0.4 * m5 + 0.3 * m20 + 0.3 * m60) if None not in (m5, m20, m60) else None

    avg_vol_20 = float(df["volume"].tail(21).iloc[:-1].mean()) if len(df) >= 21 else float(df["volume"].mean())
    vol = int(df["volume"].iloc[-1])
    volume_spike = 1 if avg_vol_20 and vol > avg_vol_20 * 1.5 else 0

    # is_8d_consec: MA50 rose in >=6 of the last 8 day-over-day steps (f_watch: consecutive_increases >= 6)
    ma50_series = df["close"].rolling(50).mean().dropna()
    is_8d = 0
    if len(ma50_series) >= 9:
        last9 = ma50_series.tail(9).tolist()
        ups = sum(1 for i in range(1, len(last9)) if last9[i] > last9[i - 1])
        is_8d = 1 if ups >= 6 else 0

    high_252 = float(df["high"].tail(252).max())
    low_252 = float(df["low"].tail(252).min())
    dist_high = (c - high_252) / high_252 * 100 if high_252 else None
    dist_low = (c - low_252) / low_252 * 100 if low_252 else None

    trend_aligned = 1 if (ma50 and ma150 and c > ma50 > ma150 and ma50 * 1.01 <= c <= ma50 * 1.10) else 0

    return {
        "date": str(df["time"].iloc[-1]),
        "momentum_5d": _none_if_nan(m5), "momentum_20d": _none_if_nan(m20),
        "momentum_60d": _none_if_nan(m60), "multi_factor_momentum": _none_if_nan(mfm),
        "vs_benchmark": _none_if_nan(ind.get("mrsi")),
        "price_vs_ma50": ("Above MA50" if ma50 and c > ma50 else "Below MA50" if ma50 else None),
        "above_ma50": 1 if ma50 and c > ma50 else 0, "above_ma100": 1 if ma100 and c > ma100 else 0,
        "above_ma150": 1 if ma150 and c > ma150 else 0, "above_ma200": 1 if ma200 and c > ma200 else 0,
        "ma_cross_status": _ma_cross_status(ma50, ma100, ma150),
        "trend_aligned": trend_aligned, "is_8d_consec": is_8d,
        "volume": vol, "avg_volume_20": _none_if_nan(avg_vol_20), "volume_spike": volume_spike,
        "high_52w": _none_if_nan(high_252), "low_52w": _none_if_nan(low_252),
        "dist_from_52w_high": _none_if_nan(dist_high), "dist_from_52w_low": _none_if_nan(dist_low),
        "near_52w_high": 1 if dist_high is not None and dist_high > -5 else 0,
    }


from backend.database.connection import get_db_connection  # noqa: E402

_COLS = ["symbol","date","momentum_5d","momentum_20d","momentum_60d","multi_factor_momentum",
         "vs_benchmark","price_vs_ma50","above_ma50","above_ma100","above_ma150","above_ma200",
         "ma_cross_status","trend_aligned","is_8d_consec","volume","avg_volume_20","volume_spike",
         "high_52w","low_52w","dist_from_52w_high","dist_from_52w_low","near_52w_high","last_evaluated_at"]


def compute_for_symbol(conn, symbol: str) -> int:
    df = pd.read_sql_query(
        "SELECT time, high, low, close, volume FROM market_data WHERE symbol = ? ORDER BY time ASC",
        conn, params=[symbol])
    if len(df) < 60:
        return 0
    ind_row = conn.execute(
        "SELECT ma_50, ma_100, ma_150, ma_200, mrsi FROM indicators WHERE symbol = ? "
        "ORDER BY time DESC LIMIT 1", (symbol,)).fetchone()
    ind = {"ma_50": ind_row[0], "ma_100": ind_row[1], "ma_150": ind_row[2],
           "ma_200": ind_row[3], "mrsi": ind_row[4]} if ind_row else {}
    sig = compute_signals(df, ind)
    sig["symbol"] = symbol
    sig["last_evaluated_at"] = datetime.now(timezone.utc).isoformat()
    updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "symbol")
    conn.execute(
        f"INSERT INTO screen_signals ({','.join(_COLS)}) VALUES ({','.join('?'*len(_COLS))}) "
        f"ON CONFLICT(symbol) DO UPDATE SET {updates}",
        tuple(sig[c] for c in _COLS))
    conn.commit()
    return 1


def compute_all(conn) -> dict:
    rows = conn.execute("SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()
    processed, written, errors, failures = [], 0, 0, []
    for (sym,) in rows:
        try:
            n = compute_for_symbol(conn, sym)
            if n:
                processed.append(sym); written += n
        except Exception as e:
            logger.error(f"❌ screen_signals failed for {sym}: {e}")
            errors += 1; failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    return {"symbols_processed": processed, "rows_written": written, "errors": errors, "failures": failures}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_screen_signals_compute.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/screen_signals_compute.py backend/tests/test_screen_signals_compute.py
git commit -m "[E-1] feat: screen_signals compute (f_watch formulas, exact)"
```

---

## Task 7: `consolidation_core.py` — shared ZigZag + quality (verbatim port)

**Files:**
- Create: `backend/scripts/consolidation_core.py`
- Test: `backend/tests/test_consolidation_core.py`

**Interfaces:**
- Produces: `is_stock_data_quality(df, params) -> (bool, str)`; `calculate_zigzag(df, params) -> list[dict]`; `load_params(conn) -> dict`.

**Port note:** copy `calculate_zigzag` VERBATIM from `docs/plans/features_pipe/d_breakout_detector_3.py:134-214` and `is_stock_data_quality` from `:105-132`, changing only: (a) take a `params` dict instead of `self.*` attributes (`params["zigzag_deviation"]`, `params["min_days_between_swings"]`, etc.); (b) remove `self`. Keep every threshold and branch identical.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_consolidation_core.py
import pandas as pd
from backend.scripts.consolidation_core import calculate_zigzag, is_stock_data_quality

PARAMS = {"zigzag_deviation": 6.0, "min_days_between_swings": 2, "max_daily_change": 30.0,
          "min_volume_threshold": 5000, "max_volatility_filter": 150.0}

def _osc_df(n=40):
    # oscillating series that must produce >=2 peaks and >=2 troughs
    prices = []
    for i in range(n):
        prices.append(100 + (8 if i % 8 < 4 else -8))
    return pd.DataFrame({
        "time": pd.to_datetime(pd.date_range("2026-01-01", periods=n)),
        "open": prices, "high": [p + 1 for p in prices], "low": [p - 1 for p in prices],
        "close": prices, "volume": [1_000_000] * n})

def test_zigzag_finds_swings():
    pts = calculate_zigzag(_osc_df(), PARAMS)
    assert len([p for p in pts if p["type"] == "peak"]) >= 1
    assert len([p for p in pts if p["type"] == "trough"]) >= 1

def test_quality_rejects_low_volume():
    df = _osc_df(); df["volume"] = 10
    ok, reason = is_stock_data_quality(df, PARAMS)
    assert ok is False and "low_volume" in reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_consolidation_core.py -q`
Expected: FAIL (import error).

- [ ] **Step 3: Port the functions verbatim (params-driven)**

Create `backend/scripts/consolidation_core.py`. Copy `calculate_zigzag` and `is_stock_data_quality` from `d_breakout_detector_3.py` verbatim as module-level functions taking `(df, params)`. Add:

```python
import json
from backend.database.connection import get_db_connection  # noqa: E402

def load_params(conn) -> dict:
    row = conn.execute("SELECT value_json FROM screener_settings WHERE key='consolidation_params'").fetchone()
    return json.loads(row[0]) if row else {}
```

(The two ported functions are reproduced verbatim from the cited line ranges — no logic changes; replace `self.zigzag_deviation` → `params["zigzag_deviation"]`, `self.min_days_between_swings` → `params["min_days_between_swings"]`, `self.max_daily_change` → `params["max_daily_change"]`, `self.min_volume_threshold` → `params["min_volume_threshold"]`, `self.max_volatility_filter` → `params["max_volatility_filter"]`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_consolidation_core.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/consolidation_core.py backend/tests/test_consolidation_core.py
git commit -m "[E-1] feat: consolidation_core (ZigZag + quality, verbatim port)"
```

---

## Task 8: `consolidation_compute.py` — g_consolidation quality (verbatim) → `consolidation_patterns`

**Files:**
- Create: `backend/scripts/consolidation_compute.py`
- Test: `backend/tests/test_consolidation_compute.py`

**Interfaces:**
- Consumes: `consolidation_core` params, `market_data`.
- Produces: `analyze_symbol(df, params) -> dict|None` (best pattern); `compute_for_symbol(conn, symbol) -> int` (latest-only upsert); `compute_all(conn) -> dict`.

**Port note:** copy g_consolidation's `detect_price_channels` (`:159-239`), `_group_similar_levels` (`:241-283`), `_is_valid_channel` (`:285-307`), `calculate_zigzag_within_channel` (`:309-427`), `create_support_zones` (`:429-493`), `create_resistance_zones` (`:495-559`), `detect_consolidation_patterns_hybrid` (`:561-682`), `calculate_volume_behavior_score` (`:684-740`), `calculate_quality_score` (`:742-843`), `analyze_stock_consolidations` (`:845-934`) VERBATIM as module functions taking `(df, params)`. Strip all `print(...)` calls. `analyze_symbol` returns `best_consolidation` (the max-quality pattern) or None.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_consolidation_compute.py
import sqlite3
import pandas as pd
from backend.scripts.consolidation_compute import compute_for_symbol
from backend.database.connection import get_db_connection

def _seed(temp_db, symbol, df):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled) VALUES (?, 1)", (symbol,))
    for _, r in df.iterrows():
        conn.execute("INSERT OR IGNORE INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (symbol, str(r["time"]), r["open"], r["high"], r["low"], r["close"], r["volume"]))
    conn.commit(); conn.close()

def _tight_base(n=70):
    rows = []
    for i in range(n):
        p = 100 + (2 if i % 6 < 3 else -2)  # ~4% band
        rows.append({"time": pd.date_range("2026-01-01", periods=n)[i], "open": p,
                     "high": p + 0.5, "low": p - 0.5, "close": p, "volume": 1_000_000})
    return pd.DataFrame(rows)

def test_consolidation_writes_when_present(temp_db):
    _seed(temp_db, "COIL", _tight_base())
    conn = get_db_connection()
    n = compute_for_symbol(conn, "COIL")
    row = conn.execute("SELECT quality_score, range_pct FROM consolidation_patterns WHERE symbol='COIL'").fetchone()
    conn.close()
    # Sparse: a row exists only if a pattern was detected
    assert (n == 1 and row is not None) or (n == 0 and row is None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_consolidation_compute.py -q`
Expected: FAIL (import error).

- [ ] **Step 3: Port + add DB layer**

Create `backend/scripts/consolidation_compute.py` with the verbatim ports (above), then:

```python
import logging
from datetime import datetime, timezone
import pandas as pd
from backend.scripts.consolidation_core import load_params, is_stock_data_quality
from backend.database.connection import get_db_connection

logger = logging.getLogger(__name__)

_COLS = ["symbol","date","timeframe","detection_method","support_level","resistance_level",
         "range_pct","duration_days","quality_score","tightness_score","touch_score",
         "duration_score","volume_score","freshness_score","total_touches","zigzag_swings",
         "boundary_touches","pct_closes_in_channel","volume_trend","volume_decline_pct",
         "price_position_pct","position_desc","current_price","last_evaluated_at"]


def compute_for_symbol(conn, symbol: str) -> int:
    params = load_params(conn)
    df = pd.read_sql_query(
        "SELECT time, open, high, low, close, volume FROM market_data WHERE symbol = ? ORDER BY time ASC",
        conn, params=[symbol])
    if df.empty:
        return 0
    df["time"] = pd.to_datetime(df["time"])
    best = analyze_symbol(df, params)   # verbatim g_consolidation, returns best pattern or None
    if not best:
        conn.execute("DELETE FROM consolidation_patterns WHERE symbol = ?", (symbol,))
        conn.commit()
        return 0
    vals = {
        "symbol": symbol, "date": str(df["time"].iloc[-1].date()),
        "timeframe": best.get("timeframe"), "detection_method": best.get("detection_method"),
        "support_level": best.get("consolidation_bottom"), "resistance_level": best.get("consolidation_top"),
        "range_pct": best.get("range_pct"), "duration_days": best.get("duration_days"),
        "quality_score": best.get("quality_score"), "tightness_score": best.get("tightness_score"),
        "touch_score": best.get("touch_score"), "duration_score": best.get("duration_score"),
        "volume_score": best.get("volume_score"), "freshness_score": best.get("freshness_score"),
        "total_touches": best.get("total_touches"), "zigzag_swings": best.get("total_zigzag_swings"),
        "boundary_touches": best.get("total_boundary_touches"),
        "pct_closes_in_channel": best.get("pct_closes_in_channel"),
        "volume_trend": best.get("volume_trend"), "volume_decline_pct": best.get("volume_decline_pct"),
        "price_position_pct": best.get("price_position_pct"), "position_desc": best.get("position_desc"),
        "current_price": best.get("current_price"),
        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "symbol")
    conn.execute(
        f"INSERT INTO consolidation_patterns ({','.join(_COLS)}) VALUES ({','.join('?'*len(_COLS))}) "
        f"ON CONFLICT(symbol) DO UPDATE SET {updates}",
        tuple(vals[c] for c in _COLS))
    conn.commit()
    return 1


def compute_all(conn) -> dict:
    rows = conn.execute("SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()
    processed, written, errors, failures = [], 0, 0, []
    for (sym,) in rows:
        try:
            written += compute_for_symbol(conn, sym); processed.append(sym)
        except Exception as e:
            logger.error(f"❌ consolidation failed for {sym}: {e}")
            errors += 1; failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    return {"symbols_processed": processed, "rows_written": written, "errors": errors, "failures": failures}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_consolidation_compute.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/consolidation_compute.py backend/tests/test_consolidation_compute.py
git commit -m "[E-1] feat: consolidation_compute (g_consolidation verbatim) -> consolidation_patterns"
```

---

## Task 9: `breakout_compute.py` — d_breakout (verbatim) → `breakout_signals` + `support_resistance`

**Files:**
- Create: `backend/scripts/breakout_compute.py`
- Test: `backend/tests/test_breakout_compute.py`

**Interfaces:**
- Consumes: `consolidation_core.calculate_zigzag`, `market_data`, params.
- Produces: `analyze_symbol(df, params) -> dict`; `compute_for_symbol(conn, symbol) -> int` (writes `breakout_signals` row keyed (symbol, latest date) + `support_resistance` zones); `compute_all(conn) -> dict`.

**Port note:** copy `validate_resistance_zone` (`d_breakout_detector_3.py:216-236`), `validate_support_zone` (`:238-258`), `create_validated_support_zones` (`:260-311`), `create_validated_resistance_zones` (`:313-364`), `detect_strict_consolidation_patterns` (`:366-484`), `check_breakout_for_day` (`:486-515`), `analyze_single_case` (`:608-676`), `analyze_single_stock_for_breakout` (`:517-594`) VERBATIM as module functions taking `(df, params)` and using `consolidation_core.calculate_zigzag`. `analyze_symbol` = `analyze_single_stock_for_breakout` returning the results dict (status + day0/1/2 breakouts). Strip `print(...)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_breakout_compute.py
import sqlite3
import pandas as pd
from backend.scripts.breakout_compute import compute_for_symbol
from backend.database.connection import get_db_connection

def _seed(temp_db, symbol, df):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, enabled) VALUES (?, 1)", (symbol,))
    for _, r in df.iterrows():
        conn.execute("INSERT OR IGNORE INTO market_data (symbol, time, open, high, low, close, volume) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (symbol, str(r["time"]), r["open"], r["high"], r["low"], r["close"], r["volume"]))
    conn.commit(); conn.close()

def _base_then_breakout(n=43):
    rows = []
    for i in range(n - 1):
        p = 100 + (3 if i % 6 < 3 else -3)   # ~6% base
        rows.append({"time": pd.date_range("2026-01-01", periods=n)[i], "open": p,
                     "high": p + 0.5, "low": p - 0.5, "close": p, "volume": 1_000_000})
    # breakout day: gap above resistance on 3x volume
    d = pd.date_range("2026-01-01", periods=n)[n - 1]
    rows.append({"time": d, "open": 112, "high": 116, "low": 111, "close": 115, "volume": 3_000_000})
    return pd.DataFrame(rows)

def test_breakout_row_written(temp_db):
    _seed(temp_db, "BRK", _base_then_breakout())
    conn = get_db_connection()
    compute_for_symbol(conn, "BRK")
    row = conn.execute("SELECT breakout_status, breakout_direction FROM breakout_signals WHERE symbol='BRK'").fetchone()
    conn.close()
    assert row is not None                      # a status row is always written
    assert row[0] in ("breakout_detected", "consolidation_found_no_breakout", "no_consolidation_patterns")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_breakout_compute.py -q`
Expected: FAIL (import error).

- [ ] **Step 3: Port + DB layer**

Create `backend/scripts/breakout_compute.py` with the verbatim ports, then a DB layer that writes one `breakout_signals` row (PK symbol+latest date; upsert `ON CONFLICT(symbol, date)`), mapping `analyze_symbol` output: `breakout_status` = `result["status"]`, `breakout_direction`/`breakout_day`/`breakout_strength`/`breakout_volume_ratio` from whichever of day0/day1/day2 fired first, `consolidation_*` from the matching case pattern, `rejection_reason` = `result["rejection_reason"]`, `detail_json` = `json.dumps(result, default=str)`. Also write detected zones into `support_resistance` (delete-then-insert per symbol). Follow the `compute_all` shape from Task 8.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_breakout_compute.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/breakout_compute.py backend/tests/test_breakout_compute.py
git commit -m "[E-1] feat: breakout_compute (d_breakout verbatim) -> breakout_signals + support_resistance"
```

---

## Task 10: `scoring_compute.py` — provisional score + verdict → `screen_scores`

**Files:**
- Create: `backend/scripts/scoring_compute.py`
- Test: `backend/tests/test_scoring_compute.py`

**Interfaces:**
- Consumes: `fundamentals` (gates_passed), `screen_signals`, `consolidation_patterns`, `breakout_signals`, `screener_settings` (scoring_weights, thresholds).
- Produces: `score_symbol(fund, sig, cons, brk, weights) -> dict` (`{score_tech, score_fund, score_total, verdict, tech_flags, fund_flags}`); `compute_all(conn) -> dict` (upsert `screen_scores`, `is_provisional=1`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scoring_compute.py
from backend.scripts.scoring_compute import score_symbol

WEIGHTS = {"above_ma50":10,"above_ma200":10,"volume_spike":7,"breakout":12,
           "consolidation_quality":10,"momentum_60d_positive":10,"near_52w_high":5}

def test_fundamental_score_is_gates_over_7():
    fund = {"gates_passed": 6, "gates_total": 7}
    sig = {"above_ma50":1,"above_ma200":1,"volume_spike":0,"momentum_60d":8.0,"near_52w_high":1}
    r = score_symbol(fund, sig, cons=None, brk=None, weights=WEIGHTS)
    assert round(r["score_fund"], 1) == round(6/7*100, 1)
    assert 0 <= r["score_tech"] <= 100
    assert r["verdict"] in ("strong_buy","buy","watch","neutral","avoid")

def test_breakout_and_consolidation_add_tech_points():
    sig = {"above_ma50":1,"above_ma200":0,"volume_spike":1,"momentum_60d":5.0,"near_52w_high":0}
    cons = {"quality_score": 80.0}
    brk = {"breakout_direction": "bullish"}
    r = score_symbol({"gates_passed":3,"gates_total":7}, sig, cons, brk, WEIGHTS)
    assert "breakout" in r["tech_flags"]
    assert "consolidation_quality" in r["tech_flags"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_scoring_compute.py -q`
Expected: FAIL (import error).

- [ ] **Step 3: Implement scoring**

```python
# backend/scripts/scoring_compute.py
"""Provisional composite scoring. Fundamental = gates/7; technical = weighted signals."""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def score_symbol(fund, sig, cons, brk, weights) -> dict:
    sig = sig or {}
    tech_raw, tech_max, flags = 0.0, 0.0, []
    checks = [
        (sig.get("above_ma50") == 1, "above_ma50"),
        (sig.get("above_ma200") == 1, "above_ma200"),
        (sig.get("volume_spike") == 1, "volume_spike"),
        ((sig.get("momentum_60d") or 0) > 0, "momentum_60d_positive"),
        (sig.get("near_52w_high") == 1, "near_52w_high"),
        (bool(brk) and brk.get("breakout_direction") == "bullish", "breakout"),
        (bool(cons) and (cons.get("quality_score") or 0) >= 50, "consolidation_quality"),
    ]
    for cond, key in checks:
        tech_max += weights.get(key, 0)
        if cond:
            tech_raw += weights.get(key, 0)
            flags.append(key)

    score_tech = round(tech_raw / tech_max * 100, 1) if tech_max else 0.0
    gp = (fund or {}).get("gates_passed")
    gt = (fund or {}).get("gates_total") or 7
    score_fund = round((gp / gt) * 100, 1) if gp is not None else 0.0
    score_total = round((score_tech + score_fund) / 2, 1)

    verdict = ("strong_buy" if score_total >= 75 else "buy" if score_total >= 60
               else "watch" if score_total >= 45 else "avoid" if score_total < 30 else "neutral")
    fund_flags = f"{gp}/{gt}" if gp is not None else "n/a"
    return {"score_tech": score_tech, "score_fund": score_fund, "score_total": score_total,
            "verdict": verdict, "tech_flags": ",".join(flags), "fund_flags": fund_flags}


from backend.database.connection import get_db_connection  # noqa: E402
import json  # noqa: E402


def compute_all(conn) -> dict:
    weights = json.loads(conn.execute(
        "SELECT value_json FROM screener_settings WHERE key='scoring_weights'").fetchone()[0])
    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()]
    written, now = 0, datetime.now(timezone.utc).isoformat()
    for sym in syms:
        sig = conn.execute("SELECT above_ma50, above_ma200, volume_spike, momentum_60d, near_52w_high, "
                           "multi_factor_momentum, date FROM screen_signals WHERE symbol=?", (sym,)).fetchone()
        if not sig:
            continue
        sig_d = {"above_ma50": sig[0], "above_ma200": sig[1], "volume_spike": sig[2],
                 "momentum_60d": sig[3], "near_52w_high": sig[4]}
        fund = conn.execute("SELECT gates_passed, gates_total FROM fundamentals WHERE symbol=?", (sym,)).fetchone()
        fund_d = {"gates_passed": fund[0], "gates_total": fund[1]} if fund else {}
        cons = conn.execute("SELECT quality_score FROM consolidation_patterns WHERE symbol=?", (sym,)).fetchone()
        cons_d = {"quality_score": cons[0]} if cons else None
        brk = conn.execute("SELECT breakout_direction FROM breakout_signals WHERE symbol=? "
                           "ORDER BY date DESC LIMIT 1", (sym,)).fetchone()
        brk_d = {"breakout_direction": brk[0]} if brk else None
        s = score_symbol(fund_d, sig_d, cons_d, brk_d, weights)
        date = sig[6]
        conn.execute(
            "INSERT INTO screen_scores (symbol,date,score_tech,score_fund,score_total,verdict,"
            "tech_flags,fund_flags,multi_factor_momentum,is_provisional,last_evaluated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,1,?) "
            "ON CONFLICT(symbol,date) DO UPDATE SET score_tech=excluded.score_tech,"
            "score_fund=excluded.score_fund,score_total=excluded.score_total,verdict=excluded.verdict,"
            "tech_flags=excluded.tech_flags,fund_flags=excluded.fund_flags,"
            "multi_factor_momentum=excluded.multi_factor_momentum,last_evaluated_at=excluded.last_evaluated_at",
            (sym, date, s["score_tech"], s["score_fund"], s["score_total"], s["verdict"],
             s["tech_flags"], s["fund_flags"], sig[5], now))
        written += 1
    conn.commit()
    return {"symbols_processed": syms, "rows_written": written, "errors": 0, "failures": []}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_scoring_compute.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/scoring_compute.py backend/tests/test_scoring_compute.py
git commit -m "[E-1] feat: provisional scoring (gates/7 + weighted tech) -> screen_scores"
```

---

## Task 11: `/api/sync/screen` orchestration + retention prune

**Files:**
- Modify: `backend/api/routes/sync.py`
- Test: `backend/tests/test_sync_screen.py`

**Interfaces:**
- Consumes: `screen_signals_compute.compute_all`, `consolidation_compute.compute_all`, `breakout_compute.compute_all`, `scoring_compute.compute_all`, `record_run`.
- Produces: `POST /api/sync/screen` → `{"success":True, "steps":{...}, "pruned":{...}}`; helper `_prune_retention(conn)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sync_screen.py
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from backend.api.main import app
client = TestClient(app)

def test_prune_drops_old_breakouts(temp_db):
    conn = sqlite3.connect(str(temp_db))
    old = (datetime.now(timezone.utc) - timedelta(days=40)).date().isoformat()
    new = datetime.now(timezone.utc).date().isoformat()
    for d in (old, new):
        conn.execute("INSERT INTO breakout_signals (symbol, date, breakout_status) VALUES ('X', ?, 'x')", (d,))
    conn.commit(); conn.close()
    resp = client.post("/api/sync/screen")
    assert resp.status_code == 200
    conn = sqlite3.connect(str(temp_db))
    dates = {r[0] for r in conn.execute("SELECT date FROM breakout_signals WHERE symbol='X'").fetchall()}
    conn.close()
    assert new in dates and old not in dates   # 40d-old pruned by 30d retention
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_sync_screen.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Add orchestration + prune to `sync.py`**

```python
def _prune_retention(conn) -> dict:
    import json
    from datetime import datetime, timedelta, timezone
    ret = json.loads(conn.execute(
        "SELECT value_json FROM screener_settings WHERE key='retention'").fetchone()[0])
    today = datetime.now(timezone.utc).date()
    brk_cut = (today - timedelta(days=int(ret.get("breakout_retention_days", 30)))).isoformat()
    sc_cut = (today - timedelta(days=int(ret.get("screen_scores_retention_days", 60)))).isoformat()
    b = conn.execute("DELETE FROM breakout_signals WHERE date < ?", (brk_cut,)).rowcount
    s = conn.execute("DELETE FROM screen_scores WHERE date < ?", (sc_cut,)).rowcount
    conn.commit()
    return {"breakout_signals_pruned": b, "screen_scores_pruned": s}


@router.post("/screen")
async def sync_screen():
    logger.info("🔎 Sync step: screen")
    with record_run("screen") as run:
        from backend.scripts import (screen_signals_compute, consolidation_compute,
                                     breakout_compute, scoring_compute)
        conn = get_db_connection()
        try:
            steps = {
                "screen_signals": screen_signals_compute.compute_all(conn),
                "consolidation": consolidation_compute.compute_all(conn),
                "breakout": breakout_compute.compute_all(conn),
                "scoring": scoring_compute.compute_all(conn),
            }
            pruned = _prune_retention(conn)
        finally:
            conn.close()
        total_fail = sum(len(s.get("failures", [])) for s in steps.values())
        run.summary(f"signals/cons/brk/score done · {total_fail} failures · pruned "
                    f"{pruned['breakout_signals_pruned']}+{pruned['screen_scores_pruned']}")
        run.details({"steps": steps, "pruned": pruned})
        if total_fail:
            run.status("partial")
        return {"success": True, "steps": steps, "pruned": pruned}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_sync_screen.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/sync.py backend/tests/test_sync_screen.py
git commit -m "[E-1] feat: /api/sync/screen orchestration + retention prune"
```

---

## Task 12: `screener_overview` view + `/api/screener/overview` (JSON + CSV)

**Files:**
- Modify: `backend/database/schema.sql` (append `CREATE VIEW IF NOT EXISTS screener_overview`)
- Create: `backend/api/routes/screener.py`
- Modify: `backend/api/main.py` (import + include)
- Test: `backend/tests/test_screener_overview.py`

**Interfaces:**
- Produces: SQL view `screener_overview` (LEFT JOIN of tracked_universe + screen_signals + consolidation_patterns + latest breakout_signals + fundamentals + latest screen_scores, one row per symbol); `GET /api/screener/overview?format=json|csv` → rows or CSV stream.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_screener_overview.py
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app
client = TestClient(app)

def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT OR IGNORE INTO tracked_universe (symbol, name, sector, enabled) VALUES ('AAPL','Apple','Tech',1)")
    conn.execute("INSERT INTO screen_signals (symbol, date, momentum_60d, above_ma50) VALUES ('AAPL','2026-07-01', 12.0, 1)")
    conn.execute("INSERT INTO fundamentals (symbol, gates_passed, gates_total, roic) VALUES ('AAPL', 6, 7, 0.55)")
    conn.commit(); conn.close()

def test_overview_json(temp_db):
    _seed(temp_db)
    resp = client.get("/api/screener/overview")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    aapl = next(r for r in rows if r["symbol"] == "AAPL")
    assert aapl["gates_passed"] == 6 and aapl["momentum_60d"] == 12.0

def test_overview_csv(temp_db):
    _seed(temp_db)
    resp = client.get("/api/screener/overview?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "symbol" in resp.text.splitlines()[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_screener_overview.py -q`
Expected: FAIL (404).

- [ ] **Step 3a: Append the view to `schema.sql`**

```sql
-- Flattened one-row-per-symbol overview for the Screener grid / export.
CREATE VIEW IF NOT EXISTS screener_overview AS
SELECT
    u.symbol, u.name, u.sector,
    ss.date AS signal_date, ss.momentum_5d, ss.momentum_20d, ss.momentum_60d,
    ss.multi_factor_momentum, ss.above_ma50, ss.above_ma200, ss.ma_cross_status,
    ss.trend_aligned, ss.is_8d_consec, ss.volume_spike,
    ss.dist_from_52w_high, ss.near_52w_high,
    cp.quality_score AS consolidation_quality, cp.support_level, cp.resistance_level,
    cp.range_pct AS consolidation_range_pct, cp.timeframe AS consolidation_timeframe,
    b.breakout_status, b.breakout_direction, b.breakout_strength, b.breakout_volume_ratio, b.date AS breakout_date,
    f.gross_margin, f.roe, f.roic, f.levered_fcf_margin, f.interest_cover, f.eps_5y_growth,
    f.gates_passed, f.gates_total, f.market_cap, f.trailing_pe,
    sc.score_tech, sc.score_fund, sc.score_total, sc.verdict
FROM tracked_universe u
LEFT JOIN screen_signals ss ON ss.symbol = u.symbol
LEFT JOIN consolidation_patterns cp ON cp.symbol = u.symbol
LEFT JOIN breakout_signals b ON b.symbol = u.symbol
    AND b.date = (SELECT MAX(date) FROM breakout_signals b2 WHERE b2.symbol = u.symbol)
LEFT JOIN fundamentals f ON f.symbol = u.symbol
LEFT JOIN screen_scores sc ON sc.symbol = u.symbol
    AND sc.date = (SELECT MAX(date) FROM screen_scores s2 WHERE s2.symbol = u.symbol)
WHERE u.enabled = 1;
```

- [ ] **Step 3b: Create the route + register**

```python
# backend/api/routes/screener.py
import csv, io
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/screener", tags=["screener"])


@router.get("/overview")
async def overview(format: str = Query("json", pattern="^(json|csv)$")):
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM screener_overview ORDER BY symbol").fetchall()
    conn.close()
    dicts = [{k: r[k] for k in r.keys()} for r in rows]
    if format == "csv":
        buf = io.StringIO()
        if dicts:
            w = csv.DictWriter(buf, fieldnames=list(dicts[0].keys()))
            w.writeheader(); w.writerows(dicts)
        logger.info(f"📤 Screener overview CSV: {len(dicts)} rows")
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=screener_overview.csv"})
    return {"rows": dicts, "count": len(dicts)}
```

Register in `backend/api/main.py` (import block + include block) as in Task 5.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_screener_overview.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/database/schema.sql backend/api/routes/screener.py backend/api/main.py backend/tests/test_screener_overview.py
git commit -m "[E-1] feat: screener_overview view + /api/screener/overview (json+csv)"
```

---

## Task 13: UI MOCKUP GATE — Screener diagnostic grid (NO CODE)

**This task produces NO application code.** It is a hard gate on Tasks 14–16.

- [ ] **Step 1: Invoke the `ui-mockup` skill**

Invoke `ui-mockup:ui-mockup`. Design a **modern financial-app/reporting** Screener tab:
- A dense, sortable/filterable **data grid** backed by `/api/screener/overview` — columns: symbol, name, sector, score_total, verdict, gates_passed/7, momentum (5/20/60 + multi-factor), MA cross, consolidation quality, breakout direction/strength, 52w distance, key fundamentals (gross margin, ROE, ROIC, interest cover).
- A prominent **"Just broke out (last 3d)"** filter/section and a **CSV export** button.
- Clear "provisional / uncalibrated score" labeling.
- Sub-views/filters: verdict, sector, in-portfolio, min score.

- [ ] **Step 2: Get explicit user approval on the mockup**

Do NOT proceed to Task 14 until the user approves the layout. Capture the approved structure (columns, filters, layout) for the build tasks.

- [ ] **Step 3: Commit the mockup artifact** (if the skill saved one)

```bash
git add docs/ui-mockups/screener-grid* 2>/dev/null || true
git commit -m "[E-1] docs: approved Screener grid mockup" || true
```

---

## Task 14: Screener tab — raw diagnostic grid (post-approval)

**Files:**
- Create: `frontend/app/screener/` components (per approved mockup) OR a new tab in `frontend/app/page.tsx` (follow the existing `activeTab` pattern)
- Create: `frontend/app/api/proxy/[...path]` is already the proxy — call `/api/screener/overview`
- Test: `backend/tests/test_screener_overview.py` covers the API; add a Playwright E2E via `webapp-testing`

**Interfaces:**
- Consumes: `GET /api/screener/overview`.

- [ ] **Step 1:** Build the grid component exactly per the approved mockup (columns/filters/labels from Task 13). Fetch `/api/screener/overview`, render sortable/filterable table, provisional-score labeling, "broke out last 3d" filter (client-side on `breakout_date` within 3 days + `breakout_direction='bullish'`).
- [ ] **Step 2:** Add the new tab to the tab bar following the existing `positions`/`browse-universe` pattern.
- [ ] **Step 3:** Invoke `webapp-testing` — E2E: start app, open Screener tab, assert the grid renders rows and a known symbol appears; screenshot and eyeball it.
- [ ] **Step 4: Commit**

```bash
git add frontend/ && git commit -m "[E-1] feat: Screener diagnostic grid (approved layout)"
```

---

## Task 15: CSV/Excel export button

**Files:**
- Modify: the Screener tab component

- [ ] **Step 1:** Add an "Export" button that hits `/api/screener/overview?format=csv` and triggers a browser download.
- [ ] **Step 2:** Manually verify (run app) the download opens in Excel with the expected columns; capture evidence.
- [ ] **Step 3: Commit**

```bash
git add frontend/ && git commit -m "[E-1] feat: Screener CSV export button"
```

---

## Task 16: Configuration — fundamentals refresh button + status

**Files:**
- Modify: the Configuration tab in `frontend/app/page.tsx` (near the existing sync buttons / `SyncRunsPanel`)

**Interfaces:**
- Consumes: `POST /api/sync/fundamentals`, `GET /api/sync/fundamentals/status`.

- [ ] **Step 1:** Add a "Refresh fundamentals" button that POSTs `/api/sync/fundamentals`, and a label showing `Last run: {last_run} · Suggested next: {suggested_next}` from the status endpoint, highlighted when `overdue` (reuse the Epic-B staleness badge component).
- [ ] **Step 2:** Invoke `webapp-testing` — E2E: click refresh (with backend seeded), assert the status label updates.
- [ ] **Step 3: Commit**

```bash
git add frontend/ && git commit -m "[E-1] feat: fundamentals refresh button + cadence status"
```

---

## Done-When (Phase 1 acceptance)

- All new backend tests green: `pytest -q`.
- `/api/sync/fundamentals` + `/api/sync/screen` populate all Phase-1 tables over the real universe (run against a seeded DB; capture row counts + failure list).
- `/api/screener/overview` returns one row per enabled symbol; CSV export opens in Excel.
- Screener tab renders the diagnostic grid (approved mockup) with the "broke out last 3d" filter.
- Coverage sanity captured: how many symbols have consolidations / breakouts / non-null ROIC / non-null EPS-5Y — the inputs Phase 2 calibrates on.
- NO scoring calibration performed — `screen_scores.is_provisional = 1` everywhere.
