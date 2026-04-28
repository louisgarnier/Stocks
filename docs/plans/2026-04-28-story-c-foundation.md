# Story C — Foundation (Universe + Market Data + Design System) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lay the foundation for the Tech Analysis tab: install Tailwind + shadcn/ui design system, build a `tracked_universe` table with auto-seeders for index lists (S&P 500, CAC 40) and a manual-add slot, port `b_grab_histo_data_up.py` as a scoped batched yfinance ingestion service writing to a new `market_data` table.

**Architecture:** Three tightly-coupled subsystems shipped together because Story D (indicators) depends on all three. (1) Frontend gets a real component library — shadcn/ui on Tailwind v4. New UI built with these components; existing inline-styled tabs migrate as touched in later stories. (2) The universe is a single SQLite table with a JSON `sources` column allowing the same symbol to belong to multiple lists; index lists are toggleable in the Configuration tab; manual tickers persist independent of index refreshes. (3) Market data ingestion runs as an explicit sync step (no auto-scheduling) — yfinance batched download for performance, idempotent INSERT OR IGNORE keyed on `(symbol, time)`.

**Tech Stack:** Next.js 16 + React 19 + Tailwind CSS v4 + shadcn/ui + lucide-react + class-variance-authority + tailwind-merge. Backend: FastAPI + SQLite + yfinance + pandas. Tests: pytest with FastAPI TestClient and the existing `temp_db` fixture, monkeypatching yfinance for hermeticity.

---

## File Structure

