# Epic G — Sell Signals on Holdings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute 11 toggleable technical sell signals against current IBKR holdings, persist them in `holding_signals`, and surface a traffic-light column on the Positions tab plus a click-to-expand fired-signal list. Threshold tuning lives in a new Configuration sub-section.

**Architecture:** Pure-Python signal evaluators (one per signal type) compute against the latest two `indicators` rows + `cost_basis_price` from `positions_ibkr`. A new `holding_signals` table stores `(symbol, signal_type)` results with `fired BOOLEAN`, `value`, `threshold`, `last_evaluated_at`. A `signal_settings` table holds the global enabled-set + threshold config. A new sync step (`POST /api/sync/holding-signals`) UPSERTs results and is wired into `/api/sync/full` after the `indicators` step. Frontend reads `GET /api/holding-signals` once on tab mount, renders a traffic-light column, and reuses shadcn's Collapsible for the per-row fired-signal panel.

**Tech Stack:** SQLite (no new tables outside the schema file), FastAPI router, pandas not required (signal math is row-level — no rolling windows, all rolling math already lives in `indicators`). Frontend: shadcn `Collapsible`, no new charting libs.

---

## File Structure

**Create:**
- `backend/scripts/holding_signals_compute.py` — 11 signal evaluators + `compute_all_signals(conn)` orchestrator
- `backend/api/routes/holding_signals.py` — `POST /api/sync/holding-signals`, `GET /api/holding-signals`, `GET /api/holding-signals/{symbol}`, `POST /api/holding-signals/settings`
- `backend/tests/test_holding_signals_compute.py` — unit tests per evaluator + orchestrator integration test
- `backend/tests/test_holding_signals_routes.py` — endpoint tests
- `frontend/components/ui/collapsible.tsx` — shadcn Collapsible (added via `npx shadcn add collapsible`)

**Modify:**
- `backend/database/schema.sql` — add `holding_signals` and `signal_settings` tables
- `backend/api/main.py` — register `holding_signals_router`
- `backend/api/routes/sync.py` — add `_step_holding_signals` and wire into `sync_full` after indicators
- `frontend/app/page.tsx` — Positions tab Signals column + expand panel; Configuration tab Signals settings card; new state + fetcher

**Delete:** none.

---

## Workflow gates

This epic has two explicit pause points beyond plan approval:

1. **Before Task 5 (Positions tab UI)** — per project workflow Step 6.2, UI stories need a visual mockup approved before any code is written. Drop in a quick HTML mockup via `ui-mockup:ui-mockup` and get approval.
2. **Before Task 6 (Configuration UI)** — same reason; this is also UI.

Tasks 1-4 (backend) and Task 7 (smoke) can chain without gates.

---

## Task 1: Schema — `holding_signals` + `signal_settings` tables

**Files:**
- Modify: `backend/database/schema.sql`
- Test: `backend/tests/test_holding_signals_compute.py` (new file, schema test for now)

- [ ] **Step 1.1: Write the failing schema test**

Create `backend/tests/test_holding_signals_compute.py`:

```python
"""Tests for holding signals compute and storage."""
import sqlite3


def test_schema_creates_holding_signals_and_settings_tables(temp_db):
    """init_database (called by temp_db fixture) creates the new tables."""
    conn = sqlite3.connect(str(temp_db))
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert "holding_signals" in tables
    assert "signal_settings" in tables


def test_signal_settings_seeded_with_11_defaults(temp_db):
    """First run pre-populates the 11 signal types as enabled with defaults."""
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT signal_type, enabled, threshold FROM signal_settings ORDER BY signal_type"
    ).fetchall()
    conn.close()
    types = {r[0] for r in rows}
    assert types == {
        "ma50_break", "ma100_break", "ma150_break", "ma200_break",
        "death_cross", "volume_dryup", "distribution_day",
        "rsi_weakness", "mrsi_flip",
        "trailing_drawdown", "stop_loss",
    }
    by_type = {r[0]: r for r in rows}
    assert by_type["trailing_drawdown"][2] == 0.10  # 10% default
    assert by_type["stop_loss"][2] == 0.08          # 8% default
    assert all(r[1] == 1 for r in rows)             # all enabled by default
```

- [ ] **Step 1.2: Run the test, confirm both fail**

```bash
source backend/venv/bin/activate
python -m pytest backend/tests/test_holding_signals_compute.py -v
```

Expected: both tests fail (`holding_signals` not in tables; `signal_settings` empty/missing).

- [ ] **Step 1.3: Append schema and seed defaults**

Append to `backend/database/schema.sql` (right after the `indicators` block, before any view definitions):

```sql
-- Sell signals computed per held symbol per signal_type.
-- One row per (symbol, signal_type); UPSERT on each evaluation.
-- Sold-out symbols are deleted on next sync.
CREATE TABLE IF NOT EXISTS holding_signals (
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    fired INTEGER NOT NULL,             -- 0 or 1
    value REAL,                         -- the measured value (e.g. close $138.40)
    threshold REAL,                     -- the comparison threshold (e.g. MA50 $145.20)
    last_evaluated_at TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, signal_type)
);
CREATE INDEX IF NOT EXISTS idx_holding_signals_symbol ON holding_signals(symbol);

-- Global on/off + threshold config per signal_type.
-- Seeded with all 11 enabled + sensible defaults; user tunes via Configuration UI.
CREATE TABLE IF NOT EXISTS signal_settings (
    signal_type TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    threshold REAL                      -- only used by trailing_drawdown / stop_loss
);
```

