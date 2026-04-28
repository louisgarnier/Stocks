# Story M — Migrate to Supabase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the live database from local SQLite to Supabase-hosted Postgres while keeping tests on SQLite for speed. Make all SQL portable between both engines.

**Architecture:** Engine-agnostic data layer. `backend/database/connection.py` reads `SUPABASE_DB_URL` from env: present → psycopg2 to Supabase, absent → SQLite (test default). All SQL written in syntax both engines accept (`INSERT ... ON CONFLICT ... DO NOTHING/UPDATE` instead of SQLite-specific `INSERT OR IGNORE/REPLACE`). One-shot migration script reads every row from the existing SQLite file and bulk-inserts into Postgres.

**Tech Stack:** psycopg2-binary, python-dotenv (already present), FastAPI (unchanged), pandas + sqlite3 stdlib for the migration script. Supabase free tier. No frontend changes.

---

## Pre-flight (manual, you do this once)

These steps require you to interact with the Supabase web UI. The plan tasks below assume these are done.

1. **Create Supabase project** at https://supabase.com/dashboard. Pick the closest region (eu-west for France).
2. **Copy connection string** from Project Settings → Database → Connection string → URI mode (the one starting `postgresql://postgres:...`).
3. **Save it locally** — you'll paste it into `.env` in Task 1.

That's it for manual steps. Schema and data come from this plan.

---

## File Structure

**Create:**
- `backend/database/connection_pg.py` — psycopg2 connection helper (engine-aware)
- `backend/scripts/migrate_sqlite_to_supabase.py` — one-shot data migration
- `backend/database/schema_pg_init.sql` — Postgres-flavored schema for first-time provisioning (kept side-by-side with the existing `schema.sql` which stays SQLite-canonical for tests)
- `backend/tests/test_connection_engine.py` — unit tests for the engine switch

**Modify:**
- `backend/database/connection.py` — engine switch (SQLite if no env, Postgres if `SUPABASE_DB_URL` set)
- `backend/database/schema.sql` — change `INTEGER PRIMARY KEY AUTOINCREMENT` → `INTEGER PRIMARY KEY` (works in both); other minor portability fixes
- `backend/api/routes/sync.py` — `INSERT INTO import_logs ...` works as-is (was already explicit columns)
- `backend/utils/ca_status.py` — already uses `get_db_connection()` so engine swap is transparent (verify)
- `backend/scripts/parse_csv_trades.py` — replace `INSERT OR IGNORE` if any → `ON CONFLICT DO NOTHING`
- `backend/scripts/fetch_flex_trades.py` — replace `INSERT OR IGNORE` / `INSERT OR REPLACE` → ON CONFLICT
- `.env.example` — add `SUPABASE_DB_URL` template
- `backend/requirements.txt` — add `psycopg2-binary>=2.9`

**Delete:** none. The migration script can be deleted after the migration is verified, but leaving it for re-runs is fine.

---

## Task 1: Add Postgres dep + .env template

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: Add psycopg2 to requirements**

In `backend/requirements.txt` append:

```
psycopg2-binary>=2.9
```

Install:
```bash
/Library/Frameworks/Python.framework/Versions/3.10/bin/pip install psycopg2-binary
```

Verify:
```bash
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -c "import psycopg2; print(psycopg2.__version__)"
```
Expected: a version like `2.9.10 (dt dec pq3 ext lo64)` printed.

- [ ] **Step 2: Add .env template**