**Create:**
- `frontend/postcss.config.mjs` — Tailwind v4 PostCSS plugin
- `frontend/lib/utils.ts` — shadcn `cn()` helper
- `frontend/components.json` — shadcn config (paths, style, baseColor)
- `frontend/components/ui/*.tsx` — shadcn-generated components (Button, Card, Dialog, Table, Tabs, Badge, Input, Select, Switch, Sonner)
- `backend/api/routes/universe.py` — universe CRUD + index toggle/refresh endpoints
- `backend/api/routes/market_data.py` — market data query endpoint (used later by Story D's indicators)
- `backend/scripts/universe_seeders.py` — Wikipedia scrapers for index member lists
- `backend/scripts/market_data_ingestor.py` — yfinance batched downloader → `market_data` table
- `backend/tests/test_universe_routes.py`
- `backend/tests/test_market_data_routes.py`
- `backend/tests/test_universe_seeders.py`
- `backend/tests/test_market_data_ingestor.py`

**Modify:**
- `frontend/app/globals.css` — migrate to Tailwind v4 syntax (`@import "tailwindcss"`), add `@theme inline` design tokens
- `frontend/package.json` — add deps: `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `@radix-ui/*` (auto-added by shadcn), `sonner`
- `frontend/tsconfig.json` — add `paths` alias `"@/*": ["./*"]` for shadcn
- `frontend/app/page.tsx` — replace the Configuration tab content with a shadcn-built Universe + Market Data section
- `backend/database/schema.sql` — add `tracked_universe`, `tracked_indices`, `market_data` tables
- `backend/api/main.py` — register `universe_router` and `market_data_router`
- `backend/api/routes/sync.py` — add a "universe" step before "transactions" so IBKR holdings auto-flow into the universe

**Delete:** none.

---

## Task 1: Install design system (Tailwind v4 + shadcn/ui)

This is a one-shot bootstrap, not TDD. The "test" is that the dev server compiles and a sample shadcn `<Button>` renders.

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/tsconfig.json`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/lib/utils.ts`
- Create: `frontend/components.json`
- Modify: `frontend/package.json` (via npm install)

- [ ] **Step 1: Install runtime deps**

Run from project root:
```bash
cd frontend && npm install class-variance-authority clsx tailwind-merge lucide-react sonner @radix-ui/react-slot @radix-ui/react-dialog @radix-ui/react-tabs @radix-ui/react-select @radix-ui/react-switch @radix-ui/react-label
```

Expected: deps added to `package.json`, no errors.

- [ ] **Step 2: Migrate globals.css to Tailwind v4 syntax + add theme tokens**

Overwrite `frontend/app/globals.css` with:

```css
@import "tailwindcss";

@theme inline {
  --color-background: oklch(0.99 0 0);
  --color-foreground: oklch(0.15 0.02 250);
  --color-card: oklch(1 0 0);
  --color-card-foreground: oklch(0.15 0.02 250);
  --color-primary: oklch(0.55 0.22 260);
  --color-primary-foreground: oklch(0.98 0 0);
  --color-secondary: oklch(0.96 0.01 250);
  --color-secondary-foreground: oklch(0.20 0.02 250);
  --color-muted: oklch(0.96 0.01 250);
  --color-muted-foreground: oklch(0.55 0.02 250);
  --color-accent: oklch(0.93 0.02 250);
  --color-accent-foreground: oklch(0.20 0.02 250);
  --color-destructive: oklch(0.62 0.22 30);
  --color-success: oklch(0.62 0.18 145);
  --color-warning: oklch(0.78 0.16 75);
  --color-border: oklch(0.92 0 0);
  --color-input: oklch(0.92 0 0);
  --color-ring: oklch(0.55 0.22 260);
  --radius: 0.5rem;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Consolas, monospace;
}

* {
  border-color: var(--color-border);
}

body {
  background: var(--color-background);
  color: var(--color-foreground);
  font-feature-settings: "rlig" 1, "calt" 1;
}

/* Tabular numerals for prices/percentages */
.tabular-nums {
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 3: Create PostCSS config**

Create `frontend/postcss.config.mjs`:

```js
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
export default config;
```

Then install the PostCSS plugin: `cd frontend && npm install -D @tailwindcss/postcss`

- [ ] **Step 4: Create cn() helper**

Create `frontend/lib/utils.ts`:

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 5: Add path alias**

In `frontend/tsconfig.json`, add to `compilerOptions`:

```json
"paths": {
  "@/*": ["./*"]
}
```

(Append to the existing `compilerOptions` block; preserve other keys.)

- [ ] **Step 6: Create shadcn config**

Create `frontend/components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

- [ ] **Step 7: Install initial shadcn components**

```bash
cd frontend && npx shadcn@latest add button card input label badge table dialog tabs select switch sonner
```

Answer "yes" to any TypeScript or alias prompts. Files land in `frontend/components/ui/`.

- [ ] **Step 8: Verify the dev server compiles cleanly**

Restart the frontend dev server:
```bash
lsof -ti:3000 | xargs kill -9 2>/dev/null; cd /Users/louisgarnier/Claude/Stocks/frontend && npm run dev
```

Then in another terminal: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/`
Expected: 200.

Open http://localhost:3000/ in a browser — the existing UI should still render (we didn't change page content). Confirm no Tailwind/shadcn-related errors in the dev server log (`/tmp/next.log`).

- [ ] **Step 9: Commit**

```bash
cd /Users/louisgarnier/Claude/Stocks && git add frontend/
git commit -m "[STORY-C-1] feat: install Tailwind v4 + shadcn/ui design system

- Migrate globals.css to Tailwind v4 (@import + @theme inline tokens)
- Add postcss.config.mjs, lib/utils.ts (cn helper), components.json
- tsconfig path alias @/*
- Install initial shadcn components: button, card, input, label,
  badge, table, dialog, tabs, select, switch, sonner

Foundation for upcoming UI work. Existing inline-styled tabs migrate
as touched in later stories.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Schema — `tracked_universe`, `tracked_indices`, `market_data` tables

**Files:**
- Modify: `backend/database/schema.sql`
- Test: `backend/tests/test_universe_routes.py` (created here, more added later)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_universe_routes.py`:

```python
"""Tests for universe + market_data tables and routes."""
import sqlite3


def test_universe_schema_has_tracked_universe(temp_db):
    """The schema must create a tracked_universe table with required columns."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_universe'")
    assert cur.fetchone() is not None, "tracked_universe table missing"

    cur.execute("PRAGMA table_info(tracked_universe)")
    cols = {r[1] for r in cur.fetchall()}
    expected = {"symbol", "name", "sector", "currency", "exchange", "benchmark",
                "sources", "enabled", "added_at", "last_synced_at"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"
    conn.close()


def test_universe_schema_has_tracked_indices(temp_db):
    """tracked_indices table must exist."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_indices'")
    assert cur.fetchone() is not None
    cur.execute("PRAGMA table_info(tracked_indices)")
    cols = {r[1] for r in cur.fetchall()}
    expected = {"name", "enabled", "last_refreshed_at", "symbol_count"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"
    conn.close()


def test_market_data_schema(temp_db):
    """market_data table must exist with PK (symbol, time)."""
    conn = sqlite3.connect(str(temp_db))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='market_data'")
    assert cur.fetchone() is not None
    cur.execute("PRAGMA table_info(market_data)")
    rows = cur.fetchall()
    cols = {r[1] for r in rows}
    expected = {"symbol", "time", "open", "high", "low", "close", "adj_close", "volume"}
    missing = expected - cols
    assert not missing, f"missing columns: {missing}"
    pk_cols = sorted([r[1] for r in rows if r[5] > 0])
    assert pk_cols == ["symbol", "time"], f"expected composite PK (symbol, time), got {pk_cols}"
    conn.close()
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_routes.py -v`
Expected: 3 failures with "tracked_universe table missing" / "tracked_indices table missing" / "market_data table missing".

- [ ] **Step 3: Add the three tables to schema.sql**

Append to `backend/database/schema.sql` (after the existing `positions_ibkr` index block):

```sql
-- Tracked universe — symbols we ingest market data for
CREATE TABLE IF NOT EXISTS tracked_universe (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    currency TEXT,
    exchange TEXT,
    benchmark TEXT,
    sources TEXT NOT NULL DEFAULT '[]',  -- JSON array, e.g. ["sp500", "ibkr_position"]
    enabled INTEGER NOT NULL DEFAULT 1,
    added_at TIMESTAMP NOT NULL,
    last_synced_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tracked_universe_enabled ON tracked_universe(enabled);

-- Index list metadata — e.g., S&P 500 enable/disable + last refresh
CREATE TABLE IF NOT EXISTS tracked_indices (
    name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    last_refreshed_at TIMESTAMP,
    symbol_count INTEGER DEFAULT 0
);

-- Market OHLCV data — one row per symbol per day
CREATE TABLE IF NOT EXISTS market_data (
    symbol TEXT NOT NULL,
    time TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adj_close REAL,
    volume INTEGER,
    PRIMARY KEY (symbol, time)
);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_time ON market_data(time);
```

- [ ] **Step 4: Run tests, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_routes.py -v`
Expected: 3 passed.

- [ ] **Step 5: Apply schema to the live DB**

Apply additions to the production DB:
```bash
sqlite3 output/database/finance.db < backend/database/schema.sql
sqlite3 output/database/finance.db ".schema tracked_universe"
```
Expected: shows the new CREATE TABLE statement.

- [ ] **Step 6: Commit**

```bash
git add backend/database/schema.sql backend/tests/test_universe_routes.py
git commit -m "[STORY-C-2] feat: add tracked_universe / tracked_indices / market_data tables

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Universe CRUD endpoints

**Files:**
- Create: `backend/api/routes/universe.py`
- Modify: `backend/api/main.py`
- Test: `backend/tests/test_universe_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_universe_routes.py`:

```python
import json
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_universe_empty(temp_db):
    """GET /api/universe returns an empty list when nothing is tracked."""
    resp = client.get("/api/universe")
    assert resp.status_code == 200
    assert resp.json() == {"symbols": [], "count": 0}


def test_add_manual_symbol(temp_db):
    """POST /api/universe/manual creates a manual entry."""
    resp = client.post("/api/universe/manual", json={"symbol": "TSLA"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["symbol"]["symbol"] == "TSLA"
    assert "manual" in body["symbol"]["sources"]


def test_add_manual_symbol_uppercases(temp_db):
    """Manual symbols are normalized to uppercase."""
    resp = client.post("/api/universe/manual", json={"symbol": "tsla"})
    assert resp.status_code == 200
    assert resp.json()["symbol"]["symbol"] == "TSLA"


def test_add_manual_symbol_idempotent(temp_db):
    """Adding the same manual symbol twice is a no-op."""
    client.post("/api/universe/manual", json={"symbol": "TSLA"})
    resp = client.post("/api/universe/manual", json={"symbol": "TSLA"})
    assert resp.status_code == 200
    # Should not have duplicates
    list_resp = client.get("/api/universe")
    syms = [s["symbol"] for s in list_resp.json()["symbols"]]
    assert syms.count("TSLA") == 1


def test_remove_manual_symbol(temp_db):
    """DELETE /api/universe/manual/{symbol} removes manual contribution.
    If symbol came only from 'manual', the row is deleted.
    """
    client.post("/api/universe/manual", json={"symbol": "TSLA"})
    resp = client.delete("/api/universe/manual/TSLA")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    list_resp = client.get("/api/universe")
    assert list_resp.json()["count"] == 0


def test_remove_manual_keeps_row_if_other_sources(temp_db):
    """If symbol exists from sp500 AND manual, removing 'manual' leaves the row with just sp500."""
    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('TSLA', '[\"sp500\", \"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    resp = client.delete("/api/universe/manual/TSLA")
    assert resp.status_code == 200
    list_resp = client.get("/api/universe")
    body = list_resp.json()
    assert body["count"] == 1
    assert body["symbols"][0]["sources"] == ["sp500"]


def test_list_indices(temp_db):
    """GET /api/universe/indices returns the seeded index list."""
    resp = client.get("/api/universe/indices")
    assert resp.status_code == 200
    body = resp.json()
    names = {idx["name"] for idx in body["indices"]}
    assert "sp500" in names
    assert "cac40" in names


def test_toggle_index(temp_db):
    """POST /api/universe/indices/{name}/toggle flips the enabled flag."""
    resp = client.post("/api/universe/indices/sp500/toggle")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    resp = client.post("/api/universe/indices/sp500/toggle")
    assert resp.json()["enabled"] is False
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_routes.py::test_get_universe_empty -v`
Expected: FAIL with 404 (route does not exist).

- [ ] **Step 3: Implement the universe router**

Create `backend/api/routes/universe.py`:

```python
"""Universe management routes — tracked symbols and index lists."""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/universe", tags=["universe"])

KNOWN_INDICES = ["sp500", "cac40", "nasdaq100", "dow30", "dax40", "ftse100"]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _ensure_indices_seeded(conn) -> None:
    """Populate tracked_indices with known names if missing (idempotent)."""
    for name in KNOWN_INDICES:
        conn.execute(
            "INSERT OR IGNORE INTO tracked_indices (name, enabled) VALUES (?, 0)",
            (name,),
        )
    conn.commit()


def _row_to_dict(row) -> dict:
    return {
        "symbol": row[0],
        "name": row[1],
        "sector": row[2],
        "currency": row[3],
        "exchange": row[4],
        "benchmark": row[5],
        "sources": json.loads(row[6] or "[]"),
        "enabled": bool(row[7]),
        "added_at": row[8],
        "last_synced_at": row[9],
    }


class ManualSymbolRequest(BaseModel):
    symbol: str


@router.get("")
async def list_universe():
    """Return all tracked symbols."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT symbol, name, sector, currency, exchange, benchmark, sources, "
        "enabled, added_at, last_synced_at FROM tracked_universe "
        "WHERE enabled=1 ORDER BY symbol"
    ).fetchall()
    conn.close()
    symbols = [_row_to_dict(r) for r in rows]
    return {"symbols": symbols, "count": len(symbols)}


@router.post("/manual")
async def add_manual_symbol(req: ManualSymbolRequest):
    """Add a symbol with source='manual'. Merges if symbol already exists from another source."""
    sym = req.symbol.strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="symbol required")

    conn = get_db_connection()
    row = conn.execute(
        "SELECT sources FROM tracked_universe WHERE symbol = ?", (sym,)
    ).fetchone()
    if row:
        sources = json.loads(row[0] or "[]")
        if "manual" not in sources:
            sources.append("manual")
            conn.execute(
                "UPDATE tracked_universe SET sources = ?, enabled = 1 WHERE symbol = ?",
                (json.dumps(sources), sym),
            )
    else:
        conn.execute(
            "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) VALUES (?, ?, 1, ?)",
            (sym, json.dumps(["manual"]), _now_iso()),
        )
    conn.commit()
    full = conn.execute(
        "SELECT symbol, name, sector, currency, exchange, benchmark, sources, "
        "enabled, added_at, last_synced_at FROM tracked_universe WHERE symbol = ?",
        (sym,),
    ).fetchone()
    conn.close()
    return {"success": True, "symbol": _row_to_dict(full)}


@router.delete("/manual/{symbol}")
async def remove_manual_symbol(symbol: str):
    """Remove the 'manual' tag from a symbol. If 'manual' was the only source, delete the row."""
    sym = symbol.upper()
    conn = get_db_connection()
    row = conn.execute(
        "SELECT sources FROM tracked_universe WHERE symbol = ?", (sym,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"{sym} not in universe")
    sources = [s for s in json.loads(row[0] or "[]") if s != "manual"]
    if not sources:
        conn.execute("DELETE FROM tracked_universe WHERE symbol = ?", (sym,))
    else:
        conn.execute(
            "UPDATE tracked_universe SET sources = ? WHERE symbol = ?",
            (json.dumps(sources), sym),
        )
    conn.commit()
    conn.close()
    return {"success": True, "symbol": sym, "remaining_sources": sources}


@router.get("/indices")
async def list_indices():
    """Return all known indices with enabled flag and metadata."""
    conn = get_db_connection()
    _ensure_indices_seeded(conn)
    rows = conn.execute(
        "SELECT name, enabled, last_refreshed_at, symbol_count FROM tracked_indices ORDER BY name"
    ).fetchall()
    conn.close()
    return {
        "indices": [
            {"name": r[0], "enabled": bool(r[1]), "last_refreshed_at": r[2], "symbol_count": r[3]}
            for r in rows
        ]
    }


@router.post("/indices/{name}/toggle")
async def toggle_index(name: str):
    """Flip enabled flag for an index. (Refreshing the symbol list is a separate endpoint.)"""
    if name not in KNOWN_INDICES:
        raise HTTPException(status_code=404, detail=f"unknown index: {name}")
    conn = get_db_connection()
    _ensure_indices_seeded(conn)
    row = conn.execute("SELECT enabled FROM tracked_indices WHERE name = ?", (name,)).fetchone()
    new_val = 0 if row[0] else 1
    conn.execute("UPDATE tracked_indices SET enabled = ? WHERE name = ?", (new_val, name))
    conn.commit()
    conn.close()
    return {"name": name, "enabled": bool(new_val)}
```

- [ ] **Step 4: Register the router**

In `backend/api/main.py`, add after the `sync_router` import:

```python
from backend.api.routes.universe import router as universe_router
```

And after `app.include_router(sync_router)`:

```python
app.include_router(universe_router)
```

- [ ] **Step 5: Run the universe-route tests, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_routes.py -v`
Expected: all 11 tests (3 schema + 8 route) pass.

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/universe.py backend/api/main.py backend/tests/test_universe_routes.py
git commit -m "[STORY-C-3] feat: universe CRUD endpoints (manual symbols + index toggle)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: S&P 500 + CAC 40 seeders (Wikipedia-based)

Both indices in one task because they share the scraping shape (`pd.read_html` of a Wikipedia table). Other indices can be added later by following the same pattern.

**Files:**
- Create: `backend/scripts/universe_seeders.py`
- Test: `backend/tests/test_universe_seeders.py`
- Modify: `backend/api/routes/universe.py` — add `POST /indices/{name}/refresh`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_universe_seeders.py`:

```python
"""Tests for index list seeders."""
import json
from unittest.mock import patch

import pandas as pd

from backend.scripts.universe_seeders import seed_index


def _fake_sp500_table():
    """Return a DataFrame mimicking what pd.read_html returns for the S&P 500 Wikipedia page."""
    return pd.DataFrame({
        "Symbol": ["AAPL", "MSFT", "NVDA"],
        "Security": ["Apple Inc.", "Microsoft Corp.", "NVIDIA Corp."],
        "GICS Sector": ["Information Technology", "Information Technology", "Information Technology"],
    })


def _fake_cac40_table():
    return pd.DataFrame({
        "Ticker": ["MC.PA", "AIR.PA"],
        "Company": ["LVMH", "Airbus"],
        "Sector": ["Consumer", "Industrials"],
    })


def test_seed_sp500_inserts_rows(temp_db, monkeypatch):
    """seed_index('sp500') populates tracked_universe with sources=['sp500']."""
    import backend.scripts.universe_seeders as seeders
    monkeypatch.setattr(seeders, "_fetch_sp500_dataframe", lambda: _fake_sp500_table())

    result = seed_index("sp500")
    assert result["inserted"] == 3
    assert result["count"] == 3

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT symbol, name, sector, currency, sources FROM tracked_universe ORDER BY symbol"
    ).fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["AAPL", "MSFT", "NVDA"]
    assert rows[0][1] == "Apple Inc."
    assert rows[0][2] == "Information Technology"
    assert rows[0][3] == "USD"
    assert json.loads(rows[0][4]) == ["sp500"]


def test_seed_sp500_idempotent_merges_sources(temp_db, monkeypatch):
    """If a symbol is already in tracked_universe with another source, seeding adds 'sp500' to sources."""
    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    import backend.scripts.universe_seeders as seeders
    monkeypatch.setattr(seeders, "_fetch_sp500_dataframe", lambda: _fake_sp500_table())
    seed_index("sp500")

    conn = sqlite3.connect(str(temp_db))
    sources = conn.execute("SELECT sources FROM tracked_universe WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert set(json.loads(sources)) == {"manual", "sp500"}


def test_seed_cac40(temp_db, monkeypatch):
    import backend.scripts.universe_seeders as seeders
    monkeypatch.setattr(seeders, "_fetch_cac40_dataframe", lambda: _fake_cac40_table())

    result = seed_index("cac40")
    assert result["inserted"] == 2

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    row = conn.execute("SELECT currency, benchmark FROM tracked_universe WHERE symbol='MC.PA'").fetchone()
    conn.close()
    assert row[0] == "EUR"
    assert row[1] == "^FCHI"


def test_seed_unknown_index_raises(temp_db):
    import pytest
    with pytest.raises(ValueError, match="unknown index"):
        seed_index("ftse101")
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_seeders.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.scripts.universe_seeders'`.

- [ ] **Step 3: Implement the seeders**

Create `backend/scripts/universe_seeders.py`:

```python
"""Wikipedia-based index list seeders for tracked_universe."""
import json
from datetime import datetime
from typing import Callable

import pandas as pd

from backend.database.connection import get_db_connection

# Each index: { name: (currency, benchmark, fetcher) }
# Benchmark is the symbol used as denominator for Mansfield Relative Strength (Story D).
_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CAC40_URL = "https://en.wikipedia.org/wiki/CAC_40"


def _fetch_sp500_dataframe() -> pd.DataFrame:
    """Pull the S&P 500 constituents table from Wikipedia. Returns a DataFrame with at least columns Symbol, Security, GICS Sector."""
    tables = pd.read_html(_SP500_URL)
    # First table on that page is constituents
    df = tables[0]
    # Wikipedia sometimes uses "Symbol" or "Ticker symbol"
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    df = df.rename(columns={col: "Symbol"})
    # Some tickers like BRK.B come with a period that yfinance accepts as BRK-B
    df["Symbol"] = df["Symbol"].astype(str).str.replace(".", "-", regex=False)
    return df


def _fetch_cac40_dataframe() -> pd.DataFrame:
    """Pull the CAC 40 constituents table from Wikipedia."""
    tables = pd.read_html(_CAC40_URL)
    # Find the table with a Ticker column (Wikipedia table order varies)
    for t in tables:
        if "Ticker" in t.columns:
            return t
    raise RuntimeError("Could not find CAC 40 ticker table on Wikipedia")


_INDEX_CONFIG = {
    "sp500": {
        "currency": "USD",
        "benchmark": "^GSPC",
        "fetcher": _fetch_sp500_dataframe,
        "symbol_col": "Symbol",
        "name_col": "Security",
        "sector_col": "GICS Sector",
    },
    "cac40": {
        "currency": "EUR",
        "benchmark": "^FCHI",
        "fetcher": _fetch_cac40_dataframe,
        "symbol_col": "Ticker",
        "name_col": "Company",
        "sector_col": "Sector",
    },
}


def seed_index(index_name: str) -> dict:
    """Fetch the index member list and upsert into tracked_universe.

    For each member: if symbol already exists, append index_name to its sources
    array (idempotent). Else create a new row with sources=[index_name].

    Returns: {"index": str, "inserted": int, "updated": int, "count": int}
    """
    if index_name not in _INDEX_CONFIG:
        raise ValueError(f"unknown index: {index_name}")
    cfg = _INDEX_CONFIG[index_name]
    df = cfg["fetcher"]()

    conn = get_db_connection()
    inserted = 0
    updated = 0
    now = datetime.now().astimezone().isoformat()

    for _, row in df.iterrows():
        sym = str(row[cfg["symbol_col"]]).strip().upper()
        if not sym or sym == "NAN":
            continue
        name = str(row.get(cfg["name_col"], "")) if cfg["name_col"] in row else None
        sector = str(row.get(cfg["sector_col"], "")) if cfg["sector_col"] in row else None
        existing = conn.execute(
            "SELECT sources FROM tracked_universe WHERE symbol = ?", (sym,)
        ).fetchone()
        if existing:
            sources = json.loads(existing[0] or "[]")
            if index_name not in sources:
                sources.append(index_name)
                conn.execute(
                    "UPDATE tracked_universe SET sources = ?, sector = COALESCE(sector, ?), "
                    "name = COALESCE(name, ?) WHERE symbol = ?",
                    (json.dumps(sources), sector, name, sym),
                )
                updated += 1
        else:
            conn.execute(
                "INSERT INTO tracked_universe "
                "(symbol, name, sector, currency, benchmark, sources, enabled, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (sym, name, sector, cfg["currency"], cfg["benchmark"],
                 json.dumps([index_name]), now),
            )
            inserted += 1

    # Update tracked_indices metadata
    cnt = conn.execute(
        "SELECT COUNT(*) FROM tracked_universe WHERE sources LIKE ?",
        (f'%"{index_name}"%',),
    ).fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO tracked_indices (name, enabled, last_refreshed_at, symbol_count) "
        "VALUES (?, COALESCE((SELECT enabled FROM tracked_indices WHERE name=?), 1), ?, ?)",
        (index_name, index_name, now, cnt),
    )
    conn.commit()
    conn.close()
    return {"index": index_name, "inserted": inserted, "updated": updated, "count": cnt}
```

- [ ] **Step 4: Add the refresh endpoint**

In `backend/api/routes/universe.py`, append:

```python
@router.post("/indices/{name}/refresh")
async def refresh_index(name: str):
    """Re-fetch the index member list from its source and upsert into tracked_universe."""
    from backend.scripts.universe_seeders import seed_index, _INDEX_CONFIG
    if name not in _INDEX_CONFIG:
        raise HTTPException(status_code=404, detail=f"unknown index: {name}")
    try:
        result = seed_index(name)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ refresh_index({name}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 5: Run tests, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_universe_seeders.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/universe_seeders.py backend/api/routes/universe.py backend/tests/test_universe_seeders.py
git commit -m "[STORY-C-4] feat: S&P 500 + CAC 40 seeders + refresh endpoint

Wikipedia-scraped via pandas.read_html. Idempotent: existing symbols
get their sources array appended; new symbols get inserted with
currency + benchmark assigned by index. Refresh endpoint at
POST /api/universe/indices/{name}/refresh.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: IBKR positions auto-sync into universe

When IBKR positions arrive via `/api/sync/positions` or `/api/sync/full`, every held symbol should auto-flow into `tracked_universe` with source `ibkr_position`. If sold (no longer in `positions_ibkr`), the `ibkr_position` source is removed; if no other source remains, the symbol is dropped from the universe.

**Files:**
- Modify: `backend/api/routes/sync.py`
- Test: `backend/tests/test_sync_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_sync_routes.py`:

```python
def test_sync_positions_adds_held_symbols_to_universe(temp_db, stub_flex_http, monkeypatch):
    """After /api/sync/positions, every symbol in positions_ibkr is also in tracked_universe with source 'ibkr_position'."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/positions")
    assert resp.status_code == 200

    import json as _json
    conn = sqlite3.connect(str(temp_db))
    row = conn.execute(
        "SELECT sources FROM tracked_universe WHERE symbol = 'TEST'"
    ).fetchone()
    conn.close()
    assert row is not None, "TEST symbol should be auto-added to tracked_universe"
    assert "ibkr_position" in _json.loads(row[0])


def test_sold_position_removes_ibkr_source(temp_db):
    """If a symbol previously had source 'ibkr_position' but is no longer in positions_ibkr, the source is removed."""
    import json as _json
    from backend.api.routes.sync import _sync_positions_to_universe

    conn = sqlite3.connect(str(temp_db))
    # Universe has FOO from a prior sync, but it's no longer in positions_ibkr
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('FOO', '[\"ibkr_position\"]', 1, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('BAR', '[\"sp500\", \"ibkr_position\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    _sync_positions_to_universe()

    conn = sqlite3.connect(str(temp_db))
    foo = conn.execute("SELECT sources FROM tracked_universe WHERE symbol = 'FOO'").fetchone()
    bar = conn.execute("SELECT sources FROM tracked_universe WHERE symbol = 'BAR'").fetchone()
    conn.close()
    assert foo is None, "FOO had only ibkr_position; should be deleted now that no longer held"
    assert bar is not None and _json.loads(bar[0]) == ["sp500"], "BAR retains sp500 source"
```

- [ ] **Step 2: Run, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_positions_adds_held_symbols_to_universe backend/tests/test_sync_routes.py::test_sold_position_removes_ibkr_source -v`
Expected: ImportError on `_sync_positions_to_universe`.

- [ ] **Step 3: Implement the helper and call it**

In `backend/api/routes/sync.py`, add this helper near `_flag_orange`:

```python
def _sync_positions_to_universe() -> None:
    """Reconcile positions_ibkr with tracked_universe.

    For every symbol currently in positions_ibkr: ensure 'ibkr_position' is in
    its sources array (creating the row if missing).
    For every symbol in tracked_universe with 'ibkr_position' but NOT in
    positions_ibkr: remove 'ibkr_position' from sources, and delete the row
    if that was its only source.
    """
    import json as _json
    conn = get_db_connection()
    held = {r[0] for r in conn.execute("SELECT symbol FROM positions_ibkr").fetchall()}

    # Add held symbols to universe
    now = datetime.now().astimezone().isoformat()
    for sym in held:
        existing = conn.execute(
            "SELECT sources FROM tracked_universe WHERE symbol = ?", (sym,)
        ).fetchone()
        if existing:
            sources = _json.loads(existing[0] or "[]")
            if "ibkr_position" not in sources:
                sources.append("ibkr_position")
                conn.execute(
                    "UPDATE tracked_universe SET sources = ?, enabled = 1 WHERE symbol = ?",
                    (_json.dumps(sources), sym),
                )
        else:
            conn.execute(
                "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
                "VALUES (?, ?, 1, ?)",
                (sym, _json.dumps(["ibkr_position"]), now),
            )

    # Remove ibkr_position from sold-out symbols
    rows = conn.execute(
        "SELECT symbol, sources FROM tracked_universe WHERE sources LIKE '%ibkr_position%'"
    ).fetchall()
    for sym, sources_json in rows:
        if sym in held:
            continue
        sources = [s for s in _json.loads(sources_json or "[]") if s != "ibkr_position"]
        if not sources:
            conn.execute("DELETE FROM tracked_universe WHERE symbol = ?", (sym,))
        else:
            conn.execute(
                "UPDATE tracked_universe SET sources = ? WHERE symbol = ?",
                (_json.dumps(sources), sym),
            )

    conn.commit()
    conn.close()
```

In `sync_positions` (the endpoint), append `_sync_positions_to_universe()` after `result = save_positions_ibkr(positions)`:

```python
@router.post("/positions")
async def sync_positions():
    logger.info("📊 Sync step: positions")
    try:
        xml = fetch_flex_response("positions")
        positions = parse_positions_from_xml(xml)
        result = save_positions_ibkr(positions)
        _sync_positions_to_universe()
        return {
            "success": True,
            "positions_inserted": result["positions_inserted"],
            "last_updated": result["last_updated"],
        }
    except Exception as e:
        logger.error(f"❌ sync_positions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

In `_step_positions` (orchestrator helper), do the same:

```python
def _step_positions(xml: str) -> dict:
    result = save_positions_ibkr(parse_positions_from_xml(xml))
    _sync_positions_to_universe()
    return result
```

- [ ] **Step 4: Run tests, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py -v`
Expected: all sync tests pass (12 total).

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/sync.py backend/tests/test_sync_routes.py
git commit -m "[STORY-C-5] feat: auto-sync IBKR positions to tracked_universe

Every symbol in positions_ibkr is auto-tagged with source 'ibkr_position'
in tracked_universe. Sold positions (no longer in positions_ibkr) have
the source removed; row is deleted if no other source remains.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Market data ingestion service (yfinance batched)

**Files:**
- Create: `backend/scripts/market_data_ingestor.py`
- Test: `backend/tests/test_market_data_ingestor.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_market_data_ingestor.py`:

```python
"""Tests for the yfinance-backed market data ingestor."""
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pytest

from backend.scripts.market_data_ingestor import ingest_market_data


def _fake_ohlcv_df(symbol: str, days: int = 5) -> pd.DataFrame:
    """Build a tiny multi-index DataFrame in the shape yf.download returns for one symbol."""
    end = datetime(2026, 4, 27)
    dates = pd.date_range(end - timedelta(days=days - 1), end, freq="D")
    df = pd.DataFrame({
        "Open": [100.0 + i for i in range(days)],
        "High": [102.0 + i for i in range(days)],
        "Low": [99.0 + i for i in range(days)],
        "Close": [101.0 + i for i in range(days)],
        "Adj Close": [101.0 + i for i in range(days)],
        "Volume": [1_000_000 + i * 1000 for i in range(days)],
    }, index=dates)
    return df


def test_ingest_writes_rows(temp_db, monkeypatch):
    """ingest_market_data writes one row per (symbol, date) to market_data."""
    # Seed the universe with one symbol
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    # Stub yf.download to return a fake bars frame keyed by symbol
    fake = _fake_ohlcv_df("AAPL", days=5)
    import backend.scripts.market_data_ingestor as ingestor

    def fake_download(symbols, start=None, end=None, group_by="ticker", threads=True, progress=False, auto_adjust=False):
        # Return a frame keyed by single ticker as yf does
        return {"AAPL": fake}

    monkeypatch.setattr(ingestor, "_yf_download", fake_download)

    result = ingest_market_data()
    assert result["symbols_processed"] == 1
    assert result["rows_inserted"] == 5

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM market_data WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert cnt == 5


def test_ingest_idempotent(temp_db, monkeypatch):
    """Running ingest twice doesn't duplicate rows (PK conflict resolved)."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.commit()
    conn.close()

    import backend.scripts.market_data_ingestor as ingestor
    monkeypatch.setattr(ingestor, "_yf_download", lambda *a, **k: {"AAPL": _fake_ohlcv_df("AAPL", days=5)})

    ingest_market_data()
    ingest_market_data()

    conn = sqlite3.connect(str(temp_db))
    cnt = conn.execute("SELECT COUNT(*) FROM market_data WHERE symbol='AAPL'").fetchone()[0]
    conn.close()
    assert cnt == 5  # not 10


def test_ingest_skips_disabled_symbols(temp_db, monkeypatch):
    """Symbols with enabled=0 are skipped."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 0, datetime('now'))"
    )
    conn.commit()
    conn.close()

    import backend.scripts.market_data_ingestor as ingestor
    called = []
    monkeypatch.setattr(ingestor, "_yf_download", lambda symbols, **k: called.append(symbols) or {})

    result = ingest_market_data()
    assert result["symbols_processed"] == 0
    assert called == []  # no yfinance call


def test_ingest_only_fetches_since_last_bar(temp_db, monkeypatch):
    """For each symbol, yfinance is asked for bars starting after the latest stored bar."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO tracked_universe (symbol, sources, enabled, added_at) "
        "VALUES ('AAPL', '[\"manual\"]', 1, datetime('now'))"
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
        "VALUES ('AAPL', '2026-04-20', 100, 102, 99, 101, 101, 1000000)"
    )
    conn.commit()
    conn.close()

    import backend.scripts.market_data_ingestor as ingestor
    captured = {}

    def fake_download(symbols, start=None, end=None, **k):
        captured["start"] = start
        captured["symbols"] = symbols
        return {}

    monkeypatch.setattr(ingestor, "_yf_download", fake_download)

    ingest_market_data()
    # Should ask for bars strictly after 2026-04-20
    assert captured["start"] >= "2026-04-21"
```

- [ ] **Step 2: Run, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_market_data_ingestor.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the ingestor**

Create `backend/scripts/market_data_ingestor.py`:

```python
"""Batched yfinance ingestion service for market_data table.

Reads enabled symbols from tracked_universe, asks yfinance for bars since
each symbol's latest stored bar, writes rows idempotently to market_data.
"""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

BATCH_SIZE = 50  # yfinance handles 50-100 well in one call

# Indirected so tests can monkeypatch
def _yf_download(symbols, start=None, end=None, group_by="ticker", threads=True, progress=False, auto_adjust=False):
    import yfinance as yf
    return yf.download(
        tickers=symbols, start=start, end=end, group_by=group_by,
        threads=threads, progress=progress, auto_adjust=auto_adjust,
    )


def _latest_bar_date(conn, symbol: str) -> Optional[str]:
    row = conn.execute("SELECT MAX(time) FROM market_data WHERE symbol = ?", (symbol,)).fetchone()
    return row[0] if row and row[0] else None


def _enabled_symbols(conn) -> list[str]:
    rows = conn.execute(
        "SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol"
    ).fetchall()
    return [r[0] for r in rows]


def _normalize_response(resp, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """yf.download returns either a DataFrame (single symbol) or dict / multi-index DataFrame (multiple).

    Normalize to {symbol: DataFrame_with_OHLCV_cols}.
    """
    if isinstance(resp, dict):
        return {s: resp[s] for s in symbols if s in resp and resp[s] is not None}
    if isinstance(resp, pd.DataFrame):
        if isinstance(resp.columns, pd.MultiIndex):
            # Two-level columns: (ticker, field). Use level 0 to slice per symbol.
            level0 = resp.columns.get_level_values(0).unique()
            return {s: resp[s].copy() for s in symbols if s in level0}
        else:
            # Single symbol, flat columns
            if symbols:
                return {symbols[0]: resp.copy()}
    return {}


def _insert_bars(conn, symbol: str, df: pd.DataFrame) -> int:
    """Insert OHLCV bars idempotently. Returns number of rows actually inserted."""
    if df is None or df.empty:
        return 0
    inserted = 0
    for ts, row in df.iterrows():
        if pd.isna(row.get("Close")):
            continue
        date_str = ts.strftime("%Y-%m-%d")
        cur = conn.execute(
            "INSERT OR IGNORE INTO market_data "
            "(symbol, time, open, high, low, close, adj_close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                symbol, date_str,
                _safe_float(row.get("Open")),
                _safe_float(row.get("High")),
                _safe_float(row.get("Low")),
                _safe_float(row.get("Close")),
                _safe_float(row.get("Adj Close", row.get("Close"))),
                _safe_int(row.get("Volume")),
            ),
        )
        if cur.rowcount > 0:
            inserted += 1
    return inserted


def _safe_float(v) -> Optional[float]:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> Optional[int]:
    try:
        if v is None or pd.isna(v):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def ingest_market_data(default_lookback_days: int = 365) -> dict:
    """Pull market data from yfinance for all enabled symbols in tracked_universe.

    For each symbol: start = max(stored bar) + 1 day, or today - default_lookback_days
    if no bars stored yet.

    Returns: {"symbols_processed": int, "rows_inserted": int, "errors": int}
    """
    conn = get_db_connection()
    symbols = _enabled_symbols(conn)
    if not symbols:
        conn.close()
        return {"symbols_processed": 0, "rows_inserted": 0, "errors": 0}

    today = datetime.now().date()
    rows_inserted = 0
    errors = 0
    processed = 0
    now_iso = datetime.now().astimezone().isoformat()

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        # Compute start as the OLDEST start across the batch (yfinance gives us a
        # single window; per-symbol filter happens at insert time anyway)
        starts = []
        for sym in batch:
            last = _latest_bar_date(conn, sym)
            if last:
                next_day = (datetime.strptime(last, "%Y-%m-%d").date() + timedelta(days=1))
                starts.append(next_day)
            else:
                starts.append(today - timedelta(days=default_lookback_days))
        batch_start = min(starts).isoformat()
        batch_end = (today + timedelta(days=1)).isoformat()  # yfinance end is exclusive

        if batch_start >= batch_end:
            # All up-to-date
            processed += len(batch)
            continue

        try:
            resp = _yf_download(batch, start=batch_start, end=batch_end, threads=True)
            per_symbol = _normalize_response(resp, batch)
            for sym in batch:
                df = per_symbol.get(sym)
                inserted_n = _insert_bars(conn, sym, df)
                rows_inserted += inserted_n
                conn.execute(
                    "UPDATE tracked_universe SET last_synced_at = ? WHERE symbol = ?",
                    (now_iso, sym),
                )
                processed += 1
        except Exception as e:
            logger.error(f"❌ yf.download failed for batch {batch[0]}..{batch[-1]}: {e}")
            errors += len(batch)
            continue

        conn.commit()

    conn.close()
    logger.info(
        f"✅ Market data ingest: {processed} symbols, {rows_inserted} new rows, {errors} errors"
    )
    return {"symbols_processed": processed, "rows_inserted": rows_inserted, "errors": errors}
```

- [ ] **Step 4: Run, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_market_data_ingestor.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/market_data_ingestor.py backend/tests/test_market_data_ingestor.py
git commit -m "[STORY-C-6] feat: yfinance batched market data ingestor

Reads enabled symbols from tracked_universe, asks yfinance for bars
since each symbol's latest stored bar (or default_lookback_days for
new symbols), writes idempotently to market_data via
INSERT OR IGNORE on PK (symbol, time). 50-symbol batches with
threads=True. yf.download is indirected through _yf_download so tests
monkeypatch it for hermetic runs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `/api/sync/market-data` endpoint + market data query

**Files:**
- Create: `backend/api/routes/market_data.py`
- Modify: `backend/api/main.py`
- Test: `backend/tests/test_market_data_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_market_data_routes.py`:

```python
"""Tests for /api/market-data and /api/sync/market-data routes."""
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_market_data_for_symbol(temp_db):
    """GET /api/market-data/{symbol} returns OHLCV rows."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
        "VALUES ('AAPL', '2026-04-27', 100, 102, 99, 101, 101, 1500000)"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/market-data/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert len(body["bars"]) == 1
    bar = body["bars"][0]
    assert bar["close"] == 101


def test_market_data_404_for_unknown_symbol(temp_db):
    resp = client.get("/api/market-data/NOPE")
    assert resp.status_code == 404


def test_sync_market_data_endpoint(temp_db, monkeypatch):
    """POST /api/sync/market-data runs the ingestor."""
    import backend.scripts.market_data_ingestor as ing
    monkeypatch.setattr(
        ing, "ingest_market_data",
        lambda **kw: {"symbols_processed": 3, "rows_inserted": 12, "errors": 0},
    )
    resp = client.post("/api/sync/market-data")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["symbols_processed"] == 3
    assert body["rows_inserted"] == 12
```

- [ ] **Step 2: Run, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_market_data_routes.py -v`
Expected: 404 errors.

- [ ] **Step 3: Implement the market_data router**

Create `backend/api/routes/market_data.py`:

```python
"""Market data query routes (read access to OHLCV table)."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


@router.get("/{symbol}")
async def get_market_data(
    symbol: str,
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=10000),
):
    """Return OHLCV bars for a symbol, newest first."""
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
        "SELECT time, open, high, low, close, adj_close, volume "
        "FROM market_data WHERE " + " AND ".join(where) +
        " ORDER BY time DESC LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"no bars for {sym}")
    bars = [
        {
            "time": r[0], "open": r[1], "high": r[2], "low": r[3],
            "close": r[4], "adj_close": r[5], "volume": r[6],
        }
        for r in rows
    ]
    return {"symbol": sym, "bars": bars, "count": len(bars)}
