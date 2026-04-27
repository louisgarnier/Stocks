# Sync Pipeline Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic `/api/transactions/flex-import` endpoint with a decoupled 4-step sync pipeline (Positions → Transactions → Corporate Actions → Splits) plus an orchestrator. Drop the now-unneeded reconciliation feature so positions are read directly from the IBKR snapshot as source of truth.

**Architecture:** Each pipeline step is an independent FastAPI endpoint under `/api/sync/*`. Steps 1 and 2 each pull from the IBKR Flex API (same query, different slice persisted). Steps 3 and 4 are thin wrappers over existing corporate-actions and apply-splits logic. The `/api/sync/full` orchestrator runs all four in sequence using a single shared Flex response across steps 1+2 to avoid double-fetching. Env-var configuration supports a fallback from dedicated query IDs (positions-only, trades-only) down to existing unified ones, so the user can split queries at IBKR later with a one-line config change.

**Tech Stack:** Python 3.10, FastAPI, SQLite, pytest with FastAPI TestClient, real-DB integration tests using a `temp_db` monkeypatch fixture (no DB mocks), HTTP responses stubbed via `monkeypatch` for hermeticity.

---

## File Structure

**Create:**
- `backend/tests/conftest.py` — shared `temp_db` fixture and stub-Flex-response helpers
- `backend/tests/fixtures/flex_response_minimal.xml` — minimal sample Flex XML with 1 trade + 1 position
- `backend/api/routes/sync.py` — new `/api/sync/*` router (4 step endpoints + orchestrator)
- `backend/tests/test_sync_routes.py` — integration tests for all sync endpoints

**Modify:**
- `backend/api/routes/positions.py` — drop reconciliation logic, return raw `positions_ibkr` only
- `backend/api/main.py` — register new `sync_router`, deprecate flex-import import
- `backend/scripts/fetch_flex_trades.py` — add `fetch_flex_response(query_type)` helper, env-var fallback for query IDs
- `backend/database/schema.sql` — remove `positions_calculated` table block
- `backend/api/routes/transactions.py` — delete `/api/transactions/flex-import` route + its imports
- `frontend/app/page.tsx` — drop recon UI (Position interface fields, summary cards, Qty Rec column, Recalculate Rec button), point Sync IBKR button at `/api/sync/full`

**Delete:**
- `backend/scripts/calculate_and_save_positions.py`
- `backend/database/finance.db` (stale empty duplicate)

---

## Task 1: Shared test fixtures (conftest.py)

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/fixtures/flex_response_minimal.xml`

- [ ] **Step 1: Write the fixtures**

Create `backend/tests/fixtures/flex_response_minimal.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryName="test" type="AF">
  <FlexStatements count="1">
    <FlexStatement accountId="TEST" fromDate="20260101" toDate="20260131">
      <Trades>
        <Trade transactionID="T0001" symbol="TEST" currency="USD" assetCategory="STK"
               tradeDate="20260115" quantity="10" tradePrice="100.50"
               proceeds="-1005.00" ibCommission="-1.00" costBasis="1006.00"
               buySell="BUY"/>
      </Trades>
      <OpenPositions>
        <OpenPosition symbol="TEST" position="10" costBasisMoney="1006.00"
                      costBasisPrice="100.60" markPrice="105.00"
                      positionValue="1050.00" fifoPnlUnrealized="44.00"
                      currency="USD" assetCategory="STK"/>
      </OpenPositions>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
```

Create `backend/tests/conftest.py`:

```python
"""Shared pytest fixtures for backend tests."""
import tempfile
from pathlib import Path
import pytest

import backend.database.connection as db_module
from backend.database.connection import init_database

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_db():
    """Create an isolated temp SQLite DB for one test, fully initialized."""
    original_db = db_module.DB_FILE
    temp_dir = tempfile.mkdtemp()
    temp_db_path = Path(temp_dir) / "test.db"
    db_module.DB_FILE = temp_db_path
    init_database()
    yield temp_db_path
    if temp_db_path.exists():
        temp_db_path.unlink()
    db_module.DB_FILE = original_db


@pytest.fixture
def flex_xml_minimal():
    """Read the minimal Flex XML fixture (1 trade, 1 position)."""
    return (FIXTURES_DIR / "flex_response_minimal.xml").read_text()


@pytest.fixture
def stub_flex_http(monkeypatch, flex_xml_minimal):
    """Stub the IBKR Flex HTTP layer to return the minimal XML.

    The two functions in fetch_flex_trades.py that hit IBKR are
    request_flex_query (returns a reference code) and fetch_flex_results
    (returns XML). We stub both so tests are hermetic.
    """
    import backend.scripts.fetch_flex_trades as flex
    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    return flex_xml_minimal