Also add a seeder block at the end of `init_database()` in `backend/database/connection.py` (find it, then add right before `conn.commit()` in that function):

```python
# Seed signal_settings defaults if empty (idempotent).
existing = conn.execute("SELECT COUNT(*) FROM signal_settings").fetchone()[0]
if existing == 0:
    defaults = [
        ("ma50_break", 1, None),
        ("ma100_break", 1, None),
        ("ma150_break", 1, None),
        ("ma200_break", 1, None),
        ("death_cross", 1, None),
        ("volume_dryup", 1, None),
        ("distribution_day", 1, None),
        ("rsi_weakness", 1, None),
        ("mrsi_flip", 1, None),
        ("trailing_drawdown", 1, 0.10),
        ("stop_loss", 1, 0.08),
    ]
    conn.executemany(
        "INSERT INTO signal_settings (signal_type, enabled, threshold) VALUES (?, ?, ?)",
        defaults,
    )
```

- [ ] **Step 1.4: Run test, confirm pass**

```bash
python -m pytest backend/tests/test_holding_signals_compute.py -v
```

Expected: both schema tests PASS.

- [ ] **Step 1.5: Run the full test suite to make sure no other test broke**

```bash
python -m pytest backend/tests/ 2>&1 | tail -5
```

Expected: all green (or pre-existing warnings only).

- [ ] **Step 1.6: Commit**

```bash
git add backend/database/schema.sql backend/database/connection.py backend/tests/test_holding_signals_compute.py
git commit -m "[STORY-G-1] feat: holding_signals + signal_settings tables with seeded defaults"
```

---

## Task 2: Signal compute library (11 evaluators + orchestrator)

Pure functions: input is the row data, output is `(fired: bool, value: float | None, threshold: float | None)`. The orchestrator pulls held symbols from `positions_ibkr`, joins with the latest two `indicators` rows + latest two `market_data` bars (for volume/close history needed by `volume_dryup`, `distribution_day`, `trailing_drawdown`), evaluates each enabled signal, and UPSERTs.

**Files:**
- Create: `backend/scripts/holding_signals_compute.py`
- Modify: `backend/tests/test_holding_signals_compute.py` (add evaluator tests)

- [ ] **Step 2.1: Write failing tests for the 11 evaluators**

Append to `backend/tests/test_holding_signals_compute.py`:

```python
from backend.scripts.holding_signals_compute import (
    eval_ma_break,
    eval_death_cross,
    eval_volume_dryup,
    eval_distribution_day,
    eval_rsi_weakness,
    eval_mrsi_flip,
    eval_trailing_drawdown,
    eval_stop_loss,
)


def test_ma50_break_fires_when_close_below_ma50():
    fired, value, threshold = eval_ma_break(close=138.40, ma=145.20)
    assert fired is True
    assert value == 138.40
    assert threshold == 145.20


def test_ma50_break_does_not_fire_when_close_above_ma50():
    fired, _, _ = eval_ma_break(close=150.00, ma=145.20)
    assert fired is False


def test_ma_break_returns_not_fired_when_ma_is_none():
    """Insufficient history → signal absent, not fired."""
    fired, value, threshold = eval_ma_break(close=138.40, ma=None)
    assert fired is False
    assert threshold is None


def test_death_cross_fires_when_ma50_crosses_below_ma150_today():
    # Yesterday: MA50 (148) >= MA150 (147). Today: MA50 (145) < MA150 (146).
    fired, _, _ = eval_death_cross(
        ma50_today=145, ma150_today=146,
        ma50_yesterday=148, ma150_yesterday=147,
    )
    assert fired is True


def test_death_cross_no_fire_when_already_below_yesterday():
    fired, _, _ = eval_death_cross(
        ma50_today=145, ma150_today=146,
        ma50_yesterday=144, ma150_yesterday=145,
    )
    assert fired is False


def test_volume_dryup_fires_when_5d_avg_below_half_of_20d():
    # 5-day avg = 400k, 20-day avg = 1M → 0.4 < 0.5 → fire
    fired, value, threshold = eval_volume_dryup(avg_5d=400_000, avg_20d=1_000_000)
    assert fired is True
    assert value == 400_000
    assert threshold == 500_000  # 50% of 20d avg


def test_volume_dryup_no_fire_when_5d_above_half():
    fired, _, _ = eval_volume_dryup(avg_5d=600_000, avg_20d=1_000_000)
    assert fired is False


def test_distribution_day_fires_on_down_day_high_volume():
    # Down day: close < prev_close. Volume > 1.5x 20-day avg.
    fired, _, _ = eval_distribution_day(
        close=98, prev_close=100, volume=2_000_000, vol_ma_20=1_000_000,
    )
    assert fired is True


def test_distribution_day_no_fire_on_up_day_even_with_high_volume():
    fired, _, _ = eval_distribution_day(
        close=102, prev_close=100, volume=2_000_000, vol_ma_20=1_000_000,
    )
    assert fired is False


def test_rsi_weakness_fires_when_drops_below_50_from_above():
    # Yesterday: 52 (>=50). Today: 48 (<50). Fire.
    fired, _, _ = eval_rsi_weakness(rsi_today=48, rsi_yesterday=52)
    assert fired is True


def test_rsi_weakness_no_fire_when_already_below_yesterday():
    fired, _, _ = eval_rsi_weakness(rsi_today=48, rsi_yesterday=49)
    assert fired is False


def test_mrsi_flip_fires_when_crosses_below_zero():
    fired, _, _ = eval_mrsi_flip(mrsi_today=-0.05, mrsi_yesterday=0.10)
    assert fired is True


def test_mrsi_flip_no_fire_when_still_positive():
    fired, _, _ = eval_mrsi_flip(mrsi_today=0.02, mrsi_yesterday=0.10)
    assert fired is False


def test_trailing_drawdown_fires_at_default_10pct():
    # 30-day high = 200, latest close = 178. Drawdown = 11% > 10%. Fire.
    fired, value, threshold = eval_trailing_drawdown(
        close=178, high_30d=200, drawdown_pct=0.10,
    )
    assert fired is True
    assert value == 178
    assert threshold == 180.0   # 200 * (1 - 0.10)


def test_trailing_drawdown_no_fire_at_5pct_when_threshold_10pct():
    fired, _, _ = eval_trailing_drawdown(close=190, high_30d=200, drawdown_pct=0.10)
    assert fired is False


def test_stop_loss_fires_when_close_below_cost_minus_pct():
    # Cost basis 100, default 8% threshold → fire if close < 92.
    fired, value, threshold = eval_stop_loss(
        close=91, cost_basis_price=100, drawdown_pct=0.08,
    )
    assert fired is True
    assert threshold == 92.0


def test_stop_loss_no_fire_when_above_threshold():
    fired, _, _ = eval_stop_loss(close=95, cost_basis_price=100, drawdown_pct=0.08)
    assert fired is False
```

