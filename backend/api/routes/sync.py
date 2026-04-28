"""Sync pipeline routes — independent steps + orchestrator.

Each step is an independent endpoint. The /full orchestrator runs all four
in sequence, sharing a single Flex Query response across the positions and
transactions steps to avoid double-fetching.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from backend.api.utils.logger import logger
from backend.database.connection import get_db_connection
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
        _sync_positions_to_universe()
        return {
            "success": True,
            "positions_inserted": result["positions_inserted"],
            "last_updated": result["last_updated"],
        }
    except Exception as e:
        logger.error(f"❌ sync_positions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transactions")
async def sync_transactions():
    """Pull trades from IBKR; write only the transactions table; flag affected symbols as CA-orange."""
    logger.info("📋 Sync step: transactions")
    try:
        xml = fetch_flex_response("trades_last_month")
        trades = parse_trades_from_xml(xml)
        result = insert_flex_trades(trades, source_file="api_sync_transactions")
        _flag_orange(result.get("inserted_symbols", []))
        _log_import("api_sync_transactions", result)
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
        from backend.scripts.apply_splits import apply_all_splits
        result = apply_all_splits()
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ sync_splits failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full")
async def sync_full():
    """Run the full pipeline: positions, transactions, corporate actions, splits.

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


def _run(steps: list, name: str, fn) -> bool:
    try:
        result = fn()
        steps.append({"name": name, "status": "ok", "result": result})
        return True
    except Exception as e:
        logger.error(f"❌ Step '{name}' failed: {e}")
        steps.append({"name": name, "status": "error", "error": str(e)})
        return False


def _wrap(steps: list) -> dict:
    success = all(s["status"] == "ok" for s in steps)
    return {"success": success, "steps": steps}


def _step_positions(xml: str) -> dict:
    result = save_positions_ibkr(parse_positions_from_xml(xml))
    _sync_positions_to_universe()
    return result


def _step_transactions(xml: str) -> dict:
    result = insert_flex_trades(parse_trades_from_xml(xml), source_file="api_sync_full")
    _flag_orange(result.get("inserted_symbols", []))
    _log_import("api_sync_full", result)
    return result


def _step_corporate_actions() -> dict:
    from backend.scripts.fetch_corporate_actions import fetch_and_import_corporate_actions
    return fetch_and_import_corporate_actions(incremental=True)


def _step_splits() -> dict:
    from backend.scripts.apply_splits import apply_all_splits
    return apply_all_splits()


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


def _flag_orange(symbols: list) -> None:
    if not symbols:
        return
    from backend.utils.ca_status import set_ca_status
    try:
        set_ca_status(symbols, "orange")
    except Exception as e:
        logger.warning(f"⚠️  CA status update failed: {e}")


def _log_import(source_file: str, result: dict) -> None:
    """Append a row to import_logs so the Load tab's history surfaces this sync."""
    errors = result.get("errors", 0) or 0
    status = "success" if errors == 0 else "partial"
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO import_logs (filename, import_date, parsed, inserted, skipped, errors, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                source_file,
                datetime.now().astimezone().isoformat(),
                result.get("fetched", 0) or 0,
                result.get("inserted", 0) or 0,
                result.get("skipped", 0) or 0,
                errors,
                status,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"⚠️  import_logs write failed for {source_file}: {e}")
