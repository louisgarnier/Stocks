"""Holding signals API: sync, list, per-symbol, settings."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection
from backend.scripts.holding_signals_compute import compute_all_signals

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
        raise HTTPException(
            status_code=404,
            detail=f"unknown signal_type: {payload.signal_type}",
        )
    conn.commit()
    conn.close()
    return {"success": True, "signal_type": payload.signal_type}