- [ ] **Step 2.2: Run the new tests, confirm all fail**

```bash
python -m pytest backend/tests/test_holding_signals_compute.py -v
```

Expected: 16+ tests fail with `ModuleNotFoundError: backend.scripts.holding_signals_compute`.

- [ ] **Step 2.3: Implement the evaluators**

Create `backend/scripts/holding_signals_compute.py`:

```python
"""Sell-signal evaluators for held positions.

Each evaluator is a pure function returning (fired, value, threshold).
- `value` is the observed quantity (e.g. latest close, latest 5d volume).
- `threshold` is the comparison level (e.g. MA50, 50% of 20d volume).
- A None on either input that the signal needs → fired=False, value/threshold=None.

The orchestrator `compute_all_signals(conn)` joins these against the latest
indicators + market_data rows for every held symbol, UPSERTs into
holding_signals, and deletes rows for sold-out symbols.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

EvalResult = Tuple[bool, Optional[float], Optional[float]]


def _na() -> EvalResult:
    return (False, None, None)


def eval_ma_break(close: Optional[float], ma: Optional[float]) -> EvalResult:
    if close is None or ma is None:
        return _na()
    return (close < ma, close, ma)


def eval_death_cross(
    ma50_today: Optional[float], ma150_today: Optional[float],
    ma50_yesterday: Optional[float], ma150_yesterday: Optional[float],
) -> EvalResult:
    if None in (ma50_today, ma150_today, ma50_yesterday, ma150_yesterday):
        return _na()
    fired = ma50_yesterday >= ma150_yesterday and ma50_today < ma150_today
    return (fired, ma50_today, ma150_today)


def eval_volume_dryup(
    avg_5d: Optional[float], avg_20d: Optional[float],
) -> EvalResult:
    if avg_5d is None or avg_20d is None or avg_20d == 0:
        return _na()
    threshold = avg_20d * 0.5
    return (avg_5d < threshold, avg_5d, threshold)


def eval_distribution_day(
    close: Optional[float], prev_close: Optional[float],
    volume: Optional[float], vol_ma_20: Optional[float],
) -> EvalResult:
    if None in (close, prev_close, volume, vol_ma_20) or vol_ma_20 == 0:
        return _na()
    threshold = vol_ma_20 * 1.5
    fired = (close < prev_close) and (volume > threshold)
    return (fired, volume, threshold)


def eval_rsi_weakness(
    rsi_today: Optional[float], rsi_yesterday: Optional[float],
) -> EvalResult:
    if rsi_today is None or rsi_yesterday is None:
        return _na()
    fired = rsi_yesterday >= 50 and rsi_today < 50
    return (fired, rsi_today, 50.0)


def eval_mrsi_flip(
    mrsi_today: Optional[float], mrsi_yesterday: Optional[float],
) -> EvalResult:
    if mrsi_today is None or mrsi_yesterday is None:
        return _na()
    fired = mrsi_yesterday >= 0 and mrsi_today < 0
    return (fired, mrsi_today, 0.0)


def eval_trailing_drawdown(
    close: Optional[float], high_30d: Optional[float], drawdown_pct: float,
) -> EvalResult:
    if close is None or high_30d is None:
        return _na()
    threshold = high_30d * (1.0 - drawdown_pct)
    return (close < threshold, close, threshold)


def eval_stop_loss(
    close: Optional[float], cost_basis_price: Optional[float], drawdown_pct: float,
) -> EvalResult:
    if close is None or cost_basis_price is None:
        return _na()
    threshold = cost_basis_price * (1.0 - drawdown_pct)
    return (close < threshold, close, threshold)
```

