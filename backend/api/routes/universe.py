"""Universe management routes — tracked symbols and index lists."""
import json
from datetime import datetime
from typing import Optional, TypedDict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection


class TickerProbe(TypedDict, total=False):
    valid: bool
    reason: Optional[str]
    name: Optional[str]
    currency: Optional[str]
    exchange: Optional[str]
    sector: Optional[str]


def probe_ticker(symbol: str) -> TickerProbe:
    """Validate a ticker against yfinance and pull lightweight metadata.

    Returns {valid: bool, reason?, name?, currency?, exchange?, sector?}.
    Indirected so tests can monkeypatch without hitting the network.

    Validation: 5-day history must produce >= 1 bar with non-NaN Close.
    Catches the same failure modes as the ingestor: 404, empty df, all-NaN.
    Metadata: fast_info first (cheap), info as fallback (slower, can 404).
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"valid": True, "reason": None}  # offline / dev fallback — let it through

    try:
        ticker = yf.Ticker(symbol)
        h = ticker.history(period="5d")
        if h is None or h.empty:
            return {"valid": False, "reason": "yfinance returned no bars (ticker not found)"}
        if "Close" not in h.columns or h["Close"].dropna().empty:
            return {"valid": False, "reason": "yfinance returned bars but all Close values are NaN (delisted?)"}
    except Exception as e:
        return {"valid": False, "reason": f"yfinance probe failed: {type(e).__name__}: {e}"}

    name: Optional[str] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    try:
        fi = getattr(ticker, "fast_info", None)
        if fi is not None:
            currency = getattr(fi, "currency", None) or currency
            exchange = getattr(fi, "exchange", None) or exchange
    except Exception:
        pass
    try:
        info = ticker.info or {}
        name = info.get("longName") or info.get("shortName") or name
        currency = currency or info.get("currency")
        exchange = exchange or info.get("exchange")
        sector = info.get("sector")
    except Exception:
        pass

    return {
        "valid": True,
        "reason": None,
        "name": name,
        "currency": currency,
        "exchange": exchange,
        "sector": sector,
    }

router = APIRouter(prefix="/api/universe", tags=["universe"])

KNOWN_INDICES = ["sp500", "cac40", "nasdaq100", "dow30", "dax40", "ftse100"]

KNOWN_BENCHMARKS = [
    {"symbol": "^GSPC", "name": "S&P 500", "currency": "USD", "exchange": "INDEX"},
    {"symbol": "^FCHI", "name": "CAC 40", "currency": "EUR", "exchange": "INDEX"},
    {"symbol": "^GDAXI", "name": "DAX", "currency": "EUR", "exchange": "INDEX"},
    {"symbol": "^FTSE", "name": "FTSE 100", "currency": "GBP", "exchange": "INDEX"},
]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


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


def _ensure_indices_seeded(conn) -> None:
    """Populate tracked_indices with known names if missing (idempotent). Also seeds benchmark symbols."""
    for name in KNOWN_INDICES:
        conn.execute(
            "INSERT OR IGNORE INTO tracked_indices (name, enabled) VALUES (?, 0)",
            (name,),
        )
    _ensure_benchmarks_seeded(conn)
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
    """Return all enabled tracked symbols."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT symbol, name, sector, currency, exchange, benchmark, sources, "
        "enabled, added_at, last_synced_at FROM tracked_universe "
        "WHERE enabled=1 ORDER BY symbol"
    ).fetchall()
    conn.close()
    symbols = [_row_to_dict(r) for r in rows]
    return {"symbols": symbols, "count": len(symbols)}


SUFFIX_HINTS = (
    ".AS (Euronext Amsterdam) · .L (London) · .PA (Paris) · "
    ".DE (XETRA) · .SW (SIX Swiss) · .TO (Toronto) · .HK (Hong Kong)"
)