Append to `.env.example` (create the file if it doesn't exist; do NOT touch the live `.env` until later):

```
# Supabase — when set, backend uses Postgres instead of SQLite.
# Get it from: Supabase Dashboard > Project Settings > Database > Connection string > URI
# Example: postgresql://postgres.xxx:password@aws-0-eu-west-X.pooler.supabase.com:6543/postgres
SUPABASE_DB_URL=
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt .env.example
git commit -m "[STORY-M-1] feat: add psycopg2-binary dep + SUPABASE_DB_URL .env template

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Engine-aware connection layer

The single most important change. `get_db_connection()` keeps the same name and external interface, but internally picks SQLite or Postgres based on env. Both return connection objects whose `.execute()` returns mapping-style rows.

**Files:**
- Modify: `backend/database/connection.py`
- Test: `backend/tests/test_connection_engine.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_connection_engine.py`:

```python
"""Engine-switch tests for connection.py.

Verifies that get_db_connection() picks SQLite when SUPABASE_DB_URL is unset
and that the returned connection supports both row[0] and row['col'] access.
"""
import sqlite3
import pytest


def test_sqlite_used_when_no_env(monkeypatch, temp_db):
    """No SUPABASE_DB_URL → SQLite path, identical to current behavior."""
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    # Should be a sqlite3.Connection
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_sqlite_row_supports_dict_access(monkeypatch, temp_db):
    """SQLite rows must support row[0] and row['col'] both."""
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    from backend.database.connection import get_db_connection
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity) VALUES ('AAPL', 100)"
    )
    conn.commit()
    row = conn.execute("SELECT symbol, quantity FROM positions_ibkr").fetchone()
    assert row[0] == "AAPL"
    assert row["symbol"] == "AAPL"
    assert row[1] == 100
    assert row["quantity"] == 100
    conn.close()


def test_postgres_path_imports_psycopg2_only_when_needed():
    """Setting SUPABASE_DB_URL routes through psycopg2. We mock the connect call so this test doesn't need a real DB."""
    import os
    import backend.database.connection as conn_mod
    original_connect = getattr(conn_mod, "_pg_connect", None)

    called_with = {}
    def fake_connect(url):
        called_with["url"] = url
        class FakeConn:
            def cursor(self):
                class FakeCursor:
                    def execute(self, *a, **k): return None
                    def fetchone(self): return None
                    def fetchall(self): return []
                    def close(self): pass
                return FakeCursor()
            def execute(self, *a, **k): return self.cursor().execute(*a, **k)
            def commit(self): pass
            def close(self): pass
        return FakeConn()

    conn_mod._pg_connect = fake_connect
    try:
        os.environ["SUPABASE_DB_URL"] = "postgresql://fake"
        c = conn_mod.get_db_connection()
        assert called_with["url"] == "postgresql://fake"
        c.close()
    finally:
        os.environ.pop("SUPABASE_DB_URL", None)
        if original_connect:
            conn_mod._pg_connect = original_connect
```

- [ ] **Step 2: Run, verify failures**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_connection_engine.py -v`
Expected: third test fails with `AttributeError: module 'backend.database.connection' has no attribute '_pg_connect'`. First two pass already if the SQLite path is unchanged.

- [ ] **Step 3: Refactor connection.py**

Replace `backend/database/connection.py` with:

```python
"""Database connection — engine-aware.

If SUPABASE_DB_URL is set in env, connect to Postgres via psycopg2.
Otherwise fall back to local SQLite.

Returned connection objects implement a consistent subset:
  - .execute(sql, params=None) → cursor
  - .cursor() → cursor
  - .commit()
  - .close()
  - Rows accessed via row[i] OR row['col_name']
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_DIR = PROJECT_ROOT / "output" / "database"
DB_FILE = DB_DIR / "finance.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


# Indirected so tests can monkeypatch
def _pg_connect(url: str):
    import psycopg2
    from psycopg2.extras import DictCursor
    conn = psycopg2.connect(url, cursor_factory=DictCursor)
    return _PgConnectionWrapper(conn)


class _PgConnectionWrapper:
    """Thin wrapper exposing the same execute() shorthand sqlite3.Connection has."""
    def __init__(self, real_conn):
        self._conn = real_conn

    def execute(self, sql: str, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db_connection():
    """Return a DB connection. Postgres if SUPABASE_DB_URL set, else SQLite."""
    url = os.getenv("SUPABASE_DB_URL")
    if url:
        return _pg_connect(url)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    """Initialize the SQLite database (Postgres init is done via schema_pg_init.sql + Supabase SQL Editor)."""
    if os.getenv("SUPABASE_DB_URL"):
        # Postgres init is a separate one-shot in Story M; skip here.
        return
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if SCHEMA_FILE.exists():
        conn = get_db_connection()
        cursor = conn.cursor()
        with open(SCHEMA_FILE, "r") as f:
            cursor.executescript(f.read())
        conn.commit()
        conn.close()
        print(f"✅ Database initialized at {DB_FILE}")


def get_db_path() -> Path:
    return DB_FILE
```