```

Add a sync step in `backend/api/routes/sync.py`:

```python
@router.post("/market-data")
async def sync_market_data():
    """Pull yfinance bars for all enabled symbols in tracked_universe → market_data."""
    logger.info("📈 Sync step: market-data")
    try:
        from backend.scripts.market_data_ingestor import ingest_market_data
        result = ingest_market_data()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ sync_market_data failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

In `backend/api/main.py`, register the router:

```python
from backend.api.routes.market_data import router as market_data_router
```

```python
app.include_router(market_data_router)
```

- [ ] **Step 4: Run, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_market_data_routes.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/api/routes/market_data.py backend/api/routes/sync.py backend/api/main.py backend/tests/test_market_data_routes.py
git commit -m "[STORY-C-7] feat: GET /api/market-data/{symbol} + POST /api/sync/market-data

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Frontend — Configuration tab Universe section (shadcn UI)

This is where the Configuration tab gets its first shadcn-styled component, replacing inline-styled markup. Touches `page.tsx` substantially.

**Files:**
- Modify: `frontend/app/page.tsx` — replace Configuration tab content (currently the upload form section)

- [ ] **Step 1: Read the current Configuration tab block**

Locate `{activeTab === 'configuration' && (` in `frontend/app/page.tsx` (one block, ~250 lines). Note its current content: database stats, CSV upload, Flex import dropdown, import history table.

