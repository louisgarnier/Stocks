"""Provisional composite scoring. Fundamental = gates/7; technical = weighted signals."""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def score_symbol(fund, sig, cons, brk, weights) -> dict:
    sig = sig or {}
    tech_raw, tech_max, flags = 0.0, 0.0, []
    checks = [
        (sig.get("above_ma50") == 1, "above_ma50"),
        (sig.get("above_ma200") == 1, "above_ma200"),
        (sig.get("volume_spike") == 1, "volume_spike"),
        ((sig.get("momentum_60d") or 0) > 0, "momentum_60d_positive"),
        (sig.get("near_52w_high") == 1, "near_52w_high"),
        (bool(brk) and brk.get("breakout_direction") == "bullish", "breakout"),
        (bool(cons) and (cons.get("quality_score") or 0) >= 50, "consolidation_quality"),
    ]
    for cond, key in checks:
        tech_max += weights.get(key, 0)
        if cond:
            tech_raw += weights.get(key, 0)
            flags.append(key)

    score_tech = round(tech_raw / tech_max * 100, 1) if tech_max else 0.0
    gp = (fund or {}).get("gates_passed")
    gt = (fund or {}).get("gates_total") or 7
    score_fund = round((gp / gt) * 100, 1) if gp is not None else 0.0
    score_total = round((score_tech + score_fund) / 2, 1)

    verdict = ("strong_buy" if score_total >= 75 else "buy" if score_total >= 60
               else "watch" if score_total >= 45 else "avoid" if score_total < 30 else "neutral")
    fund_flags = f"{gp}/{gt}" if gp is not None else "n/a"
    return {"score_tech": score_tech, "score_fund": score_fund, "score_total": score_total,
            "verdict": verdict, "tech_flags": ",".join(flags), "fund_flags": fund_flags}


import json  # noqa: E402

# Canonical seed — MUST mirror backend/database/schema.sql's `scoring_weights`
# row exactly. See CONSOLIDATION_DEFAULTS in consolidation_core.py for why:
# guards against a missing/partial row after seed-drift (a missing weight key
# would otherwise silently score that factor as 0 instead of its seeded weight).
SCORING_WEIGHTS_DEFAULTS = {
    "above_ma50": 10,
    "above_ma200": 10,
    "ma50_rising_8d": 10,
    "ma50_above_ma200": 8,
    "macd_bullish": 8,
    "rsi_neutral": 5,
    "volume_spike": 7,
    "breakout": 12,
    "consolidation_quality": 10,
    "momentum_20d_positive": 8,
    "momentum_60d_positive": 10,
    "near_52w_high": 5,
}


def load_scoring_weights(conn) -> dict:
    row = conn.execute(
        "SELECT value_json FROM screener_settings WHERE key='scoring_weights'").fetchone()
    if not row:
        return dict(SCORING_WEIGHTS_DEFAULTS)
    return {**SCORING_WEIGHTS_DEFAULTS, **json.loads(row[0])}


def compute_all(conn) -> dict:
    """Compute provisional scores for every enabled symbol in tracked_universe.

    Returns: {
        "symbols_processed": list[str],
        "rows_written": int,
        "errors": int,
        "failures": list[str],
    }

    "failures" only captures real exceptions (scoring crashed for this symbol).
    Symbols with no screen_signals row are skipped silently — that's an
    upstream compute concern, not a scoring failure.
    """
    weights = load_scoring_weights(conn)
    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()]
    written, now = 0, datetime.now(timezone.utc).isoformat()
    errors = 0
    failures: list[str] = []
    for sym in syms:
        try:
            sig = conn.execute("SELECT above_ma50, above_ma200, volume_spike, momentum_60d, near_52w_high, "
                               "multi_factor_momentum, date FROM screen_signals WHERE symbol=?", (sym,)).fetchone()
            if not sig:
                continue
            sig_d = {"above_ma50": sig[0], "above_ma200": sig[1], "volume_spike": sig[2],
                     "momentum_60d": sig[3], "near_52w_high": sig[4]}
            fund = conn.execute("SELECT gates_passed, gates_total FROM fundamentals WHERE symbol=?", (sym,)).fetchone()
            fund_d = {"gates_passed": fund[0], "gates_total": fund[1]} if fund else {}
            cons = conn.execute("SELECT quality_score FROM consolidation_patterns WHERE symbol=?", (sym,)).fetchone()
            cons_d = {"quality_score": cons[0]} if cons else None
            brk = conn.execute("SELECT breakout_direction FROM breakout_signals WHERE symbol=? "
                               "ORDER BY date DESC LIMIT 1", (sym,)).fetchone()
            brk_d = {"breakout_direction": brk[0]} if brk else None
            s = score_symbol(fund_d, sig_d, cons_d, brk_d, weights)
            date = sig[6]
            conn.execute(
                "INSERT INTO screen_scores (symbol,date,score_tech,score_fund,score_total,verdict,"
                "tech_flags,fund_flags,multi_factor_momentum,is_provisional,last_evaluated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,1,?) "
                "ON CONFLICT(symbol,date) DO UPDATE SET score_tech=excluded.score_tech,"
                "score_fund=excluded.score_fund,score_total=excluded.score_total,verdict=excluded.verdict,"
                "tech_flags=excluded.tech_flags,fund_flags=excluded.fund_flags,"
                "multi_factor_momentum=excluded.multi_factor_momentum,last_evaluated_at=excluded.last_evaluated_at",
                (sym, date, s["score_tech"], s["score_fund"], s["score_total"], s["verdict"],
                 s["tech_flags"], s["fund_flags"], sig[5], now))
            written += 1
        except Exception as exc:
            logger.warning("[Scoring] ❌ failed symbol=%s: %s", sym, exc)
            errors += 1
            failures.append(sym)
            continue
    conn.commit()
    logger.info("[Scoring] ✅ scored %d, failed %d", written, errors)
    return {"symbols_processed": syms, "rows_written": written, "errors": errors, "failures": failures}
