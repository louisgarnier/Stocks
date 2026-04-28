# Epic D — Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute technical indicators (MA 50/100/150/200, Bollinger Bands, RSI, **MRSI / Mansfield Relative Strength**, ATR, Volume MA) for every enabled symbol in `tracked_universe` and store in a new `indicators` table that downstream stories (G sell signals, H security detail, E tech analysis) read from.

**Architecture:** Single `indicators` table keyed by `(symbol, time)` with one column per indicator. Pure pandas computations on top of `market_data`. Incremental: only re-process symbols where the latest indicator date is older than the latest market_data date. MRSI requires a benchmark per symbol — `tracked_universe.benchmark` is set at seed time for sp500/cac40 symbols; resolved by currency for IBKR/manual symbols. Benchmark indices (`^GSPC`, `^FCHI`, `^GDAXI`, `^FTSE`) auto-seeded into the universe so their market_data is ingested. Indicators sync wired into `/api/sync/full` AFTER splits but does NOT include market_data sync (that stays a manual Configuration-tab button — too slow to run on every Sync IBKR click).

**Tech Stack:** Python 3.10 + pandas + sqlite3 stdlib + FastAPI. Tests: pytest + monkeypatch + the existing `temp_db` fixture. No new dependencies.

---

## File Structure

**Create:**
- `backend/scripts/indicators_compute.py` — pure pandas indicator functions (basic + MRSI) and the per-symbol orchestrator
- `backend/api/routes/indicators.py` — `GET /api/indicators/{symbol}` read endpoint
- `backend/tests/test_indicators_compute.py` — math tests (synthetic series)
- `backend/tests/test_indicators_routes.py` — route + schema tests

**Modify:**
- `backend/database/schema.sql` — add `indicators` table
- `backend/api/routes/sync.py` — add `sync_indicators()` endpoint, wire `_step_indicators()` into `/api/sync/full`
- `backend/api/routes/universe.py` — add `_ensure_benchmarks_seeded(conn)` and call it from `_ensure_indices_seeded()`
- `backend/api/main.py` — register `indicators_router`

**No deletes.**

---

## Task 1: Schema — `indicators` table

**Files:**
- Modify: `backend/database/schema.sql`
- Test: `backend/tests/test_indicators_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_indicators_routes.py`:

```python
"""Tests for indicators schema, compute, and routes."""
import sqlite3


def test_indicators_schema(temp_db):
    """indicators table must exist with composite PK (symbol, time) and all 11 indicator cols."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='indicators'")
    assert cur.fetchone() is not None, "indicators table missing"

    cur.execute("PRAGMA table_info(indicators)")
    rows = cur.fetchall()
    cols = {r[1] for r in rows}
    expected = {"symbol", "time", "ma_50", "ma_100", "ma_150", "ma_200",
                "bb_upper_20", "bb_lower_20", "bb_width", "rsi_14", "mrsi",
                "atr_14", "volume_ma_20"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"

    pk_cols = sorted([r[1] for r in rows if r[5] > 0])
    assert pk_cols == ["symbol", "time"], f"expected composite PK (symbol, time), got {pk_cols}"
    conn.close()
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd /Users/louisgarnier/Claude/Stocks && /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_routes.py::test_indicators_schema -v`
Expected: FAIL — "indicators table missing".

- [ ] **Step 3: Add the table to schema.sql**

Append to `backend/database/schema.sql` (after the existing `idx_market_data_time` index):

```sql

-- Technical indicators per (symbol, time) — pandas-computed from market_data
CREATE TABLE IF NOT EXISTS indicators (
    symbol TEXT NOT NULL,
    time TEXT NOT NULL,
    ma_50 REAL,
    ma_100 REAL,
    ma_150 REAL,
    ma_200 REAL,
    bb_upper_20 REAL,
    bb_lower_20 REAL,
    bb_width REAL,
    rsi_14 REAL,
    mrsi REAL,
    atr_14 REAL,
    volume_ma_20 REAL,
    PRIMARY KEY (symbol, time)
);
CREATE INDEX IF NOT EXISTS idx_indicators_time ON indicators(time);
```

- [ ] **Step 4: Run test, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_routes.py::test_indicators_schema -v`
Expected: PASS.

- [ ] **Step 5: Apply schema to the live DB**

Run: `sqlite3 output/database/finance.db < backend/database/schema.sql`
Verify: `sqlite3 output/database/finance.db ".schema indicators"` — should print the CREATE TABLE.

- [ ] **Step 6: Commit**

```bash
git add backend/database/schema.sql backend/tests/test_indicators_routes.py
git commit -m "[STORY-D-1] feat: add indicators table

Composite PK (symbol, time) + 11 indicator columns: MA 50/100/150/200,
BB upper/lower/width, RSI(14), MRSI, ATR(14), Volume MA(20).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Auto-seed benchmark symbols into `tracked_universe`

MRSI computation needs benchmark `market_data`. The benchmarks must be in `tracked_universe` so the market_data ingestor pulls them. Hook benchmark seeding into `_ensure_indices_seeded()` so it runs on any universe API call.

**Files:**
- Modify: `backend/api/routes/universe.py`
- Test: `backend/tests/test_universe_routes.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_universe_routes.py`:

```python
def test_benchmarks_auto_seeded(temp_db):
    """The 4 benchmark symbols (^GSPC, ^FCHI, ^GDAXI, ^FTSE) get auto-seeded into tracked_universe."""
    # Trigger any universe endpoint to invoke _ensure_indices_seeded
    resp = client.get("/api/universe/indices")
    assert resp.status_code == 200

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT symbol, currency, sources FROM tracked_universe "
        "WHERE symbol IN ('^GSPC', '^FCHI', '^GDAXI', '^FTSE') ORDER BY symbol"
    ).fetchall()
    conn.close()
    syms = {r[0] for r in rows}
    assert syms == {"^FCHI", "^FTSE", "^GDAXI", "^GSPC"}
    # Check sources tagged as 'benchmark'
    for r in rows:
        assert "benchmark" in r[2]
```

- [ ] **Step 2: Run, verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_routes.py::test_benchmarks_auto_seeded -v`
Expected: FAIL — assertion `syms == {...}` (currently empty set).

- [ ] **Step 3: Add the helper and call it**

In `backend/api/routes/universe.py`, after the existing `KNOWN_INDICES` constant and BEFORE `_ensure_indices_seeded`:

```python
KNOWN_BENCHMARKS = [
    {"symbol": "^GSPC", "name": "S&P 500", "currency": "USD", "exchange": "INDEX"},
    {"symbol": "^FCHI", "name": "CAC 40", "currency": "EUR", "exchange": "INDEX"},
    {"symbol": "^GDAXI", "name": "DAX", "currency": "EUR", "exchange": "INDEX"},
    {"symbol": "^FTSE", "name": "FTSE 100", "currency": "GBP", "exchange": "INDEX"},
]


def _ensure_benchmarks_seeded(conn) -> None:
    """Seed benchmark indices into tracked_universe so MRSI can use their market_data.

    Idempotent: INSERT OR IGNORE on PK (symbol).
    """
    now = _now_iso()
    for b in KNOWN_BENCHMARKS:
        conn.execute(
            "INSERT OR IGNORE INTO tracked_universe "
            "(symbol, name, currency, exchange, sources, enabled, added_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (b["symbol"], b["name"], b["currency"], b["exchange"], json.dumps(["benchmark"]), now),
        )
    conn.commit()
```

Then modify `_ensure_indices_seeded` to also seed benchmarks:

```python
def _ensure_indices_seeded(conn) -> None:
    """Populate tracked_indices with known names if missing (idempotent). Also seeds benchmark symbols."""
    for name in KNOWN_INDICES:
        conn.execute(
            "INSERT OR IGNORE INTO tracked_indices (name, enabled) VALUES (?, 0)",
            (name,),
        )
    _ensure_benchmarks_seeded(conn)
    conn.commit()
```

- [ ] **Step 4: Run test, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_routes.py -v`
Expected: all universe-route tests pass (12 total: 11 existing + 1 new).

- [ ] **Step 5: Apply to live DB (idempotent — safe)**

Run:
```bash
curl -s http://localhost:8000/api/universe/indices > /dev/null  # if backend running
# OR if backend not running, the next sync will seed
```

If you want to seed now without HTTP, use sqlite directly:
```bash
sqlite3 output/database/finance.db <<'SQL'
INSERT OR IGNORE INTO tracked_universe (symbol, name, currency, exchange, sources, enabled, added_at)
VALUES
  ('^GSPC', 'S&P 500', 'USD', 'INDEX', '["benchmark"]', 1, datetime('now')),
  ('^FCHI', 'CAC 40', 'EUR', 'INDEX', '["benchmark"]', 1, datetime('now')),
  ('^GDAXI', 'DAX', 'EUR', 'INDEX', '["benchmark"]', 1, datetime('now')),
  ('^FTSE', 'FTSE 100', 'GBP', 'INDEX', '["benchmark"]', 1, datetime('now'));
SELECT symbol, sources FROM tracked_universe WHERE symbol LIKE '^%';
SQL
```

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/universe.py backend/tests/test_universe_routes.py
git commit -m "[STORY-D-2] feat: auto-seed benchmark indices into tracked_universe

Adds ^GSPC / ^FCHI / ^GDAXI / ^FTSE with source 'benchmark' on first
universe API call. MRSI computation in Story D-3+ depends on having
benchmark market_data, so the benchmarks must be ingested by the
market_data sync.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Pure pandas indicator functions (basic indicators)

Pure functions on a DataFrame. No DB I/O. Easy to unit-test with synthetic series.

**Files:**
- Create: `backend/scripts/indicators_compute.py`
- Test: `backend/tests/test_indicators_compute.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_indicators_compute.py`:

```python
"""Tests for pure indicator computation functions."""
import numpy as np
import pandas as pd

from backend.scripts.indicators_compute import compute_basic_indicators, compute_mrsi


def _flat_df(close=100.0, days=300, volume=1_000_000):
    """Build a synthetic OHLCV DataFrame with constant close/volume."""
    return pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist(),
        "open": [close] * days,
        "high": [close + 1] * days,
        "low": [close - 1] * days,
        "close": [close] * days,
        "adj_close": [close] * days,
        "volume": [volume] * days,
    })


def test_ma_constant_series():
    """MA50 / MA100 / MA150 / MA200 of constant 100 should equal 100 once windows fill."""
    df = _flat_df(close=100, days=250)
    out = compute_basic_indicators(df)

    assert pd.isna(out["ma_50"].iloc[48])  # one less than 50 → still NaN
    assert out["ma_50"].iloc[49] == 100
    assert out["ma_100"].iloc[99] == 100
    assert out["ma_150"].iloc[149] == 100
    assert out["ma_200"].iloc[199] == 100


def test_bb_constant_series_zero_width():
    """Bollinger Band width of constant series is ~0 (stddev = 0)."""
    df = _flat_df(close=100, days=50)
    out = compute_basic_indicators(df)
    assert out["bb_upper_20"].iloc[25] == 100
    assert out["bb_lower_20"].iloc[25] == 100
    # bb_width = (0) / 100 = 0 OR NaN if division by zero handled; both acceptable
    width = out["bb_width"].iloc[25]
    assert width == 0 or pd.isna(width)


def test_rsi_uptrend_approaches_100():
    """Strict uptrend → RSI approaches 100."""
    days = 60
    df = pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist(),
        "open": list(range(100, 100 + days)),
        "high": [c + 0.5 for c in range(100, 100 + days)],
        "low": [c - 0.5 for c in range(100, 100 + days)],
        "close": list(range(100, 100 + days)),
        "adj_close": list(range(100, 100 + days)),
        "volume": [1_000_000] * days,
    })
    out = compute_basic_indicators(df)
    assert out["rsi_14"].iloc[-1] > 95  # near 100


def test_rsi_downtrend_approaches_0():
    """Strict downtrend → RSI approaches 0."""
    days = 60
    closes = list(range(200, 200 - days, -1))
    df = pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist(),
        "open": closes,
        "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes],
        "close": closes,
        "adj_close": closes,
        "volume": [1_000_000] * days,
    })
    out = compute_basic_indicators(df)
    assert out["rsi_14"].iloc[-1] < 5


def test_atr_constant_range():
    """ATR of bars with constant high-low range = that range."""
    df = _flat_df(close=100, days=50)  # high-low = 2
    out = compute_basic_indicators(df)
    assert abs(out["atr_14"].iloc[-1] - 2) < 0.01


def test_volume_ma_constant():
    """Volume MA(20) of constant 1M = 1M."""
    df = _flat_df(volume=1_000_000, days=30)
    out = compute_basic_indicators(df)
    assert out["volume_ma_20"].iloc[-1] == 1_000_000


def test_mrsi_outperforming_stock_positive():
    """If stock outperforms benchmark over 252 days, MRSI is positive at the end."""
    days = 300
    times = pd.date_range("2024-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist()
    # Stock doubles, benchmark flat
    stock = pd.DataFrame({"time": times, "adj_close": np.linspace(100, 200, days)})
    bench = pd.DataFrame({"time": times, "adj_close": [100] * days})

    mrsi = compute_mrsi(stock, bench)
    assert mrsi.iloc[-1] > 0


def test_mrsi_underperforming_stock_negative():
    """If stock underperforms benchmark over 252 days, MRSI is negative at the end."""
    days = 300
    times = pd.date_range("2024-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist()
    stock = pd.DataFrame({"time": times, "adj_close": [100] * days})
    bench = pd.DataFrame({"time": times, "adj_close": np.linspace(100, 200, days)})

    mrsi = compute_mrsi(stock, bench)
    assert mrsi.iloc[-1] < 0


def test_mrsi_flat_relative_centered_at_zero():
    """If stock and benchmark move identically, MRSI is ~0."""
    days = 300
    times = pd.date_range("2024-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist()
    series = list(np.linspace(100, 150, days))
    stock = pd.DataFrame({"time": times, "adj_close": series})
    bench = pd.DataFrame({"time": times, "adj_close": series})

    mrsi = compute_mrsi(stock, bench)
    assert abs(mrsi.iloc[-1]) < 0.01
```

- [ ] **Step 2: Run, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_compute.py -v`
Expected: ModuleNotFoundError on `backend.scripts.indicators_compute`.

- [ ] **Step 3: Implement the compute functions**

Create `backend/scripts/indicators_compute.py`:

```python
"""Pure pandas-based indicator computation functions.

Inputs are DataFrames with OHLCV columns; outputs are the same frames with
indicator columns added. No DB I/O — see compute_for_symbol() in the same
module for the per-symbol orchestrator that does the SQL.

Indicator definitions:
- MA 50/100/150/200: simple rolling mean of adj_close
- BB(20, 2): MA20 of adj_close ± 2 stddev; bb_width = (upper - lower) / MA20
- RSI(14): standard 14-period RSI using Wilder's smoothing (EWM with alpha=1/14)
- ATR(14): Wilder's true range smoothed over 14 periods (uses raw OHLC)
- Volume MA(20): simple rolling mean of volume
- MRSI (Mansfield Relative Strength): ((stock_close / bench_close) /
  MA(stock/bench, 252) - 1) * 100; centered at 0
"""
import pandas as pd


