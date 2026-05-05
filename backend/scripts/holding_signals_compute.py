"""Sell-signal evaluators for held positions.

Each evaluator is a pure function returning (fired, value, threshold).
- `value` is the observed quantity (e.g. latest close, latest 5d volume).
- `threshold` is the comparison level (e.g. MA50, 50% of 20d volume).
- A None on any input the signal needs → fired=False, value/threshold=None.

The orchestrator `compute_all_signals(conn)` joins these against the latest
indicators + market_data rows for every held symbol, UPSERTs into
holding_signals, and deletes rows for sold-out symbols.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

EvalResult = Tuple[bool, Optional[float], Optional[float]]


def _na() -> EvalResult:
    return (False, None, None)


def eval_ma_break(close: Optional[float], ma: Optional[float]) -> EvalResult:
    if close is None or ma is None:
        return _na()
    return (close < ma, close, ma)


def eval_death_cross(
    ma50_today: Optional[float],
    ma150_today: Optional[float],
    ma50_yesterday: Optional[float],
    ma150_yesterday: Optional[float],
) -> EvalResult:
    if None in (ma50_today, ma150_today, ma50_yesterday, ma150_yesterday):
        return _na()
    fired = ma50_yesterday >= ma150_yesterday and ma50_today < ma150_today
    return (fired, ma50_today, ma150_today)


def eval_volume_dryup(
    avg_5d: Optional[float], avg_20d: Optional[float]
) -> EvalResult:
    if avg_5d is None or avg_20d is None or avg_20d == 0:
        return _na()
    threshold = avg_20d * 0.5
    return (avg_5d < threshold, avg_5d, threshold)


def eval_distribution_day(
    close: Optional[float],
    prev_close: Optional[float],
    volume: Optional[float],
    vol_ma_20: Optional[float],
) -> EvalResult:
    if None in (close, prev_close, volume, vol_ma_20) or vol_ma_20 == 0:
        return _na()
    threshold = vol_ma_20 * 1.5
    fired = (close < prev_close) and (volume > threshold)
    return (fired, volume, threshold)


def eval_rsi_weakness(
    rsi_today: Optional[float], rsi_yesterday: Optional[float]
) -> EvalResult:
    if rsi_today is None or rsi_yesterday is None:
        return _na()
    fired = rsi_yesterday >= 50 and rsi_today < 50
    return (fired, rsi_today, 50.0)


def eval_mrsi_flip(
    mrsi_today: Optional[float], mrsi_yesterday: Optional[float]
) -> EvalResult:
    if mrsi_today is None or mrsi_yesterday is None:
        return _na()
    fired = mrsi_yesterday >= 0 and mrsi_today < 0
    return (fired, mrsi_today, 0.0)


def eval_trailing_drawdown(
    close: Optional[float],
    high_30d: Optional[float],
    drawdown_pct: float,
) -> EvalResult:
    if close is None or high_30d is None:
        return _na()
    threshold = high_30d * (1.0 - drawdown_pct)
    return (close < threshold, close, threshold)


def eval_stop_loss(
    close: Optional[float],
    cost_basis_price: Optional[float],
    drawdown_pct: float,
) -> EvalResult:
    if close is None or cost_basis_price is None:
        return _na()
    threshold = cost_basis_price * (1.0 - drawdown_pct)
    return (close < threshold, close, threshold)


def compute_all_signals(conn) -> dict:
    """Evaluate every enabled signal_type for every held symbol; UPSERT results.

    Reads `signal_settings` for the enabled set + per-signal thresholds,
    pulls the latest 2 indicators rows + last 30 market_data bars per symbol,
    and writes one row per (symbol, signal_type) into `holding_signals`.
    Symbols no longer in `positions_ibkr` get their signal rows deleted.
    """
    settings = {
        row[0]: {"enabled": bool(row[1]), "threshold": row[2]}
        for row in conn.execute(
            "SELECT signal_type, enabled, threshold FROM signal_settings"
        ).fetchall()
    }

    held_rows = conn.execute(
        "SELECT symbol, cost_basis_price FROM positions_ibkr"
    ).fetchall()
    held_symbols = {r[0] for r in held_rows}
    cost_by_sym = {r[0]: r[1] for r in held_rows}

    if held_symbols:
        placeholders = ",".join("?" * len(held_symbols))
        conn.execute(
            f"DELETE FROM holding_signals WHERE symbol NOT IN ({placeholders})",
            tuple(held_symbols),
        )
    else:
        conn.execute("DELETE FROM holding_signals")

    now = datetime.now().astimezone().isoformat()
    signals_evaluated = 0
    failures: list[dict] = []

    for symbol in held_symbols:
        try:
            ind_rows = conn.execute(
                "SELECT time, ma_50, ma_100, ma_150, ma_200, rsi_14, mrsi, volume_ma_20 "
                "FROM indicators WHERE symbol=? ORDER BY time DESC LIMIT 2",
                (symbol,),
            ).fetchall()
            bar_rows = conn.execute(
                "SELECT time, close, volume FROM market_data "
                "WHERE symbol=? ORDER BY time DESC LIMIT 30",
                (symbol,),
            ).fetchall()
            if not ind_rows or not bar_rows:
                # Silent skip: missing upstream data is the responsibility of
                # /sync/market-data + /sync/indicators, not this step. The
                # Positions tab pill shows ⚪ N/A so the user notices.
                continue

            ind_today = ind_rows[0]
            ind_yest = ind_rows[1] if len(ind_rows) > 1 else (None,) * 8
            bar_today = bar_rows[0]
            bar_yest = bar_rows[1] if len(bar_rows) > 1 else (None, None, None)

            last_30_closes = [b[1] for b in bar_rows if b[1] is not None]
            high_30d = max(last_30_closes) if last_30_closes else None

            last_5_vols = [b[2] for b in bar_rows[:5] if b[2] is not None]
            last_20_vols = [b[2] for b in bar_rows[:20] if b[2] is not None]
            avg_5d = sum(last_5_vols) / len(last_5_vols) if last_5_vols else None
            avg_20d = sum(last_20_vols) / len(last_20_vols) if last_20_vols else None

            close_today = bar_today[1]
            close_yest = bar_yest[1]
            vol_today = bar_today[2]

            td_pct = (settings.get("trailing_drawdown") or {}).get("threshold") or 0.10
            sl_pct = (settings.get("stop_loss") or {}).get("threshold") or 0.08

            evaluations = [
                ("ma50_break",       eval_ma_break(close_today, ind_today[1])),
                ("ma100_break",      eval_ma_break(close_today, ind_today[2])),
                ("ma150_break",      eval_ma_break(close_today, ind_today[3])),
                ("ma200_break",      eval_ma_break(close_today, ind_today[4])),
                ("death_cross",      eval_death_cross(ind_today[1], ind_today[3], ind_yest[1], ind_yest[3])),
                ("volume_dryup",     eval_volume_dryup(avg_5d, avg_20d)),
                ("distribution_day", eval_distribution_day(close_today, close_yest, vol_today, ind_today[7])),
                ("rsi_weakness",     eval_rsi_weakness(ind_today[5], ind_yest[5])),
                ("mrsi_flip",        eval_mrsi_flip(ind_today[6], ind_yest[6])),
                ("trailing_drawdown", eval_trailing_drawdown(close_today, high_30d, td_pct)),
                ("stop_loss",        eval_stop_loss(close_today, cost_by_sym.get(symbol), sl_pct)),
            ]

            for signal_type, (fired, value, threshold) in evaluations:
                if not settings.get(signal_type, {}).get("enabled", True):
                    continue
                conn.execute(
                    "INSERT INTO holding_signals (symbol, signal_type, fired, value, threshold, last_evaluated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(symbol, signal_type) DO UPDATE SET "
                    "  fired=excluded.fired, value=excluded.value, threshold=excluded.threshold, "
                    "  last_evaluated_at=excluded.last_evaluated_at",
                    (symbol, signal_type, 1 if fired else 0, value, threshold, now),
                )
                signals_evaluated += 1
        except Exception as e:
            logger.error(f"❌ signal compute failed for {symbol}: {e}")
            failures.append({"symbol": symbol, "reason": f"{type(e).__name__}: {e}"})

    conn.commit()
    return {
        "symbols_processed": len(held_symbols),
        "signals_evaluated": signals_evaluated,
        "failures": failures,
    }
