# Epic H v1 — Security Detail View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Click any symbol anywhere → opens a slide-in panel with everything we know about it: position info (held mode) or basic stats (not-held mode), latest indicators, transactions, recent OHLCV bars. Verifies the data we've been writing to the database is correct, per-symbol. Bandaid until the full Epic H ships chart + sell simulator + signal checklist.

**Architecture:** One backend endpoint (`GET /api/security/{symbol}/detail`) returning everything needed in a single round trip — positions row if held, transactions filtered by symbol, latest indicator row, last 30 OHLCV bars. Frontend uses shadcn `<Sheet>` (right-side slide-in panel). Single React component handles both Mode A (held) and Mode B (not held) — branches on the response's `is_held` flag. Click handlers wired into the Browse Universe table (Configuration tab) AND the Positions tab list. Charts, sell simulator, signal checklist deferred to a follow-up.

**Tech Stack:** FastAPI + SQLite (no new deps backend). shadcn/ui Sheet + Table + Badge + Card (frontend). Recharts NOT used in v1.

---

## File Structure

**Create:**
- `backend/api/routes/security.py` — `GET /api/security/{symbol}/detail` endpoint
- `backend/tests/test_security_routes.py` — endpoint tests
- `frontend/components/ui/sheet.tsx` — shadcn Sheet component (added via `npx shadcn add sheet`)
- `frontend/components/security-detail/SecurityDetailSheet.tsx` — the modal component itself
- `frontend/components/security-detail/SecurityDetailContent.tsx` — internal render component (Mode A / Mode B logic)

**Modify:**
- `backend/api/main.py` — register `security_router`
- `frontend/app/page.tsx` — add `selectedSymbol` state, wire row clicks (Browse Universe table + Positions table), render `<SecurityDetailSheet>` once at top level

**Delete:** none.

---

## Task 1: Backend `/api/security/{symbol}/detail` endpoint

Single endpoint, single SQL trip. Combines positions, transactions, indicators, recent OHLCV.

**Files:**
- Create: `backend/api/routes/security.py`
- Modify: `backend/api/main.py`
- Test: `backend/tests/test_security_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_security_routes.py`:

```python
"""Tests for /api/security/{symbol}/detail."""
import sqlite3
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def _seed_security(temp_db, symbol: str, held: bool, days: int = 30):
    """Insert tracked_universe row + market_data + 1 indicators row + optionally positions_ibkr + transactions."""
    import json as _json
    conn = sqlite3.connect(str(temp_db))
    sources = ["sp500", "ibkr_position"] if held else ["sp500"]
    conn.execute(
        "INSERT INTO tracked_universe (symbol, name, sector, currency, sources, enabled, added_at) "
        "VALUES (?, ?, ?, ?, ?, 1, datetime('now'))",
        (symbol, f"{symbol} Inc.", "Tech", "USD", _json.dumps(sources)),
    )
    if held:
        conn.execute(
            "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_money, cost_basis_price, "
            "mark_price, position_value, unrealized_pnl, currency, asset_category) "
            "VALUES (?, 100, 15000, 150, 200, 20000, 5000, 'USD', 'STK')",
            (symbol,),
        )
        conn.execute(
            "INSERT INTO transactions (transaction_id, symbol, trade_date, quantity, t_price, currency) "
            "VALUES (?, ?, '2025-12-15', 100, 150, 'USD')",
            (f"T-{symbol}-001", symbol),
        )
    for i in range(days):
        ts = f"2026-04-{i + 1:02d}"
        c = 100.0 + i * 0.5
        conn.execute(
            "INSERT INTO market_data (symbol, time, open, high, low, close, adj_close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1000000)",
            (symbol, ts, c, c + 1, c - 1, c, c),
        )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_100, ma_150, ma_200, "
        "bb_upper_20, bb_lower_20, bb_width, rsi_14, mrsi, atr_14, volume_ma_20) "
        "VALUES (?, '2026-04-30', 110, 108, 105, 100, 115, 105, 0.09, 62, 0.05, 2.5, 1500000)",
        (symbol,),
    )
    conn.commit()
    conn.close()


def test_security_detail_held(temp_db):
    """Held symbol returns is_held=true + position + transactions + indicators + bars."""
    _seed_security(temp_db, "AAPL", held=True)

    resp = client.get("/api/security/AAPL/detail")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["symbol"] == "AAPL"
    assert body["is_held"] is True
    assert body["universe"]["name"] == "AAPL Inc."
    assert body["universe"]["sector"] == "Tech"
    assert "ibkr_position" in body["universe"]["sources"]

    assert body["position"]["quantity"] == 100
    assert body["position"]["cost_basis_price"] == 150

    assert len(body["transactions"]) == 1
    assert body["transactions"][0]["transaction_id"] == "T-AAPL-001"

    assert body["indicators"]["mrsi"] == 0.05
    assert body["indicators"]["rsi_14"] == 62

    assert len(body["bars"]) == 30
    assert body["bars"][0]["time"] >= body["bars"][-1]["time"]  # newest first


def test_security_detail_not_held(temp_db):
    """Non-held symbol returns is_held=false, position=None, transactions=[]."""
    _seed_security(temp_db, "MSFT", held=False)

    resp = client.get("/api/security/MSFT/detail")
    assert resp.status_code == 200
    body = resp.json()

    assert body["is_held"] is False
    assert body["position"] is None
    assert body["transactions"] == []
    assert body["indicators"]["mrsi"] == 0.05
    assert len(body["bars"]) == 30


def test_security_detail_404_unknown(temp_db):
    resp = client.get("/api/security/NOPE/detail")
    assert resp.status_code == 404


def test_security_detail_uppercases_symbol(temp_db):
    _seed_security(temp_db, "AAPL", held=False)
    resp = client.get("/api/security/aapl/detail")
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "AAPL"
```

