"""Sync run recorder — writes one row per sync action to sync_runs.

Used by every POST /api/sync/* endpoint plus the manual ticker add path.
Captures start/finish timestamps, status, a one-line summary, and a JSON
blob of details (per-step results, per-symbol failures, etc.).

Usage:
    from backend.utils.sync_recorder import record_run

    with record_run("market_data") as run:
        result = ingest_market_data()
        run.summary(f"{result['symbols_processed']} symbols · {result['rows_inserted']} new bars")
        run.details(result)
        if result.get("errors", 0) > 0:
            run.status("partial")
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from backend.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class _RunBuilder:
    """Mutable builder passed to the with-block so callers can set summary/details/status."""

    def __init__(self) -> None:
        self._summary: Optional[str] = None
        self._details: Any = None
        self._status: Optional[str] = None  # auto-derived if not set

    def summary(self, text: str) -> None:
        self._summary = text

    def details(self, payload: Any) -> None:
        self._details = payload

    def status(self, value: str) -> None:
        if value not in ("success", "partial", "error"):
            raise ValueError(f"status must be success|partial|error, got {value!r}")
        self._status = value


@contextmanager
def record_run(action: str) -> Iterator[_RunBuilder]:
    """Context manager that records a sync_runs row on exit.

    On exception inside the with-block: status='error', details includes the
    exception message, then the exception is re-raised so the caller's normal
    error path runs.
    """
    started = datetime.now(timezone.utc).astimezone()
    builder = _RunBuilder()
    error_msg: Optional[str] = None

    try:
        yield builder
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        if builder._status is None:
            builder._status = "error"
        if builder._details is None:
            builder._details = {"error": error_msg}
        elif isinstance(builder._details, dict):
            builder._details.setdefault("error", error_msg)
        raise
    finally:
        finished = datetime.now(timezone.utc).astimezone()
        duration_ms = int((finished - started).total_seconds() * 1000)
        if builder._status is None:
            builder._status = "success"
        details_json = json.dumps(builder._details, default=str) if builder._details is not None else None
        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO sync_runs (started_at, finished_at, duration_ms, action, status, summary, details_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    started.isoformat(),
                    finished.isoformat(),
                    duration_ms,
                    action,
                    builder._status,
                    builder._summary or (error_msg if error_msg else None),
                    details_json,
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            # Never let recorder failures break the actual sync action — just log.
            logger.error(f"⚠️  sync_runs write failed for action={action}: {e}")