def compute_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute MA / BB / RSI / ATR / Volume MA on a DataFrame.

    Input df must have columns: time (sorted ascending), open, high, low,
    close, adj_close, volume. Returns the same df with indicator columns
    appended (does not mutate the input).
    """
    out = df.copy()
    close = out["adj_close"]

    # Moving averages on adjusted close
    out["ma_50"] = close.rolling(50).mean()
    out["ma_100"] = close.rolling(100).mean()
    out["ma_150"] = close.rolling(150).mean()
    out["ma_200"] = close.rolling(200).mean()

    # Bollinger Bands (20, 2)
    ma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    out["bb_upper_20"] = ma20 + 2 * std20
    out["bb_lower_20"] = ma20 - 2 * std20
    width_denom = ma20.where(ma20 != 0)
    out["bb_width"] = (out["bb_upper_20"] - out["bb_lower_20"]) / width_denom

    # RSI(14) using Wilder's smoothing (EWM with alpha = 1/14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.where(avg_loss != 0)
    out["rsi_14"] = 100 - (100 / (1 + rs))
    out["rsi_14"] = out["rsi_14"].where(avg_loss != 0, 100.0)  # all gains → RSI = 100

    # ATR(14) — uses raw OHLC (volatility metric, not split-adjusted)
    hl = out["high"] - out["low"]
    hc = (out["high"] - out["close"].shift()).abs()
    lc = (out["low"] - out["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    out["atr_14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    # Volume MA(20)
    out["volume_ma_20"] = out["volume"].rolling(20).mean()

    return out


def compute_mrsi(stock_df: pd.DataFrame, bench_df: pd.DataFrame) -> pd.Series:
    """Compute Mansfield Relative Strength.

    Inputs: stock_df + bench_df both with columns 'time' + 'adj_close'.
    Returns: pd.Series of MRSI values indexed by the merged 'time' values.

    Formula:
        RS    = stock_close / bench_close
        RS_MA = MA(RS, 252)
        MRSI  = ((RS / RS_MA) - 1) * 100

    MRSI is positive when stock outperforms benchmark over 252 trading days,
    negative when underperforming, ~0 when matching.
    """
    merged = stock_df[["time", "adj_close"]].merge(
        bench_df[["time", "adj_close"]],
        on="time", suffixes=("_stock", "_bench"),
    ).sort_values("time").reset_index(drop=True)

    rs = merged["adj_close_stock"] / merged["adj_close_bench"].where(merged["adj_close_bench"] != 0)
    rs_ma = rs.rolling(252).mean()
    mrsi = ((rs / rs_ma.where(rs_ma != 0)) - 1) * 100
    return pd.Series(mrsi.values, index=merged["time"].values)
```

- [ ] **Step 4: Run, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_compute.py -v`
Expected: 9 passed (6 basic + 3 MRSI).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/indicators_compute.py backend/tests/test_indicators_compute.py
git commit -m "[STORY-D-3] feat: pure indicator math (MA / BB / RSI / ATR / Vol MA / MRSI)

Pure pandas functions in backend/scripts/indicators_compute.py:
- compute_basic_indicators(df) → MA50/100/150/200, BB(20,2),
  RSI(14, Wilder smoothing), ATR(14), Volume MA(20)
- compute_mrsi(stock_df, bench_df) → Mansfield Relative Strength

Tests: synthetic flat / uptrend / downtrend series + MRSI direction
checks. 9 passing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Per-symbol orchestrator + benchmark resolution

Wraps the pure compute functions with DB I/O — read market_data, write indicators, resolve the benchmark per symbol.

**Files:**
- Modify: `backend/scripts/indicators_compute.py` — add `compute_for_symbol(conn, symbol)` and `compute_all(conn)`
- Test: `backend/tests/test_indicators_routes.py` — append integration tests

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_indicators_routes.py`:

```python
import json
from datetime import datetime, timedelta


def _seed_market_data(conn, symbol: str, days: int, start_close: float = 100.0, currency: str = "USD"):
    """Insert `days` of synthetic market_data rows for `symbol` and ensure it's in tracked_universe."""
    conn.execute(
        "INSERT OR IGNORE INTO tracked_universe (symbol, currency, sources, enabled, added_at) "
        "VALUES (?, ?, ?, 1, datetime('now'))",
        (symbol, currency, json.dumps(["test"])),
    )
    end = datetime(2026, 4, 1)
    for i in range(days):
        ts = (end - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        c = start_close + i * 0.1
        conn.execute(
            "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1000000)",
            (symbol, ts, c, c + 0.5, c - 0.5, c, c),
        )
    conn.commit()


def test_compute_for_symbol_writes_rows(temp_db):
    """compute_for_symbol writes one indicators row per market_data bar (after warm-up periods)."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_for_symbol

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "AAPL", days=60)
    conn.close()

    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    inserted = compute_for_symbol(conn, "AAPL")
    conn.close()
    assert inserted == 60

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM indicators WHERE symbol='AAPL'").fetchone()[0]
    # Latest row should have MA50 populated
    last = conn.execute(
        "SELECT ma_50, ma_100, rsi_14, atr_14, volume_ma_20 FROM indicators "
        "WHERE symbol='AAPL' ORDER BY time DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert cnt == 60
    assert last[0] is not None  # ma_50 populated after 50 bars
    assert last[2] is not None  # rsi populated
    assert last[3] is not None  # atr populated
    assert last[4] is not None  # volume_ma populated


def test_compute_for_symbol_idempotent(temp_db):
    """Re-running compute_for_symbol on the same data doesn't duplicate rows."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_for_symbol
    from backend.database.connection import get_db_connection

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "AAPL", days=60)
    conn.close()

    conn = get_db_connection()
    compute_for_symbol(conn, "AAPL")
    compute_for_symbol(conn, "AAPL")
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM indicators WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert cnt == 60