```

- [ ] **Step 2: Verify fixture loads**

Create a quick verification by running:

Run: `cd /Users/louisgarnier/Claude/Stocks && /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_database.py::test_database_initialization -v`
Expected: PASS (test_database.py already uses its own temp_db; we're verifying our env still works before adding shared fixture)

- [ ] **Step 3: Commit**

```bash
python3 scripts/git_ops.py add backend/tests/conftest.py backend/tests/fixtures/flex_response_minimal.xml
python3 scripts/git_ops.py commit -m "[SYNC-1] test: add shared temp_db fixture and minimal Flex XML"
```

> If `scripts/git_ops.py` does not exist on this branch, fall back to: `git add ...` and `git commit -m "..."` with the same arguments.

---

## Task 2: Simplify /api/positions (drop recon) + frontend recon UI

These ship together: API drops recon fields, frontend stops reading them.

**Files:**
- Modify: `backend/api/routes/positions.py:1-129` — replace whole file
- Modify: `frontend/app/page.tsx:128-156` (Position interface), `1944-1985` (recon buttons + summary cards), `2010-2017` (Qty Rec column header), `2059-2078` (Qty Rec cell)
- Test: `backend/tests/test_sync_routes.py` (created here, more added later)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_sync_routes.py`:

```python
"""Tests for sync pipeline routes."""
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_get_positions_returns_raw_ibkr_only(temp_db):
    """GET /api/positions returns positions_ibkr rows without any recon fields."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_money, "
        "cost_basis_price, mark_price, position_value, unrealized_pnl, "
        "currency, asset_category) VALUES "
        "('AAPL', 100, 15000, 150, 200, 20000, 5000, 'USD', 'STK')"
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/positions")
    assert resp.status_code == 200
    body = resp.json()

    assert body["success"] is True
    assert len(body["positions"]) == 1
    pos = body["positions"][0]

    # raw IBKR fields present
    assert pos["symbol"] == "AAPL"
    assert pos["quantity"] == 100
    assert pos["cost_basis_money"] == 15000

    # recon fields removed
    assert "qty_calculated" not in pos
    assert "qty_diff" not in pos
    assert "qty_diff_pct" not in pos
    assert "rec_status" not in pos
    assert "transaction_count" not in pos

    # summary no longer carries recon counters
    assert "matched" not in body["summary"]
    assert "warnings" not in body["summary"]
    assert "errors" not in body["summary"]
    assert body["summary"]["total_positions"] == 1
```

- [ ] **Step 2: Run test, verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_get_positions_returns_raw_ibkr_only -v`
Expected: FAIL because current `/api/positions` returns `qty_calculated`, `rec_status`, etc.

- [ ] **Step 3: Replace positions.py with simplified version**

Overwrite `backend/api/routes/positions.py` with:

```python
"""API routes for portfolio positions.

Returns raw IBKR positions (source of truth). No reconciliation —
positions and transactions both come from the same Flex Query, so they
are inherently consistent at sync time.
"""