@router.post("/manual")
async def add_manual_symbol(req: ManualSymbolRequest):
    """Add a symbol with source='manual'. Validates against yfinance first.

    Rejects unknown tickers at add time with a helpful error including
    common exchange suffixes. Auto-fills name/currency/exchange/sector
    from yfinance metadata when available.
    """
    from backend.utils.sync_recorder import record_run

    sym = req.symbol.strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="symbol required")

    with record_run("manual_add") as run:
        # Validate against yfinance BEFORE inserting. Skip the probe if the
        # symbol already exists in our universe (e.g. ibkr_position) — we
        # don't want a transient yfinance hiccup to block a merge-add.
        conn = get_db_connection()
        existing = conn.execute(
            "SELECT sources FROM tracked_universe WHERE symbol = ?", (sym,)
        ).fetchone()

        probe: TickerProbe = {"valid": True}
        if existing is None:
            probe = probe_ticker(sym)
            if not probe.get("valid"):
                conn.close()
                run.summary(f"{sym} rejected: {probe.get('reason')}")
                run.details({"symbol": sym, "probe": dict(probe)})
                run.status("error")
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"'{sym}' not found in yfinance: {probe.get('reason')}. "
                        f"Try with an exchange suffix — common ones: {SUFFIX_HINTS}"
                    ),
                )

        existed = existing is not None
        if existing:
            sources = json.loads(existing[0] or "[]")
            if "manual" not in sources:
                sources.append("manual")
                conn.execute(
                    "UPDATE tracked_universe SET sources = ?, enabled = 1 WHERE symbol = ?",
                    (json.dumps(sources), sym),
                )
        else:
            conn.execute(
                "INSERT INTO tracked_universe "
                "(symbol, name, currency, exchange, sector, sources, enabled, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    sym,
                    probe.get("name"),
                    probe.get("currency"),
                    probe.get("exchange"),
                    probe.get("sector"),
                    json.dumps(["manual"]),
                    _now_iso(),
                ),
            )
        conn.commit()
        full = conn.execute(
            "SELECT symbol, name, sector, currency, exchange, benchmark, sources, "
            "enabled, added_at, last_synced_at FROM tracked_universe WHERE symbol = ?",
            (sym,),
        ).fetchone()
        conn.close()
        logger.info(f"📥 Added manual symbol: {sym}")
        if existed:
            run.summary(f"{sym} merged (manual tag)")
        else:
            meta_bits = [b for b in [probe.get("name"), probe.get("currency"), probe.get("exchange")] if b]
            run.summary(f"{sym} added" + (f" ({' · '.join(meta_bits)})" if meta_bits else ""))
        run.details({"symbol": sym, "existed": existed, "probe": dict(probe)})
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
    logger.info(f"🗑️ Removed manual source from: {sym} (remaining: {sources})")
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
    """Flip enabled flag for an index. Refreshing the symbol list is a separate endpoint."""
    if name not in KNOWN_INDICES:
        raise HTTPException(status_code=404, detail=f"unknown index: {name}")
    conn = get_db_connection()
    _ensure_indices_seeded(conn)
    row = conn.execute("SELECT enabled FROM tracked_indices WHERE name = ?", (name,)).fetchone()
    new_val = 0 if row[0] else 1
    conn.execute("UPDATE tracked_indices SET enabled = ? WHERE name = ?", (new_val, name))
    conn.commit()
    conn.close()
    logger.info(f"⚙️ Toggled index {name}: enabled={bool(new_val)}")
    return {"name": name, "enabled": bool(new_val)}


@router.get("/coverage")
async def get_universe_coverage():
    """Return every enabled symbol with bar count + latest close + latest indicator preview.

    Used by the Configuration tab Browse Universe table.
    """
    sql = """
        WITH bar_counts AS (
            SELECT symbol, COUNT(*) AS bars, MAX(time) AS latest_time
            FROM market_data
            GROUP BY symbol
        ),
        latest_close AS (
            SELECT md.symbol, md.close AS latest_close
            FROM market_data md
            JOIN bar_counts bc ON bc.symbol = md.symbol AND bc.latest_time = md.time
        ),
        latest_ind AS (
            SELECT i.symbol, i.ma_50, i.rsi_14, i.mrsi, i.bb_width
            FROM indicators i
            JOIN (
                SELECT symbol, MAX(time) AS t FROM indicators GROUP BY symbol
            ) m ON m.symbol = i.symbol AND m.t = i.time
        )
        SELECT tu.symbol, tu.name, tu.sources, tu.sector, tu.currency, tu.exchange,
               COALESCE(bc.bars, 0) AS bars, bc.latest_time,
               lc.latest_close,
               li.ma_50, li.rsi_14, li.mrsi, li.bb_width
        FROM tracked_universe tu
        LEFT JOIN bar_counts bc ON bc.symbol = tu.symbol
        LEFT JOIN latest_close lc ON lc.symbol = tu.symbol
        LEFT JOIN latest_ind li ON li.symbol = tu.symbol
        WHERE tu.enabled = 1
        ORDER BY tu.symbol
    """
    conn = get_db_connection()
    rows = conn.execute(sql).fetchall()
    conn.close()
    items = [
        {
            "symbol": r[0],
            "name": r[1],
            "sources": json.loads(r[2] or "[]"),
            "sector": r[3],
            "currency": r[4],
            "exchange": r[5],
            "bars": r[6],
            "latest_time": r[7],
            "latest_close": r[8],
            "ma_50": r[9],
            "rsi_14": r[10],
            "mrsi": r[11],
            "bb_width": r[12],
        }
        for r in rows
    ]
    return {"items": items, "count": len(items)}


@router.post("/indices/{name}/refresh")
async def refresh_index(name: str):
    """Re-fetch the index member list from its source and upsert into tracked_universe."""
    from backend.scripts.universe_seeders import seed_index, _INDEX_CONFIG
    if name not in _INDEX_CONFIG:
        raise HTTPException(status_code=404, detail=f"unknown index: {name}")
    try:
        result = seed_index(name)
        logger.info(f"📥 Refreshed index {name}: inserted={result['inserted']}, updated={result['updated']}, count={result['count']}")
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ refresh_index({name}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