- [ ] **Step 2: Add Universe management state hooks**

Near the existing useState hooks (~line 165 area), add:

```typescript
interface UniverseSymbol {
  symbol: string;
  name: string | null;
  sector: string | null;
  currency: string | null;
  exchange: string | null;
  benchmark: string | null;
  sources: string[];
  enabled: boolean;
  added_at: string;
  last_synced_at: string | null;
}
interface IndexInfo {
  name: string;
  enabled: boolean;
  last_refreshed_at: string | null;
  symbol_count: number;
}

const [universe, setUniverse] = useState<UniverseSymbol[]>([]);
const [indices, setIndices] = useState<IndexInfo[]>([]);
const [universeLoading, setUniverseLoading] = useState(false);
const [manualSymbolInput, setManualSymbolInput] = useState<string>('');
const [marketDataSyncing, setMarketDataSyncing] = useState(false);
```

- [ ] **Step 3: Add handlers**

Add near the other fetch/handler functions:

```typescript
const fetchUniverse = async () => {
  try {
    const r = await fetch('/api/proxy/api/universe');
    if (r.ok) setUniverse((await r.json()).symbols);
  } catch (e) { console.error('fetchUniverse', e); }
};

const fetchIndices = async () => {
  try {
    const r = await fetch('/api/proxy/api/universe/indices');
    if (r.ok) setIndices((await r.json()).indices);
  } catch (e) { console.error('fetchIndices', e); }
};

const handleToggleIndex = async (name: string) => {
  await fetch(`/api/proxy/api/universe/indices/${name}/toggle`, { method: 'POST' });
  await fetchIndices();
};

const handleRefreshIndex = async (name: string) => {
  setUniverseLoading(true);
  try {
    await fetch(`/api/proxy/api/universe/indices/${name}/refresh`, { method: 'POST' });
    await fetchIndices();
    await fetchUniverse();
  } finally {
    setUniverseLoading(false);
  }
};

const handleAddManualSymbol = async () => {
  const sym = manualSymbolInput.trim().toUpperCase();
  if (!sym) return;
  await fetch('/api/proxy/api/universe/manual', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol: sym }),
  });
  setManualSymbolInput('');
  await fetchUniverse();
};

const handleRemoveManualSymbol = async (sym: string) => {
  await fetch(`/api/proxy/api/universe/manual/${sym}`, { method: 'DELETE' });
  await fetchUniverse();
};

const handleSyncMarketData = async () => {
  setMarketDataSyncing(true);
  try {
    const r = await fetch('/api/proxy/api/sync/market-data', { method: 'POST' });
    const body = await r.json();
    console.log('market-data sync', body);
  } finally {
    setMarketDataSyncing(false);
  }
};
```