- [ ] **Step 4: Run all tests, confirm green**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/ -q --ignore=backend/tests/test_database.py 2>&1 | tail -10`

Expected: same pass/fail count as before. The pre-existing failures (test_database.py with its leftover schema-init test) and `test_health_endpoint` pre-existing failures are unchanged. New `test_connection_engine.py` 3/3 pass.

- [ ] **Step 5: Commit**

```bash
git add backend/database/connection.py backend/tests/test_connection_engine.py
git commit -m "[STORY-M-2] feat: engine-aware connection (SQLite default, Postgres when SUPABASE_DB_URL set)

- Wraps psycopg2 connection in a thin shim so .execute() returns cursors
  with same call shape as sqlite3
- DictCursor for Postgres → row['col'] access matches sqlite3.Row
- _pg_connect indirection for hermetic tests

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Replace SQLite-specific SQL with portable syntax

`INSERT OR IGNORE` and `INSERT OR REPLACE` are SQLite-only. Both engines support `INSERT ... ON CONFLICT (cols) DO NOTHING/UPDATE`, so we standardize on that.

**Files:**
- Modify: `backend/scripts/fetch_flex_trades.py`
- Modify: `backend/api/routes/universe.py`
- Modify: `backend/scripts/universe_seeders.py` (will exist after Story C — flag as TODO if running Story M before C)
- Modify: `backend/scripts/market_data_ingestor.py` (Story C — same flag)

Run-order note: **Story M ships before Story C.** The Story C plan has been written assuming SQLite syntax. After Story M, when we get to Story C, we'll write its `INSERT OR IGNORE` calls using `ON CONFLICT` instead. Story M only modifies what already exists today.

- [ ] **Step 1: Find every SQLite-only INSERT in current code**

Run:
```bash
grep -rn "INSERT OR IGNORE\|INSERT OR REPLACE" backend/ --include='*.py' | grep -v __pycache__
```

Expected output (today, before Story C):
- `backend/scripts/fetch_flex_trades.py` — INSERT OR IGNORE in `insert_flex_trades`
- (Any others — list them; the steps below assume only fetch_flex_trades.py)

- [ ] **Step 2: Replace in `fetch_flex_trades.py`**

Find every `INSERT OR IGNORE INTO transactions ...` line and rewrite. The SQL pattern to use:

```sql
INSERT INTO transactions (transaction_id, ...) VALUES (?, ...)
ON CONFLICT (transaction_id) DO NOTHING
```

Concretely, locate the existing `INSERT OR IGNORE INTO transactions` statement (search the file). Replace `INSERT OR IGNORE INTO transactions (...)` with `INSERT INTO transactions (...) ON CONFLICT (transaction_id) DO NOTHING`.

If there are multiple `INSERT OR IGNORE` calls (e.g., one in `insert_flex_trades`, possibly more), apply the same transform to each. The conflict column is whichever UNIQUE column was driving the IGNORE — typically `transaction_id`.

- [ ] **Step 3: Verify the test suite still green**

Run:
```bash
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py -v
```

Expected: 10 pass (same as before). `ON CONFLICT` works in SQLite 3.24+ identically.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/fetch_flex_trades.py
git commit -m "[STORY-M-3] refactor: replace SQLite-only INSERT OR IGNORE with portable ON CONFLICT

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Postgres-flavored schema file

Most of `schema.sql` works in Postgres unchanged. The few exceptions get patched into a separate `schema_pg_init.sql` for first-time Postgres provisioning. The original `schema.sql` stays SQLite-canonical for tests.

**Files:**
- Create: `backend/database/schema_pg_init.sql`

- [ ] **Step 1: Write the Postgres schema**

Create `backend/database/schema_pg_init.sql`:

```sql
-- Postgres schema for Supabase. Run once via Supabase SQL Editor or psql.
-- This is functionally identical to schema.sql but adapted to Postgres syntax:
--   * INTEGER PRIMARY KEY AUTOINCREMENT  -> SERIAL PRIMARY KEY
--   * TIMESTAMP DEFAULT CURRENT_TIMESTAMP -> TIMESTAMPTZ DEFAULT NOW()
--   * INTEGER DEFAULT 0/1 for booleans   -> BOOLEAN DEFAULT FALSE/TRUE
--   * REAL                              -> DOUBLE PRECISION
--   * TEXT                              -> TEXT (unchanged, no length cap needed)
--
-- Run after creating the Supabase project; before the data-migration script.

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    transaction_id TEXT UNIQUE NOT NULL,
    source_file TEXT,
    asset_category TEXT DEFAULT 'Stocks',
    currency TEXT,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    trade_time TEXT,
    quantity DOUBLE PRECISION NOT NULL,
    t_price DOUBLE PRECISION,
    c_price DOUBLE PRECISION,
    proceeds DOUBLE PRECISION,
    comm_fee DOUBLE PRECISION,
    basis DOUBLE PRECISION,
    original_transaction_id TEXT UNIQUE,
    stock_splits_applied TEXT,
    updated_quantity DOUBLE PRECISION,
    updated_t_price DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS import_logs (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    import_date TIMESTAMPTZ DEFAULT NOW(),
    parsed INTEGER DEFAULT 0,
    inserted INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    status TEXT DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    id SERIAL PRIMARY KEY,
    sec_id TEXT NOT NULL,
    ca_type TEXT NOT NULL,
    ex_date TEXT,
    record_date TEXT,
    pay_date TEXT,
    declared_date TEXT,
    amount DOUBLE PRECISION,
    currency TEXT,
    split_ratio DOUBLE PRECISION,
    split_from DOUBLE PRECISION,
    split_to DOUBLE PRECISION,
    split_direction TEXT,
    dividend_type TEXT,
    frequency TEXT,
    adjusted INTEGER DEFAULT 1,
    source TEXT DEFAULT 'yfinance',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sec_id, ca_type, ex_date)
);

CREATE TABLE IF NOT EXISTS corporate_actions_status (
    sec_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('grey', 'green', 'orange')),
    last_fetched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS updated_transactions (
    id SERIAL PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    original_quantity DOUBLE PRECISION NOT NULL,
    original_price DOUBLE PRECISION NOT NULL,
    updated_quantity DOUBLE PRECISION NOT NULL,
    updated_price DOUBLE PRECISION NOT NULL,
    split_ratio DOUBLE PRECISION NOT NULL,
    ca_id INTEGER,
    ca_type TEXT NOT NULL,
    ca_date TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE,
    FOREIGN KEY (ca_id) REFERENCES corporate_actions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_transactions_trade_date ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_transactions_original_id ON transactions(original_transaction_id);
CREATE INDEX IF NOT EXISTS idx_import_logs_date ON import_logs(import_date);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_sec_id ON corporate_actions(sec_id);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_type ON corporate_actions(ca_type);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_ex_date ON corporate_actions(ex_date);
CREATE INDEX IF NOT EXISTS idx_updated_transactions_transaction_id ON updated_transactions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_updated_transactions_symbol ON updated_transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_updated_transactions_ca_id ON updated_transactions(ca_id);

CREATE OR REPLACE VIEW transactions_adjusted AS
SELECT
    t.transaction_id,
    t.symbol,
    t.trade_date,
    t.currency,
    t.asset_category,
    t.source_file,
    t.proceeds,
    t.comm_fee,
    t.basis,
    t.created_at,
    t.updated_at,
    COALESCE(ut.updated_quantity, t.quantity) AS quantity,
    COALESCE(ut.updated_price, t.t_price) AS t_price,
    t.quantity AS original_quantity,
    t.t_price AS original_price,
    CASE WHEN ut.transaction_id IS NOT NULL THEN 1 ELSE 0 END AS is_adjusted,
    ut.split_ratio,
    ut.ca_id,
    ut.ca_type,
    ut.ca_date
FROM transactions t
LEFT JOIN updated_transactions ut ON t.transaction_id = ut.transaction_id
WHERE t.symbol NOT LIKE '%.%';

CREATE TABLE IF NOT EXISTS positions_ibkr (
    symbol TEXT PRIMARY KEY,
    quantity DOUBLE PRECISION NOT NULL,
    cost_basis_money DOUBLE PRECISION,
    cost_basis_price DOUBLE PRECISION,
    mark_price DOUBLE PRECISION,
    position_value DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    currency TEXT,
    asset_category TEXT,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_positions_ibkr_symbol ON positions_ibkr(symbol);
```

- [ ] **Step 2: Sanity-check the file is well-formed**

