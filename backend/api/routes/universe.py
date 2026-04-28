"""Universe management routes — tracked symbols and index lists."""
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection

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
    logger.info(f"📥 Added manual symbol: {sym}")
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