- [ ] **Step 2.4: Run the evaluator tests, confirm all pass**

```bash
python -m pytest backend/tests/test_holding_signals_compute.py -v
```

Expected: all 16+ pass.

- [ ] **Step 2.5: Write a failing orchestrator integration test**

Append to `backend/tests/test_holding_signals_compute.py`:

```python
import sqlite3
from backend.scripts.holding_signals_compute import compute_all_signals


def _seed_held_symbol(temp_db, symbol="NVDA"):
    """One held symbol with cost basis 100 and two indicator/bar rows."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
        "VALUES (?, 10, 100, 'USD')", (symbol,)
    )
    # Yesterday: MA50 above MA150, RSI=55, MRSI=+0.05, close=99.
    # Today: MA50 below MA150, RSI=48, MRSI=-0.02, close=85 (15% below cost).
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_100, ma_150, ma_200, "
        "rsi_14, mrsi, volume_ma_20) "
        "VALUES (?, '2026-04-27', 110, 108, 109, 105, 55, 0.05, 1000000)", (symbol,)
    )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_100, ma_150, ma_200, "
        "rsi_14, mrsi, volume_ma_20) "
        "VALUES (?, '2026-04-28', 100, 105, 110, 108, 48, -0.02, 1000000)", (symbol,)
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
        "VALUES (?, '2026-04-27', 99, 100, 98, 99, 1100000)", (symbol,)
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
        "VALUES (?, '2026-04-28', 99, 99, 84, 85, 1800000)", (symbol,)
    )
    conn.commit()
    conn.close()


def test_orchestrator_evaluates_and_upserts(temp_db):
    _seed_held_symbol(temp_db)
    conn = sqlite3.connect(str(temp_db))
    result = compute_all_signals(conn)
    rows = conn.execute(
        "SELECT signal_type, fired FROM holding_signals WHERE symbol='NVDA'"
    ).fetchall()
    conn.close()
    by_type = {r[0]: bool(r[1]) for r in rows}
    # Today's MA50 (100) < MA150 (110) → ma_break fires; ditto ma100, ma200.
    assert by_type["ma50_break"] is True
    # Death cross: yesterday MA50 (110) >= MA150 (109); today MA50 (100) < MA150 (110) → fire.
    assert by_type["death_cross"] is True
    # RSI yesterday 55 → today 48 → fire.
    assert by_type["rsi_weakness"] is True
    # MRSI yesterday +0.05 → today -0.02 → fire.
    assert by_type["mrsi_flip"] is True
    # Stop loss: close 85 < 100 * (1 - 0.08) = 92 → fire.
    assert by_type["stop_loss"] is True
    assert result["symbols_processed"] == 1


def test_orchestrator_deletes_rows_for_sold_out_symbols(temp_db):
    """Symbol present in holding_signals but no longer in positions_ibkr → deleted."""
    conn = sqlite3.connect(str(temp_db))
    # Seed a stale row directly.
    conn.execute(
        "INSERT INTO holding_signals (symbol, signal_type, fired, last_evaluated_at) "
        "VALUES ('OLDCO', 'ma50_break', 1, '2026-04-01')"
    )
    conn.commit()
    compute_all_signals(conn)
    cnt = conn.execute(
        "SELECT COUNT(*) FROM holding_signals WHERE symbol='OLDCO'"
    ).fetchone()[0]
    conn.close()
    assert cnt == 0
```

- [ ] **Step 2.6: Run, confirm orchestrator tests fail**

```bash
python -m pytest backend/tests/test_holding_signals_compute.py::test_orchestrator_evaluates_and_upserts -v
```

Expected: `ImportError: cannot import name 'compute_all_signals'`.

- [ ] **Step 2.7: Implement `compute_all_signals`**

Append to `backend/scripts/holding_signals_compute.py`:

```python
def compute_all_signals(conn) -> dict:
    """Evaluate every enabled signal_type for every currently-held symbol.

    - Reads signal_settings to get the enabled set + per-signal thresholds.
    - For each symbol in positions_ibkr: pulls latest 2 indicators rows,
      latest 2 market_data bars, computes 5d/20d volume averages and
      30d high from market_data, and runs each evaluator.
    - UPSERTs into holding_signals.
    - DELETEs holding_signals rows whose symbol is not in positions_ibkr.

    Returns: {"symbols_processed": int, "signals_evaluated": int}.
    """
    settings = {
        row[0]: {"enabled": bool(row[1]), "threshold": row[2]}
        for row in conn.execute(
            "SELECT signal_type, enabled, threshold FROM signal_settings"
        ).fetchall()
    }

    held_rows = conn.execute(
        "SELECT symbol, cost_basis_price FROM positions_ibkr"
    ).fetchall()
    held_symbols = {r[0] for r in held_rows}
    cost_by_sym = {r[0]: r[1] for r in held_rows}

    # Drop signals for sold-out symbols.
    if held_symbols:
        placeholders = ",".join("?" * len(held_symbols))
        conn.execute(
            f"DELETE FROM holding_signals WHERE symbol NOT IN ({placeholders})",
            tuple(held_symbols),
        )
    else:
        conn.execute("DELETE FROM holding_signals")

    now = datetime.now().astimezone().isoformat()
    signals_evaluated = 0

    for symbol in held_symbols:
        ind_rows = conn.execute(
            "SELECT time, ma_50, ma_100, ma_150, ma_200, rsi_14, mrsi, volume_ma_20 "
            "FROM indicators WHERE symbol=? ORDER BY time DESC LIMIT 2",
            (symbol,),
        ).fetchall()
        bar_rows = conn.execute(
            "SELECT time, close, volume FROM market_data "
            "WHERE symbol=? ORDER BY time DESC LIMIT 30",
            (symbol,),
        ).fetchall()
        if not ind_rows or not bar_rows:
            continue

        ind_today = ind_rows[0]
        ind_yest = ind_rows[1] if len(ind_rows) > 1 else (None,) * 8
        bar_today = bar_rows[0]
        bar_yest = bar_rows[1] if len(bar_rows) > 1 else (None, None, None)
        last_30_closes = [b[1] for b in bar_rows if b[1] is not None]
        high_30d = max(last_30_closes) if last_30_closes else None
        last_5_vols = [b[2] for b in bar_rows[:5] if b[2] is not None]
        last_20_vols = [b[2] for b in bar_rows[:20] if b[2] is not None]
        avg_5d = sum(last_5_vols) / len(last_5_vols) if last_5_vols else None
        avg_20d = sum(last_20_vols) / len(last_20_vols) if last_20_vols else None
        close_today = bar_today[1]
        close_yest = bar_yest[1]
        vol_today = bar_today[2]

        evaluations = [
            ("ma50_break",      eval_ma_break(close_today, ind_today[1])),
            ("ma100_break",     eval_ma_break(close_today, ind_today[2])),
            ("ma150_break",     eval_ma_break(close_today, ind_today[3])),
            ("ma200_break",     eval_ma_break(close_today, ind_today[4])),
            ("death_cross",     eval_death_cross(ind_today[1], ind_today[3], ind_yest[1], ind_yest[3])),
            ("volume_dryup",    eval_volume_dryup(avg_5d, avg_20d)),
            ("distribution_day", eval_distribution_day(close_today, close_yest, vol_today, ind_today[7])),
            ("rsi_weakness",    eval_rsi_weakness(ind_today[5], ind_yest[5])),
            ("mrsi_flip",       eval_mrsi_flip(ind_today[6], ind_yest[6])),
            ("trailing_drawdown", eval_trailing_drawdown(close_today, high_30d,
                                  settings.get("trailing_drawdown", {}).get("threshold") or 0.10)),
            ("stop_loss",       eval_stop_loss(close_today, cost_by_sym.get(symbol),
                                  settings.get("stop_loss", {}).get("threshold") or 0.08)),
        ]

        for signal_type, (fired, value, threshold) in evaluations:
            if not settings.get(signal_type, {}).get("enabled", True):
                continue
            conn.execute(
                "INSERT INTO holding_signals (symbol, signal_type, fired, value, threshold, last_evaluated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(symbol, signal_type) DO UPDATE SET "
                "  fired=excluded.fired, value=excluded.value, threshold=excluded.threshold, "
                "  last_evaluated_at=excluded.last_evaluated_at",
                (symbol, signal_type, 1 if fired else 0, value, threshold, now),
            )
            signals_evaluated += 1

    conn.commit()
    return {
        "symbols_processed": len(held_symbols),
        "signals_evaluated": signals_evaluated,
    }
```

- [ ] **Step 2.8: Run all tests in this file, confirm pass**

```bash
python -m pytest backend/tests/test_holding_signals_compute.py -v
```

Expected: all pass.

- [ ] **Step 2.9: Commit**

```bash
git add backend/scripts/holding_signals_compute.py backend/tests/test_holding_signals_compute.py
git commit -m "[STORY-G-2] feat: 11 sell-signal evaluators + compute_all_signals orchestrator"
```

---

## Task 3: `POST /api/sync/holding-signals` + orchestrator wiring

**Files:**
- Create: `backend/api/routes/holding_signals.py`
- Modify: `backend/api/main.py`, `backend/api/routes/sync.py`
- Test: `backend/tests/test_holding_signals_routes.py` (new)

- [ ] **Step 3.1: Write failing test for the sync endpoint**

Create `backend/tests/test_holding_signals_routes.py`:

```python
"""Tests for /api/sync/holding-signals + /api/holding-signals reads."""
import sqlite3

from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def _seed(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
        "VALUES ('NVDA', 10, 100, 'USD')"
    )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_150, rsi_14, mrsi) "
        "VALUES ('NVDA', '2026-04-27', 110, 109, 55, 0.05)"
    )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_150, rsi_14, mrsi) "
        "VALUES ('NVDA', '2026-04-28', 100, 110, 48, -0.02)"
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, close, volume) "
        "VALUES ('NVDA', '2026-04-28', 85, 1500000)"
    )
    conn.commit()
    conn.close()


def test_sync_endpoint_runs_compute(temp_db):
    _seed(temp_db)
    r = client.post("/api/sync/holding-signals")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["symbols_processed"] == 1


def test_get_all_signals_returns_fired_only_filter(temp_db):
    _seed(temp_db)
    client.post("/api/sync/holding-signals")
    r = client.get("/api/holding-signals?fired=true")
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(it["fired"] is True for it in items)


def test_get_signals_for_one_symbol(temp_db):
    _seed(temp_db)
    client.post("/api/sync/holding-signals")
    r = client.get("/api/holding-signals/NVDA")
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "NVDA"
    assert any(s["signal_type"] == "stop_loss" and s["fired"] for s in data["signals"])


def test_settings_post_updates_threshold(temp_db):
    r = client.post(
        "/api/holding-signals/settings",
        json={"signal_type": "stop_loss", "enabled": True, "threshold": 0.05},
    )
    assert r.status_code == 200
    conn = sqlite3.connect(str(temp_db))
    row = conn.execute(
        "SELECT enabled, threshold FROM signal_settings WHERE signal_type='stop_loss'"
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] == 0.05
```