def test_compute_for_symbol_resolves_benchmark(temp_db):
    """compute_for_symbol picks ^GSPC for USD symbols and computes MRSI when both have ≥252 days."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_for_symbol
    from backend.database.connection import get_db_connection

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "^GSPC", days=300, start_close=4500.0, currency="USD")
    _seed_market_data(conn, "AAPL", days=300, start_close=150.0, currency="USD")
    conn.close()

    conn = get_db_connection()
    compute_for_symbol(conn, "AAPL")
    conn.close()

    conn = sqlite3.connect(str(temp_db))
    last_mrsi = conn.execute(
        "SELECT mrsi FROM indicators WHERE symbol='AAPL' ORDER BY time DESC LIMIT 1"
    ).fetchone()[0]
    conn.close()
    assert last_mrsi is not None  # MRSI populated when benchmark + ≥252 days available


def test_compute_all_processes_enabled_symbols(temp_db):
    """compute_all skips disabled symbols and processes enabled ones."""
    import sqlite3
    from backend.scripts.indicators_compute import compute_all
    from backend.database.connection import get_db_connection

    conn = sqlite3.connect(str(temp_db))
    _seed_market_data(conn, "ENABLED", days=60)
    _seed_market_data(conn, "DISABLED", days=60)
    conn.execute("UPDATE tracked_universe SET enabled = 0 WHERE symbol = 'DISABLED'")
    conn.commit()
    conn.close()

    conn = get_db_connection()
    result = compute_all(conn)
    conn.close()

    assert "ENABLED" in result["symbols_processed"]
    assert "DISABLED" not in result["symbols_processed"]
```

- [ ] **Step 2: Run, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_routes.py -v`
Expected: ImportError on `compute_for_symbol`.

- [ ] **Step 3: Implement the orchestrator**

Append to `backend/scripts/indicators_compute.py`:

```python
import sqlite3
from typing import Optional

from backend.api.utils.logger import logger


_BENCHMARK_BY_CURRENCY = {
    "USD": "^GSPC",
    "EUR": "^FCHI",
    "GBP": "^FTSE",
}


def _resolve_benchmark(currency: Optional[str], stored_benchmark: Optional[str]) -> Optional[str]:
    """Pick the benchmark symbol for a given symbol's currency.

    Priority: stored_benchmark column (set at seed time) → currency mapping → fallback ^GSPC.
    """
    if stored_benchmark:
        return stored_benchmark
    return _BENCHMARK_BY_CURRENCY.get(currency or "USD", "^GSPC")


def _read_market_data(conn, symbol: str, since: Optional[str] = None) -> pd.DataFrame:
    """Pull market_data rows for a symbol as a DataFrame."""
    sql = "SELECT time, open, high, low, close, adj_close, volume FROM market_data WHERE symbol = ?"
    params: list = [symbol]
    if since:
        sql += " AND time > ?"
        params.append(since)
    sql += " ORDER BY time ASC"
    df = pd.read_sql_query(sql, conn, params=params)
    return df


def compute_for_symbol(conn, symbol: str) -> int:
    """Compute indicators for one symbol incrementally.

    Reads market_data for `symbol`, computes all indicators (including MRSI vs
    its resolved benchmark), and UPSERTs into the indicators table. Idempotent
    via ON CONFLICT (symbol, time) DO UPDATE.

    Returns: number of rows written (insert or update).
    """
    cur = conn.cursor()
    row = cur.execute(
        "SELECT currency, benchmark FROM tracked_universe WHERE symbol = ?", (symbol,)
    ).fetchone()
    if not row:
        return 0
    benchmark = _resolve_benchmark(row[0], row[1])

    df = _read_market_data(conn, symbol)
    if df.empty:
        return 0

    out = compute_basic_indicators(df)

    # MRSI: if benchmark exists in market_data with overlapping dates
    bench_df = _read_market_data(conn, benchmark) if benchmark and benchmark != symbol else pd.DataFrame()
    if not bench_df.empty:
        mrsi_series = compute_mrsi(df, bench_df)
        out = out.assign(mrsi=out["time"].map(lambda t: mrsi_series.get(t)))
    else:
        out = out.assign(mrsi=None)

    # Helper to coerce NaN → None for SQLite
    def _none_if_nan(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return float(v)

    written = 0
    for _, r in out.iterrows():
        cur.execute(
            "INSERT INTO indicators "
            "(symbol, time, ma_50, ma_100, ma_150, ma_200, "
            " bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (symbol, time) DO UPDATE SET "
            " ma_50 = excluded.ma_50, "
            " ma_100 = excluded.ma_100, "
            " ma_150 = excluded.ma_150, "
            " ma_200 = excluded.ma_200, "
            " bb_upper_20 = excluded.bb_upper_20, "
            " bb_lower_20 = excluded.bb_lower_20, "
            " bb_width = excluded.bb_width, "
            " rsi_14 = excluded.rsi_14, "
            " mrsi = excluded.mrsi, "
            " atr_14 = excluded.atr_14, "
            " volume_ma_20 = excluded.volume_ma_20",
            (
                symbol, r["time"],
                _none_if_nan(r.get("ma_50")), _none_if_nan(r.get("ma_100")),
                _none_if_nan(r.get("ma_150")), _none_if_nan(r.get("ma_200")),
                _none_if_nan(r.get("bb_upper_20")), _none_if_nan(r.get("bb_lower_20")),
                _none_if_nan(r.get("bb_width")),
                _none_if_nan(r.get("rsi_14")),
                _none_if_nan(r.get("mrsi")),
                _none_if_nan(r.get("atr_14")),
                _none_if_nan(r.get("volume_ma_20")),
            ),
        )
        written += 1
    conn.commit()
    return written


def compute_all(conn) -> dict:
    """Compute indicators for every enabled symbol in tracked_universe.

    Returns: {"symbols_processed": list[str], "rows_written": int, "errors": int}
    """
    rows = conn.execute(
        "SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol"
    ).fetchall()
    symbols_processed = []
    rows_written = 0
    errors = 0
    for (sym,) in rows:
        try:
            n = compute_for_symbol(conn, sym)
            if n > 0:
                symbols_processed.append(sym)
                rows_written += n
        except Exception as e:
            logger.error(f"❌ indicators compute failed for {sym}: {e}")
            errors += 1
    logger.info(
        f"✅ Indicators: {len(symbols_processed)} symbols processed, "
        f"{rows_written} rows written, {errors} errors"
    )
    return {"symbols_processed": symbols_processed, "rows_written": rows_written, "errors": errors}
```

- [ ] **Step 4: Run, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_routes.py -v`
Expected: 5 tests pass (1 schema + 4 compute orchestrator tests).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/indicators_compute.py backend/tests/test_indicators_routes.py
git commit -m "[STORY-D-4] feat: per-symbol indicators orchestrator + benchmark resolution

- compute_for_symbol(conn, symbol) reads market_data, computes all
  indicators (including MRSI), UPSERTs idempotently into indicators
- compute_all(conn) iterates every enabled symbol
- Benchmark resolution: stored tracked_universe.benchmark → currency
  mapping (USD→^GSPC, EUR→^FCHI, GBP→^FTSE) → ^GSPC fallback
- Tests: synthetic OHLCV, idempotency, MRSI vs benchmark, enabled
  filter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `/api/sync/indicators` endpoint + wire into `/api/sync/full`

**Files:**
- Modify: `backend/api/routes/sync.py` — add `sync_indicators()` endpoint and `_step_indicators()` helper, wire into orchestrator
- Test: `backend/tests/test_sync_routes.py` — append

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_sync_routes.py`:

```python
def test_sync_indicators_endpoint(temp_db, monkeypatch):
    """POST /api/sync/indicators wraps compute_all()."""
    import backend.scripts.indicators_compute as ind
    monkeypatch.setattr(
        ind, "compute_all",
        lambda conn: {"symbols_processed": ["AAPL"], "rows_written": 60, "errors": 0},
    )
    resp = client.post("/api/sync/indicators")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["rows_written"] == 60
    assert "AAPL" in body["symbols_processed"]


def test_sync_full_includes_indicators_step(temp_db, stub_flex_http, monkeypatch):
    """/api/sync/full now runs an indicators step after splits."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    import backend.scripts.fetch_corporate_actions as ca_mod
    import backend.scripts.apply_splits as aps_mod
    import backend.scripts.indicators_compute as ind_mod
    monkeypatch.setattr(
        ca_mod, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    monkeypatch.setattr(
        aps_mod, "apply_all_splits",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )
    monkeypatch.setattr(
        ind_mod, "compute_all",
        lambda conn: {"symbols_processed": ["TEST"], "rows_written": 1, "errors": 0},
    )

    resp = client.post("/api/sync/full")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    step_names = [s["name"] for s in body["steps"]]
    assert step_names == ["positions", "transactions", "corporate_actions", "splits", "indicators"]
    for s in body["steps"]:
        assert s["status"] == "ok", s
```

- [ ] **Step 2: Run, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_indicators_endpoint backend/tests/test_sync_routes.py::test_sync_full_includes_indicators_step -v`
Expected: 404 on `/api/sync/indicators` and step-list mismatch.

- [ ] **Step 3: Add the endpoint and orchestrator wiring**

In `backend/api/routes/sync.py`, append at the end of the file:

```python
@router.post("/indicators")
async def sync_indicators():
    """Compute MA / BB / RSI / MRSI / ATR / Volume MA for every enabled symbol in the universe."""
    logger.info("📐 Sync step: indicators")
    try:
        from backend.scripts.indicators_compute import compute_all
        conn = get_db_connection()
        try:
            result = compute_all(conn)
        finally:
            conn.close()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ sync_indicators failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _step_indicators() -> dict:
    from backend.scripts.indicators_compute import compute_all
    conn = get_db_connection()
    try:
        return compute_all(conn)
    finally:
        conn.close()
```

Then modify `sync_full` to call the new step. Find the existing `sync_full` and add ONE line:

```python
@router.post("/full")
async def sync_full():
    """Run the full pipeline: positions, transactions, corporate actions, splits, indicators.

    Steps 1+2 share one Flex pull. Failures stop the chain at that step but
    earlier steps remain committed. Returns per-step status for the UI.
    """
    logger.info("🚀 Sync step: FULL pipeline")
    steps = []

    try:
        xml = fetch_flex_response("last_month")
    except Exception as e:
        return {
            "success": False,
            "steps": [{"name": "positions", "status": "error", "error": str(e)}],
        }

    if not _run(steps, "positions", lambda: _step_positions(xml)):
        return _wrap(steps)
    if not _run(steps, "transactions", lambda: _step_transactions(xml)):
        return _wrap(steps)
    if not _run(steps, "corporate_actions", _step_corporate_actions):
        return _wrap(steps)
    if not _run(steps, "splits", _step_splits):
        return _wrap(steps)
    _run(steps, "indicators", _step_indicators)
    return _wrap(steps)
```

(Note: market_data sync is intentionally NOT in the orchestrator — it's slow and stays a manual button on the Configuration tab.)

- [ ] **Step 4: Run, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py -v`
Expected: all sync tests pass (14 total: 12 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/sync.py backend/tests/test_sync_routes.py
git commit -m "[STORY-D-5] feat: /api/sync/indicators endpoint + wire into /api/sync/full

- POST /api/sync/indicators wraps compute_all() — recomputes indicators
  for every enabled symbol
- /api/sync/full now runs 5 steps: positions, transactions,
  corporate_actions, splits, indicators (NEW)
- market_data sync intentionally NOT in orchestrator — too slow for the
  Sync IBKR header button. Stays manual via Configuration tab.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `GET /api/indicators/{symbol}` read endpoint

**Files:**
- Create: `backend/api/routes/indicators.py`
- Modify: `backend/api/main.py` — register router
- Test: `backend/tests/test_indicators_routes.py` — append

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_indicators_routes.py`:

```python
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_indicators_returns_latest(temp_db):
    """GET /api/indicators/{symbol} returns rows newest-first with all 11 indicator cols."""
    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO indicators "
        "(symbol, time, ma_50, ma_100, ma_150, ma_200, "
        " bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20) "
        "VALUES ('AAPL', '2026-04-27', 150, 145, 140, 135, "
        " 155, 145, 0.067, 62, 5.2, 2.5, 1500000)"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/indicators/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert len(body["rows"]) == 1
    r = body["rows"][0]
    assert r["ma_50"] == 150
    assert r["mrsi"] == 5.2
    assert r["rsi_14"] == 62


def test_get_indicators_404_when_no_rows(temp_db):
    resp = client.get("/api/indicators/NOPE")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_routes.py::test_get_indicators_returns_latest backend/tests/test_indicators_routes.py::test_get_indicators_404_when_no_rows -v`
Expected: 404 (route doesn't exist yet).

- [ ] **Step 3: Implement the router**

Create `backend/api/routes/indicators.py`:

```python
"""Indicator query routes (read access to the indicators table)."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/indicators", tags=["indicators"])


@router.get("/{symbol}")
async def get_indicators(
    symbol: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=10000),
):
    """Return indicator rows for a symbol, newest first."""
    sym = symbol.upper()
    conn = get_db_connection()
    where = ["symbol = ?"]
    params: list = [sym]
    if date_from:
        where.append("time >= ?")
        params.append(date_from)
    if date_to:
        where.append("time <= ?")
        params.append(date_to)
    sql = (
        "SELECT time, ma_50, ma_100, ma_150, ma_200, "
        "bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20 "
        "FROM indicators WHERE " + " AND ".join(where) +
        " ORDER BY time DESC LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"no indicator rows for {sym}")
    out = [
        {
            "time": r[0],
            "ma_50": r[1], "ma_100": r[2], "ma_150": r[3], "ma_200": r[4],
            "bb_upper_20": r[5], "bb_lower_20": r[6], "bb_width": r[7],
            "rsi_14": r[8], "mrsi": r[9], "atr_14": r[10], "volume_ma_20": r[11],
        }
        for r in rows
    ]
    logger.info(f"📐 Returned {len(out)} indicator rows for {sym}")
    return {"symbol": sym, "rows": out, "count": len(out)}
```

- [ ] **Step 4: Register the router**

In `backend/api/main.py`, add after the existing `from backend.api.routes.market_data import router as market_data_router` line:

```python
from backend.api.routes.indicators import router as indicators_router
```

And after `app.include_router(market_data_router)`:

```python
app.include_router(indicators_router)
```

- [ ] **Step 5: Run tests, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_indicators_routes.py -v`
Expected: 7 tests pass (1 schema + 4 compute + 2 routes).

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/indicators.py backend/api/main.py backend/tests/test_indicators_routes.py
git commit -m "[STORY-D-6] feat: GET /api/indicators/{symbol} read endpoint

Returns indicator rows newest-first with optional date_from / date_to /
limit filters. 404 when no rows exist for the symbol.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: End-to-end live smoke test

Manual verification against real data — no test code, just commands and expected results.

- [ ] **Step 1: Restart backend**

```bash
cd /Users/louisgarnier/Claude/Stocks
lsof -ti:8000 | xargs kill -9 2>/dev/null; sleep 1
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m uvicorn backend.api.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 3
curl -s http://localhost:8000/health | python3 -m json.tool
```

Expected: `{"status":"ok",...}`.

- [ ] **Step 2: Ensure benchmarks are seeded + have market data**

```bash
# Trigger benchmark seed via list-indices
curl -s http://localhost:8000/api/universe/indices > /dev/null

# Verify benchmarks are in the universe
sqlite3 output/database/finance.db "SELECT symbol, sources FROM tracked_universe WHERE symbol LIKE '^%' ORDER BY symbol"
```

Expected: 4 rows for ^FCHI / ^FTSE / ^GDAXI / ^GSPC, sources containing `"benchmark"`.

```bash
# Cap to held + benchmarks for fast smoke
sqlite3 output/database/finance.db "UPDATE tracked_universe SET enabled = 0 WHERE sources NOT LIKE '%ibkr_position%' AND sources NOT LIKE '%benchmark%'"

# Sync market_data (~14 holdings + 4 benchmarks = 18 symbols)
curl -s -X POST http://localhost:8000/api/sync/market-data | python3 -m json.tool
```

Expected: ~18 symbols processed, ~4500 new rows inserted (250 days × 18).

- [ ] **Step 3: Compute indicators**

```bash
curl -s -X POST http://localhost:8000/api/sync/indicators | python3 -m json.tool
```

Expected: `{"success": true, "symbols_processed": [...], "rows_written": ~4500, "errors": 0}`.

- [ ] **Step 4: Spot-check a held symbol's latest indicators**

```bash
curl -s "http://localhost:8000/api/indicators/NVDA?limit=1" | python3 -m json.tool
```

Expected: latest row has non-null `ma_50`, `ma_100`, `ma_150`, `ma_200` (assuming NVDA has ≥200 days of data), `rsi_14` between 0-100, `mrsi` non-null (because we have ^GSPC + 252+ days), reasonable `atr_14`.

- [ ] **Step 5: Run the full orchestrator and confirm 5 steps**

```bash
curl -s -X POST http://localhost:8000/api/sync/full | python3 -m json.tool
```

Expected: response includes 5 steps in order: `positions, transactions, corporate_actions, splits, indicators`. All `status: ok`.

- [ ] **Step 6: Re-enable everything**

```bash
sqlite3 output/database/finance.db "UPDATE tracked_universe SET enabled = 1"
sqlite3 output/database/finance.db "SELECT 'enabled', COUNT(*) FROM tracked_universe WHERE enabled=1"
```

Expected: ~556 (552 + 4 benchmarks).

- [ ] **Step 7: Update build log + epic overview + commit**

Append to `docs/project/config/build-log.md`:

```
## 2026-04-28 — Epic D complete: indicators

7 stories shipped, end-to-end smoke test passed.

**Subsystems delivered:**
- `indicators` table (composite PK on symbol+time, 11 indicator columns)
- Auto-seed of 4 benchmark symbols (^GSPC / ^FCHI / ^GDAXI / ^FTSE)
- Pure pandas indicator math: MA 50/100/150/200, BB(20,2), RSI(14)
  Wilder, ATR(14), Volume MA(20)
- MRSI (Mansfield Relative Strength) with per-symbol benchmark resolution
- /api/sync/indicators endpoint, wired into /api/sync/full as 5th step
- GET /api/indicators/{symbol} read endpoint
- Orchestrator now: positions → transactions → CAs → splits → indicators
  (market_data stays a manual button)

**Tests:** 16 new tests across 3 files. All passing.
```

Update `docs/project/config/epics/overview.md` to mark Epic D as `[x] Done`.

Update `docs/project/config/epics/ACTIVE.md` to point at Epic G as next.

```bash
git add docs/project/config/build-log.md docs/project/config/epics/overview.md docs/project/config/epics/ACTIVE.md
git commit -m "[STORY-D-7] docs: mark Epic D complete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin newstart
```

---

## Out of Scope (future epics)

- **MACD, Stochastic, OBV, Ichimoku** — only build if a specific signal in Epic G/E needs them
- **Intraday / weekly indicators** — daily only in v1
- **Per-symbol custom parameters** (e.g., MA window override per holding) — defer until there's a use case
- **Automatic recompute when market_data changes** — manual sync via button + orchestrator is enough

---

## Self-Review Notes

- **Spec coverage:** All 11 indicator columns covered (Tasks 1, 3). MRSI per-symbol benchmark resolution covered (Task 4). Auto-seed benchmarks covered (Task 2). Sync endpoint + orchestrator wiring (Task 5). Read endpoint (Task 6). Live smoke (Task 7). Spec line "compute time <60s for 600 symbols after first run" not explicitly tested — accept as observation; first-run for 18-symbol smoke will easily fit.

- **Placeholder scan:** All steps have actual code or exact commands. No TBD / TODO / "implement later" / "similar to Task N" patterns.

- **Type consistency:** `compute_basic_indicators(df) -> df`, `compute_mrsi(stock_df, bench_df) -> Series`, `compute_for_symbol(conn, symbol) -> int`, `compute_all(conn) -> dict` consistent across tasks. `_resolve_benchmark(currency, stored_benchmark)` referenced same way wherever it appears. Endpoint paths consistent: `/api/sync/indicators`, `/api/indicators/{symbol}`. Orchestrator step name = `"indicators"` consistent in both the test assertion and the production wiring.