Then add to the mount `useEffect` (find the one that calls `fetchHealth` etc.):

```typescript
fetchUniverse();
fetchIndices();
```

- [ ] **Step 4: Add the Universe section UI to the Configuration tab**

Inside the `{activeTab === 'configuration' && (` block, prepend (above the existing CSV upload section) this:

```tsx
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { RefreshCcw, X, Plus, Database } from "lucide-react";
```

Wait, imports go at the top of the file, not inside the JSX. Add the import block at the top of `frontend/app/page.tsx` (after the existing imports).

Inside the Configuration tab content, BEFORE the existing upload section:

```tsx
{/* Universe management — shadcn-styled */}
<div className="p-6 space-y-6">
  <Card>
    <CardHeader className="flex flex-row items-center justify-between">
      <CardTitle className="flex items-center gap-2">
        <Database className="w-5 h-5" />
        Tracked Universe
      </CardTitle>
      <Badge variant="secondary">{universe.length} symbols</Badge>
    </CardHeader>
    <CardContent className="space-y-6">

      {/* Index toggles */}
      <div>
        <h4 className="text-sm font-semibold mb-3 text-foreground">Index lists</h4>
        <div className="space-y-2">
          {indices.map((idx) => (
            <div key={idx.name} className="flex items-center justify-between p-3 rounded-md border bg-card">
              <div className="flex items-center gap-3">
                <Switch
                  checked={idx.enabled}
                  onCheckedChange={() => handleToggleIndex(idx.name)}
                  id={`switch-${idx.name}`}
                />
                <label htmlFor={`switch-${idx.name}`} className="text-sm font-medium cursor-pointer">
                  {idx.name.toUpperCase()}
                </label>
                <Badge variant="outline" className="text-xs">
                  {idx.symbol_count} symbols
                </Badge>
                {idx.last_refreshed_at && (
                  <span className="text-xs text-muted-foreground">
                    Refreshed {new Date(idx.last_refreshed_at).toLocaleDateString()}
                  </span>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleRefreshIndex(idx.name)}
                disabled={universeLoading}
              >
                <RefreshCcw className="w-4 h-4 mr-1" />
                Refresh
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Manual tickers */}
      <div>
        <h4 className="text-sm font-semibold mb-3 text-foreground">Custom tickers</h4>
        <div className="flex gap-2 mb-3">
          <Input
            placeholder="Add ticker (e.g. NVDA)"
            value={manualSymbolInput}
            onChange={(e) => setManualSymbolInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddManualSymbol(); }}
            className="max-w-xs"
          />
          <Button onClick={handleAddManualSymbol} disabled={!manualSymbolInput.trim()}>
            <Plus className="w-4 h-4 mr-1" />
            Add
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {universe
            .filter((s) => s.sources.includes('manual'))
            .map((s) => (
              <Badge key={s.symbol} variant="secondary" className="gap-1">
                {s.symbol}
                <button
                  onClick={() => handleRemoveManualSymbol(s.symbol)}
                  className="ml-1 hover:text-destructive"
                  title="Remove"
                >
                  <X className="w-3 h-3" />
                </button>
              </Badge>
            ))}
          {universe.filter((s) => s.sources.includes('manual')).length === 0 && (
            <span className="text-sm text-muted-foreground">No manual tickers yet.</span>
          )}
        </div>
      </div>

    </CardContent>
  </Card>

  {/* Market data sync */}
  <Card>
    <CardHeader className="flex flex-row items-center justify-between">
      <CardTitle>Market Data</CardTitle>
      <Button onClick={handleSyncMarketData} disabled={marketDataSyncing}>
        <RefreshCcw className={`w-4 h-4 mr-2 ${marketDataSyncing ? 'animate-spin' : ''}`} />
        {marketDataSyncing ? 'Syncing…' : 'Sync market data'}
      </Button>
    </CardHeader>
    <CardContent className="text-sm text-muted-foreground">
      Pulls daily OHLCV bars from yfinance for every enabled symbol in the universe.
      First-time syncs fetch the past year; subsequent runs only fetch new bars.
    </CardContent>
  </Card>
</div>
```