- [ ] **Step 3.2: Run, confirm fails (no router yet)**

```bash
python -m pytest backend/tests/test_holding_signals_routes.py -v
```

Expected: `ImportError` for the not-yet-registered router OR 404 on the routes.

- [ ] **Step 3.3: Implement the router**

Create `backend/api/routes/holding_signals.py`:

```python
"""Holding signals API: sync, list, per-symbol, settings."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.database.connection import get_db_connection
from backend.scripts.holding_signals_compute import compute_all_signals
from backend.api.utils.logger import logger

router = APIRouter()


@router.post("/api/sync/holding-signals")
async def sync_holding_signals():
    logger.info("📡 Sync step: holding-signals")
    try:
        conn = get_db_connection()
        try:
            result = compute_all_signals(conn)
        finally:
            conn.close()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ sync_holding_signals failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/holding-signals")
async def get_all_holding_signals(fired: Optional[bool] = None):
    conn = get_db_connection()
    sql = (
        "SELECT symbol, signal_type, fired, value, threshold, last_evaluated_at "
        "FROM holding_signals"
    )
    args: tuple = ()
    if fired is not None:
        sql += " WHERE fired=?"
        args = (1 if fired else 0,)
    sql += " ORDER BY symbol, signal_type"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return {
        "items": [
            {
                "symbol": r[0],
                "signal_type": r[1],
                "fired": bool(r[2]),
                "value": r[3],
                "threshold": r[4],
                "last_evaluated_at": r[5],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/api/holding-signals/{symbol}")
async def get_holding_signals_for_symbol(symbol: str):
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT signal_type, fired, value, threshold, last_evaluated_at "
        "FROM holding_signals WHERE symbol=? ORDER BY signal_type",
        (symbol.upper(),),
    ).fetchall()
    conn.close()
    return {
        "symbol": symbol.upper(),
        "signals": [
            {
                "signal_type": r[0],
                "fired": bool(r[1]),
                "value": r[2],
                "threshold": r[3],
                "last_evaluated_at": r[4],
            }
            for r in rows
        ],
    }


class SettingsUpdate(BaseModel):
    signal_type: str
    enabled: bool
    threshold: Optional[float] = None


@router.post("/api/holding-signals/settings")
async def update_signal_settings(payload: SettingsUpdate):
    conn = get_db_connection()
    cur = conn.execute(
        "UPDATE signal_settings SET enabled=?, threshold=? WHERE signal_type=?",
        (1 if payload.enabled else 0, payload.threshold, payload.signal_type),
    )
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail=f"unknown signal_type: {payload.signal_type}")
    conn.commit()
    conn.close()
    return {"success": True, "signal_type": payload.signal_type}
```

- [ ] **Step 3.4: Register the router**

In `backend/api/main.py`, after the existing `from backend.api.routes.security import router as security_router` line:

```python
from backend.api.routes.holding_signals import router as holding_signals_router
```

And after `app.include_router(security_router)`:

```python
app.include_router(holding_signals_router)
```

- [ ] **Step 3.5: Wire into `/api/sync/full`**

In `backend/api/routes/sync.py`, add this helper near `_step_indicators`:

```python
def _step_holding_signals() -> dict:
    from backend.scripts.holding_signals_compute import compute_all_signals
    conn = get_db_connection()
    try:
        return compute_all_signals(conn)
    finally:
        conn.close()
```

And in `sync_full`, right after `_run(steps, "indicators", _step_indicators)`:

```python
_run(steps, "holding_signals", _step_holding_signals)
```

- [ ] **Step 3.6: Run all route tests, confirm pass**

```bash
python -m pytest backend/tests/test_holding_signals_routes.py backend/tests/test_sync_routes.py -v
```

Expected: all pass.

- [ ] **Step 3.7: Commit**

```bash
git add backend/api/routes/holding_signals.py backend/api/main.py backend/api/routes/sync.py backend/tests/test_holding_signals_routes.py
git commit -m "[STORY-G-3] feat: POST /api/sync/holding-signals + wire into /api/sync/full"
```

---

## Task 4: GET endpoints (already covered by Task 3)

Tasks 3.1–3.7 already cover `GET /api/holding-signals`, `GET /api/holding-signals/{symbol}`, and `POST /api/holding-signals/settings`. No separate work item — collapse G-4 into G-3 in the build log when this lands.

---

## ▼▼▼ WORKFLOW GATE — UI mockup approval ▼▼▼

Before Task 5, run `ui-mockup:ui-mockup` and get user approval of the Positions tab Signals column + expand panel layout. Do NOT touch frontend code until approved.

---

## Task 5: Positions tab Signals column + expand panel

**Files:**
- Create: `frontend/components/ui/collapsible.tsx` (via shadcn)
- Modify: `frontend/app/page.tsx`

