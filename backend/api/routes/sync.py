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
from backend.utils.sync_recorder import record_run

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


@router.get("/runs")
async def list_sync_runs(action: str | None = None, limit: int = 100, offset: int = 0):
    """List recent sync runs ordered newest-first.

    Filter by action (ibkr|market_data|analytics|manual_add) via ?action=.
    Pagination via ?limit + ?offset (default 100 / 0).
    """
    import json as _json
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    conn = get_db_connection()
    sql = (
        "SELECT id, started_at, finished_at, duration_ms, action, status, summary, details_json "
        "FROM sync_runs"
    )
    params: tuple = ()
    if action:
        sql += " WHERE action = ?"
        params = (action,)
    sql += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
    rows = conn.execute(sql, params + (limit, offset)).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM sync_runs" + (" WHERE action = ?" if action else ""),
        (action,) if action else (),
    ).fetchone()[0]
    conn.close()
    return {
        "items": [
            {
                "id": r[0],
                "started_at": r[1],
                "finished_at": r[2],
                "duration_ms": r[3],
                "action": r[4],
                "status": r[5],
                "summary": r[6],
                "details": _json.loads(r[7]) if r[7] else None,
            }
            for r in rows
        ],
        "count": len(rows),
        "total": total,
    }


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
    _run(steps, "holding_signals", _step_holding_signals)
    return _wrap(steps)


@router.post("/ibkr")
async def sync_ibkr():
    """IBKR-only pipeline: positions, transactions, corporate_actions, splits.

    Independent of yfinance and local compute. A failure here never blocks
    market-data ingest or analytics — those are reachable via their own
    dedicated endpoints.
    """
    logger.info("🚀 Sync step: IBKR pipeline")
    with record_run("ibkr") as run:
        steps: list = []

        try:
            xml = fetch_flex_response("last_month")
        except Exception as e:
            steps.append({"name": "positions", "status": "error", "error": str(e)})
            run.summary(f"Flex pull failed: {e}")
            run.details({"steps": steps})
            run.status("error")
            return {"success": False, "steps": steps}

        if not _run(steps, "positions", lambda: _step_positions(xml)):
            return _finalize_run(run, steps)
        if not _run(steps, "transactions", lambda: _step_transactions(xml)):
            return _finalize_run(run, steps)
        if not _run(steps, "corporate_actions", _step_corporate_actions):
            return _finalize_run(run, steps)
        _run(steps, "splits", _step_splits)
        return _finalize_run(run, steps)


@router.post("/analytics")
async def sync_analytics():
    """Recompute analytics: indicators, then holding signals.

    Pure local compute against already-stored market_data + positions_ibkr.
    No external API calls — safe to run anytime, independent of IBKR Flex
    or yfinance availability.
    """
    logger.info("📐 Sync step: analytics (indicators + holding_signals)")
    with record_run("analytics") as run:
        steps: list = []
        _run(steps, "indicators", _step_indicators)
        _run(steps, "holding_signals", _step_holding_signals)
        return _finalize_run(run, steps)


# Canonical seed — MUST mirror backend/database/schema.sql's `retention` row
# exactly. See CONSOLIDATION_DEFAULTS in consolidation_core.py for why:
# guards against a missing/partial row after seed-drift (previously a
# missing ROW crashed `.fetchone()[0]` on None outright).
RETENTION_DEFAULTS = {
    "breakout_fresh_days": 3,
    "breakout_retention_days": 30,
    "screen_scores_retention_days": 60,
}


def _load_retention(conn) -> dict:
    row = conn.execute(
        "SELECT value_json FROM screener_settings WHERE key='retention'").fetchone()
    if not row:
        return dict(RETENTION_DEFAULTS)
    import json
    return {**RETENTION_DEFAULTS, **json.loads(row[0])}


def _prune_retention(conn) -> dict:
    from datetime import datetime, timedelta, timezone
    ret = _load_retention(conn)
    today = datetime.now(timezone.utc).date()
    brk_cut = (today - timedelta(days=int(ret.get("breakout_retention_days", 30)))).isoformat()
    sc_cut = (today - timedelta(days=int(ret.get("screen_scores_retention_days", 60)))).isoformat()
    b = conn.execute("DELETE FROM breakout_signals WHERE date < ?", (brk_cut,)).rowcount
    s = conn.execute("DELETE FROM screen_scores WHERE date < ?", (sc_cut,)).rowcount
    conn.commit()
    return {"breakout_signals_pruned": b, "screen_scores_pruned": s}


