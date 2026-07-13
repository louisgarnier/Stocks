"""Tests for sync pipeline routes."""
import inspect
import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.routes import sync as sync_routes

client = TestClient(app)


def test_blocking_sync_endpoints_run_in_threadpool():
    """These endpoints call blocking I/O (yfinance ingest, requests.get flex
    pulls, DB writes) with no internal await; they MUST be plain `def` so
    FastAPI dispatches them to its threadpool, not `async def` — an `async def`
    would run the blocking work directly on the event loop and hang every other
    request (including GET /api/dashboard) for the sync's whole duration."""
    for name in ("sync_ibkr", "sync_market_data", "sync_fundamentals", "sync_analytics", "sync_screen"):
        fn = getattr(sync_routes, name)
        assert not inspect.iscoroutinefunction(fn), f"{name} must be plain def, not async def"


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

    with pytest.raises(RuntimeError, match="IBKR_FLEX_TOKEN"):
        flex.fetch_flex_response("last_month")


def test_fetch_flex_response_falls_back_to_unified_for_positions(monkeypatch, flex_xml_minimal):
    """When IBKR_QUERY_ID_positions is unset, helper falls back to IBKR_QUERY_ID_last_month."""
    import backend.scripts.fetch_flex_trades as flex

    used_query_id = []
    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: used_query_id.append(qid) or "REF123")
    monkeypatch.setattr(flex, "fetch_flex_results", lambda token, ref: flex_xml_minimal)
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.delenv("IBKR_QUERY_ID_positions", raising=False)
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    flex.fetch_flex_response("positions")
    assert used_query_id == ["9999"]


def test_sync_positions_writes_only_positions_table(temp_db, stub_flex_http, monkeypatch):
    """POST /api/sync/positions populates positions_ibkr and leaves transactions empty."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/positions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["positions_inserted"] == 1

    conn = sqlite3.connect(str(temp_db))
    pos_count = conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0]
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    assert pos_count == 1
    assert tx_count == 0


def test_sync_transactions_writes_only_transactions_table(temp_db, stub_flex_http, monkeypatch):
    """POST /api/sync/transactions populates transactions and leaves positions_ibkr empty."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/transactions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["inserted"] >= 1

    conn = sqlite3.connect(str(temp_db))
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    pos_count = conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0]
    ca_status = conn.execute(
        "SELECT status FROM corporate_actions_status WHERE sec_id='TEST'"
    ).fetchone()
    conn.close()
    assert tx_count == 1
    assert pos_count == 0
    assert ca_status is not None and ca_status[0] == "orange"