- [ ] **Step 5.1: Add shadcn Collapsible**

```bash
cd frontend && npx shadcn@latest add collapsible
```

- [ ] **Step 5.2: Add types and state**

In `frontend/app/page.tsx`, near the other interfaces (~line 248 area, near `UniverseCoverageItem`):

```tsx
interface HoldingSignal {
  signal_type: string;
  fired: boolean;
  value: number | null;
  threshold: number | null;
  last_evaluated_at: string | null;
}

interface HoldingSignalsBySymbol {
  [symbol: string]: HoldingSignal[];
}
```

In the state block (near `useState<UniverseCoverageItem[]>`):

```tsx
const [holdingSignals, setHoldingSignals] = useState<HoldingSignalsBySymbol>({});
const [expandedSignalRow, setExpandedSignalRow] = useState<string | null>(null);
```

In the `fetch*` block:

```tsx
const fetchHoldingSignals = async () => {
  try {
    const r = await fetch('/api/proxy/api/holding-signals');
    if (r.ok) {
      const data = await r.json();
      const grouped: HoldingSignalsBySymbol = {};
      for (const it of data.items) {
        (grouped[it.symbol] ||= []).push(it);
      }
      setHoldingSignals(grouped);
    }
  } catch (e) { console.error('fetchHoldingSignals', e); }
};
```

Add `fetchHoldingSignals();` inside the existing `useEffect` that fires on tab change (the same one that calls `fetchUniverseCoverage()`).

- [ ] **Step 5.3: Add Signals column to Positions table header**

In the table header column array (around `'cost_basis_price' as const`), append:

```tsx
{ key: 'signals' as const, label: 'Signals', align: 'center' },
```

(Note: `'signals'` is non-sortable for v1; the existing `handlePositionsSort` should ignore it via a guard — see Step 5.4.)

In `handlePositionsSort`:

```tsx
const handlePositionsSort = (column: string) => {
  if (column === 'signals') return;
  // ... existing body ...
};
```

- [ ] **Step 5.4: Add Signals cell + expand row**

Inside the `<tr key={pos.symbol} ...>` body, append a new `<td>`:

```tsx
<td style={{ padding: '12px', textAlign: 'center', fontSize: '14px' }}>
  {(() => {
    const fired = (holdingSignals[pos.symbol] ?? []).filter(s => s.fired).length;
    const light = fired === 0 ? '🟢' : fired <= 2 ? '🟡' : '🔴';
    return (
      <button
        onClick={(e) => {
          e.stopPropagation();
          setExpandedSignalRow(expandedSignalRow === pos.symbol ? null : pos.symbol);
        }}
        style={{ background: 'none', border: 'none', fontSize: '18px', cursor: 'pointer' }}
        title={`${fired} fired`}
      >
        {light} {fired > 0 ? fired : ''}
      </button>
    );
  })()}
</td>
```

Below the `<tr>`, render the expanded fired-signal list when matching:

```tsx
{expandedSignalRow === pos.symbol && (
  <tr>
    <td colSpan={6} style={{ backgroundColor: '#f9fafb', padding: '12px 24px' }}>
      <div style={{ fontSize: '13px', color: '#1f2937' }}>
        {(holdingSignals[pos.symbol] ?? []).filter(s => s.fired).length === 0 ? (
          <span style={{ color: '#6b7280' }}>No fired signals</span>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
            {(holdingSignals[pos.symbol] ?? []).filter(s => s.fired).map(s => (
              <li key={s.signal_type} style={{ padding: '4px 0' }}>
                <strong>{s.signal_type.replace(/_/g, ' ')}:</strong>{' '}
                {s.value != null ? s.value.toFixed(2) : '—'}{' '}
                vs threshold {s.threshold != null ? s.threshold.toFixed(2) : '—'}
              </li>
            ))}
          </ul>
        )}
      </div>
    </td>
  </tr>
)}
```

(Adjust `colSpan` to match the new total column count — should be 6 after adding Signals.)

- [ ] **Step 5.5: Smoke-test in browser**

Restart `./start.sh`. Click Positions tab, confirm:
- Each held symbol shows 🟢/🟡/🔴 in the Signals column
- Click the traffic light → expands into a sub-row listing fired signals
- Click again → collapses
- Row click into the Detail Sheet still works (the `e.stopPropagation()` handles the conflict)

- [ ] **Step 5.6: Commit**

```bash
git add frontend/components/ui/collapsible.tsx frontend/app/page.tsx
git commit -m "[STORY-G-5] feat: Positions tab traffic-light Signals column + expand panel"
```

---

## ▼▼▼ WORKFLOW GATE — Configuration UI mockup approval ▼▼▼

Before Task 6, run `ui-mockup:ui-mockup` for the Signals settings card and get approval.

---

## Task 6: Configuration tab — Signals settings card

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 6.1: Add settings state + fetcher**

```tsx
interface SignalSetting {
  signal_type: string;
  enabled: boolean;
  threshold: number | null;
}

const [signalSettings, setSignalSettings] = useState<SignalSetting[]>([]);

const fetchSignalSettings = async () => {
  try {
    const r = await fetch('/api/proxy/api/holding-signals/settings');
    if (r.ok) setSignalSettings((await r.json()).items);
  } catch (e) { console.error('fetchSignalSettings', e); }
};

const updateSignalSetting = async (s: SignalSetting) => {
  try {
    await fetch('/api/proxy/api/holding-signals/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(s),
    });
    await fetchSignalSettings();
  } catch (e) { console.error('updateSignalSetting', e); }
};
```