- [ ] **Step 5: Type-check**

Run: `cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit 2>&1 | grep -v __tests__`
Expected: no output.

- [ ] **Step 6: Visually verify**

Open `http://localhost:3000` → Configuration tab.
Expected:
- A new "Tracked Universe" card at the top with the 6 index switches (sp500, cac40, nasdaq100, dow30, dax40, ftse100), each with refresh button
- A "Custom tickers" input + add button + badge list area
- A "Market Data" card with sync button
- Below: the existing CSV upload + Flex import section (untouched)

- [ ] **Step 7: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "[STORY-C-8] feat: Configuration tab Universe section with shadcn/ui

- Index toggles (sp500/cac40/etc) with per-index refresh button
- Manual ticker input with badge list
- Market data sync card with action button
- First shadcn-styled section in the app; sets the visual tone

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: End-to-end smoke test

Manual verification — run live against real Wikipedia + yfinance.

- [ ] **Step 1: Restart backend with the new schema applied**

```bash
lsof -ti:8000 | xargs kill -9 2>/dev/null; sleep 1
cd /Users/louisgarnier/Claude/Stocks
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m uvicorn backend.api.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 3
curl -s http://localhost:8000/health
```
Expected: `{"status":"ok","database":"connected",...}`

- [ ] **Step 2: List indices**