Quick local syntax verification — Python doesn't ship a Postgres parser, but we can check no obvious issues:

```bash
grep -c "CREATE TABLE" backend/database/schema_pg_init.sql
```
Expected: 6 (transactions, import_logs, corporate_actions, corporate_actions_status, updated_transactions, positions_ibkr).

- [ ] **Step 3: Commit**

```bash
git add backend/database/schema_pg_init.sql
git commit -m "[STORY-M-4] feat: Postgres-flavored schema for first-time Supabase provisioning

Side-by-side with schema.sql (which stays SQLite-canonical for tests).
SERIAL PKs, TIMESTAMPTZ, DOUBLE PRECISION, CREATE OR REPLACE VIEW.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Data migration script

Reads every row from the live SQLite file and bulk-inserts into Postgres via `execute_values` for speed. Tables migrated in dependency order (parents before children).

**Files:**
- Create: `backend/scripts/migrate_sqlite_to_supabase.py`

- [ ] **Step 1: Write the script**

Create `backend/scripts/migrate_sqlite_to_supabase.py`:

```python
"""One-shot data migration: SQLite (output/database/finance.db) → Supabase Postgres.

Usage:
  export SUPABASE_DB_URL="postgresql://..."
  python3 backend/scripts/migrate_sqlite_to_supabase.py

Reads every row from the local SQLite file, batch-inserts into Postgres via
psycopg2.extras.execute_values, and verifies row counts after each table.

Idempotent on conflict — uses ON CONFLICT DO NOTHING so re-running won't
duplicate. Order matters because of foreign keys (updated_transactions
references transactions and corporate_actions).
"""
import os
import sqlite3
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

PROJECT_ROOT = Path(__file__).parent.parent.parent
SQLITE_PATH = PROJECT_ROOT / "output" / "database" / "finance.db"

# (table_name, conflict_column_or_None) — order respects FK deps
TABLES = [
    ("transactions", "transaction_id"),
    ("corporate_actions", None),  # composite UNIQUE — handled below
    ("corporate_actions_status", "sec_id"),
    ("updated_transactions", None),  # SERIAL PK; we strip 'id' on insert
    ("positions_ibkr", "symbol"),
    ("import_logs", None),  # SERIAL PK; we strip 'id'
]


def _get_columns(sqlite_conn, table: str) -> list[str]:
    """Return column names for a SQLite table in declared order."""
    cur = sqlite_conn.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def _quoted(name: str) -> str:
    """Quote identifier for Postgres."""
    return f'"{name}"'


def _build_insert(table: str, cols: list[str], conflict_col: str | None) -> str:
    col_list = ", ".join(_quoted(c) for c in cols)
    placeholders = "%s"  # execute_values handles the multi-row template
    sql = f"INSERT INTO {_quoted(table)} ({col_list}) VALUES %s"
    if conflict_col:
        sql += f" ON CONFLICT ({_quoted(conflict_col)}) DO NOTHING"
    elif table == "corporate_actions":
        sql += " ON CONFLICT (sec_id, ca_type, ex_date) DO NOTHING"
    elif table in ("updated_transactions", "import_logs"):
        # SERIAL PKs — let Postgres assign new IDs
        sql += " ON CONFLICT DO NOTHING"
    return sql


def migrate(sqlite_path: Path, pg_url: str) -> dict:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_path}")
    sconn = sqlite3.connect(str(sqlite_path))
    sconn.row_factory = sqlite3.Row
    pconn = psycopg2.connect(pg_url)

    summary: dict = {}
    try:
        for table, conflict_col in TABLES:
            cols = _get_columns(sconn, table)
            if not cols:
                summary[table] = {"skipped": "table not in SQLite"}
                continue
            # For SERIAL PK tables, drop the 'id' column so Postgres assigns
            insert_cols = [c for c in cols if not (c == "id" and table in ("updated_transactions", "import_logs"))]
            rows = sconn.execute(
                f"SELECT {', '.join(_quoted(c) for c in insert_cols)} FROM {_quoted(table)}"
            ).fetchall()
            data = [tuple(r[c] for c in insert_cols) for r in rows]

            with pconn.cursor() as cur:
                if data:
                    sql = _build_insert(table, insert_cols, conflict_col)
                    execute_values(cur, sql, data, page_size=500)
                cur.execute(f"SELECT COUNT(*) FROM {_quoted(table)}")
                pg_count = cur.fetchone()[0]
            pconn.commit()
            summary[table] = {"sqlite_rows": len(rows), "postgres_rows": pg_count}
            print(f"✅ {table}: copied {len(rows)} rows (Postgres now has {pg_count})")
    finally:
        sconn.close()
        pconn.close()
    return summary