(Note: This needs a corresponding `GET /api/holding-signals/settings` endpoint — add to the backend before Step 6.2 if missing. Append to `backend/api/routes/holding_signals.py`:

```python
@router.get("/api/holding-signals/settings")
async def get_signal_settings():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT signal_type, enabled, threshold FROM signal_settings ORDER BY signal_type"
    ).fetchall()
    conn.close()
    return {
        "items": [
            {"signal_type": r[0], "enabled": bool(r[1]), "threshold": r[2]}
            for r in rows
        ]
    }
```

Add a small route test for it before continuing.)

- [ ] **Step 6.2: Add Signals settings Card to Configuration tab**

In `frontend/app/page.tsx`, inside the Configuration tab body (`{activeTab === 'configuration' && ...}`), after the Market Data Card, append:

```tsx
<Card>
  <CardHeader>
    <CardTitle className="flex items-center gap-2">
      Signal Settings
      <Badge variant="secondary" className="ml-auto">
        {signalSettings.filter(s => s.enabled).length}/{signalSettings.length} enabled
      </Badge>
    </CardTitle>
  </CardHeader>
  <CardContent className="space-y-2">
    {signalSettings.map(s => (
      <div key={s.signal_type} className="flex items-center justify-between p-3 rounded-md border bg-card">
        <div className="flex items-center gap-3">
          <Switch
            checked={s.enabled}
            onCheckedChange={(checked) => updateSignalSetting({ ...s, enabled: checked })}
          />
          <span className="text-sm font-medium">{s.signal_type.replace(/_/g, ' ')}</span>
        </div>
        {s.threshold != null && (
          <Input
            type="number"
            step="0.01"
            value={s.threshold}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              if (!isNaN(v)) updateSignalSetting({ ...s, threshold: v });
            }}
            className="max-w-[100px]"
          />
        )}
      </div>
    ))}
  </CardContent>
</Card>
```

- [ ] **Step 6.3: Wire fetcher into the tab effect**

Add `fetchSignalSettings();` to the same useEffect that already calls `fetchUniverseCoverage`.

- [ ] **Step 6.4: Smoke-test in browser**

Restart, navigate to Configuration tab. Confirm:
- All 11 signal toggles render
- `trailing_drawdown` and `stop_loss` show a numeric input with the threshold
- Toggling/changing threshold persists across reload (DB write succeeds)

- [ ] **Step 6.5: Commit**

```bash
git add frontend/app/page.tsx backend/api/routes/holding_signals.py backend/tests/test_holding_signals_routes.py
git commit -m "[STORY-G-6] feat: Signal settings card in Configuration tab + GET settings endpoint"
```

---

## Task 7: End-to-end smoke test

**Files:**
- None (manual verification + document in build-log).

- [ ] **Step 7.1: Run full sync against live DB**

```bash
curl -s -X POST http://localhost:8000/api/sync/full | jq .
```

Expected: a `holding_signals` step appears in the response with `status: "ok"` and `result.symbols_processed` matching held position count.

- [ ] **Step 7.2: Read back signals**

```bash
curl -s http://localhost:8000/api/holding-signals | jq '.items[] | select(.fired == true)'
```

Confirm at least one fired signal across the held universe; spot-check the math against the indicator values.

- [ ] **Step 7.3: Browser end-to-end**

Open Positions tab in the browser. Confirm:
- Traffic-light per row matches CLI output count
- Click expands → shows fired list
- Click into Security Detail Sheet still works via the row click

- [ ] **Step 7.4: Tune a threshold and re-verify**

In Configuration tab, drop `stop_loss` threshold from 8% → 5%. Click Sync (or POST `/api/sync/holding-signals`). Confirm fewer rows fire stop_loss (since the threshold got tighter) and Positions tab traffic lights update.

- [ ] **Step 7.5: Update build-log + close epic in ACTIVE.md**

Append to `docs/project/config/build-log.md` an Epic G section listing the 6 stories shipped + endpoints added. Move Epic G to "Recently shipped" in `docs/project/config/epics/ACTIVE.md` and promote Epic E to "Currently active."

- [ ] **Step 7.6: Commit**

```bash
git add docs/project/config/build-log.md docs/project/config/epics/ACTIVE.md
git commit -m "[STORY-G-7] docs: mark Epic G complete + log smoke-test results"
```

---

## Self-review

- **Spec coverage:** All 11 signal types → Task 2. `holding_signals` table → Task 1. Sync orchestrator wiring → Task 3. UI traffic light + expand → Task 5. Settings UI + threshold tuning → Task 6. End-to-end → Task 7. Sold-out symbol cleanup → Task 2.7 + Task 2 orchestrator test. ✅
- **Placeholders:** none.
- **Type consistency:** `compute_all_signals(conn)` consistent. Evaluator return type `(fired, value, threshold)` consistent across all 8 evaluator functions and the orchestrator's call sites. Settings shape `(signal_type, enabled, threshold)` consistent across schema, seeder, GET, POST.
- **Workflow gates surfaced:** plan approval (now), then mockup approval before Tasks 5 and 6.
