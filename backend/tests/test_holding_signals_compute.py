"""Tests for holding signals compute and storage."""
import sqlite3

import pytest


def test_schema_creates_holding_signals_and_settings_tables(temp_db):
    conn = sqlite3.connect(str(temp_db))
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert "holding_signals" in tables
    assert "signal_settings" in tables


def test_signal_settings_seeded_with_11_defaults(temp_db):
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute(
        "SELECT signal_type, enabled, threshold FROM signal_settings ORDER BY signal_type"
    ).fetchall()
    conn.close()
    types = {r[0] for r in rows}
    assert types == {
        "ma50_break", "ma100_break", "ma150_break", "ma200_break",
        "death_cross", "volume_dryup", "distribution_day",
        "rsi_weakness", "mrsi_flip",
        "trailing_drawdown", "stop_loss",
    }
    by_type = {r[0]: r for r in rows}
    assert by_type["trailing_drawdown"][2] == 0.10
    assert by_type["stop_loss"][2] == 0.08
    assert all(r[1] == 1 for r in rows)


# ---- Evaluator unit tests ---------------------------------------------------

from backend.scripts.holding_signals_compute import (
    eval_ma_break,
    eval_death_cross,
    eval_volume_dryup,
    eval_distribution_day,
    eval_rsi_weakness,
    eval_mrsi_flip,
    eval_trailing_drawdown,
    eval_stop_loss,
    compute_all_signals,
)


def test_ma_break_fires_when_close_below_ma():
    fired, value, threshold = eval_ma_break(close=138.40, ma=145.20)
    assert fired is True
    assert value == 138.40
    assert threshold == 145.20


def test_ma_break_does_not_fire_when_close_above_ma():
    fired, _, _ = eval_ma_break(close=150.00, ma=145.20)
    assert fired is False


def test_ma_break_returns_not_fired_when_ma_is_none():
    fired, value, threshold = eval_ma_break(close=138.40, ma=None)
    assert fired is False
    assert threshold is None


def test_death_cross_fires_on_today_crossover():
    fired, _, _ = eval_death_cross(
        ma50_today=145, ma150_today=146,
        ma50_yesterday=148, ma150_yesterday=147,
    )
    assert fired is True


def test_death_cross_no_fire_when_already_below_yesterday():
    fired, _, _ = eval_death_cross(
        ma50_today=145, ma150_today=146,
        ma50_yesterday=144, ma150_yesterday=145,
    )
    assert fired is False


def test_volume_dryup_fires_when_5d_below_half_of_20d():
    fired, value, threshold = eval_volume_dryup(avg_5d=400_000, avg_20d=1_000_000)
    assert fired is True
    assert value == 400_000
    assert threshold == 500_000


def test_volume_dryup_no_fire_when_5d_above_half():
    fired, _, _ = eval_volume_dryup(avg_5d=600_000, avg_20d=1_000_000)
    assert fired is False


def test_distribution_day_fires_on_down_day_high_volume():
    fired, _, _ = eval_distribution_day(
        close=98, prev_close=100, volume=2_000_000, vol_ma_20=1_000_000,
    )
    assert fired is True


def test_distribution_day_no_fire_on_up_day():
    fired, _, _ = eval_distribution_day(
        close=102, prev_close=100, volume=2_000_000, vol_ma_20=1_000_000,
    )
    assert fired is False


def test_rsi_weakness_fires_when_drops_below_50_from_above():
    fired, _, _ = eval_rsi_weakness(rsi_today=48, rsi_yesterday=52)
    assert fired is True


def test_rsi_weakness_no_fire_when_already_below():
    fired, _, _ = eval_rsi_weakness(rsi_today=48, rsi_yesterday=49)
    assert fired is False


def test_mrsi_flip_fires_when_crosses_below_zero():
    fired, _, _ = eval_mrsi_flip(mrsi_today=-0.05, mrsi_yesterday=0.10)
    assert fired is True


def test_mrsi_flip_no_fire_when_still_positive():
    fired, _, _ = eval_mrsi_flip(mrsi_today=0.02, mrsi_yesterday=0.10)
    assert fired is False


def test_trailing_drawdown_fires_at_default_10pct():
    fired, value, threshold = eval_trailing_drawdown(
        close=178, high_30d=200, drawdown_pct=0.10,
    )
    assert fired is True
    assert value == 178
    assert threshold == 180.0


def test_trailing_drawdown_no_fire_at_5pct_when_threshold_10pct():
    fired, _, _ = eval_trailing_drawdown(close=190, high_30d=200, drawdown_pct=0.10)
    assert fired is False


def test_stop_loss_fires_when_close_below_threshold():
    fired, value, threshold = eval_stop_loss(
        close=91, cost_basis_price=100, drawdown_pct=0.08,
    )
    assert fired is True
    assert threshold == 92.0


def test_stop_loss_no_fire_when_above_threshold():
    fired, _, _ = eval_stop_loss(close=95, cost_basis_price=100, drawdown_pct=0.08)
    assert fired is False


# ---- Orchestrator integration tests ----------------------------------------


def _seed_held_symbol(temp_db, symbol="NVDA"):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
        "VALUES (?, 10, 100, 'USD')", (symbol,)
    )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_100, ma_150, ma_200, "
        "rsi_14, mrsi, volume_ma_20) "
        "VALUES (?, '2026-04-27', 110, 108, 109, 105, 55, 0.05, 1000000)", (symbol,)
    )
    conn.execute(
        "INSERT INTO indicators (symbol, time, ma_50, ma_100, ma_150, ma_200, "
        "rsi_14, mrsi, volume_ma_20) "
        "VALUES (?, '2026-04-28', 100, 105, 110, 108, 48, -0.02, 1000000)", (symbol,)
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
        "VALUES (?, '2026-04-27', 99, 100, 98, 99, 1100000)", (symbol,)
    )
    conn.execute(
        "INSERT INTO market_data (symbol, time, open, high, low, close, volume) "
        "VALUES (?, '2026-04-28', 99, 99, 84, 85, 1800000)", (symbol,)
    )
    conn.commit()
    conn.close()


def test_orchestrator_evaluates_and_upserts(temp_db):
    _seed_held_symbol(temp_db)
    conn = sqlite3.connect(str(temp_db))
    result = compute_all_signals(conn)
    rows = conn.execute(
        "SELECT signal_type, fired FROM holding_signals WHERE symbol='NVDA'"
    ).fetchall()
    conn.close()
    by_type = {r[0]: bool(r[1]) for r in rows}
    assert by_type["ma50_break"] is True
    assert by_type["death_cross"] is True
    assert by_type["rsi_weakness"] is True
    assert by_type["mrsi_flip"] is True
    assert by_type["stop_loss"] is True
    assert result["symbols_processed"] == 1


def test_orchestrator_deletes_rows_for_sold_out_symbols(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO holding_signals (symbol, signal_type, fired, last_evaluated_at) "
        "VALUES ('OLDCO', 'ma50_break', 1, '2026-04-01')"
    )
    conn.commit()
    compute_all_signals(conn)
    cnt = conn.execute(
        "SELECT COUNT(*) FROM holding_signals WHERE symbol='OLDCO'"
    ).fetchone()[0]
    conn.close()
    assert cnt == 0
