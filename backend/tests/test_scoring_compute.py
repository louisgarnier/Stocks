import json
import sqlite3

from backend.scripts.scoring_compute import score_symbol, compute_all

WEIGHTS = {"above_ma50":10,"above_ma200":10,"volume_spike":7,"breakout":12,
           "consolidation_quality":10,"momentum_60d_positive":10,"near_52w_high":5}

def test_fundamental_score_is_gates_over_7():
    fund = {"gates_passed": 6, "gates_total": 7}
    sig = {"above_ma50":1,"above_ma200":1,"volume_spike":0,"momentum_60d":8.0,"near_52w_high":1}
    r = score_symbol(fund, sig, cons=None, brk=None, weights=WEIGHTS)
    assert round(r["score_fund"], 1) == round(6/7*100, 1)
    assert 0 <= r["score_tech"] <= 100
    assert r["verdict"] in ("strong_buy","buy","watch","neutral","avoid")

def test_breakout_and_consolidation_add_tech_points():
    sig = {"above_ma50":1,"above_ma200":0,"volume_spike":1,"momentum_60d":5.0,"near_52w_high":0}
    cons = {"quality_score": 80.0}
    brk = {"breakout_direction": "bullish"}
    r = score_symbol({"gates_passed":3,"gates_total":7}, sig, cons, brk, WEIGHTS)
    assert "breakout" in r["tech_flags"]
    assert "consolidation_quality" in r["tech_flags"]


# ---- compute_all (DB layer) integration tests --------------------------------


def _seed_tracked(conn, symbol):
    conn.execute(
        "INSERT INTO tracked_universe (symbol, enabled, added_at) VALUES (?, 1, ?)",
        (symbol, "2026-06-01T00:00:00+00:00"),
    )


def _seed_good_symbol(conn, symbol="AAPL"):
    _seed_tracked(conn, symbol)
    conn.execute(
        "INSERT INTO screen_signals (symbol, date, above_ma50, above_ma200, volume_spike, "
        "momentum_60d, near_52w_high, multi_factor_momentum) VALUES (?,?,?,?,?,?,?,?)",
        (symbol, "2026-06-30", 1, 1, 0, 8.0, 1, 0.5),
    )
    conn.execute(
        "INSERT INTO fundamentals (symbol, gates_passed, gates_total) VALUES (?,?,?)",
        (symbol, 6, 7),
    )
    conn.execute(
        "INSERT INTO consolidation_patterns (symbol, quality_score) VALUES (?,?)",
        (symbol, 80.0),
    )
    conn.execute(
        "INSERT INTO breakout_signals (symbol, date, breakout_direction) VALUES (?,?,?)",
        (symbol, "2026-06-30", "bullish"),
    )


def test_compute_all_scores_and_upserts_symbol(temp_db):
    conn = sqlite3.connect(str(temp_db))
    _seed_good_symbol(conn, "AAPL")
    conn.commit()

    weights = json.loads(conn.execute(
        "SELECT value_json FROM screener_settings WHERE key='scoring_weights'").fetchone()[0])
    expected = score_symbol(
        {"gates_passed": 6, "gates_total": 7},
        {"above_ma50": 1, "above_ma200": 1, "volume_spike": 0, "momentum_60d": 8.0, "near_52w_high": 1},
        {"quality_score": 80.0},
        {"breakout_direction": "bullish"},
        weights,
    )

    result = compute_all(conn)

    row = conn.execute(
        "SELECT score_tech, score_fund, score_total, verdict, is_provisional, tech_flags, fund_flags "
        "FROM screen_scores WHERE symbol=? AND date=?",
        ("AAPL", "2026-06-30"),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == expected["score_tech"]
    assert row[1] == expected["score_fund"]
    assert row[2] == expected["score_total"]
    assert row[3] == expected["verdict"]
    assert row[4] == 1  # is_provisional
    assert row[5] == expected["tech_flags"]
    assert row[6] == expected["fund_flags"]
    assert result["errors"] == 0
    assert result["failures"] == []
    assert result["rows_written"] == 1


def test_compute_all_isolates_per_symbol_failures(temp_db):
    """A malformed row for one symbol must not abort scoring for the rest."""
    conn = sqlite3.connect(str(temp_db))
    _seed_good_symbol(conn, "AAPL")

    # BADCO: momentum_60d is a non-numeric string. score_symbol does
    # `(sig.get("momentum_60d") or 0) > 0`, which raises TypeError when
    # comparing a truthy str to an int — a realistic malformed-data case.
    _seed_tracked(conn, "BADCO")
    conn.execute(
        "INSERT INTO screen_signals (symbol, date, above_ma50, above_ma200, volume_spike, "
        "momentum_60d, near_52w_high) VALUES (?,?,?,?,?,?,?)",
        ("BADCO", "2026-06-30", 1, 0, 0, "bad", 0),
    )
    conn.commit()

    result = compute_all(conn)

    good_row = conn.execute(
        "SELECT score_total FROM screen_scores WHERE symbol=?", ("AAPL",)
    ).fetchone()
    bad_row = conn.execute(
        "SELECT score_total FROM screen_scores WHERE symbol=?", ("BADCO",)
    ).fetchone()
    conn.close()

    assert good_row is not None  # good symbol still scored despite BADCO failing
    assert bad_row is None  # bad symbol never got a row written
    assert result["errors"] == 1
    assert "BADCO" in result["failures"]
    assert result["rows_written"] == 1