if __name__ == "__main__":
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        print("ERROR: SUPABASE_DB_URL not set in environment", file=sys.stderr)
        sys.exit(1)
    summary = migrate(SQLITE_PATH, url)
    print("\n=== Migration summary ===")
    for table, info in summary.items():
        print(f"  {table}: {info}")
```

- [ ] **Step 2: Commit (script ready, won't run until Tasks 6-7)**

```bash
git add backend/scripts/migrate_sqlite_to_supabase.py
git commit -m "[STORY-M-5] feat: SQLite-to-Supabase data migration script

Reads every row from output/database/finance.db, batch-inserts via
psycopg2.execute_values to Postgres. Order respects FK deps. Strips
'id' column for SERIAL PK tables. ON CONFLICT DO NOTHING for idempotency.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Provision the Postgres schema on Supabase

Run-once: takes the schema we wrote in Task 4 and applies it to the Supabase project. Manual but bounded.

**Prerequisites:** Supabase project created, connection URL saved (see Pre-flight).

- [ ] **Step 1: Set the env var**

In your shell (NOT committed):
```bash
export SUPABASE_DB_URL="postgresql://postgres.xxx:yourpassword@aws-0-eu-west-X.pooler.supabase.com:6543/postgres"
```

Verify:
```bash
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -c "import os, psycopg2; psycopg2.connect(os.environ['SUPABASE_DB_URL']).close(); print('connection OK')"
```
Expected: `connection OK` (otherwise fix the connection string).

- [ ] **Step 2: Apply the schema**

Pipe the schema file directly into Postgres:
```bash
psql "$SUPABASE_DB_URL" -f backend/database/schema_pg_init.sql
```

Expected output: a series of `CREATE TABLE` / `CREATE INDEX` / `CREATE VIEW` notices (or "NOTICE: ... already exists" if idempotent reruns).

If `psql` is not installed on the Mac, use the Supabase web SQL Editor instead:
- Go to Supabase Dashboard → SQL Editor
- Paste the contents of `backend/database/schema_pg_init.sql`
- Click Run

- [ ] **Step 3: Verify tables exist**

```bash
psql "$SUPABASE_DB_URL" -c "\dt"
```

Expected: 6 tables listed: corporate_actions, corporate_actions_status, import_logs, positions_ibkr, transactions, updated_transactions. Plus the `transactions_adjusted` view (visible via `\dv`).

- [ ] **Step 4: No commit — this is environment-side, not code**

---

## Task 7: Run the data migration

- [ ] **Step 1: Confirm SUPABASE_DB_URL still set + migration script in place**

```bash
echo "${SUPABASE_DB_URL:-NOT SET}" | head -c 30
ls -l backend/scripts/migrate_sqlite_to_supabase.py
```

- [ ] **Step 2: Run the migration**

```bash
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 backend/scripts/migrate_sqlite_to_supabase.py
```

Expected output:
```
✅ transactions: copied 587 rows (Postgres now has 587)
✅ corporate_actions: copied 209 rows (Postgres now has 209)
✅ corporate_actions_status: copied X rows (Postgres now has X)
✅ updated_transactions: copied 25 rows (Postgres now has 25)
✅ positions_ibkr: copied 14 rows (Postgres now has 14)
✅ import_logs: copied X rows (Postgres now has X)
```

If counts mismatch (e.g., source has 587 but Postgres ends with 580), re-running the script is safe (ON CONFLICT DO NOTHING). Diagnose any leftover diff before proceeding.

- [ ] **Step 3: Spot-check via psql**

```bash
psql "$SUPABASE_DB_URL" -c "SELECT symbol, quantity FROM positions_ibkr ORDER BY symbol LIMIT 5"
```
Expected: your 5 alphabetically-first positions. Sanity check that types didn't get mangled (numbers should be numbers, no strange casts).

