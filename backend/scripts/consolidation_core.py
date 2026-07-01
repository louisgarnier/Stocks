"""
Consolidation core — shared ZigZag + data-quality primitives.

⚠️ `calculate_zigzag` and `is_stock_data_quality` are a VERBATIM port from
docs/plans/features_pipe/d_breakout_detector_3.py (lines 105-132 and 134-214
respectively). The only changes are: converted from instance methods to
module-level functions taking `(df, params)`, and every `self.<attr>` became
`params["<attr>"]`. Every threshold, branch, and comparison is unchanged.
Do not "improve" or refactor this logic — see Task 7 brief.
"""
import json
from typing import Dict, List, Tuple

import pandas as pd

from backend.database.connection import get_db_connection  # noqa: E402


def is_stock_data_quality(df: pd.DataFrame, params: dict) -> Tuple[bool, str]:
    """Check data quality - EXACT same as original"""
    if len(df) < 10:
        return False, "insufficient_data"

    # Check for suspicious gaps
    df['price_change_pct'] = df['close'].pct_change().abs() * 100
    max_change = df['price_change_pct'].max()
    if max_change > params["max_daily_change"]:
        return False, f"suspicious_gap_{max_change:.1f}%"

    # Check volatility
    price_range = df['high'].max() - df['low'].min()
    avg_price = df['close'].mean()
    volatility_pct = (price_range / avg_price) * 100

    if volatility_pct > params["max_volatility_filter"]:
        return False, f"high_volatility_{volatility_pct:.1f}%"

    # Check volume
    avg_volume = df['volume'].mean()
    if avg_volume < params["min_volume_threshold"]:
        return False, f"low_volume_{avg_volume:.0f}"

    if df['low'].min() <= 0:
        return False, "invalid_prices"

    return True, "quality_ok"


def calculate_zigzag(df: pd.DataFrame, params: dict) -> List[Dict]:
    """Calculate ZigZag indicator - EXACT same as original"""
    if len(df) < 3:
        return []

    zigzag_points = []
    current_trend = None
    last_extreme = {
        'type': 'start',
        'price': df.iloc[0]['close'],
        'date': df.iloc[0]['time'],
        'index': 0,
        'high': df.iloc[0]['high'],
        'low': df.iloc[0]['low']
    }

    for i in range(1, len(df)):
        current_high = df.iloc[i]['high']
        current_low = df.iloc[i]['low']
        current_date = df.iloc[i]['time']

        # Check minimum days between swings
        days_diff = (current_date - last_extreme['date']).days
        if days_diff < params["min_days_between_swings"] and last_extreme['type'] != 'start':
            continue

        high_change_pct = ((current_high - last_extreme['price']) / last_extreme['price']) * 100
        low_change_pct = ((current_low - last_extreme['price']) / last_extreme['price']) * 100

        if high_change_pct >= params["zigzag_deviation"]:
            if current_trend == 'down' and last_extreme['type'] in ['trough', 'start']:
                zigzag_points.append(last_extreme)

            last_extreme = {
                'type': 'peak',
                'price': current_high,
                'date': current_date,
                'index': i,
                'high': current_high,
                'low': current_low
            }
            current_trend = 'up'

        elif low_change_pct <= -params["zigzag_deviation"]:
            if current_trend == 'up' and last_extreme['type'] in ['peak', 'start']:
                zigzag_points.append(last_extreme)

            last_extreme = {
                'type': 'trough',
                'price': current_low,
                'date': current_date,
                'index': i,
                'high': current_high,
                'low': current_low
            }
            current_trend = 'down'

        elif current_trend == 'up' and current_high > last_extreme['price']:
            last_extreme = {
                'type': 'peak',
                'price': current_high,
                'date': current_date,
                'index': i,
                'high': current_high,
                'low': current_low
            }

        elif current_trend == 'down' and current_low < last_extreme['price']:
            last_extreme = {
                'type': 'trough',
                'price': current_low,
                'date': current_date,
                'index': i,
                'high': current_high,
                'low': current_low
            }

    if last_extreme['type'] != 'start':
        zigzag_points.append(last_extreme)

    return zigzag_points


# Canonical seed — MUST mirror backend/database/schema.sql's
# `consolidation_params` row exactly. Guards against schema seed drift:
# a DB whose row is missing or partially populated (e.g. after a code
# deploy adds a new key that an existing finance.db's `INSERT OR IGNORE`
# seed never backfills) still yields every key the compute modules read
# via `params["key"]`, instead of raising KeyError for every symbol.
CONSOLIDATION_DEFAULTS = {
    "zigzag_deviation": 6.0,
    "lookback_days": 40,
    "min_days_between_swings": 2,
    "breakout_confirmation_pct": 1.5,
    "volume_lookback_days": 20,
    "min_resistance_touches": 2,
    "min_support_touches": 2,
    "extreme_grouping_tolerance": 2.5,
    "timeframes": [15, 30, 60],
    "max_consolidation_range_pct": 5.0,
    "min_consolidation_duration": 20,
    "max_daily_change": 30.0,
    "min_volume_threshold": 5000,
    "max_volatility_filter": 150.0,
    "channel_test_tolerance": 0.02,
    "min_touches_per_level": 2,
    "min_range_size_pct": 2.0,
    "min_bounces_in_channel": 3,
    # Previously-hardcoded consolidation gates, now tunable (R-2). Defaults keep
    # the original strict values so out-of-the-box breakout signals stay reliable;
    # loosen these in the app to surface more (lower-quality) candidates.
    "min_pct_in_channel": 70.0,        # % of bars that must sit inside the channel
    "min_boundary_touches": 4,          # min support+resistance boundary tests
    "min_pct_closes_in_channel": 85.0,  # % of closes that must sit inside the channel
}


def load_params(conn) -> dict:
    row = conn.execute("SELECT value_json FROM screener_settings WHERE key='consolidation_params'").fetchone()
    if not row:
        return dict(CONSOLIDATION_DEFAULTS)
    return {**CONSOLIDATION_DEFAULTS, **json.loads(row[0])}