```bash
curl -s http://localhost:8000/api/universe/indices | python3 -m json.tool
```
Expected: 6 indices, all with `enabled: false` initially.

- [ ] **Step 3: Refresh S&P 500 from Wikipedia (live network call)**

```bash
curl -s -X POST http://localhost:8000/api/universe/indices/sp500/refresh | python3 -m json.tool
```
Expected: `{"success": true, "inserted": ~503, "updated": 0, "count": ~503}`. Takes ~5 seconds.

- [ ] **Step 4: List the universe**

```bash
curl -s http://localhost:8000/api/universe | python3 -c "import json,sys; d=json.load(sys.stdin); print('count:',d['count']); print('first 5:',[s['symbol'] for s in d['symbols'][:5]])"
```
Expected: ~503 symbols, first 5 alphabetical (e.g. A, AAPL, ABBV, ABNB, ABT).

- [ ] **Step 5: Add a manual ticker**

```bash
curl -s -X POST -H "Content-Type: application/json" -d '{"symbol":"NVDA"}' http://localhost:8000/api/universe/manual | python3 -m json.tool
```
Expected: NVDA gets `sources: ["sp500", "manual"]` (already in S&P, manual added).

- [ ] **Step 6: Sync IBKR positions to merge into universe**

```bash
curl -s -X POST http://localhost:8000/api/sync/positions | python3 -m json.tool
```
Then:
```bash
sqlite3 output/database/finance.db "SELECT symbol, sources FROM tracked_universe WHERE sources LIKE '%ibkr_position%' LIMIT 5"
```
Expected: held symbols (e.g. PLTR, NVDA) have `ibkr_position` in their sources array.