from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("")
async def get_positions():
    """Return all positions stored in positions_ibkr (the IBKR snapshot)."""
    logger.info("📊 Fetching positions from positions_ibkr...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT symbol, quantity, cost_basis_money, cost_basis_price,
                   mark_price, position_value, unrealized_pnl,
                   currency, asset_category, last_updated
            FROM positions_ibkr
            ORDER BY ABS(COALESCE(position_value, 0)) DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()

        positions = [
            {
                "symbol": r[0],
                "quantity": r[1],
                "cost_basis_money": r[2],
                "cost_basis_price": r[3],
                "mark_price": r[4],
                "position_value": r[5],
                "unrealized_pnl": r[6],
                "currency": r[7],
                "asset_category": r[8],
                "last_updated": r[9],
            }
            for r in rows
        ]

        logger.info(f"✅ Returned {len(positions)} positions")
        return {
            "success": True,
            "positions": positions,
            "summary": {
                "total_positions": len(positions),
                "last_updated": rows[0][9] if rows else None,
            },
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

The `POST /api/positions/refresh` route is removed entirely (will be replaced by `/api/sync/recalc` — but recalc is no longer needed since we're not building positions_calculated). Frontend callers updated below.

- [ ] **Step 4: Run test, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_get_positions_returns_raw_ibkr_only -v`
Expected: PASS

- [ ] **Step 5: Update frontend to drop recon UI**

In `frontend/app/page.tsx`:

(a) Replace the `Position` interface (around line 128) with:

```typescript
interface Position {
  symbol: string;
  quantity: number;
  cost_basis_money: number;
  cost_basis_price: number;
  mark_price: number;
  position_value: number;
  unrealized_pnl: number;
  currency: string;
  asset_category: string;
  last_updated: string;
}
```

(b) Replace the `PositionsResponse` interface (around line 146) with:

```typescript
interface PositionsResponse {
  success: boolean;
  positions: Position[];
  summary: {
    total_positions: number;
    last_updated: string | null;
  };
}
```

(c) Remove the `positionsSortBy` `'rec_status'` value from the union type (around line 192). New type:

```typescript
const [positionsSortBy, setPositionsSortBy] = useState<'symbol' | 'quantity' | 'cost_basis_price' | 'position_value' | 'unrealized_pnl'>('position_value');
```

Same change in the `handlePositionsSort` parameter type (around line 440).

(d) Delete the `refreshPositions` function and the "🔄 Recalculate Rec" button block in the Positions tab (around lines 426-438 and 1944-1962). Also delete every other call to `'/api/proxy/api/positions/refresh'` in the file (search for it; there are calls inside `handleFlexImport`, file upload, etc.).

(e) Delete the four summary cards (Total / Matched / Warnings / Errors) around lines 1965-1985 and replace with a single card:

```tsx
{positions?.summary && (
  <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
    <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '8px', padding: '16px', minWidth: '180px' }}>
      <p style={{ fontSize: '12px', color: '#2563eb', fontWeight: '500' }}>Open Positions</p>
      <p style={{ fontSize: '24px', fontWeight: '600', color: '#1d4ed8' }}>{positions.summary.total_positions}</p>
    </div>
  </div>
)}
```

(f) Delete the "Qty Rec" column header (around lines 2016) and the corresponding `<td>` cell (around lines 2059-2078).

- [ ] **Step 6: Run frontend type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -v __tests__`
Expected: no output (no production errors)

- [ ] **Step 7: Commit**

```bash
python3 scripts/git_ops.py add backend/api/routes/positions.py backend/tests/test_sync_routes.py frontend/app/page.tsx
python3 scripts/git_ops.py commit -m "[SYNC-2] feat: drop reconciliation, return raw positions_ibkr"
```

---

## Task 3: Drop positions_calculated table + script

**Files:**
- Modify: `backend/database/schema.sql:135-146` — delete the positions_calculated CREATE TABLE block + its index
- Delete: `backend/scripts/calculate_and_save_positions.py`
- Delete: `backend/database/finance.db` (stale empty duplicate)
- Run: SQL `DROP TABLE` on existing real DB at `output/database/finance.db`

- [ ] **Step 1: Drop the table from the live DB**

Run: `sqlite3 output/database/finance.db "DROP TABLE IF EXISTS positions_calculated;"`
Then verify:
Run: `sqlite3 output/database/finance.db ".tables" | tr ' ' '\n' | sort`
Expected: list of remaining tables, no `positions_calculated`.

- [ ] **Step 2: Remove the table from schema.sql**

In `backend/database/schema.sql`, delete lines 135-146 (the entire `Positions calculated from transactions` block and its index). The file should jump directly from the `transactions_adjusted` view to the `positions_ibkr` table.

- [ ] **Step 3: Delete the calculator script**

Run: `git rm backend/scripts/calculate_and_save_positions.py`

- [ ] **Step 4: Delete the stale duplicate DB file**

Run: `rm -f backend/database/finance.db`

(Not tracked by git, so no `git rm` needed. Verify with `git status` — should show no new tracked changes from this file.)

- [ ] **Step 5: Verify nothing else imports the deleted module**

Run: `grep -rn "calculate_and_save_positions\|positions_calculated" backend/ frontend/app frontend/src 2>/dev/null | grep -v __pycache__`
Expected: no matches. (If any survive, delete those references — most likely in `routes/transactions.py` upload/delete handlers and in `routes/positions.py` if Task 2 missed any.)

- [ ] **Step 6: Run full test suite to confirm nothing broke**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/ -x 2>&1 | tail -30`
Expected: all currently-passing tests still pass (some pre-existing tests like `test_frontend_backend_sync.py` may rely on the old recon endpoint — if so, delete or update them as part of this task).

- [ ] **Step 7: Commit**

```bash
python3 scripts/git_ops.py add backend/database/schema.sql backend/scripts/calculate_and_save_positions.py
python3 scripts/git_ops.py commit -m "[SYNC-3] refactor: drop positions_calculated table and recalc script"
```

---

## Task 4: Add `fetch_flex_response()` helper

A single function that does the IBKR Flex round-trip (request reference, wait, fetch XML) and returns the XML string. Used by every sync step that needs Flex data.

**Files:**
- Modify: `backend/scripts/fetch_flex_trades.py` — add helper after `fetch_flex_results` definition
- Test: `backend/tests/test_sync_routes.py` — add helper tests

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_sync_routes.py`:

```python
def test_fetch_flex_response_returns_xml(monkeypatch, flex_xml_minimal):
    """fetch_flex_response wraps request + fetch and returns the XML string."""
    import backend.scripts.fetch_flex_trades as flex

    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    xml = flex.fetch_flex_response("last_month")
    assert "<FlexQueryResponse" in xml
    assert "TEST" in xml


def test_fetch_flex_response_raises_on_missing_token(monkeypatch):
    """Helper raises a clear error when IBKR_FLEX_TOKEN is unset."""
    import backend.scripts.fetch_flex_trades as flex
    monkeypatch.delenv("IBKR_FLEX_TOKEN", raising=False)
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    import pytest
    with pytest.raises(RuntimeError, match="IBKR_FLEX_TOKEN"):
        flex.fetch_flex_response("last_month")
```

- [ ] **Step 2: Run test, verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_fetch_flex_response_returns_xml backend/tests/test_sync_routes.py::test_fetch_flex_response_raises_on_missing_token -v`
Expected: FAIL with `AttributeError: module 'backend.scripts.fetch_flex_trades' has no attribute 'fetch_flex_response'`

- [ ] **Step 3: Implement the helper**

In `backend/scripts/fetch_flex_trades.py`, add this function after `fetch_flex_results` (around line 137):

```python
def fetch_flex_response(query_type: str) -> str:
    """Pull a Flex Query response as XML.

    Resolves env-var query IDs in this priority order:
      1. dedicated:  IBKR_QUERY_ID_positions   /  IBKR_QUERY_ID_trades_<query_type>
      2. unified:    IBKR_QUERY_ID_<query_type>

    `query_type` is one of: "positions", "trades_last_year", "trades_last_month",
    "last_year", "last_month". The "positions" / "trades_*" forms try the
    dedicated env var first; "last_*" forms go straight to unified.

    Raises RuntimeError on missing token or query ID.
    """
    token = os.getenv("IBKR_FLEX_TOKEN")
    if not token:
        raise RuntimeError("IBKR_FLEX_TOKEN not set")

    # Resolve query ID with fallback
    candidates = [f"IBKR_QUERY_ID_{query_type}"]
    if query_type == "positions":
        candidates.append("IBKR_QUERY_ID_last_month")  # unified fallback
    elif query_type.startswith("trades_"):
        candidates.append(f"IBKR_QUERY_ID_{query_type.removeprefix('trades_')}")

    query_id = None
    for var in candidates:
        val = os.getenv(var)
        if val:
            query_id = val
            break
    if not query_id:
        raise RuntimeError(f"No query ID found (tried: {candidates})")

    ref = request_flex_query(token, query_id)
    if not ref:
        raise RuntimeError("Flex query reference request failed")

    time.sleep(1)
    xml = fetch_flex_results(token, ref)
    if not xml:
        raise RuntimeError("Flex query fetch failed")
    return xml
```

- [ ] **Step 4: Run test, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_fetch_flex_response_returns_xml backend/tests/test_sync_routes.py::test_fetch_flex_response_raises_on_missing_token -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
python3 scripts/git_ops.py add backend/scripts/fetch_flex_trades.py backend/tests/test_sync_routes.py
python3 scripts/git_ops.py commit -m "[SYNC-4] feat: add fetch_flex_response helper with env-var fallback"
```

---

## Task 5: `/api/sync/positions` endpoint

POSTs trigger a Flex pull and persist *only* the open-positions slice. Transactions table must remain untouched.

**Files:**
- Create: `backend/api/routes/sync.py` — new router
- Modify: `backend/api/main.py:21-25, 46-49` — register the sync router
- Test: `backend/tests/test_sync_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_sync_routes.py`:

```python
def test_sync_positions_writes_only_positions_table(temp_db, stub_flex_http):
    """POST /api/sync/positions populates positions_ibkr and leaves transactions empty."""
    resp = client.post("/api/sync/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["positions_inserted"] == 1

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    pos_count = conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0]
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()

    assert pos_count == 1
    assert tx_count == 0  # critical: transactions untouched
```

- [ ] **Step 2: Run test, verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_positions_writes_only_positions_table -v`
Expected: FAIL with 404 (route does not exist).

- [ ] **Step 3: Create the sync router**

Create `backend/api/routes/sync.py`:

```python
"""Sync pipeline routes — independent steps + orchestrator."""
from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger
from backend.scripts.fetch_flex_trades import (
    fetch_flex_response,
    parse_positions_from_xml,
    parse_trades_from_xml,
    save_positions_ibkr,
    insert_flex_trades,
)

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/positions")
async def sync_positions():
    """Pull positions snapshot from IBKR; write only positions_ibkr."""
    logger.info("📊 Sync step: positions")
    try:
        xml = fetch_flex_response("positions")
        positions = parse_positions_from_xml(xml)
        result = save_positions_ibkr(positions)
        return {
            "success": True,
            "positions_inserted": result["positions_inserted"],
            "last_updated": result["last_updated"],
        }
    except Exception as e:
        logger.error(f"❌ sync_positions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Register the router in main.py**

In `backend/api/main.py`, add after the existing router imports (around line 25):

```python
from backend.api.routes.sync import router as sync_router
```

And after the existing `app.include_router(positions_router)` (around line 49):

```python
app.include_router(sync_router)
```

- [ ] **Step 5: Run test, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_positions_writes_only_positions_table -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
python3 scripts/git_ops.py add backend/api/routes/sync.py backend/api/main.py backend/tests/test_sync_routes.py
python3 scripts/git_ops.py commit -m "[SYNC-5] feat: add /api/sync/positions endpoint"
```

---

## Task 6: `/api/sync/transactions` endpoint

POSTs trigger a Flex pull and persist *only* the trades slice. Sets CA status to `orange` for newly-affected symbols.

**Files:**
- Modify: `backend/api/routes/sync.py` — add second endpoint
- Test: `backend/tests/test_sync_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_sync_routes.py`:

```python
def test_sync_transactions_writes_only_transactions_table(temp_db, stub_flex_http):
    """POST /api/sync/transactions populates transactions and leaves positions_ibkr empty."""
    resp = client.post("/api/sync/transactions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["inserted"] >= 1

    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    pos_count = conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0]
    ca_status = conn.execute(
        "SELECT status FROM corporate_actions_status WHERE sec_id='TEST'"
    ).fetchone()
    conn.close()

    assert tx_count == 1
    assert pos_count == 0  # critical: positions untouched
    assert ca_status is not None and ca_status[0] == "orange"
```

- [ ] **Step 2: Run test, verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_transactions_writes_only_transactions_table -v`
Expected: FAIL with 404.

- [ ] **Step 3: Implement endpoint**

In `backend/api/routes/sync.py`, add after `sync_positions`:

```python
@router.post("/transactions")
async def sync_transactions():
    """Pull trades from IBKR; write only the transactions table; flag affected symbols as CA-orange."""
    logger.info("📋 Sync step: transactions")
    try:
        xml = fetch_flex_response("trades_last_month")
        trades = parse_trades_from_xml(xml)
        result = insert_flex_trades(trades, source_file="api_sync_transactions")

        # Flag symbols touched by this import for corporate-action refresh
        if result.get("inserted_symbols"):
            from backend.utils.ca_status import set_ca_status
            try:
                set_ca_status(result["inserted_symbols"], "orange")
            except Exception as e:
                logger.warning(f"⚠️  CA status update failed: {e}")

        return {
            "success": True,
            "fetched": result.get("fetched", len(trades)),
            "inserted": result.get("inserted", 0),
            "skipped": result.get("skipped", 0),
            "errors": result.get("errors", 0),
            "inserted_symbols": result.get("inserted_symbols", []),
        }
    except Exception as e:
        logger.error(f"❌ sync_transactions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run test, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_transactions_writes_only_transactions_table -v`
Expected: PASS.

> If `insert_flex_trades` does not return `inserted_symbols` in its result dict, inspect [`fetch_flex_trades.py`](../../backend/scripts/fetch_flex_trades.py) and add that field. Searching `inserted_symbols` should reveal where to add it (used by old `/flex-import` route). Re-run test after.

- [ ] **Step 5: Commit**

```bash
python3 scripts/git_ops.py add backend/api/routes/sync.py backend/tests/test_sync_routes.py
python3 scripts/git_ops.py commit -m "[SYNC-6] feat: add /api/sync/transactions endpoint"
```

---

## Task 7: `/api/sync/corporate-actions` and `/api/sync/splits` (thin wrappers)

These are thin re-exposures of existing logic under the new path. They let the orchestrator call all four steps under one consistent prefix.

**Files:**
- Modify: `backend/api/routes/sync.py` — add two more endpoints
- Test: `backend/tests/test_sync_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_sync_routes.py`:

```python
def test_sync_corporate_actions_returns_success(temp_db, monkeypatch):
    """POST /api/sync/corporate-actions wraps the existing CA refresh logic."""
    # Stub the underlying fetcher so we don't hit yfinance
    import backend.scripts.fetch_corporate_actions as ca
    monkeypatch.setattr(
        ca, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    resp = client.post("/api/sync/corporate-actions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "parsed" in body


def test_sync_splits_returns_success(temp_db, monkeypatch):
    """POST /api/sync/splits wraps the existing apply-splits logic."""
    import backend.scripts.apply_splits as aps
    monkeypatch.setattr(
        aps, "apply_splits_to_transactions",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )
    resp = client.post("/api/sync/splits")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "applied" in body
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_corporate_actions_returns_success backend/tests/test_sync_routes.py::test_sync_splits_returns_success -v`
Expected: both FAIL with 404.

- [ ] **Step 3: Implement endpoints**

In `backend/api/routes/sync.py`, append:

```python
@router.post("/corporate-actions")
async def sync_corporate_actions():
    """Refresh corporate actions from yfinance for orange/stale symbols."""
    logger.info("📑 Sync step: corporate-actions")
    try:
        from backend.scripts.fetch_corporate_actions import fetch_and_import_corporate_actions
        result = fetch_and_import_corporate_actions(incremental=True)
        return {
            "success": True,
            "parsed": result["parsed"],
            "inserted": result["inserted"],
            "skipped": result["skipped"],
            "errors": result["errors"],
            "updated_transactions": result.get("updated_transactions", 0),
        }
    except Exception as e:
        logger.error(f"❌ sync_corporate_actions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/splits")
async def sync_splits():
    """Apply known splits to transactions, producing updated_transactions rows."""
    logger.info("✂️  Sync step: splits")
    try:
        from backend.scripts.apply_splits import apply_splits_to_transactions
        result = apply_splits_to_transactions()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ sync_splits failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

> If `apply_splits_to_transactions` is named differently in [`apply_splits.py`](../../backend/scripts/apply_splits.py), grep for the actual entry-point function name and use that. The existing `/api/transactions/apply-splits` route already calls it — copy the import line from there.

- [ ] **Step 4: Run tests, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_corporate_actions_returns_success backend/tests/test_sync_routes.py::test_sync_splits_returns_success -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
python3 scripts/git_ops.py add backend/api/routes/sync.py backend/tests/test_sync_routes.py
python3 scripts/git_ops.py commit -m "[SYNC-7] feat: add /api/sync/corporate-actions and /api/sync/splits"
```

---

## Task 8: `/api/sync/full` orchestrator

Calls Flex once, persists positions and transactions from the same XML, then runs corp-actions and splits. Returns per-step results so the frontend can show a 4-step progress bar.

**Files:**
- Modify: `backend/api/routes/sync.py` — add orchestrator endpoint
- Test: `backend/tests/test_sync_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_sync_routes.py`:

```python
def test_sync_full_runs_all_four_steps(temp_db, stub_flex_http, monkeypatch):
    """POST /api/sync/full runs positions, transactions, CAs, splits — in that order."""
    import backend.scripts.fetch_corporate_actions as ca_mod
    import backend.scripts.apply_splits as aps_mod

    monkeypatch.setattr(
        ca_mod, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    monkeypatch.setattr(
        aps_mod, "apply_splits_to_transactions",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )

    # Track Flex HTTP calls — orchestrator must call only once for steps 1+2 combined
    call_log = []
    import backend.scripts.fetch_flex_trades as flex
    original = flex.request_flex_query
    def tracked_request(token, qid):
        call_log.append(qid)
        return "REF123"
    monkeypatch.setattr(flex, "request_flex_query", tracked_request)

    resp = client.post("/api/sync/full")
    assert resp.status_code == 200
    body = resp.json()

    assert body["success"] is True
    assert "steps" in body
    step_names = [s["name"] for s in body["steps"]]
    assert step_names == ["positions", "transactions", "corporate_actions", "splits"]
    for s in body["steps"]:
        assert s["status"] == "ok"

    # Single Flex call shared across positions + transactions
    assert len(call_log) == 1

    # Both tables populated from the same response
    import sqlite3
    conn = sqlite3.connect(str(temp_db))
    assert conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
    conn.close()
```

- [ ] **Step 2: Run test, verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_full_runs_all_four_steps -v`
Expected: FAIL with 404.

- [ ] **Step 3: Implement the orchestrator**

In `backend/api/routes/sync.py`, append:

```python
@router.post("/full")
async def sync_full():
    """Run the full pipeline:
      1. Pull Flex once
      2. Persist positions snapshot
      3. Persist trades + flag CA-orange
      4. Refresh corporate actions
      5. Apply splits

    Returns per-step status. Failures stop the chain at that step but earlier
    steps remain committed.
    """
    logger.info("🚀 Sync step: FULL pipeline")
    steps = []

    def run(name, fn):
        try:
            result = fn()
            steps.append({"name": name, "status": "ok", "result": result})
            return True
        except Exception as e:
            logger.error(f"❌ Step '{name}' failed: {e}")
            steps.append({"name": name, "status": "error", "error": str(e)})
            return False

    # Step 1+2: one Flex pull, two persists
    try:
        xml = fetch_flex_response("last_month")  # unified query covers both
    except Exception as e:
        return {
            "success": False,
            "steps": [{"name": "positions", "status": "error", "error": str(e)}],
        }

    def step_positions():
        positions = parse_positions_from_xml(xml)
        return save_positions_ibkr(positions)

    def step_transactions():
        trades = parse_trades_from_xml(xml)
        result = insert_flex_trades(trades, source_file="api_sync_full")
        if result.get("inserted_symbols"):
            from backend.utils.ca_status import set_ca_status
            try:
                set_ca_status(result["inserted_symbols"], "orange")
            except Exception as e:
                logger.warning(f"⚠️  CA status update failed: {e}")
        return result

    def step_corporate_actions():
        from backend.scripts.fetch_corporate_actions import fetch_and_import_corporate_actions
        return fetch_and_import_corporate_actions(incremental=True)

    def step_splits():
        from backend.scripts.apply_splits import apply_splits_to_transactions
        return apply_splits_to_transactions()

    if not run("positions", step_positions): return _wrap(steps)
    if not run("transactions", step_transactions): return _wrap(steps)
    if not run("corporate_actions", step_corporate_actions): return _wrap(steps)
    run("splits", step_splits)

    return _wrap(steps)


def _wrap(steps):
    success = all(s["status"] == "ok" for s in steps)
    return {"success": success, "steps": steps}
```

- [ ] **Step 4: Run test, verify pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py::test_sync_full_runs_all_four_steps -v`
Expected: PASS.

- [ ] **Step 5: Run all sync tests together to catch interaction bugs**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_sync_routes.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
python3 scripts/git_ops.py add backend/api/routes/sync.py backend/tests/test_sync_routes.py
python3 scripts/git_ops.py commit -m "[SYNC-8] feat: add /api/sync/full orchestrator with shared Flex response"
```

---

## Task 9: Switch frontend Sync IBKR button to `/api/sync/full`

Wire the existing header button to the new orchestrator. UI still shows a single spinner — the per-step progress bar is Story B.

**Files:**
- Modify: `frontend/app/page.tsx:762-819` (`handleFlexImport` function), `932-957` (header button)

- [ ] **Step 1: Update handleFlexImport to call /api/sync/full**

Replace the body of `handleFlexImport` (around lines 762-819) with:

```typescript
const handleFlexImport = async () => {
  setFlexLoading(true);
  setShowFlexDropdown(false);
  try {
    const response = await fetch('/api/proxy/api/sync/full', { method: 'POST' });
    if (response.ok) {
      const result = await response.json();
      const stepSummary = (result.steps || [])
        .map((s: { name: string; status: string }) => `${s.status === 'ok' ? '✅' : '❌'} ${s.name}`)
        .join(' · ');
      setUploadResult({
        success: result.success,
        message: stepSummary || 'Sync complete',
        parsed: 0,
        inserted: 0,
        skipped: 0,
        errors: 0,
      });
      await Promise.all([
        fetchHealth(),
        fetchImportLogs(),
        fetchCAStatus(),
        fetchTransactions(1, pageSize, sortBy, sortOrder, symbolFilter),
        fetchPositions(),
      ]);
    } else {
      const err = await response.json().catch(() => ({ detail: 'Sync failed' }));
      setUploadResult({
        success: false,
        message: err.detail || 'Sync failed',
        parsed: 0, inserted: 0, skipped: 0, errors: 1,
        error_details: [err.detail || 'Unknown error'],
      });
      await fetchImportLogs();
    }
  } catch (e) {
    console.error('Sync error:', e);
    setUploadResult({
      success: false,
      message: `Sync error: ${e instanceof Error ? e.message : 'Unknown'}`,
      parsed: 0, inserted: 0, skipped: 0, errors: 1,
      error_details: [e instanceof Error ? e.message : 'Unknown'],
    });
  } finally {
    setFlexLoading(false);
  }
};
```

- [ ] **Step 2: Update header button click**

In the header (around line 944), change:

```typescript
onClick={() => handleFlexImport('last_month')}
```

to:

```typescript
onClick={() => handleFlexImport()}
```

- [ ] **Step 3: Update Load-tab Flex buttons to also call /api/sync/full**

Search the file for other call sites of `handleFlexImport` (around lines 1066 and 1084). Both pass `'last_year'` or `'last_month'`. Replace each call with `handleFlexImport()`. Until dedicated query IDs are configured, both buttons do the same thing — that's fine. (Future improvement: keep two buttons but pass a query-type arg through to `/api/sync/full`. Out of scope for this story.)

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -v __tests__`
Expected: no production errors.

- [ ] **Step 5: Manual sanity check**

With backend + frontend running, click "🔄 Sync IBKR" in the browser. Watch the Network tab.
Expected: single `POST /api/proxy/api/sync/full` request returning `{success: true, steps: [...]}`. Positions and Transactions tabs populate.

- [ ] **Step 6: Commit**

```bash
python3 scripts/git_ops.py add frontend/app/page.tsx
python3 scripts/git_ops.py commit -m "[SYNC-9] feat: point frontend Sync IBKR button at /api/sync/full"
```

---

## Task 10: Delete the old `/api/transactions/flex-import` route

Now that the frontend uses the new orchestrator, the old monolithic endpoint is unused.

**Files:**
- Modify: `backend/api/routes/transactions.py:438-513` — delete the route handler
- Modify: `backend/scripts/fetch_flex_trades.py` — delete `fetch_and_import_flex_trades` (the old monolithic orchestrator function)
- Run: cross-reference grep to confirm no callers remain

- [ ] **Step 1: Verify nothing calls the old route**

Run: `grep -rn "flex-import\|fetch_and_import_flex_trades" backend/ frontend/app frontend/src 2>/dev/null | grep -v __pycache__`
Expected: matches only inside the files we're about to delete from. If a test references it, delete that test (or update to call `/api/sync/full`).

- [ ] **Step 2: Delete the route handler**

In `backend/api/routes/transactions.py`, delete lines 438-513 (the entire `@router.post("/flex-import")` handler including its docstring and traceback handling).

- [ ] **Step 3: Delete the orchestration function**

In `backend/scripts/fetch_flex_trades.py`, delete the `fetch_and_import_flex_trades` function (around lines 690-749) AND the `if __name__ == "__main__":` block at the bottom that calls it. The script should now contain only: HTTP layer, parsers, and DB writers. Drop the `import` line from the deleted route handler if it's still in `transactions.py`.

- [ ] **Step 4: Run full backend test suite**

Run: `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/ -x 2>&1 | tail -20`
Expected: PASS.

- [ ] **Step 5: Smoke-test that the API still boots**

Run: `curl -s http://localhost:8000/health`
Expected: 200 with `database: connected`. (If backend was running before this task, restart it: `lsof -ti:8000 | xargs kill && /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m uvicorn backend.api.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &`.)

- [ ] **Step 6: Commit**

```bash
python3 scripts/git_ops.py add backend/api/routes/transactions.py backend/scripts/fetch_flex_trades.py
python3 scripts/git_ops.py commit -m "[SYNC-10] refactor: remove deprecated /api/transactions/flex-import route"
```

---

## Task 11: End-to-end smoke test (real IBKR sync)

A live verification that the new pipeline works against the real IBKR Flex API and the real DB. **Run this manually — not part of the test suite.**

**Files:**
- None (manual verification + log capture)

- [ ] **Step 1: Snapshot current DB state**

Run: `sqlite3 output/database/finance.db "SELECT 'tx', COUNT(*) FROM transactions UNION ALL SELECT 'pos', COUNT(*) FROM positions_ibkr UNION ALL SELECT 'ca', COUNT(*) FROM corporate_actions UNION ALL SELECT 'updated', COUNT(*) FROM updated_transactions;"`

Record the four numbers.

- [ ] **Step 2: Trigger a real sync**

Run: `curl -s -X POST http://localhost:8000/api/sync/full | python3 -m json.tool`
Expected: a JSON document with `"success": true` and 4 step entries each with `"status": "ok"`. If any step fails, the response shows which one and why.

- [ ] **Step 3: Snapshot DB state after sync**

Run the same query as Step 1.
Expected: `pos` and `tx` counts changed (or stayed same if there's nothing new since last sync), `ca` count grew if new symbols arrived, `updated` count grew if any new splits applied.

- [ ] **Step 4: Open the frontend**

Open http://localhost:3000 in the browser. Click the **🔄 Sync IBKR** button.
Expected: spinner shows "Syncing…", then resolves. Positions tab shows fresh data with current `last_updated` timestamp.

- [ ] **Step 5: Mark plan complete**

Update `docs/project/config/build-log.md` with a one-line entry:

```
2026-04-27 — Story A complete: sync pipeline restructured to /api/sync/* with orchestrator. Reconciliation feature dropped.
```

(If `build-log.md` does not yet exist, create it with that single line.)

- [ ] **Step 6: Commit**

```bash
python3 scripts/git_ops.py add docs/project/config/build-log.md
python3 scripts/git_ops.py commit -m "[SYNC-11] docs: mark Story A complete in build log"
```

---

## Out of Scope (Story B)

- Per-step progress bar UI in the frontend
- Tab restructure (Positions / Transactions+sub-tabs / Configuration)
- Per-tab "Refresh just this" buttons
- Staleness badge in header showing time-since-last-sync
- Page.tsx component extraction

These all depend on the backend foundation built here. They are tracked for Story B.

---

## Self-Review Notes

- Spec coverage: all five backend bullets in the user-approved scope are tasked (4 endpoints + orchestrator: tasks 5–8; env-var fallback: task 4; refactor: tasks 4–8; tests: in every task; deprecation: task 10). Recon drop is tasks 2 + 3.
- Placeholder scan: each step contains the actual code or exact command. Two notes (Task 6, Task 7) flag a small contingency where an existing function name may differ — these are corrigenda, not unfilled placeholders.
- Type consistency: `fetch_flex_response`, `parse_positions_from_xml`, `parse_trades_from_xml`, `save_positions_ibkr`, `insert_flex_trades`, `apply_splits_to_transactions`, `fetch_and_import_corporate_actions` are referenced consistently across tasks. The orchestrator's per-step result shape (`{name, status, result|error}`) is consistent with the test assertions in Task 8.
