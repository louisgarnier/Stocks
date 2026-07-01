"""
Breakout compute — multi-day (day0/day1/day2) strict consolidation + breakout detection.

⚠️ `validate_resistance_zone`, `validate_support_zone`, `create_validated_support_zones`,
`create_validated_resistance_zones`, `detect_strict_consolidation_patterns`,
`check_breakout_for_day`, `analyze_single_case`, and `analyze_single_stock_for_breakout`
(-> `analyze_symbol`) are a VERBATIM port from
docs/plans/features_pipe/d_breakout_detector_3.py (lines 216-236, 238-258, 260-311,
313-364, 366-484, 486-515, 608-676, 517-594 respectively). The only changes are:
  1. Converted from instance methods (`MultiDayBreakoutDetector`) to module-level
     functions taking `(df, params)`.
  2. `self.config.<attr>` -> `params["<attr>"]`; `self.<attr>` (zigzag_deviation,
     min_days_between_swings, breakout_confirmation_pct, volume_lookback_days,
     max_daily_change, min_volume_threshold, max_volatility_filter) -> `params["<attr>"]`.
  3. `self.calculate_zigzag(df)` -> `consolidation_core.calculate_zigzag(df, params)`;
     `self.is_stock_data_quality(df)` -> `consolidation_core.is_stock_data_quality(df, params)`
     (shared with the g_consolidation port per Task 7/8's intentional sharing of that logic).
  4. `analyze_single_stock_for_breakout`'s original `self.load_stock_data(symbol, ...)` call
     is removed — `analyze_symbol` receives `df` already loaded by the caller. The exact
     `full_data.tail(...)` / `.iloc[...]` case-slicing logic for the 3 day0/day1/day2
     windows is unchanged.
  5. All `print(...)` calls from the original were stripped.

Every threshold, branch, and comparison is otherwise unchanged. Do not "improve" or
refactor this logic — see Task 9 brief.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import pandas as pd

from backend.scripts.consolidation_core import calculate_zigzag, is_stock_data_quality, load_params
from backend.database.connection import get_db_connection  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verbatim port of d_breakout_detector_3.py (MultiDayBreakoutDetector methods)
# ---------------------------------------------------------------------------

def validate_resistance_zone(zone: Dict, all_zigzag_points: List[Dict]) -> bool:
    """Validate resistance zone bi-directionally - EXACT same as original.

    Verbatim port of d_breakout_detector_3.py:216-236.
    """
    zone_dates = [peak['date'] for peak in zone['peaks']]
    first_zone_date = min(zone_dates)
    last_zone_date = max(zone_dates)

    prior_peaks = [
        p for p in all_zigzag_points
        if p['type'] == 'peak'
        and p['date'] < first_zone_date
        and p['price'] > zone['zone_top'] * 1.05
    ]

    subsequent_peaks = [
        p for p in all_zigzag_points
        if p['type'] == 'peak'
        and p['date'] > last_zone_date
        and p['price'] > zone['zone_top'] * 1.05
    ]

    return len(prior_peaks) == 0 and len(subsequent_peaks) == 0


def validate_support_zone(zone: Dict, all_zigzag_points: List[Dict]) -> bool:
    """Validate support zone bi-directionally - EXACT same as original.

    Verbatim port of d_breakout_detector_3.py:238-258.
    """
    zone_dates = [trough['date'] for trough in zone['troughs']]
    first_zone_date = min(zone_dates)
    last_zone_date = max(zone_dates)

    prior_troughs = [
        p for p in all_zigzag_points
        if p['type'] == 'trough'
        and p['date'] < first_zone_date
        and p['price'] < zone['zone_bottom'] * 0.95
    ]

    subsequent_troughs = [
        p for p in all_zigzag_points
        if p['type'] == 'trough'
        and p['date'] > last_zone_date
        and p['price'] < zone['zone_bottom'] * 0.95
    ]

    return len(prior_troughs) == 0 and len(subsequent_troughs) == 0


def create_validated_support_zones(zigzag_points: List[Dict], params: dict) -> List[Dict]:
    """Create validated support zones - EXACT same as original.

    Verbatim port of d_breakout_detector_3.py:260-311.
    """
    troughs = [p for p in zigzag_points if p['type'] == 'trough']

    if len(troughs) < params["min_support_touches"]:
        return []

    support_zones = []
    used_troughs = set()

    for i, trough1 in enumerate(troughs):
        if i in used_troughs:
            continue

        similar_troughs = [trough1]
        similar_indices = {i}

        for j, trough2 in enumerate(troughs):
            if j != i and j not in used_troughs:
                price_diff_pct = abs(trough1['price'] - trough2['price']) / trough1['price'] * 100
                if price_diff_pct <= params["extreme_grouping_tolerance"]:
                    similar_troughs.append(trough2)
                    similar_indices.add(j)

        if len(similar_troughs) >= params["min_support_touches"]:
            prices = [t['price'] for t in similar_troughs]

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
                'strength': len(similar_troughs) / len(troughs)
            }

            if validate_support_zone(support_zone, zigzag_points):
                support_zones.append(support_zone)
                used_troughs.update(similar_indices)

    support_zones.sort(key=lambda x: x['center_price'])
    return support_zones


def create_validated_resistance_zones(zigzag_points: List[Dict], params: dict) -> List[Dict]:
    """Create validated resistance zones - EXACT same as original.

    Verbatim port of d_breakout_detector_3.py:313-364.
    """
    peaks = [p for p in zigzag_points if p['type'] == 'peak']

    if len(peaks) < params["min_resistance_touches"]:
        return []

    resistance_zones = []
    used_peaks = set()

    for i, peak1 in enumerate(peaks):
        if i in used_peaks:
            continue

        similar_peaks = [peak1]
        similar_indices = {i}

        for j, peak2 in enumerate(peaks):
            if j != i and j not in used_peaks:
                price_diff_pct = abs(peak1['price'] - peak2['price']) / peak1['price'] * 100
                if price_diff_pct <= params["extreme_grouping_tolerance"]:
                    similar_peaks.append(peak2)
                    similar_indices.add(j)

        if len(similar_peaks) >= params["min_resistance_touches"]:
            prices = [p['price'] for p in similar_peaks]

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
                'strength': len(similar_peaks) / len(peaks)
            }

            if validate_resistance_zone(resistance_zone, zigzag_points):
                resistance_zones.append(resistance_zone)
                used_peaks.update(similar_indices)

    resistance_zones.sort(key=lambda x: x['center_price'], reverse=True)
    return resistance_zones


def detect_strict_consolidation_patterns(df: pd.DataFrame, resistance_zones: List[Dict],
                                          support_zones: List[Dict]) -> Tuple[List[Dict], str]:
    """Detect strict consolidation patterns and return rejection reason - EXACT COPY from original.

    Verbatim port of d_breakout_detector_3.py:366-484.
    """
    if not resistance_zones or not support_zones:
        return [], "no_zones"

    current_price = df['close'].iloc[-1]

    for resistance_zone in resistance_zones:
        for support_zone in support_zones:

            # Basic validations
            if resistance_zone['center_price'] <= support_zone['center_price']:
                continue

            range_pct = ((resistance_zone['center_price'] - support_zone['center_price']) /
                       support_zone['center_price']) * 100

            if range_pct < 5.0:
                return [], f"range_too_small_{range_pct:.1f}%"

            if range_pct > 30.0:
                return [], f"range_too_large_{range_pct:.1f}%"

            # Get all ZigZag points
            all_points = []
            all_points.extend(resistance_zone['peaks'])
            all_points.extend(support_zone['troughs'])

            if len(all_points) < 4:
                return [], f"insufficient_zigzag_points_{len(all_points)}"

            # Calculate time span
            dates = [p['date'] for p in all_points]
            start_date = min(dates)
            end_date = max(dates)
            duration_days = (end_date - start_date).days

            if duration_days < 14:
                return [], f"duration_too_short_{duration_days}d"

            # STRICT VALIDATION 1: Current price in consolidation zone
            consolidation_bottom = support_zone['center_price']
            consolidation_top = resistance_zone['center_price']
            zone_tolerance = 0.02

            expected_min = consolidation_bottom * (1 - zone_tolerance)
            expected_max = consolidation_top * (1 + zone_tolerance)

            if not (expected_min <= current_price <= expected_max):
                return [], f"current_price_outside_zone_{current_price:.2f}_vs_{expected_min:.2f}-{expected_max:.2f}"

            # STRICT VALIDATION 2: No post-consolidation breaks
            post_data = df[df['time'] > end_date]
            if not post_data.empty:
                breaks_below = post_data[post_data['close'] < consolidation_bottom * 0.97]
                breaks_above = post_data[post_data['close'] > consolidation_top * 1.03]

                if len(breaks_below) > 0:
                    lowest_break = breaks_below['close'].min()
                    return [], f"post_consolidation_break_below_{lowest_break:.2f}_vs_{consolidation_bottom:.2f}"

                if len(breaks_above) > 0:
                    highest_break = breaks_above['close'].max()
                    return [], f"post_consolidation_break_above_{highest_break:.2f}_vs_{consolidation_top:.2f}"

            # STRICT VALIDATION 3: 95% of closes in consolidation zone
            range_data = df[(df['time'] >= start_date) & (df['time'] <= end_date)]
            if range_data.empty:
                return [], "no_data_during_consolidation"

            close_tolerance = 0.02
            close_min = consolidation_bottom * (1 - close_tolerance)
            close_max = consolidation_top * (1 + close_tolerance)

            range_closes = range_data['close']
            closes_in_range = range_closes[
                (range_closes >= close_min) &
                (range_closes <= close_max)
            ]
            pct_closes_in_range = len(closes_in_range) / len(range_closes) * 100

            if pct_closes_in_range < 95:
                return [], f"insufficient_closes_in_zone_{pct_closes_in_range:.1f}%_need_95%"

            # STRICT VALIDATION 4: 70% of highs/lows in consolidation range
            hl_tolerance = 0.05
            hl_min = consolidation_bottom * (1 - hl_tolerance)
            hl_max = consolidation_top * (1 + hl_tolerance)

            within_range = range_data[
                (range_data['low'] >= hl_min) &
                (range_data['high'] <= hl_max)
            ]
            pct_within_range = len(within_range) / len(range_data) * 100

            if pct_within_range < 70:
                return [], f"insufficient_highs_lows_in_range_{pct_within_range:.1f}%_need_70%"

            # ALL VALIDATIONS PASSED
            pattern = {
                'type': 'strict_consolidation',
                'resistance_zone': resistance_zone,
                'support_zone': support_zone,
                'start_date': start_date,
                'end_date': end_date,
                'duration_days': duration_days,
                'range_pct': range_pct,
                'total_zigzag_points': len(all_points),
                'strength': (resistance_zone['strength'] + support_zone['strength']) / 2,
                'pct_within_range': pct_within_range,
                'pct_closes_in_range': pct_closes_in_range,
                'current_price': current_price,
                'consolidation_bottom': consolidation_bottom,
                'consolidation_top': consolidation_top,
            }

            return [pattern], "validated"

    return [], "no_valid_combinations"


def check_breakout_for_day(consolidation_pattern: Dict, breakout_price: float, breakout_volume: float,
                            avg_volume: float, day_name: str, params: dict) -> Dict:
    """Check if a specific day's price broke out of consolidation.

    Verbatim port of d_breakout_detector_3.py:486-515.
    """
    resistance_level = consolidation_pattern['consolidation_top']
    support_level = consolidation_pattern['consolidation_bottom']

    # Breakout thresholds
    bullish_breakout_level = resistance_level * (1 + params["breakout_confirmation_pct"] / 100)
    bearish_breakout_level = support_level * (1 - params["breakout_confirmation_pct"] / 100)

    # Determine breakout status
    breakout_direction = 'none'
    breakout_strength = 0

    if breakout_price >= bullish_breakout_level:
        breakout_direction = 'bullish'
        breakout_strength = (breakout_price - resistance_level) / resistance_level * 100
    elif breakout_price <= bearish_breakout_level:
        breakout_direction = 'bearish'
        breakout_strength = (support_level - breakout_price) / support_level * 100

    # Volume analysis
    volume_ratio = breakout_volume / avg_volume if avg_volume > 0 else 0

    return {
        f'{day_name}_breakout': breakout_direction,
        f'{day_name}_price': breakout_price,
        f'{day_name}_volume': breakout_volume,
        f'{day_name}_volume_ratio': volume_ratio,
        f'{day_name}_breakout_strength': breakout_strength
    }


def get_insufficient_data_result(case_num: int, day_prefix: str) -> Dict:
    """Return insufficient data result for a case.

    Verbatim port of d_breakout_detector_3.py:596-606.
    """
    return {
        f'case{case_num}_has_consolidation': False,
        f'case{case_num}_rejection_reason': 'insufficient_data',
        f'{day_prefix}_breakout': 'N/A',
        f'{day_prefix}_price': 0,
        f'{day_prefix}_volume': 0,
        f'{day_prefix}_volume_ratio': 0,
        f'{day_prefix}_breakout_strength': 0
    }


def analyze_single_case(case_data: pd.DataFrame, case_num: int, avg_volume: float, day_prefix: str,
                         params: dict) -> Dict:
    """Analyze a single case using the same logic as simple analysis.

    Verbatim port of d_breakout_detector_3.py:608-676.
    """
    result = {}

    # Split data: consolidation = all but last, breakout = last
    consolidation_data = case_data.iloc[:-1].copy()  # First 40 days
    breakout_data = case_data.iloc[-1]  # Last day

    # Quality check on consolidation data
    is_quality, quality_reason = is_stock_data_quality(consolidation_data, params)
    if not is_quality:
        result[f'case{case_num}_has_consolidation'] = False
        result[f'case{case_num}_rejection_reason'] = f'quality_filter_{quality_reason}'
        result[f'{day_prefix}_breakout'] = 'N/A'
        result[f'{day_prefix}_price'] = breakout_data['close']
        result[f'{day_prefix}_volume'] = breakout_data['volume']
        result[f'{day_prefix}_volume_ratio'] = breakout_data['volume'] / avg_volume if avg_volume > 0 else 0
        result[f'{day_prefix}_breakout_strength'] = 0
        return result

    # Calculate ZigZag on consolidation data
    zigzag_points = calculate_zigzag(consolidation_data, params)

    if not zigzag_points or len(zigzag_points) < 4:
        result[f'case{case_num}_has_consolidation'] = False
        result[f'case{case_num}_rejection_reason'] = f'insufficient_swings_{len(zigzag_points) if zigzag_points else 0}'
        result[f'{day_prefix}_breakout'] = 'N/A'
        result[f'{day_prefix}_price'] = breakout_data['close']
        result[f'{day_prefix}_volume'] = breakout_data['volume']
        result[f'{day_prefix}_volume_ratio'] = breakout_data['volume'] / avg_volume if avg_volume > 0 else 0
        result[f'{day_prefix}_breakout_strength'] = 0
        return result

    # Create validated zones from consolidation data
    support_zones = create_validated_support_zones(zigzag_points, params)
    resistance_zones = create_validated_resistance_zones(zigzag_points, params)

    # Detect consolidation patterns using EXACT same logic
    consolidation_patterns, rejection_reason = detect_strict_consolidation_patterns(
        consolidation_data, resistance_zones, support_zones
    )

    if not consolidation_patterns:
        result[f'case{case_num}_has_consolidation'] = False
        result[f'case{case_num}_rejection_reason'] = rejection_reason
        result[f'{day_prefix}_breakout'] = 'N/A'
        result[f'{day_prefix}_price'] = breakout_data['close']
        result[f'{day_prefix}_volume'] = breakout_data['volume']
        result[f'{day_prefix}_volume_ratio'] = breakout_data['volume'] / avg_volume if avg_volume > 0 else 0
        result[f'{day_prefix}_breakout_strength'] = 0
        return result

    # Valid consolidation found - check breakout
    result[f'case{case_num}_has_consolidation'] = True
    result[f'case{case_num}_rejection_reason'] = 'consolidation_found'
    result[f'case{case_num}_consolidation_pattern'] = consolidation_patterns[0]

    # Check breakout for this day
    consolidation_pattern = consolidation_patterns[0]
    breakout_info = check_breakout_for_day(
        consolidation_pattern,
        breakout_data['close'],
        breakout_data['volume'],
        avg_volume,
        day_prefix,
        params
    )
    result.update(breakout_info)

    return result


def analyze_symbol(df: pd.DataFrame, params: dict) -> Dict:
    """Analyze single stock for all 3 breakout patterns.

    Verbatim port of d_breakout_detector_3.py:517-594
    (analyze_single_stock_for_breakout), exposed under the new name `analyze_symbol`.
    Adaptation: the original `self.load_stock_data(symbol, ...)` call is removed — `df`
    is passed in already loaded by the caller. The exact `full_data.tail(...)` /
    `.iloc[...]` case-slicing logic for the 3 day0/day1/day2 windows is unchanged.
    """
    if df.empty:
        return {
            'symbol': None,
            'status': 'insufficient_data',
            'rejection_reason': 'no_data'
        }

    full_data = df

    try:
        # Average volume (use config parameter for lookback days)
        recent_volumes = full_data['volume'].tail(min(params["volume_lookback_days"], len(full_data)))
        avg_volume = recent_volumes.mean()

        results = {
            'avg_volume_10d': avg_volume
        }

        # Case 1: Use EXACT same logic as simple analysis
        # Take last 41 days, consolidation = first 40, breakout = last 1
        if len(full_data) >= params["lookback_days"] + 1:  # 41 days
            case1_data = full_data.tail(params["lookback_days"] + 1).copy()  # Last 41 days
            case1_result = analyze_single_case(case1_data, 1, avg_volume, "day0", params)
            results.update(case1_result)
        else:
            results.update(get_insufficient_data_result(1, "day0"))

        # Case 2: Take days -41 to 0, consolidation = first 40, breakout = day -1
        if len(full_data) >= params["lookback_days"] + 2:  # 42 days
            case2_data = full_data.tail(params["lookback_days"] + 2).iloc[:-1].copy()  # Days -41 to -1
            case2_result = analyze_single_case(case2_data, 2, avg_volume, "day1", params)
            results.update(case2_result)
        else:
            results.update(get_insufficient_data_result(2, "day1"))

        # Case 3: Take days -42 to -1, consolidation = first 40, breakout = day -2
        if len(full_data) >= params["lookback_days"] + 3:  # 43 days
            case3_data = full_data.tail(params["lookback_days"] + 3).iloc[:-2].copy()  # Days -42 to -2
            case3_result = analyze_single_case(case3_data, 3, avg_volume, "day2", params)
            results.update(case3_result)
        else:
            results.update(get_insufficient_data_result(3, "day2"))

        # Determine overall status
        any_consolidation = any([
            results.get('case1_has_consolidation', False),
            results.get('case2_has_consolidation', False),
            results.get('case3_has_consolidation', False)
        ])

        any_breakout = any([
            results.get('day0_breakout', 'none') not in ['none', 'N/A'],
            results.get('day1_breakout', 'none') not in ['none', 'N/A'],
            results.get('day2_breakout', 'none') not in ['none', 'N/A']
        ])

        if any_breakout:
            results['status'] = 'breakout_detected'
            results['rejection_reason'] = 'breakout_found'
        elif any_consolidation:
            results['status'] = 'consolidation_found_no_breakout'
            results['rejection_reason'] = 'no_breakout'
        else:
            results['status'] = 'no_consolidation_patterns'
            results['rejection_reason'] = 'no_consolidation_in_any_case'

        return results

    except Exception as e:
        return {
            'status': 'error',
            'rejection_reason': f'error_{str(e)}'
        }


# ---------------------------------------------------------------------------
# DB layer
# ---------------------------------------------------------------------------

_DAY_CASE = [
    ("day0", 0, "case1_consolidation_pattern"),
    ("day1", 1, "case2_consolidation_pattern"),
    ("day2", 2, "case3_consolidation_pattern"),
]


def _first_fired_breakout(result: dict):
    """Return (day_prefix, breakout_day, pattern) for whichever of day0/day1/day2
    fired first (breakout not in {'none', 'N/A'}), else (None, None, None)."""
    for day_prefix, breakout_day, pattern_key in _DAY_CASE:
        direction = result.get(f'{day_prefix}_breakout', 'none')
        if direction not in ('none', 'N/A'):
            return day_prefix, breakout_day, result.get(pattern_key)
    return None, None, None


def compute_for_symbol(conn, symbol: str) -> int:
    params = load_params(conn)
    df = pd.read_sql_query(
        "SELECT time, open, high, low, close, volume FROM market_data WHERE symbol = ? ORDER BY time ASC",
        conn, params=[symbol])
    if df.empty:
        return 0
    df["time"] = pd.to_datetime(df["time"])

    result = analyze_symbol(df, params)
    result["symbol"] = symbol

    date = str(df["time"].iloc[-1].date())

    day_prefix, breakout_day, pattern = _first_fired_breakout(result)

    if day_prefix is not None:
        breakout_direction = result.get(f'{day_prefix}_breakout')
        breakout_strength = result.get(f'{day_prefix}_breakout_strength')
        breakout_volume_ratio = result.get(f'{day_prefix}_volume_ratio')
    else:
        breakout_direction = 'none'
        breakout_day = None
        breakout_strength = None
        breakout_volume_ratio = None

    if pattern:
        consolidation_bottom = pattern.get('consolidation_bottom')
        consolidation_top = pattern.get('consolidation_top')
        consolidation_range_pct = pattern.get('range_pct')
        consolidation_duration_days = pattern.get('duration_days')
    else:
        consolidation_bottom = None
        consolidation_top = None
        consolidation_range_pct = None
        consolidation_duration_days = None

    vals = {
        "symbol": symbol,
        "date": date,
        "breakout_status": result.get("status"),
        "breakout_direction": breakout_direction,
        "breakout_day": breakout_day,
        "breakout_strength": breakout_strength,
        "breakout_volume_ratio": breakout_volume_ratio,
        "consolidation_bottom": consolidation_bottom,
        "consolidation_top": consolidation_top,
        "consolidation_range_pct": consolidation_range_pct,
        "consolidation_duration_days": consolidation_duration_days,
        "rejection_reason": result.get("rejection_reason"),
        "detail_json": json.dumps(result, default=str),
        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    cols = list(vals.keys())
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c not in ("symbol", "date"))
    conn.execute(
        f"INSERT INTO breakout_signals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
        f"ON CONFLICT(symbol, date) DO UPDATE SET {updates}",
        tuple(vals[c] for c in cols))

    # support_resistance: latest-only zones extracted from the fired (or best-available)
    # consolidation pattern. Delete-then-insert per symbol.
    conn.execute("DELETE FROM support_resistance WHERE symbol = ?", (symbol,))
    if pattern:
        resistance_zone = pattern.get('resistance_zone')
        support_zone = pattern.get('support_zone')
        for zone_type, zone in (('resistance', resistance_zone), ('support', support_zone)):
            if not zone:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO support_resistance "
                "(symbol, zone_type, level, zone_bottom, zone_top, center_price, touches, strength, date, last_evaluated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (symbol, zone_type, zone.get('center_price'), zone.get('zone_bottom'), zone.get('zone_top'),
                 zone.get('center_price'), zone.get('touches'), zone.get('strength'), date,
                 vals["last_evaluated_at"]))

    conn.commit()
    return 1


def compute_all(conn) -> dict:
    rows = conn.execute("SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()
    processed, written, errors, failures = [], 0, 0, []
    for (sym,) in rows:
        try:
            written += compute_for_symbol(conn, sym); processed.append(sym)
        except Exception as e:
            logger.error(f"❌ breakout compute failed for {sym}: {e}")
            errors += 1; failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    return {"symbols_processed": processed, "rows_written": written, "errors": errors, "failures": failures}
