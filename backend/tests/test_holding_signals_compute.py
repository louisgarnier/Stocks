"""Tests for holding signals compute and storage."""
import sqlite3


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
