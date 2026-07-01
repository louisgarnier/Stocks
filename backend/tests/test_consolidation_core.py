import json
import sqlite3

import pandas as pd
from backend.scripts.consolidation_core import calculate_zigzag, is_stock_data_quality, load_params

PARAMS = {"zigzag_deviation": 6.0, "min_days_between_swings": 2, "max_daily_change": 30.0,
          "min_volume_threshold": 5000, "max_volatility_filter": 150.0}

def _osc_df(n=40):
    # oscillating series that must produce >=2 peaks and >=2 troughs
    prices = []
    for i in range(n):
        prices.append(100 + (8 if i % 8 < 4 else -8))
    return pd.DataFrame({
        "time": pd.to_datetime(pd.date_range("2026-01-01", periods=n)),
        "open": prices, "high": [p + 1 for p in prices], "low": [p - 1 for p in prices],
        "close": prices, "volume": [1_000_000] * n})

def test_zigzag_finds_swings():
    pts = calculate_zigzag(_osc_df(), PARAMS)
    assert len([p for p in pts if p["type"] == "peak"]) >= 1
    assert len([p for p in pts if p["type"] == "trough"]) >= 1

def test_quality_rejects_low_volume():
    df = _osc_df(); df["volume"] = 10
    ok, reason = is_stock_data_quality(df, PARAMS)
    assert ok is False and "low_volume" in reason


REQUIRED_KEYS = [
    "channel_test_tolerance", "min_touches_per_level", "min_range_size_pct",
    "zigzag_deviation", "max_daily_change",
]


def test_load_params_missing_row_falls_back_to_all_defaults(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("DELETE FROM screener_settings WHERE key='consolidation_params'")
    conn.commit()

    params = load_params(conn)
    conn.close()

    for key in REQUIRED_KEYS:
        assert key in params, f"missing required key {key!r} when row absent"
    assert params["zigzag_deviation"] == 6.0
    assert params["channel_test_tolerance"] == 0.02


def test_load_params_partial_row_fills_missing_keys_and_keeps_overrides(temp_db):
    conn = sqlite3.connect(str(temp_db))
    partial = {"zigzag_deviation": 9.0}  # missing channel_test_tolerance and friends; overrides zigzag_deviation
    conn.execute(
        "UPDATE screener_settings SET value_json=? WHERE key='consolidation_params'",
        (json.dumps(partial),),
    )
    conn.commit()

    params = load_params(conn)
    conn.close()

    for key in REQUIRED_KEYS:
        assert key in params, f"missing required key {key!r} on partial row"
    assert params["zigzag_deviation"] == 9.0  # DB value overrides default
    assert params["min_touches_per_level"] == 2  # falls back to canonical default
    assert params["min_range_size_pct"] == 2.0
    assert params["max_daily_change"] == 30.0