- [ ] **Step 7: Sync market data (limited to enabled symbols only — make sure only your held positions are tagged enabled, OR cap the test by disabling sp500)**

Quick cap for the smoke test: disable sp500 so we only fetch IBKR positions:
```bash
sqlite3 output/database/finance.db "UPDATE tracked_universe SET enabled=0 WHERE 'sp500' IN (SELECT value FROM json_each(sources)) AND 'ibkr_position' NOT IN (SELECT value FROM json_each(sources))"
```

Then:
```bash
curl -s -X POST http://localhost:8000/api/sync/market-data | python3 -m json.tool
```
Expected: 15-ish symbols processed, hundreds of rows inserted (one year of daily bars per symbol). Takes ~10-30 seconds.

Verify:
```bash
sqlite3 output/database/finance.db "SELECT symbol, COUNT(*) FROM market_data GROUP BY symbol ORDER BY symbol"
```
Expected: each held symbol has ~250 bars (one trading year).

- [ ] **Step 8: Visit the Configuration tab in the browser**

Open `http://localhost:3000` → Configuration. Verify:
- The Tracked Universe card shows the indices with correct symbol counts
- Manual tickers section shows NVDA (or whatever you added) as a removable badge
- Market Data card has the sync button

- [ ] **Step 9: Mark the story complete**

Append to `docs/project/config/build-log.md`:

```
2026-04-28 — Story C complete: foundation laid (Tailwind v4 + shadcn/ui design system, tracked_universe + tracked_indices + market_data tables, S&P 500 & CAC 40 seeders, IBKR positions auto-sync to universe, yfinance batched market_data ingestor, Configuration tab universe section). Stories D/E build on this.
```

- [ ] **Step 10: Commit + push**

```bash
git add docs/project/config/build-log.md
git commit -m "[STORY-C-9] docs: mark Story C complete in build log

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin newstart
```

---

## Out of Scope (Stories D / E / F / G / H)

Tracked but explicitly NOT in this story:
- Indicators computation (MA, BB, RSI, MRSI, ATR) → Story D
- Detection (S/R, breakouts, consolidation) → Story E
- Tech Analysis tab UI → Story E
- Options-based S/R → Story F
- Sell signals on holdings → Story G
- Security Detail View popup → Story H
- Auto-scheduling of syncs (cron) → future
- Migrating existing tabs (Positions/Transactions) to shadcn — done as touched

---

## Self-Review Notes

- **Spec coverage:** Universe table ✅ (Task 2), index seeders ✅ (Task 4 — sp500 + cac40 specifically; nasdaq100/dow30/dax40/ftse100 left as known but unimplemented seeders so they show in the UI but require future work — explicit limitation), manual tickers ✅ (Task 3), IBKR auto-sync ✅ (Task 5), market_data ingestion ✅ (Tasks 6, 7), shadcn/ui foundation ✅ (Task 1), Configuration tab UI ✅ (Task 8), end-to-end live smoke ✅ (Task 9). Benchmarks (`^GSPC`, `^FCHI`, etc.) need to be in `tracked_universe` for Story D's MRSI; this is handled because Task 4's `_INDEX_CONFIG` sets `benchmark` on every member, but the benchmark symbols themselves aren't seeded — **adding them as a Story D pre-requisite, not blocking C**.

- **Placeholder scan:** All steps have either complete code or exact CLI commands. Two notes about Wikipedia table layout potentially differing (CAC 40 fetcher iterates tables looking for "Ticker" column) — that's defensive programming, not a placeholder.

- **Type consistency:** Endpoint paths consistent (`/api/universe`, `/api/universe/manual`, `/api/universe/manual/{symbol}`, `/api/universe/indices`, `/api/universe/indices/{name}/toggle`, `/api/universe/indices/{name}/refresh`, `/api/sync/market-data`, `/api/market-data/{symbol}`). Function names consistent across tasks (`seed_index`, `_sync_positions_to_universe`, `ingest_market_data`, `_yf_download`). The `sources` JSON-array semantics consistent across all tasks (manual / sp500 / cac40 / ibkr_position).