---

## Task 8: Switch the live API to Supabase

- [ ] **Step 1: Add SUPABASE_DB_URL to the live `.env`**

Edit `.env` (NOT `.env.example`) and add:

```
SUPABASE_DB_URL=postgresql://postgres.xxx:yourpassword@aws-0-eu-west-X.pooler.supabase.com:6543/postgres
```

(The actual URL you saved in pre-flight.)

- [ ] **Step 2: Restart the backend**

```bash
lsof -ti:8000 | xargs kill -9 2>/dev/null; sleep 1
cd /Users/louisgarnier/Claude/Stocks
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m uvicorn backend.api.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 3
```

- [ ] **Step 3: Smoke test all major endpoints**

```bash
echo "--- /health ---"
curl -s http://localhost:8000/health | python3 -m json.tool

echo "--- /api/positions (should show 14 positions) ---"
curl -s http://localhost:8000/api/positions | python3 -c "import json,sys; d=json.load(sys.stdin); print('count:', d['summary']['total_positions'])"

echo "--- /api/transactions (paginated) ---"
curl -s "http://localhost:8000/api/transactions?limit=3" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'], 'returned:', len(d['data']))"

echo "--- /api/corporate-actions ---"
curl -s "http://localhost:8000/api/corporate-actions?limit=3" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"

echo "--- /api/transactions/import-logs ---"
curl -s http://localhost:8000/api/transactions/import-logs | python3 -c "import json,sys; d=json.load(sys.stdin); print('logs:', d['total'])"
```

Expected: each endpoint returns the same row counts you saw on SQLite. If any endpoint 500s, check `/tmp/uvicorn.log` for the failing SQL — most common issue is a SQLite-specific function (e.g., `json_each` syntax, `datetime('now')` calls).

- [ ] **Step 4: Hit the frontend**

Open http://localhost:3000 in browser. Click through each tab. Confirm Positions / Transactions / Configuration all populate.

- [ ] **Step 5: Don't commit yet** — environment change, code is unchanged

---

## Task 9: Mark complete + push

- [ ] **Step 1: Update build log**

Append to `docs/project/config/build-log.md`:

```
2026-04-28 — Story M complete: migrated live database from SQLite to Supabase Postgres.
- Engine-aware connection layer (SQLite for tests, Postgres for live API)
- Portable SQL: ON CONFLICT instead of INSERT OR IGNORE/REPLACE
- One-shot migration script (backend/scripts/migrate_sqlite_to_supabase.py)
- All 7 tables + view migrated, row counts verified
- Live API now reads/writes against Supabase
- Tests still on SQLite (fast, hermetic)
```

- [ ] **Step 2: Commit + push**

```bash
git add docs/project/config/build-log.md
git commit -m "[STORY-M-9] docs: mark Story M complete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin newstart
```

---

## Out of Scope

Tracked but explicitly NOT in Story M:
- **Migrating the test fixture to Postgres.** Tests stay on SQLite for speed. If divergence bites later, revisit.
- **Setting up Supabase row-level security (RLS).** Single-user access via service role; authentication for multi-user is a future story.
- **Realtime subscriptions** on tables (e.g., live position updates). Future feature.
- **Frontend → Supabase direct access.** Frontend talks to FastAPI today; that pattern stays.
- **Dropping the local `output/database/finance.db` file.** Keep it as backup post-migration. Delete only when comfortable.

---

## Self-Review Notes

- **Spec coverage:** Engine switch ✅ (Task 2), portable SQL ✅ (Task 3), Postgres schema ✅ (Task 4), migration script ✅ (Task 5), provisioning ✅ (Task 6), data migration ✅ (Task 7), live API switch ✅ (Task 8), build log ✅ (Task 9). Manual pre-flight (Supabase project creation) called out at the top.

- **Placeholder scan:** All steps have either runnable code/commands or clearly-marked manual interactions (Supabase Dashboard). Task 3's "list any others" caveat is bounded — the grep command produces an exact list.

- **Type consistency:** `get_db_connection`, `_pg_connect`, `_PgConnectionWrapper`, `migrate(sqlite_path, pg_url)` all referenced consistently. `SUPABASE_DB_URL` env var name same across all tasks. Tables migrated in FK order (`transactions` before `updated_transactions`).