- [ ] **Step 2: Run, verify they fail**

```bash
cd /Users/louisgarnier/Claude/Stocks
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_security_routes.py -v
```

Expected: 4 failures with 404 (route doesn't exist).

- [ ] **Step 3: Implement the security router**

Create `backend/api/routes/security.py`:

```python
"""Security Detail endpoint — combined per-symbol data for the Sheet modal."""
import json
from fastapi import APIRouter, HTTPException

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/{symbol}/detail")
async def get_security_detail(symbol: str):
    """Return everything we know about a symbol in one response.

    Shape:
    {
      "symbol": str,
      "is_held": bool,
      "universe": {symbol, name, sector, currency, sources, benchmark, ...} | None,
      "position": {quantity, cost_basis_price, position_value, ...} | None,
      "transactions": [{transaction_id, trade_date, quantity, t_price, ...}, ...],
      "indicators": {ma_50, rsi_14, mrsi, ...} | None,
      "bars": [{time, open, high, low, close, adj_close, volume}, ...]  # last 30, newest first
    }
    """
    sym = symbol.upper()
    conn = get_db_connection()

    universe_row = conn.execute(
        "SELECT symbol, name, sector, currency, exchange, benchmark, sources, "
        "enabled, added_at, last_synced_at FROM tracked_universe WHERE symbol = ?",
        (sym,),
    ).fetchone()
    if not universe_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"{sym} not in universe")

    universe = {
        "symbol": universe_row[0],
        "name": universe_row[1],
        "sector": universe_row[2],
        "currency": universe_row[3],
        "exchange": universe_row[4],
        "benchmark": universe_row[5],
        "sources": json.loads(universe_row[6] or "[]"),
        "enabled": bool(universe_row[7]),
        "added_at": universe_row[8],
        "last_synced_at": universe_row[9],
    }

    position_row = conn.execute(
        "SELECT symbol, quantity, cost_basis_money, cost_basis_price, mark_price, "
        "position_value, unrealized_pnl, currency, asset_category, last_updated "
        "FROM positions_ibkr WHERE symbol = ?",
        (sym,),
    ).fetchone()
    is_held = position_row is not None
    position = None
    if position_row:
        position = {
            "symbol": position_row[0],
            "quantity": position_row[1],
            "cost_basis_money": position_row[2],
            "cost_basis_price": position_row[3],
            "mark_price": position_row[4],
            "position_value": position_row[5],
            "unrealized_pnl": position_row[6],
            "currency": position_row[7],
            "asset_category": position_row[8],
            "last_updated": position_row[9],
        }

    transactions = []
    if is_held:
        tx_rows = conn.execute(
            "SELECT transaction_id, trade_date, quantity, t_price, proceeds, comm_fee, "
            "currency, asset_category FROM transactions WHERE symbol = ? ORDER BY trade_date DESC",
            (sym,),
        ).fetchall()
        transactions = [
            {
                "transaction_id": r[0],
                "trade_date": r[1],
                "quantity": r[2],
                "t_price": r[3],
                "proceeds": r[4],
                "comm_fee": r[5],
                "currency": r[6],
                "asset_category": r[7],
            }
            for r in tx_rows
        ]

    ind_row = conn.execute(
        "SELECT time, ma_50, ma_100, ma_150, ma_200, bb_upper_20, bb_lower_20, "
        "bb_width, rsi_14, mrsi, atr_14, volume_ma_20 FROM indicators "
        "WHERE symbol = ? ORDER BY time DESC LIMIT 1",
        (sym,),
    ).fetchone()
    indicators = None
    if ind_row:
        indicators = {
            "time": ind_row[0],
            "ma_50": ind_row[1], "ma_100": ind_row[2], "ma_150": ind_row[3], "ma_200": ind_row[4],
            "bb_upper_20": ind_row[5], "bb_lower_20": ind_row[6], "bb_width": ind_row[7],
            "rsi_14": ind_row[8], "mrsi": ind_row[9], "atr_14": ind_row[10],
            "volume_ma_20": ind_row[11],
        }

    bar_rows = conn.execute(
        "SELECT time, open, high, low, close, adj_close, volume FROM market_data "
        "WHERE symbol = ? ORDER BY time DESC LIMIT 30",
        (sym,),
    ).fetchall()
    bars = [
        {
            "time": r[0], "open": r[1], "high": r[2], "low": r[3],
            "close": r[4], "adj_close": r[5], "volume": r[6],
        }
        for r in bar_rows
    ]

    conn.close()
    logger.info(f"📂 Security detail for {sym}: held={is_held}, tx={len(transactions)}, bars={len(bars)}")

    return {
        "symbol": sym,
        "is_held": is_held,
        "universe": universe,
        "position": position,
        "transactions": transactions,
        "indicators": indicators,
        "bars": bars,
    }
```

- [ ] **Step 4: Register the router**

In `backend/api/main.py`, add after the existing `from backend.api.routes.indicators import router as indicators_router` line:

```python
from backend.api.routes.security import router as security_router
```

And after `app.include_router(indicators_router)`:

```python
app.include_router(security_router)
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd /Users/louisgarnier/Claude/Stocks
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest backend/tests/test_security_routes.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/security.py backend/api/main.py backend/tests/test_security_routes.py
git commit -m "[STORY-H-1] feat: GET /api/security/{symbol}/detail endpoint

Single endpoint returns everything for the Security Detail Sheet:
universe row + held position (if any) + transactions filtered by
symbol + latest indicator row + last 30 OHLCV bars (newest first).
404 when symbol is not in tracked_universe.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Install shadcn Sheet component

**Files:**
- Create: `frontend/components/ui/sheet.tsx` (via shadcn CLI)

- [ ] **Step 1: Run the shadcn add command**

```bash
cd /Users/louisgarnier/Claude/Stocks/frontend
npx shadcn@latest add sheet
```

Answer "yes" if prompted. The CLI writes `frontend/components/ui/sheet.tsx`.

- [ ] **Step 2: Type-check stays clean**

```bash
cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit 2>&1 | grep -v __tests__
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
cd /Users/louisgarnier/Claude/Stocks
git add frontend/components/ui/sheet.tsx
git commit -m "[STORY-H-2] feat: add shadcn Sheet component

Slide-in panel for the Security Detail modal.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: SecurityDetailSheet component (skeleton + data fetch)

The modal component itself. Holds the Sheet, fetches data from `/api/security/{symbol}/detail` when `symbol` prop changes, renders skeleton while loading. Mode A / Mode B branching is in Task 4.

**Files:**
- Create: `frontend/components/security-detail/SecurityDetailSheet.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/components/security-detail/SecurityDetailSheet.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";

export interface SecurityDetail {
  symbol: string;
  is_held: boolean;
  universe: {
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
  } | null;
  position: {
    quantity: number;
    cost_basis_money: number | null;
    cost_basis_price: number | null;
    mark_price: number | null;
    position_value: number | null;
    unrealized_pnl: number | null;
    currency: string | null;
  } | null;
  transactions: Array<{
    transaction_id: string;
    trade_date: string;
    quantity: number;
    t_price: number | null;
    proceeds: number | null;
    comm_fee: number | null;
    currency: string | null;
  }>;
  indicators: {
    time: string;
    ma_50: number | null;
    ma_100: number | null;
    ma_150: number | null;
    ma_200: number | null;
    bb_upper_20: number | null;
    bb_lower_20: number | null;
    bb_width: number | null;
    rsi_14: number | null;
    mrsi: number | null;
    atr_14: number | null;
    volume_ma_20: number | null;
  } | null;
  bars: Array<{
    time: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    adj_close: number | null;
    volume: number | null;
  }>;
}

interface Props {
  symbol: string | null;
  onClose: () => void;
}

export function SecurityDetailSheet({ symbol, onClose }: Props) {
  const [data, setData] = useState<SecurityDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/proxy/api/security/${encodeURIComponent(symbol)}/detail`)
      .then(async (r) => {
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}: ${await r.text()}`);
        }
        return r.json();
      })
      .then((d: SecurityDetail) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  return (
    <Sheet open={symbol !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <span className="font-mono">{symbol ?? ""}</span>
            {data && (
              <Badge variant={data.is_held ? "default" : "secondary"}>
                {data.is_held ? "Held" : "Not held"}
              </Badge>
            )}
            {data?.universe?.currency && (
              <Badge variant="outline" className="text-xs">{data.universe.currency}</Badge>
            )}
          </SheetTitle>
          {data?.universe?.name && (
            <p className="text-sm text-muted-foreground">{data.universe.name}</p>
          )}
        </SheetHeader>

        <div className="p-4 space-y-4">
          {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {error && <p className="text-sm text-destructive">Error: {error}</p>}
          {data && <SecurityDetailContent data={data} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// Inline content component — rendered once data is loaded.
// Mode A / Mode B branching lives here. Filled in Task 4 onward.
function SecurityDetailContent({ data }: { data: SecurityDetail }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Sources: {data.universe?.sources.join(", ") ?? "—"}
        {data.universe?.sector ? ` · Sector: ${data.universe.sector}` : ""}
      </p>
      <p className="text-xs text-muted-foreground">
        Detail rendering: pending Tasks 4–6.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit 2>&1 | grep -v __tests__
```

Expected: no output (the new component compiles in isolation).

- [ ] **Step 3: Commit**

```bash
cd /Users/louisgarnier/Claude/Stocks
git add frontend/components/security-detail/SecurityDetailSheet.tsx
git commit -m "[STORY-H-3] feat: SecurityDetailSheet component skeleton

Slide-in shadcn Sheet, fetches /api/security/{symbol}/detail on
symbol prop change, renders header (symbol + held/not-held badge +
currency + name) and a placeholder content area. Mode A / Mode B
branching comes in Tasks 4–6.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Mode A — held mode (position summary + transactions)

Replaces the placeholder `SecurityDetailContent` with held-mode rendering: position summary card + transactions table. Skip indicators + bars (next tasks).

**Files:**
- Modify: `frontend/components/security-detail/SecurityDetailSheet.tsx`

- [ ] **Step 1: Replace SecurityDetailContent with held-mode logic**

Replace the existing `SecurityDetailContent` function in `frontend/components/security-detail/SecurityDetailSheet.tsx` with:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

function SecurityDetailContent({ data }: { data: SecurityDetail }) {
  const symbolForBenchmark = data.universe?.benchmark ?? "—";
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">About</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-1">
          <div className="flex flex-wrap gap-1 mb-2">
            {data.universe?.sources.map((s) => (
              <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
            )) ?? null}
          </div>
          <p className="text-xs text-muted-foreground">
            Sector: {data.universe?.sector ?? "—"}
            {" · "}Currency: {data.universe?.currency ?? "—"}
            {" · "}Benchmark for MRSI: {symbolForBenchmark}
          </p>
        </CardContent>
      </Card>

      {data.is_held && data.position && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Position</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm">
            <Stat label="Quantity" value={fmt(data.position.quantity)} />
            <Stat label="Avg cost" value={data.position.cost_basis_price != null ? `${fmtCur(data.position.cost_basis_price, data.position.currency)}` : "—"} />
            <Stat label="Market value" value={data.position.position_value != null ? fmtCur(data.position.position_value, data.position.currency) : "—"} />
            <Stat
              label="Unrealized P&L"
              value={data.position.unrealized_pnl != null ? `${data.position.unrealized_pnl >= 0 ? "+" : ""}${fmtCur(data.position.unrealized_pnl, data.position.currency)}` : "—"}
              colorClass={data.position.unrealized_pnl != null ? (data.position.unrealized_pnl >= 0 ? "text-green-600" : "text-red-600") : undefined}
            />
          </CardContent>
        </Card>
      )}

      {data.is_held && data.transactions.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Transactions ({data.transactions.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border max-h-72 overflow-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-card">
                  <TableRow>
                    <TableHead className="text-xs">Date</TableHead>
                    <TableHead className="text-right text-xs">Side</TableHead>
                    <TableHead className="text-right text-xs">Qty</TableHead>
                    <TableHead className="text-right text-xs">Price</TableHead>
                    <TableHead className="text-right text-xs">Proceeds</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.transactions.map((t) => (
                    <TableRow key={t.transaction_id}>
                      <TableCell className="text-xs font-mono">{t.trade_date}</TableCell>
                      <TableCell className={`text-right text-xs font-semibold ${t.quantity >= 0 ? "text-green-600" : "text-red-600"}`}>
                        {t.quantity >= 0 ? "BUY" : "SELL"}
                      </TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{fmt(Math.abs(t.quantity))}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{t.t_price != null ? t.t_price.toFixed(2) : "—"}</TableCell>
                      <TableCell className="text-right text-xs font-mono tabular-nums">{t.proceeds != null ? t.proceeds.toFixed(2) : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Indicator + bars cards land in Tasks 5 and 6 */}
    </div>
  );
}

function Stat({ label, value, colorClass }: { label: string; value: string; colorClass?: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className={`font-mono font-semibold tabular-nums ${colorClass ?? ""}`}>{value}</p>
    </div>
  );
}

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function fmtCur(n: number, currency: string | null | undefined): string {
  const sym = currency === "EUR" ? "€" : currency === "GBP" ? "£" : "$";
  return `${sym}${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit 2>&1 | grep -v __tests__
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
cd /Users/louisgarnier/Claude/Stocks
git add frontend/components/security-detail/SecurityDetailSheet.tsx
git commit -m "[STORY-H-4] feat: held-mode rendering (position summary + transactions table)

About card: sources badges + sector + currency + MRSI benchmark.
Position card (held only): qty / avg cost / market value / unrealized
P&L (color-coded green/red).
Transactions card (held only): scrollable table with date, side
(buy/sell from quantity sign), qty, price, proceeds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Indicators card (both modes)

Add the indicators panel to `SecurityDetailContent`. All 11 indicator values, formatted nicely, with MRSI color-coded.

**Files:**
- Modify: `frontend/components/security-detail/SecurityDetailSheet.tsx`

- [ ] **Step 1: Add the indicators card**

Find the `{/* Indicator + bars cards land in Tasks 5 and 6 */}` comment in `SecurityDetailContent` and replace it with the indicators card:

```tsx
{data.indicators && (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm">Indicators (as of {data.indicators.time})</CardTitle>
    </CardHeader>
    <CardContent className="grid grid-cols-3 gap-3 text-sm">
      <Stat label="MA 50" value={fmt(data.indicators.ma_50)} />
      <Stat label="MA 100" value={fmt(data.indicators.ma_100)} />
      <Stat label="MA 150" value={fmt(data.indicators.ma_150)} />
      <Stat label="MA 200" value={fmt(data.indicators.ma_200)} />
      <Stat label="BB upper" value={fmt(data.indicators.bb_upper_20)} />
      <Stat label="BB lower" value={fmt(data.indicators.bb_lower_20)} />
      <Stat label="BB width" value={data.indicators.bb_width != null ? data.indicators.bb_width.toFixed(3) : "—"} />
      <Stat label="RSI(14)" value={data.indicators.rsi_14 != null ? data.indicators.rsi_14.toFixed(1) : "—"} />
      <Stat
        label="MRSI"
        value={
          data.indicators.mrsi != null
            ? `${data.indicators.mrsi > 0 ? "+" : ""}${data.indicators.mrsi.toFixed(3)}`
            : "—"
        }
        colorClass={
          data.indicators.mrsi != null
            ? data.indicators.mrsi > 0
              ? "text-green-600"
              : data.indicators.mrsi < 0
                ? "text-red-600"
                : undefined
            : undefined
        }
      />
      <Stat label="ATR(14)" value={data.indicators.atr_14 != null ? data.indicators.atr_14.toFixed(2) : "—"} />
      <Stat label="Vol MA(20)" value={fmt(data.indicators.volume_ma_20)} />
    </CardContent>
  </Card>
)}
{!data.indicators && (
  <Card>
    <CardContent className="text-sm text-muted-foreground py-4">
      No indicators yet for {data.symbol}. Run "Sync indicators" from the
      Sync IBKR pipeline.
    </CardContent>
  </Card>
)}

{/* Recent OHLCV table lands in Task 6 */}
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit 2>&1 | grep -v __tests__
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
cd /Users/louisgarnier/Claude/Stocks
git add frontend/components/security-detail/SecurityDetailSheet.tsx
git commit -m "[STORY-H-5] feat: indicators card in Security Detail Sheet

3-col grid showing all 11 indicator values: MA 50/100/150/200,
BB upper/lower/width, RSI(14), MRSI (color-coded green/red),
ATR(14), Volume MA(20). Empty-state card prompts user to run
indicators sync if no data.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Recent OHLCV bars table (both modes)

Last 30 bars in a scrollable table.

**Files:**
- Modify: `frontend/components/security-detail/SecurityDetailSheet.tsx`

- [ ] **Step 1: Add the bars table**

Replace the `{/* Recent OHLCV table lands in Task 6 */}` comment with:

```tsx
{data.bars.length > 0 && (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm">Recent bars ({data.bars.length})</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="rounded-md border max-h-72 overflow-auto">
        <Table>
          <TableHeader className="sticky top-0 bg-card">
            <TableRow>
              <TableHead className="text-xs">Date</TableHead>
              <TableHead className="text-right text-xs">Open</TableHead>
              <TableHead className="text-right text-xs">High</TableHead>
              <TableHead className="text-right text-xs">Low</TableHead>
              <TableHead className="text-right text-xs">Close</TableHead>
              <TableHead className="text-right text-xs">Volume</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.bars.map((b) => (
              <TableRow key={b.time}>
                <TableCell className="text-xs font-mono">{b.time}</TableCell>
                <TableCell className="text-right text-xs font-mono tabular-nums">{b.open != null ? b.open.toFixed(2) : "—"}</TableCell>
                <TableCell className="text-right text-xs font-mono tabular-nums">{b.high != null ? b.high.toFixed(2) : "—"}</TableCell>
                <TableCell className="text-right text-xs font-mono tabular-nums">{b.low != null ? b.low.toFixed(2) : "—"}</TableCell>
                <TableCell className="text-right text-xs font-mono tabular-nums font-semibold">{b.close != null ? b.close.toFixed(2) : "—"}</TableCell>
                <TableCell className="text-right text-xs font-mono tabular-nums">{b.volume != null ? b.volume.toLocaleString("en-US") : "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </CardContent>
  </Card>
)}
{data.bars.length === 0 && (
  <Card>
    <CardContent className="text-sm text-muted-foreground py-4">
      No market data yet for {data.symbol}. Run "Sync market data" from
      the Configuration tab.
    </CardContent>
  </Card>
)}
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit 2>&1 | grep -v __tests__
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
cd /Users/louisgarnier/Claude/Stocks
git add frontend/components/security-detail/SecurityDetailSheet.tsx
git commit -m "[STORY-H-6] feat: recent OHLCV table in Security Detail Sheet

Last 30 bars (newest first) in a scrollable table — date, OHLC
(2 decimals), volume (locale-formatted). Empty-state card prompts
user to run market_data sync if no data.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Wire row clicks (Browse Universe + Positions tab) and mount Sheet

Add `selectedSymbol` state at the top of `app/page.tsx`, render the Sheet once at the top level, wire row clicks in both surfaces.

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Add the import + state hook**

In `frontend/app/page.tsx`, add to the existing import block at the top:

```typescript
import { SecurityDetailSheet } from "@/components/security-detail/SecurityDetailSheet";
```

Add a state hook near the other useState calls (around the area where `coverageSearch` etc. live):

```typescript
const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
```

- [ ] **Step 2: Mount the Sheet at the top of the dashboard render**

Find the top-level `return (` in the `Dashboard` component. Inside the outer `<div>` that wraps the whole UI (the one with `min-h-screen` or similar), add the Sheet as the first child or right before `</div>`:

```tsx
<SecurityDetailSheet symbol={selectedSymbol} onClose={() => setSelectedSymbol(null)} />
```

(It's controlled by `symbol` — when null, the Sheet is closed.)

- [ ] **Step 3: Wire the Browse Universe row click**

Find the Browse Universe `<TableRow>` (search the file for `key={it.symbol}` inside the universe coverage table). Add an `onClick` handler and a hover style:

```tsx
<TableRow
  key={it.symbol}
  className="cursor-pointer hover:bg-secondary/40"
  onClick={() => setSelectedSymbol(it.symbol)}
>
```

- [ ] **Step 4: Wire the Positions tab row click**

Find the Positions tab's table rows (search for `getSortedAndFilteredPositions().map`). Each `<tr>` should also become clickable:

```tsx
<tr
  key={pos.symbol}
  style={{ borderBottom: '1px solid #e5e7eb', cursor: 'pointer' }}
  onClick={() => setSelectedSymbol(pos.symbol)}
>
```

(The Positions tab is still inline-styled, not shadcn — keep the inline style approach to avoid restyling the whole tab in this story.)

- [ ] **Step 5: Type-check**

```bash
cd /Users/louisgarnier/Claude/Stocks/frontend && npx tsc --noEmit 2>&1 | grep -v __tests__
```

Expected: no output.

- [ ] **Step 6: Visual sanity check**

Open `http://localhost:3000`:
- Configuration tab → Browse Universe → click "NVDA" row → Sheet slides in from the right with held badge, sources, position summary, transactions, indicators, recent bars.
- Positions tab → click NVDA → same Sheet appears.
- Configuration tab → click "AAPL" (in S&P 500 but not held) → Sheet shows "Not held" badge, no position card, no transactions, but does show indicators + bars.
- Click outside or press ESC → Sheet closes.

- [ ] **Step 7: Commit**

```bash
cd /Users/louisgarnier/Claude/Stocks
git add frontend/app/page.tsx
git commit -m "[STORY-H-7] feat: wire Sheet to Browse Universe + Positions row clicks

- Top-level selectedSymbol state in Dashboard
- SecurityDetailSheet mounted once at the root render
- Browse Universe table rows clickable → opens Sheet
- Positions tab rows clickable → opens Sheet
- ESC or click-outside closes via Sheet's controlled open state

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Live smoke test + push

Manual end-to-end verification.

- [ ] **Step 1: Restart backend (it has the new security route)**

```bash
cd /Users/louisgarnier/Claude/Stocks
lsof -ti:8000 | xargs kill -9 2>/dev/null; sleep 1
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m uvicorn backend.api.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/security/NVDA/detail
```
Expected: 200.

- [ ] **Step 2: Curl-check held vs not-held responses**

```bash
echo "--- NVDA (held) ---"
curl -s http://localhost:8000/api/security/NVDA/detail | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'held={d[\"is_held\"]}, tx={len(d[\"transactions\"])}, ind_mrsi={d[\"indicators\"][\"mrsi\"] if d[\"indicators\"] else None}, bars={len(d[\"bars\"])}')"

echo "--- AAPL (not held but in sp500) ---"
curl -s http://localhost:8000/api/security/AAPL/detail | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'held={d[\"is_held\"]}, tx={len(d[\"transactions\"])}, ind_mrsi={d[\"indicators\"][\"mrsi\"] if d[\"indicators\"] else None}, bars={len(d[\"bars\"])}')"
```

Expected:
- NVDA: `held=True`, tx=N, mrsi=~0.127, bars=30
- AAPL: `held=False`, tx=0, mrsi=some value, bars=30

- [ ] **Step 3: Browser sanity**

Open http://localhost:3000:
- Configuration tab → Browse Universe → click any row → Sheet opens with all sections populated.
- Click NVDA: should show held badge + position card + transactions + indicators + bars.
- Click AAPL (or any non-held S&P 500 row): should show not-held badge + no position card + indicators + bars.
- Press ESC or click outside → Sheet closes.

- [ ] **Step 4: Update build log + epics docs**

Append to `docs/project/config/build-log.md`:

```
## 2026-04-29 — Epic H v1 complete: Security Detail Sheet

8 stories shipped. Click any symbol anywhere → slide-in Sheet with
position info (held mode), latest indicators, transactions, recent
OHLCV bars. The inspector validates Epic D's per-symbol indicators
(MRSI, MAs, RSI) and gives every later epic (G, E, F) a place to
surface its data.

**Endpoints added:**
- GET /api/security/{symbol}/detail — combined per-symbol response

**Frontend additions:**
- shadcn Sheet component
- frontend/components/security-detail/SecurityDetailSheet.tsx
- Click handlers on Browse Universe rows + Positions tab rows
- ESC / click-outside closes

**Out of scope (Epic H follow-up):** mini price chart with MA overlays
(Recharts), sell simulator (avg-cost + realized P&L), buy/sell signal
checklist (depends on Epic G), "Open in Tech Analysis" link (depends
on Epic E), "Add to manual universe" CTA.

**Tests:** 4 new integration tests in test_security_routes.py.
```

Update `docs/project/config/epics/overview.md` to mark Epic H as `[x] Done v1` (or partial — pick one).

Update `docs/project/config/epics/ACTIVE.md` to point at Epic G as next.

- [ ] **Step 5: Commit + push**

```bash
git add docs/project/config/build-log.md docs/project/config/epics/overview.md docs/project/config/epics/ACTIVE.md
git commit -m "[STORY-H-8] docs: mark Epic H v1 complete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin newstart
```

---

## Out of Scope (Epic H follow-up or merged into G/E/F as they ship)

- Mini price chart with MA overlays (Recharts)
- Sell simulator (qty + price → realized P&L)
- Buy signal checklist (Mode B) and Sell signal checklist (Mode A) — depends on Epic G
- "Open in Tech Analysis" link — depends on Epic E
- "Add to manual universe" CTA in Mode B
- yfinance Ticker.info stats card (market cap, 52w range, beta) — needs caching layer

These can ship as additional Story H tasks (H-9 onward) once the inspector is in your hands and you've validated the data.

---

## Self-Review Notes

- **Spec coverage:** Click-to-inspect from any symbol-bearing surface ✅ (Browse Universe + Positions). Mode A held-mode (position + transactions) ✅. Mode B not-held mode (stats + indicators) ✅ — though "stats" in v1 = sources/sector/currency from tracked_universe, NOT market cap / 52w range from yfinance Ticker.info (deferred). Indicator card showing all 11 values ✅. Recent OHLCV ✅. Single backend endpoint ✅. Universal trigger ✅.

- **Placeholder scan:** All steps have actual code or exact commands. The "task 7 visual sanity check" is a manual step — explicit and bounded. No TBD/TODO/"similar to Task N".

- **Type consistency:** `SecurityDetail` interface defined once in Task 3, used unchanged in Tasks 4–6. `selectedSymbol` named consistently in Task 7 across state hook + Sheet prop + click handlers. Endpoint path `/api/security/{symbol}/detail` consistent across backend + frontend fetch. Empty-state messages reference the correct sync action ("Sync market data" / "Sync indicators").