@router.post("/screen")
async def sync_screen():
    logger.info("🔎 Sync step: screen")
    with record_run("screen") as run:
        from backend.scripts import (screen_signals_compute, consolidation_compute,
                                     breakout_compute, scoring_compute)
        conn = get_db_connection()
        try:
            steps = {
                "screen_signals": screen_signals_compute.compute_all(conn),
                "consolidation": consolidation_compute.compute_all(conn),
                "breakout": breakout_compute.compute_all(conn),
                "scoring": scoring_compute.compute_all(conn),
            }
            pruned = _prune_retention(conn)
        finally:
            conn.close()
        total_fail = sum(len(s.get("failures", [])) for s in steps.values())
        run.summary(f"signals/cons/brk/score done · {total_fail} failures · pruned "
                    f"{pruned['breakout_signals_pruned']}+{pruned['screen_scores_pruned']}")
        run.details({"steps": steps, "pruned": pruned})
        if total_fail:
            run.status("partial")
        return {"success": True, "steps": steps, "pruned": pruned}


def _finalize_run(run, steps: list) -> dict:
    """Wrap the steps list into a response and update the recorder builder.

    If any step's result includes a per-symbol `failures` list, lift them
    to a top-level details key so the UI can render them uniformly. Also
    downgrade status to "partial" when any per-symbol failure occurred,
    even if every step itself reported "ok".
    """
    success = all(s["status"] == "ok" for s in steps)
    n_ok = sum(1 for s in steps if s["status"] == "ok")
    n_err = len(steps) - n_ok

    all_failures: list = []
    for s in steps:
        result = s.get("result") if isinstance(s.get("result"), dict) else None
        if result and isinstance(result.get("failures"), list):
            for f in result["failures"]:
                all_failures.append({**f, "step": s["name"]})

    summary_bits = [f"{n_ok} ok", f"{n_err} error"]
    if all_failures:
        sample = ", ".join(f["symbol"] for f in all_failures[:3])
        if len(all_failures) > 3:
            sample += "…"
        summary_bits.append(f"{len(all_failures)} per-symbol failures ({sample})")
    if n_err:
        first_err = next(s["name"] for s in steps if s["status"] == "error")
        summary_bits.append(f"failed at: {first_err}")

    run.summary(" · ".join(summary_bits))
    run.details({"steps": steps, "failures": all_failures} if all_failures else {"steps": steps})

    if not success:
        run.status("partial" if n_ok > 0 else "error")
    elif all_failures:
        run.status("partial")
    return {"success": success, "steps": steps}


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
    with record_run("market_data") as run:
        try:
            from backend.scripts.market_data_ingestor import ingest_market_data
            result = ingest_market_data()
        except Exception as e:
            logger.error(f"❌ sync_market_data failed: {e}")
            run.summary(f"Ingest crashed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        n_failures = len(result.get("failures", []))
        failure_syms = [f["symbol"] for f in result.get("failures", [])][:5]
        summary_bits = [
            f"{result['symbols_processed']} symbols",
            f"{result['rows_inserted']:,} new bars",
        ]
        if n_failures:
            sample = ", ".join(failure_syms) + ("…" if n_failures > 5 else "")
            summary_bits.append(f"{n_failures} dropped ({sample})")
        run.summary(" · ".join(summary_bits))
        run.details(result)
        if n_failures > 0 or result.get("errors", 0) > 0:
            run.status("partial")
        return {"success": True, **result}


@router.post("/fundamentals")
async def sync_fundamentals():
    """Fetch and store fundamental metrics for all enabled symbols in tracked_universe."""
    logger.info("🏦 Sync step: fundamentals")
    with record_run("fundamentals") as run:
        try:
            result = _step_fundamentals()
        except Exception as e:
            logger.error(f"❌ sync_fundamentals failed: {e}")
            run.summary(f"Fundamentals crashed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        n_fail = len(result.get("failures", []))
        run.summary(f"{len(result['symbols_processed'])} symbols · {result['rows_written']} rows · {n_fail} failures")
        run.details(result)
        if n_fail or result.get("errors", 0):
            run.status("partial")
        return {"success": True, **result}


@router.get("/fundamentals/status")
async def fundamentals_status():
    """Get last run, suggested next run (30-day cadence), and overdue flag."""
    from datetime import datetime, timedelta, timezone
    conn = get_db_connection()
    row = conn.execute(
        "SELECT finished_at FROM sync_runs WHERE action='fundamentals' AND status != 'error' "
        "ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return {"last_run": None, "suggested_next": None, "overdue": True}
    last = datetime.fromisoformat(row[0])
    nxt = last + timedelta(days=30)
    overdue = datetime.now(timezone.utc) >= nxt.replace(tzinfo=nxt.tzinfo or timezone.utc)
    return {"last_run": row[0], "suggested_next": nxt.isoformat(), "overdue": overdue}


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


def _step_fundamentals() -> dict:
    from backend.scripts.fundamentals_fetch import fetch_all
    from backend.scripts import scoring_compute
    conn = get_db_connection()
    try:
        result = fetch_all(conn)
        # fundamentals feed score_fund — rescore so verdicts reflect the fresh data
        rescore = scoring_compute.compute_all(conn)
        result["rescored"] = rescore.get("rows_written", 0)
        return result
    finally:
        conn.close()


def _step_holding_signals() -> dict:
    from backend.scripts.holding_signals_compute import compute_all_signals
    conn = get_db_connection()
    try:
        return compute_all_signals(conn)
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
