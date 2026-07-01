"""
Consolidation compute — multi-timeframe quality-scored consolidation detection.

⚠️ `detect_price_channels`, `_group_similar_levels`, `_is_valid_channel`,
`calculate_zigzag_within_channel`, `create_support_zones`, `create_resistance_zones`,
`detect_consolidation_patterns_hybrid`, `calculate_volume_behavior_score`,
`calculate_quality_score`, and `analyze_stock_consolidations` (-> `analyze_symbol`) are a
VERBATIM port from docs/plans/features_pipe/g_consolidation.py (lines 159-934, see
docstrings on each function for the exact source range). The only changes are:
  1. Converted from instance methods (`AdvancedConsolidationDetector`) to module-level
     functions taking `(df, params)`.
  2. `self.config.<attr>` -> `params["<attr>"]`; `getattr(self.config, 'x', default)` ->
     `params.get("x", default)`.
  3. `self.timeframes` (built from `self.config.get_timeframes()`) -> built from
     `params["timeframes"]` as `{f"{d}d": d for d in params["timeframes"]}`.
  4. `analyze_stock_consolidations`'s original `self.load_stock_data(symbol, 80)` call is
     removed — `analyze_symbol` receives `df` already loaded by the caller.
  5. The quality check previously performed by g's own `is_stock_data_quality` method is
     replaced with the shared core function `consolidation_core.is_stock_data_quality`
     (same signature: returns `(bool, reason)`), per the plan's intentional sharing of
     that logic between g_consolidation and d_breakout_detector_3 ports.

All `print(...)` calls from the original were stripped. Every threshold, branch, and
comparison is otherwise unchanged. Do not "improve" or refactor this logic — see Task 8
brief.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import pandas as pd

from backend.scripts.consolidation_core import is_stock_data_quality, load_params
from backend.database.connection import get_db_connection  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verbatim port of g_consolidation.py (AdvancedConsolidationDetector methods)
# ---------------------------------------------------------------------------

def detect_price_channels(df: pd.DataFrame, params: dict) -> List[Dict]:
    """Detect horizontal price channels for consolidation.

    Verbatim port of g_consolidation.py:159-239 (detect_price_channels).
    """
    if len(df) < params["min_consolidation_duration"]:
        return []

    # Calculate rolling statistics
    window = min(10, len(df) // 3)  # Adaptive window size
    df_temp = df.copy()
    df_temp['rolling_high'] = df_temp['high'].rolling(window=window, center=True).max()
    df_temp['rolling_low'] = df_temp['low'].rolling(window=window, center=True).min()

    # Find potential support and resistance levels
    resistance_candidates = []
    support_candidates = []

    # Look for horizontal levels with multiple touches
    for i in range(window, len(df_temp) - window):
        current_high = df_temp.iloc[i]['high']
        current_low = df_temp.iloc[i]['low']

        # Check for resistance level
        nearby_highs = df_temp.iloc[i-window:i+window+1]['high']
        tolerance = current_high * params["channel_test_tolerance"]

        touches_resistance = len(nearby_highs[(nearby_highs >= current_high - tolerance) &
                                             (nearby_highs <= current_high + tolerance)])

        if touches_resistance >= params["min_touches_per_level"]:
            resistance_candidates.append({
                'level': current_high,
                'touches': touches_resistance,
                'index': i,
                'date': df_temp.iloc[i]['time']
            })

        # Check for support level
        nearby_lows = df_temp.iloc[i-window:i+window+1]['low']
        tolerance = current_low * params["channel_test_tolerance"]

        touches_support = len(nearby_lows[(nearby_lows >= current_low - tolerance) &
                                         (nearby_lows <= current_low + tolerance)])

        if touches_support >= params["min_touches_per_level"]:
            support_candidates.append({
                'level': current_low,
                'touches': touches_support,
                'index': i,
                'date': df_temp.iloc[i]['time']
            })

    # Filter and group similar levels
    resistance_levels = _group_similar_levels(resistance_candidates, 'resistance')
    support_levels = _group_similar_levels(support_candidates, 'support')

    # Create valid channels
    channels = []
    for resistance in resistance_levels:
        for support in support_levels:
            # Check if this forms a valid consolidation channel
            if _is_valid_channel(df_temp, support, resistance, params):
                channels.append({
                    'support_level': support,
                    'resistance_level': resistance,
                    'range_pct': ((resistance['level'] - support['level']) / support['level']) * 100
                })

    return channels


def _group_similar_levels(candidates: List[Dict], level_type: str) -> List[Dict]:
    """Group similar price levels together.

    Verbatim port of g_consolidation.py:241-283 (_group_similar_levels).
    """
    if not candidates:
        return []

    # Sort by number of touches (descending)
    candidates.sort(key=lambda x: x['touches'], reverse=True)

    grouped_levels = []
    used_indices = set()

    for candidate in candidates:
        if candidate['index'] in used_indices:
            continue

        # Find similar levels
        similar_levels = [candidate]
        tolerance = candidate['level'] * 0.02  # 2% tolerance for grouping

        for other in candidates:
            if (other['index'] not in used_indices and
                other['index'] != candidate['index'] and
                abs(other['level'] - candidate['level']) <= tolerance):

                similar_levels.append(other)
                used_indices.add(other['index'])

        if len(similar_levels) >= 1:  # At least one level
            # Calculate average level
            avg_level = sum(level['level'] for level in similar_levels) / len(similar_levels)
            total_touches = sum(level['touches'] for level in similar_levels)

            grouped_levels.append({
                'level': avg_level,
                'touches': total_touches,
                'type': level_type,
                'strength': len(similar_levels),
                'components': similar_levels
            })

            used_indices.add(candidate['index'])

    return grouped_levels


def _is_valid_channel(df: pd.DataFrame, support: Dict, resistance: Dict, params: dict) -> bool:
    """Check if support and resistance form a valid consolidation channel.

    Verbatim port of g_consolidation.py:285-307 (_is_valid_channel).
    """
    support_level = support['level']
    resistance_level = resistance['level']

    # Check basic validity
    if resistance_level <= support_level:
        return False

    # Check range is within consolidation limits
    range_pct = ((resistance_level - support_level) / support_level) * 100
    if not (params["min_range_size_pct"] <= range_pct <= params["max_consolidation_range_pct"]):
        return False

    # Check that price spent significant time in this channel
    channel_tolerance = (resistance_level - support_level) * 0.1  # 10% buffer
    channel_bottom = support_level - channel_tolerance
    channel_top = resistance_level + channel_tolerance

    prices_in_channel = df[(df['low'] >= channel_bottom) & (df['high'] <= channel_top)]
    pct_in_channel = len(prices_in_channel) / len(df) * 100

    return pct_in_channel >= 70  # At least 70% of time in channel


def calculate_zigzag_within_channel(df: pd.DataFrame, channel: Dict, params: dict) -> Tuple[List[Dict], Dict]:
    """Calculate ZigZag indicator within a specific price channel.

    Verbatim port of g_consolidation.py:309-427 (calculate_zigzag_within_channel).
    """
    support_level = channel['support_level']['level']
    resistance_level = channel['resistance_level']['level']
    zigzag_deviation = params.get('zigzag_deviation', 3.0)
    min_days_between_swings = params.get('min_days_between_swings', 2)

    if len(df) < 3:
        return [], {'support': 0, 'resistance': 0}

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

    channel_touches = {'support': 0, 'resistance': 0}

    for i in range(1, len(df)):
        current_high = df.iloc[i]['high']
        current_low = df.iloc[i]['low']
        current_date = df.iloc[i]['time']

        # Check minimum days between swings
        days_diff = (current_date - last_extreme['date']).days
        if days_diff < min_days_between_swings and last_extreme['type'] != 'start':
            continue

        high_change_pct = ((current_high - last_extreme['price']) / last_extreme['price']) * 100
        low_change_pct = ((current_low - last_extreme['price']) / last_extreme['price']) * 100

        # Check for channel boundary touches
        resistance_tolerance = resistance_level * 0.01  # 1% tolerance
        support_tolerance = support_level * 0.01

        if abs(current_high - resistance_level) <= resistance_tolerance:
            channel_touches['resistance'] += 1
        if abs(current_low - support_level) <= support_tolerance:
            channel_touches['support'] += 1

        # Detect peaks (but only within reasonable bounds)
        if (high_change_pct >= zigzag_deviation and
            current_high <= resistance_level * 1.02):  # Allow slight overshoot

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

        # Detect troughs (but only within reasonable bounds)
        elif (low_change_pct <= -zigzag_deviation and
              current_low >= support_level * 0.98):  # Allow slight undershoot

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

        # Update current extreme if moving in same direction (within bounds)
        elif (current_trend == 'up' and current_high > last_extreme['price'] and
              current_high <= resistance_level * 1.02):
            last_extreme = {
                'type': 'peak',
                'price': current_high,
                'date': current_date,
                'index': i,
                'high': current_high,
                'low': current_low
            }

        elif (current_trend == 'down' and current_low < last_extreme['price'] and
              current_low >= support_level * 0.98):
            last_extreme = {
                'type': 'trough',
                'price': current_low,
                'date': current_date,
                'index': i,
                'high': current_high,
                'low': current_low
            }

    # Add final extreme
    if last_extreme['type'] != 'start':
        zigzag_points.append(last_extreme)

    return zigzag_points, channel_touches


def create_support_zones(zigzag_points: List[Dict], params: dict) -> List[Dict]:
    """Create support zones.

    Verbatim port of g_consolidation.py:429-493 (create_support_zones).
    """
    troughs = [p for p in zigzag_points if p['type'] == 'trough']

    if len(troughs) < 2:
        return []

    support_zones = []
    used_troughs = set()

    # Group similar troughs
    for i, trough1 in enumerate(troughs):
        if i in used_troughs:
            continue

        similar_troughs = [trough1]
        similar_indices = {i}

        for j, trough2 in enumerate(troughs):
            if j != i and j not in used_troughs:
                price_diff_pct = abs(trough1['price'] - trough2['price']) / trough1['price'] * 100
                if price_diff_pct <= 2.5:  # grouping tolerance
                    similar_troughs.append(trough2)
                    similar_indices.add(j)

        if len(similar_troughs) >= 2:  # minimum touches
            prices = [t['price'] for t in similar_troughs]
            dates = [t['date'] for t in similar_troughs]

            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)

            zone_bottom = min_price * 0.998
            zone_top = max_price * 1.003

            support_zone = {
                'type': 'support',
                'center_price': avg_price,
                'zone_bottom': zone_bottom,
                'zone_top': zone_top,
                'min_price': min_price,
                'max_price': max_price,
                'touches': len(similar_troughs),
                'troughs': similar_troughs,
                'strength': len(similar_troughs) / len(troughs),
                'date_range': f"{min(dates).date()} to {max(dates).date()}",
                'price_range_pct': (max_price - min_price) / min_price * 100
            }

            support_zones.append(support_zone)
            used_troughs.update(similar_indices)

    return support_zones


def create_resistance_zones(zigzag_points: List[Dict], params: dict) -> List[Dict]:
    """Create resistance zones.

    Verbatim port of g_consolidation.py:495-559 (create_resistance_zones).
    """
    peaks = [p for p in zigzag_points if p['type'] == 'peak']

    if len(peaks) < 2:
        return []

    resistance_zones = []
    used_peaks = set()

    # Group similar peaks
    for i, peak1 in enumerate(peaks):
        if i in used_peaks:
            continue

        similar_peaks = [peak1]
        similar_indices = {i}

        for j, peak2 in enumerate(peaks):
            if j != i and j not in used_peaks:
                price_diff_pct = abs(peak1['price'] - peak2['price']) / peak1['price'] * 100
                if price_diff_pct <= 2.5:  # grouping tolerance
                    similar_peaks.append(peak2)
                    similar_indices.add(j)

        if len(similar_peaks) >= 2:  # minimum touches
            prices = [p['price'] for p in similar_peaks]
            dates = [p['date'] for p in similar_peaks]

            min_price = min(prices)
            max_price = max(prices)
            avg_price = sum(prices) / len(prices)

            zone_bottom = min_price * 0.997
            zone_top = max_price * 1.002

            resistance_zone = {
                'type': 'resistance',
                'center_price': avg_price,
                'zone_bottom': zone_bottom,
                'zone_top': zone_top,
                'min_price': min_price,
                'max_price': max_price,
                'touches': len(similar_peaks),
                'peaks': similar_peaks,
                'strength': len(similar_peaks) / len(peaks),
                'date_range': f"{min(dates).date()} to {max(dates).date()}",
                'price_range_pct': (max_price - min_price) / min_price * 100
            }

            resistance_zones.append(resistance_zone)
            used_peaks.update(similar_indices)

    return resistance_zones


def detect_consolidation_patterns_hybrid(df: pd.DataFrame, timeframe: str, params: dict) -> List[Dict]:
    """Detect consolidation patterns using hybrid Price Channel + ZigZag approach.

    Verbatim port of g_consolidation.py:561-682 (detect_consolidation_patterns_hybrid).
    """
    current_price = df['close'].iloc[-1]

    # Step 1: Detect price channels
    channels = detect_price_channels(df, params)

    if not channels:
        return []

    consolidation_patterns = []

    # Step 2: Validate each channel with ZigZag analysis
    for i, channel in enumerate(channels):
        support_level = channel['support_level']['level']
        resistance_level = channel['resistance_level']['level']
        range_pct = channel['range_pct']

        # Check range is within consolidation limits
        if range_pct > params["max_consolidation_range_pct"]:
            continue

        if range_pct < params["min_range_size_pct"]:
            continue

        # Check current price is within channel
        if not (support_level * 0.98 <= current_price <= resistance_level * 1.02):
            continue

        # Step 3: Validate with ZigZag analysis within channel
        zigzag_points, channel_touches = calculate_zigzag_within_channel(df, channel, params)

        total_zigzag_swings = len(zigzag_points)
        min_bounces = params.get('min_bounces_in_channel', 3)

        if total_zigzag_swings < min_bounces:
            continue

        # Check for adequate channel boundary tests
        total_boundary_touches = channel_touches['support'] + channel_touches['resistance']
        if total_boundary_touches < 4:  # Need at least 4 boundary tests
            continue

        # Calculate time metrics
        if zigzag_points:
            dates = [p['date'] for p in zigzag_points]
            start_date = min(dates)
            end_date = max(dates)
            duration_days = (end_date - start_date).days
        else:
            start_date = df['time'].iloc[0]
            end_date = df['time'].iloc[-1]
            duration_days = (end_date - start_date).days

        if duration_days < params["min_consolidation_duration"]:
            continue

        # Validate price action during consolidation period
        consolidation_data = df[(df['time'] >= start_date) & (df['time'] <= end_date)]
        if consolidation_data.empty:
            continue

        # Check percentage of closes within channel
        closes_in_channel = consolidation_data[
            (consolidation_data['close'] >= support_level * 0.98) &
            (consolidation_data['close'] <= resistance_level * 1.02)
        ]
        pct_closes_in_channel = len(closes_in_channel) / len(consolidation_data) * 100

        if pct_closes_in_channel < 85:  # Require 85% of closes in channel
            continue

        # Create comprehensive consolidation pattern
        pattern = {
            'timeframe': timeframe,
            'detection_method': 'hybrid_channel_zigzag',
            'support_level': support_level,
            'resistance_level': resistance_level,
            'channel': channel,
            'zigzag_points': zigzag_points,
            'channel_touches': channel_touches,
            'start_date': start_date,
            'end_date': end_date,
            'duration_days': duration_days,
            'range_pct': range_pct,
            'total_zigzag_swings': total_zigzag_swings,
            'total_boundary_touches': total_boundary_touches,
            'pct_closes_in_channel': pct_closes_in_channel,
            'current_price': current_price,
            'consolidation_bottom': support_level,
            'consolidation_top': resistance_level,
            'total_touches': channel['support_level']['touches'] + channel['resistance_level']['touches']
        }

        consolidation_patterns.append(pattern)

    return consolidation_patterns


def calculate_volume_behavior_score(df: pd.DataFrame, pattern: Dict) -> Dict:
    """Calculate volume behavior score during consolidation.

    Verbatim port of g_consolidation.py:684-740 (calculate_volume_behavior_score).
    """
    # Get consolidation period data
    start_date = pattern['start_date']
    end_date = pattern['end_date']
    consolidation_data = df[(df['time'] >= start_date) & (df['time'] <= end_date)].copy()

    if len(consolidation_data) < 10:
        return {'volume_score': 0, 'volume_trend': 'insufficient_data'}

    # Split into first and second half
    mid_point = len(consolidation_data) // 2
    first_half = consolidation_data.iloc[:mid_point]['volume']
    second_half = consolidation_data.iloc[mid_point:]['volume']

    first_half_avg = first_half.mean()
    second_half_avg = second_half.mean()

    # Calculate volume trend
    volume_decline_pct = (first_half_avg - second_half_avg) / first_half_avg * 100

    # Score volume behavior (0-100)
    if volume_decline_pct > 20:
        volume_score = 100
        volume_trend = 'strong_decline'
    elif volume_decline_pct > 10:
        volume_score = 80
        volume_trend = 'moderate_decline'
    elif volume_decline_pct > 0:
        volume_score = 60
        volume_trend = 'slight_decline'
    elif volume_decline_pct > -10:
        volume_score = 40
        volume_trend = 'stable'
    else:
        volume_score = 20
        volume_trend = 'increasing'

    return {
        'volume_score': volume_score,
        'volume_trend': volume_trend,
        'volume_decline_pct': volume_decline_pct,
        'first_half_avg': first_half_avg,
        'second_half_avg': second_half_avg
    }


def calculate_quality_score(pattern: Dict, volume_info: Dict, df: pd.DataFrame) -> Dict:
    """Calculate comprehensive quality score.

    Verbatim port of g_consolidation.py:742-843 (calculate_quality_score).
    """
    # 1. Tightness Score (0-25 points) - tighter range = higher score
    range_pct = pattern['range_pct']
    if range_pct <= 8:
        tightness_score = 25
    elif range_pct <= 12:
        tightness_score = 20
    elif range_pct <= 18:
        tightness_score = 15
    elif range_pct <= 25:
        tightness_score = 10
    else:
        tightness_score = 5

    # 2. Touch Count Score (0-25 points)
    total_touches = pattern['total_touches']
    if total_touches >= 6:
        touch_score = 25
    elif total_touches >= 5:
        touch_score = 20
    elif total_touches >= 4:
        touch_score = 15
    else:
        touch_score = 10

    # 3. Duration Score (0-20 points) - optimal duration gets highest score
    duration = pattern['duration_days']
    if 20 <= duration <= 40:
        duration_score = 20
    elif 15 <= duration <= 50:
        duration_score = 15
    elif 10 <= duration <= 60:
        duration_score = 10
    else:
        duration_score = 5

    # 4. Volume Score (0-20 points) - from volume analysis
    volume_score = min(20, volume_info['volume_score'] * 20 / 100)

    # 5. Freshness Score (0-10 points) - recent activity
    end_date = pattern['end_date']
    current_date = df['time'].iloc[-1]
    days_since_end = (current_date - end_date).days

    if days_since_end <= 5:
        freshness_score = 10
    elif days_since_end <= 10:
        freshness_score = 8
    elif days_since_end <= 20:
        freshness_score = 6
    elif days_since_end <= 30:
        freshness_score = 4
    else:
        freshness_score = 2

    # Calculate total quality score
    total_score = tightness_score + touch_score + duration_score + volume_score + freshness_score

    # Calculate breakout readiness (current price position)
    current_price = pattern['current_price']
    bottom = pattern['consolidation_bottom']
    top = pattern['consolidation_top']

    price_position_pct = (current_price - bottom) / (top - bottom) * 100

    if 45 <= price_position_pct <= 55:
        position_desc = "middle"
    elif price_position_pct < 30:
        position_desc = "near_support"
    elif price_position_pct > 70:
        position_desc = "near_resistance"
    else:
        position_desc = "within_range"

    return {
        'quality_score': total_score,
        'tightness_score': tightness_score,
        'touch_score': touch_score,
        'duration_score': duration_score,
        'volume_score': volume_score,
        'freshness_score': freshness_score,
        'price_position_pct': price_position_pct,
        'position_desc': position_desc,
        'days_since_last_activity': days_since_end
    }


def analyze_symbol(df: pd.DataFrame, params: dict) -> Dict:
    """Analyze stock for consolidations across all timeframes; return best pattern or None.

    Verbatim port of g_consolidation.py:845-934 (analyze_stock_consolidations), exposed
    under the new name `analyze_symbol`. Adaptations: the original
    `self.load_stock_data(symbol, 80)` call is removed (df is passed in already loaded);
    `self.timeframes` is built from `params["timeframes"]`; the quality check delegates to
    the shared `consolidation_core.is_stock_data_quality(timeframe_data, params)`.
    """
    if df.empty:
        return None

    timeframes = {f"{days}d": days for days in params["timeframes"]}

    all_consolidations = []

    # Analyze each timeframe
    for timeframe_name, days in timeframes.items():
        # Get data for this timeframe
        if len(df) < days + 5:  # need some buffer
            continue

        timeframe_data = df.tail(days + 5).copy()  # Use last N+5 days

        # Quality check
        is_quality, quality_reason = is_stock_data_quality(timeframe_data, params)
        if not is_quality:
            continue

        # Use hybrid detection method
        patterns = detect_consolidation_patterns_hybrid(timeframe_data, timeframe_name, params)

        # Analyze each pattern
        for pattern in patterns:
            # Volume analysis
            volume_info = calculate_volume_behavior_score(timeframe_data, pattern)

            # Quality scoring
            quality_info = calculate_quality_score(pattern, volume_info, timeframe_data)

            # Combine all information
            consolidation = {
                **pattern,
                **volume_info,
                **quality_info
            }

            all_consolidations.append(consolidation)

    # Select best consolidation
    best_consolidation = None
    if all_consolidations:
        best_consolidation = max(all_consolidations, key=lambda x: x['quality_score'])

    return best_consolidation


# ---------------------------------------------------------------------------
# DB layer
# ---------------------------------------------------------------------------

_COLS = ["symbol", "date", "timeframe", "detection_method", "support_level", "resistance_level",
         "range_pct", "duration_days", "quality_score", "tightness_score", "touch_score",
         "duration_score", "volume_score", "freshness_score", "total_touches", "zigzag_swings",
         "boundary_touches", "pct_closes_in_channel", "volume_trend", "volume_decline_pct",
         "price_position_pct", "position_desc", "current_price", "last_evaluated_at"]


def compute_for_symbol(conn, symbol: str) -> int:
    params = load_params(conn)
    df = pd.read_sql_query(
        "SELECT time, open, high, low, close, volume FROM market_data WHERE symbol = ? ORDER BY time ASC",
        conn, params=[symbol])
    if df.empty:
        return 0
    df["time"] = pd.to_datetime(df["time"])
    best = analyze_symbol(df, params)   # verbatim g_consolidation, returns best pattern or None
    if not best:
        conn.execute("DELETE FROM consolidation_patterns WHERE symbol = ?", (symbol,))
        conn.commit()
        return 0
    vals = {
        "symbol": symbol, "date": str(df["time"].iloc[-1].date()),
        "timeframe": best.get("timeframe"), "detection_method": best.get("detection_method"),
        "support_level": best.get("consolidation_bottom"), "resistance_level": best.get("consolidation_top"),
        "range_pct": best.get("range_pct"), "duration_days": best.get("duration_days"),
        "quality_score": best.get("quality_score"), "tightness_score": best.get("tightness_score"),
        "touch_score": best.get("touch_score"), "duration_score": best.get("duration_score"),
        "volume_score": best.get("volume_score"), "freshness_score": best.get("freshness_score"),
        "total_touches": best.get("total_touches"), "zigzag_swings": best.get("total_zigzag_swings"),
        "boundary_touches": best.get("total_boundary_touches"),
        "pct_closes_in_channel": best.get("pct_closes_in_channel"),
        "volume_trend": best.get("volume_trend"), "volume_decline_pct": best.get("volume_decline_pct"),
        "price_position_pct": best.get("price_position_pct"), "position_desc": best.get("position_desc"),
        "current_price": best.get("current_price"),
        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "symbol")
    conn.execute(
        f"INSERT INTO consolidation_patterns ({','.join(_COLS)}) VALUES ({','.join('?'*len(_COLS))}) "
        f"ON CONFLICT(symbol) DO UPDATE SET {updates}",
        tuple(vals[c] for c in _COLS))
    conn.commit()
    return 1


def compute_all(conn) -> dict:
    rows = conn.execute("SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()
    processed, written, errors, failures = [], 0, 0, []
    for (sym,) in rows:
        try:
            written += compute_for_symbol(conn, sym); processed.append(sym)
        except Exception as e:
            logger.error(f"❌ consolidation failed for {sym}: {e}")
            errors += 1; failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    return {"symbols_processed": processed, "rows_written": written, "errors": errors, "failures": failures}