def test_sync_transactions_writes_import_log(temp_db, stub_flex_http, monkeypatch):
    """Each transactions sync should append a row to import_logs so the UI history shows it."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    resp = client.post("/api/sync/transactions")
    assert resp.status_code == 200, resp.text

    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT filename, inserted, status FROM import_logs ORDER BY id DESC LIMIT 1"
    ).fetchall()
    conn.close()
    assert rows and rows[0][0] == "api_sync_transactions"
    assert rows[0][2] == "success"


def test_sync_corporate_actions_returns_success(temp_db, monkeypatch):
    """POST /api/sync/corporate-actions wraps the existing CA refresh logic."""
    import backend.scripts.fetch_corporate_actions as ca
    monkeypatch.setattr(
        ca, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    resp = client.post("/api/sync/corporate-actions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "parsed" in body


def test_sync_splits_returns_success(temp_db, monkeypatch):
    """POST /api/sync/splits wraps the existing apply-splits logic."""
    import backend.scripts.apply_splits as aps
    monkeypatch.setattr(
        aps, "apply_all_splits",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )
    resp = client.post("/api/sync/splits")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True


def test_sync_full_runs_all_five_steps(temp_db, stub_flex_http, monkeypatch):
    """POST /api/sync/full runs positions, transactions, CAs, splits, indicators — in that order, with one Flex pull."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    import backend.scripts.fetch_corporate_actions as ca_mod
    import backend.scripts.apply_splits as aps_mod
    import backend.scripts.indicators_compute as ind_mod
    monkeypatch.setattr(
        ca_mod, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    monkeypatch.setattr(
        aps_mod, "apply_all_splits",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )
    monkeypatch.setattr(
        ind_mod, "compute_all",
        lambda conn: {"symbols_processed": [], "rows_written": 0, "errors": 0},
    )

    # Track Flex HTTP calls to confirm shared pull (one call, not two)
    call_log = []
    import backend.scripts.fetch_flex_trades as flex
    monkeypatch.setattr(flex, "request_flex_query", lambda token, qid: call_log.append(qid) or "REF123")

    resp = client.post("/api/sync/full")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert [s["name"] for s in body["steps"]] == ["positions", "transactions", "corporate_actions", "splits", "indicators", "holding_signals", "screen", "portfolio_history"]
    for s in body["steps"]:
        assert s["status"] == "ok", s

    assert len(call_log) == 1  # single shared Flex call

    conn = sqlite3.connect(str(temp_db))
    assert conn.execute("SELECT COUNT(*) FROM positions_ibkr").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
    conn.close()


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


def test_sync_indicators_endpoint(temp_db, monkeypatch):
    """POST /api/sync/indicators wraps compute_all()."""
    import backend.scripts.indicators_compute as ind
    monkeypatch.setattr(
        ind, "compute_all",
        lambda conn: {"symbols_processed": ["AAPL"], "rows_written": 60, "errors": 0},
    )
    resp = client.post("/api/sync/indicators")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["rows_written"] == 60
    assert "AAPL" in body["symbols_processed"]


def test_sync_full_includes_indicators_step(temp_db, stub_flex_http, monkeypatch):
    """/api/sync/full now runs an indicators step after splits."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    import backend.scripts.fetch_corporate_actions as ca_mod
    import backend.scripts.apply_splits as aps_mod
    import backend.scripts.indicators_compute as ind_mod
    monkeypatch.setattr(
        ca_mod, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    monkeypatch.setattr(
        aps_mod, "apply_all_splits",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )
    monkeypatch.setattr(
        ind_mod, "compute_all",
        lambda conn: {"symbols_processed": ["TEST"], "rows_written": 1, "errors": 0},
    )

    resp = client.post("/api/sync/full")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    step_names = [s["name"] for s in body["steps"]]
    assert step_names == ["positions", "transactions", "corporate_actions", "splits",
                          "indicators", "holding_signals", "screen", "portfolio_history"]
    for s in body["steps"]:
        assert s["status"] == "ok", s


def test_sync_ibkr_runs_only_ibkr_steps(temp_db, stub_flex_http, monkeypatch):
    """/api/sync/ibkr runs the four IBKR-side steps and stops — no analytics."""
    monkeypatch.setenv("IBKR_FLEX_TOKEN", "fake-token")
    monkeypatch.setenv("IBKR_QUERY_ID_last_month", "9999")

    import backend.scripts.fetch_corporate_actions as ca_mod
    import backend.scripts.apply_splits as aps_mod
    monkeypatch.setattr(
        ca_mod, "fetch_and_import_corporate_actions",
        lambda incremental=True: {"parsed": 0, "inserted": 0, "skipped": 0, "errors": 0, "updated_transactions": 0},
    )
    monkeypatch.setattr(
        aps_mod, "apply_all_splits",
        lambda: {"applied": 0, "skipped": 0, "errors": 0},
    )

    resp = client.post("/api/sync/ibkr")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    step_names = [s["name"] for s in body["steps"]]
    assert step_names == ["positions", "transactions", "corporate_actions", "splits"]
    for s in body["steps"]:
        assert s["status"] == "ok", s


def test_sync_analytics_runs_only_compute_steps(temp_db, monkeypatch):
    """/api/sync/analytics runs indicators + holding_signals + screen; no IBKR or yfinance.

    The screen step is chained so screen_signals can never go stale against
    freshly recomputed indicators (regression: signals stored 2026-07-01 were
    never recomputed while indicators advanced to 07-09)."""
    import backend.scripts.indicators_compute as ind_mod
    import backend.scripts.holding_signals_compute as sig_mod
    monkeypatch.setattr(
        ind_mod, "compute_all",
        lambda conn: {"symbols_processed": ["TEST"], "rows_written": 1, "errors": 0},
    )
    monkeypatch.setattr(
        sig_mod, "compute_all_signals",
        lambda conn: {"symbols_processed": 0, "signals_evaluated": 0},
    )

    resp = client.post("/api/sync/analytics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert [s["name"] for s in body["steps"]] == ["indicators", "holding_signals", "screen", "portfolio_history"]


def test_get_sync_runs_returns_recent_first(temp_db):
    """GET /api/sync/runs returns rows newest-first with pagination."""
    conn = sqlite3.connect(str(temp_db))
    for i, action in enumerate(["ibkr", "market_data", "analytics", "manual_add"]):
        conn.execute(
            "INSERT INTO sync_runs (started_at, finished_at, duration_ms, action, status, summary, details_json) "
            "VALUES (?, ?, ?, ?, 'success', ?, '{\"k\":\"v\"}')",
            (f"2026-05-05T10:0{i}:00+02:00", f"2026-05-05T10:0{i}:01+02:00", 1000, action, f"summary {i}"),
        )
    conn.commit()
    conn.close()

    r = client.get("/api/sync/runs")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4
    assert body["total"] == 4
    actions_in_order = [it["action"] for it in body["items"]]
    assert actions_in_order == ["manual_add", "analytics", "market_data", "ibkr"]
    assert body["items"][0]["details"] == {"k": "v"}


def test_get_sync_runs_filter_by_action(temp_db):
    conn = sqlite3.connect(str(temp_db))
    for action in ["ibkr", "market_data", "ibkr"]:
        conn.execute(
            "INSERT INTO sync_runs (started_at, action, status) VALUES (?, ?, 'success')",
            ("2026-05-05T10:00:00+02:00", action),
        )
    conn.commit()
    conn.close()

    r = client.get("/api/sync/runs?action=ibkr")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(it["action"] == "ibkr" for it in body["items"])


def test_sync_analytics_lifts_per_symbol_failures_to_top_level(temp_db, monkeypatch):
    """When indicators or signals computes report per-symbol failures, the
    finalize_run wrapper must lift them to the top-level details and downgrade
    the run status to 'partial' even if all steps themselves return 'ok'."""
    import backend.scripts.indicators_compute as ind_mod
    import backend.scripts.holding_signals_compute as sig_mod
    monkeypatch.setattr(
        ind_mod, "compute_all",
        lambda conn: {
            "symbols_processed": ["AAPL"], "rows_written": 1, "errors": 1,
            "failures": [{"symbol": "FAKE", "reason": "ZeroDivisionError: bench=0"}],
        },
    )
    monkeypatch.setattr(
        sig_mod, "compute_all_signals",
        lambda conn: {"symbols_processed": 1, "signals_evaluated": 11, "failures": []},
    )

    resp = client.post("/api/sync/analytics")
    assert resp.status_code == 200
    body = resp.json()
    # Both steps reported ok at the step level…
    assert all(s["status"] == "ok" for s in body["steps"])
    # …but the run got recorded as 'partial' with a failures list.
    conn = sqlite3.connect(str(temp_db))
    row = conn.execute(
        "SELECT status, summary, details_json FROM sync_runs WHERE action='analytics' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    import json
    assert row[0] == "partial"
    assert "FAKE" in row[1]
    details = json.loads(row[2])
    assert details["failures"] == [{"symbol": "FAKE", "reason": "ZeroDivisionError: bench=0", "step": "indicators"}]


def test_sync_analytics_does_not_call_flex(temp_db, monkeypatch):
    """Analytics endpoint is independent of IBKR — even with no Flex token, it succeeds."""
    monkeypatch.delenv("IBKR_FLEX_TOKEN", raising=False)

    flex_was_called = []
    import backend.scripts.fetch_flex_trades as flex_mod
    monkeypatch.setattr(
        flex_mod, "fetch_flex_response",
        lambda *a, **k: flex_was_called.append(a) or "<should-not-be-called/>",
    )
    import backend.scripts.indicators_compute as ind_mod
    import backend.scripts.holding_signals_compute as sig_mod
    monkeypatch.setattr(ind_mod, "compute_all", lambda conn: {"symbols_processed": [], "rows_written": 0, "errors": 0})
    monkeypatch.setattr(sig_mod, "compute_all_signals", lambda conn: {"symbols_processed": 0, "signals_evaluated": 0})

    resp = client.post("/api/sync/analytics")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert flex_was_called == []


def test_market_data_sync_survives_snapshot_failure(temp_db, monkeypatch):
    """A portfolio_history failure must not fail a successful market-data ingest.

    Even if compute_history raises after ingest succeeds and commits, the
    endpoint must return HTTP 200 with success=True (not 500 with 'Ingest crashed').
    """
    import backend.scripts.market_data_ingestor as ing
    import backend.scripts.portfolio_history_compute as ph

    # Successful ingest
    monkeypatch.setattr(
        ing, "ingest_market_data",
        lambda: {
            "symbols_processed": 1,
            "rows_inserted": 5,
            "errors": 0,
            "failures": [],
        },
    )

    # Portfolio history fails after ingest succeeds
    def boom(conn):
        raise RuntimeError("snapshot exploded")

    monkeypatch.setattr(ph, "compute_history", boom)

    resp = client.post("/api/sync/market-data")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["rows_inserted"] == 5
    assert "error" in body["portfolio_history"]
