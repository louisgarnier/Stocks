"""Fetch fundamentals + compute the 7-gate MOAT quality scorecard."""
import logging
from datetime import datetime, timezone
from backend.database.connection import get_db_connection  # noqa: E402

logger = logging.getLogger(__name__)


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # NaN guard
    except (TypeError, ValueError):
        return None


def _stmt_value(stmt: dict, *labels):
    """Fetch a line-item from a statement dict by trying label aliases.
    Value may be a scalar (latest) or a list (oldest->newest); returns the latest scalar."""
    for label in labels:
        if label in stmt and stmt[label] is not None:
            v = stmt[label]
            if isinstance(v, (list, tuple)):
                return _num(v[-1]) if len(v) else None
            return _num(v)
    return None


def _eps_series(stmt: dict):
    for label in ("Diluted EPS", "Basic EPS"):
        if label in stmt and isinstance(stmt[label], (list, tuple)):
            vals = [_num(x) for x in stmt[label] if _num(x) is not None]
            if len(vals) >= 2:
                return vals
    return []


def _cagr(series):
    """CAGR from oldest->newest positive EPS series; None if not computable."""
    if len(series) < 2:
        return None
    first, last = series[0], series[-1]
    if first is None or last is None or first <= 0 or last <= 0:
        return None
    years = len(series) - 1
    return (last / first) ** (1.0 / years) - 1.0


def compute_quality_gates(info: dict, income: dict, balance: dict, gate_thresholds: dict) -> dict:
    info = info or {}
    income = income or {}
    balance = balance or {}
    missing = []

    gross_margin = _num(info.get("grossMargins"))
    roe = _num(info.get("returnOnEquity"))
    free_cashflow = _num(info.get("freeCashflow"))
    total_revenue = _num(info.get("totalRevenue"))

    levered_fcf_margin = (free_cashflow / total_revenue
                          if free_cashflow is not None and total_revenue else None)

    ebit = _stmt_value(income, "EBIT", "Operating Income")
    tax_provision = _stmt_value(income, "Tax Provision", "Income Tax Expense")
    pretax = _stmt_value(income, "Pretax Income", "Pre Tax Income")
    interest_expense = _stmt_value(income, "Interest Expense")
    total_debt = _stmt_value(balance, "Total Debt")
    total_equity = _stmt_value(balance, "Stockholders Equity", "Total Equity Gross Minority Interest")
    cash = _stmt_value(balance, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")

    # ROIC = NOPAT / invested capital, with pre-tax ROCE fallback
    roic, roic_method = None, None
    if ebit is not None and total_debt is not None and total_equity is not None:
        if tax_provision is not None and pretax not in (None, 0) and cash is not None:
            tax_rate = max(0.0, min(1.0, tax_provision / pretax))
            invested = total_debt + total_equity - cash
            if invested:
                roic, roic_method = ebit * (1 - tax_rate) / invested, "nopat"
        if roic is None:  # fallback
            denom = total_debt + total_equity
            if denom:
                roic, roic_method = ebit / denom, "roce"

    interest_cover = (ebit / interest_expense
                      if ebit is not None and interest_expense not in (None, 0) else None)

    eps_annual = _eps_series(income)
    eps_5y_growth = _cagr(eps_annual)

    values = {
        "gross_margin": gross_margin, "roe": roe, "roic": roic,
        "levered_fcf_margin": levered_fcf_margin, "interest_cover": interest_cover,
        "eps_5y_growth": eps_5y_growth, "free_cashflow": free_cashflow,
    }
    for k, v in values.items():
        if v is None:
            missing.append(k)

    gates_passed = sum(
        1 for k, thr in gate_thresholds.items()
        if values.get(k) is not None and values[k] > thr
    )
    return {
        **values, "roic_method": roic_method,
        "gates_passed": gates_passed, "gates_total": len(gate_thresholds),
        "fields_missing": missing,
        "raw": {"ebit": ebit, "tax_provision": tax_provision, "total_revenue": total_revenue,
                "total_debt": total_debt, "total_equity": total_equity, "cash": cash,
                "interest_expense": interest_expense, "eps_annual": eps_annual},
    }


import json


def _yf_ticker(symbol):
    """Indirected so tests can monkeypatch. Returns a yfinance Ticker."""
    import yfinance as yf
    return yf.Ticker(symbol)


def _as_dict(stmt):
    """Normalize a yfinance statement (DataFrame or dict) to {label: latest_or_series}.
    DataFrame: columns are period dates (newest first); we return oldest->newest lists."""
    if stmt is None:
        return {}
    if isinstance(stmt, dict):
        return stmt
    try:
        # pandas DataFrame: index = line items, columns = periods (newest first)
        out = {}
        cols = list(stmt.columns)[::-1]  # oldest->newest
        for label in stmt.index:
            out[str(label)] = [stmt.loc[label, c] for c in cols]
        return out
    except Exception:
        return {}


def _earnings_list(hist):
    if hist is None:
        return []
    if isinstance(hist, list):
        return hist
    try:
        return hist.reset_index().to_dict("records")
    except Exception:
        return []


def _load_gates(conn) -> dict:
    row = conn.execute("SELECT value_json FROM screener_settings WHERE key='quality_gates'").fetchone()
    return json.loads(row[0]) if row else {}


_COLS = [
    "symbol","long_name","sector","industry","country","currency","exchange","quote_type",
    "gross_margin","roe","roic","roic_method","levered_fcf_margin","interest_cover",
    "eps_5y_growth","free_cashflow","gates_passed","gates_total",
    "ebit","tax_provision","total_revenue","total_debt","total_equity","cash",
    "interest_expense","eps_annual_json","market_cap","trailing_pe","forward_pe",
    "trailing_eps","forward_eps","dividend_yield","recommendation_mean","recommendation_key",
    "number_of_analyst_opinions","target_mean_price","target_high_price","target_low_price",
    "earnings_history_json","beat_rate_4q","fetched_at","fetch_error","fields_missing_json",
]


def fetch_for_symbol(conn, symbol: str, gates: dict) -> bool:
    t = _yf_ticker(symbol)
    info = t.info or {}
    income = _as_dict(getattr(t, "income_stmt", None))
    balance = _as_dict(getattr(t, "balance_sheet", None))
    earnings = _earnings_list(getattr(t, "earnings_history", None))

    q = compute_quality_gates(info, income, balance, gates)
    raw = q["raw"]

    beats = [e for e in earnings if _num(e.get("epsActual")) is not None and _num(e.get("epsEstimate")) is not None]
    beat_rate = (sum(1 for e in beats if _num(e["epsActual"]) > _num(e["epsEstimate"])) / len(beats)
                 if beats else None)

    now = datetime.now(timezone.utc).isoformat()
    values = {
        "symbol": symbol, "long_name": info.get("longName"), "sector": info.get("sector"),
        "industry": info.get("industry"), "country": info.get("country"),
        "currency": info.get("currency"), "exchange": info.get("exchange"),
        "quote_type": info.get("quoteType"),
        "gross_margin": q["gross_margin"], "roe": q["roe"], "roic": q["roic"],
        "roic_method": q["roic_method"], "levered_fcf_margin": q["levered_fcf_margin"],
        "interest_cover": q["interest_cover"], "eps_5y_growth": q["eps_5y_growth"],
        "free_cashflow": q["free_cashflow"], "gates_passed": q["gates_passed"],
        "gates_total": q["gates_total"], "ebit": raw["ebit"], "tax_provision": raw["tax_provision"],
        "total_revenue": raw["total_revenue"], "total_debt": raw["total_debt"],
        "total_equity": raw["total_equity"], "cash": raw["cash"],
        "interest_expense": raw["interest_expense"], "eps_annual_json": json.dumps(raw["eps_annual"]),
        "market_cap": _num(info.get("marketCap")), "trailing_pe": _num(info.get("trailingPE")),
        "forward_pe": _num(info.get("forwardPE")), "trailing_eps": _num(info.get("trailingEps")),
        "forward_eps": _num(info.get("forwardEps")), "dividend_yield": _num(info.get("dividendYield")),
        "recommendation_mean": _num(info.get("recommendationMean")),
        "recommendation_key": info.get("recommendationKey"),
        "number_of_analyst_opinions": _num(info.get("numberOfAnalystOpinions")),
        "target_mean_price": _num(info.get("targetMeanPrice")),
        "target_high_price": _num(info.get("targetHighPrice")),
        "target_low_price": _num(info.get("targetLowPrice")),
        "earnings_history_json": json.dumps(earnings, default=str), "beat_rate_4q": beat_rate,
        "fetched_at": now, "fetch_error": None, "fields_missing_json": json.dumps(q["fields_missing"]),
    }
    cols = ",".join(_COLS)
    placeholders = ",".join("?" * len(_COLS))
    updates = ",".join(f"{c}=excluded.{c}" for c in _COLS if c != "symbol")
    conn.execute(
        f"INSERT INTO fundamentals ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(symbol) DO UPDATE SET {updates}",
        tuple(values[c] for c in _COLS),
    )
    conn.commit()
    return True


def fetch_all(conn) -> dict:
    gates = _load_gates(conn)
    rows = conn.execute("SELECT symbol FROM tracked_universe WHERE enabled = 1 ORDER BY symbol").fetchall()
    processed, written, errors, failures = [], 0, 0, []
    for (sym,) in rows:
        try:
            if fetch_for_symbol(conn, sym, gates):
                processed.append(sym); written += 1
        except Exception as e:
            logger.error(f"❌ fundamentals fetch failed for {sym}: {e}")
            errors += 1
            failures.append({"symbol": sym, "reason": f"{type(e).__name__}: {e}"})
    return {"symbols_processed": processed, "rows_written": written, "errors": errors, "failures": failures}


def run() -> dict:
    conn = get_db_connection()
    try:
        return fetch_all(conn)
    finally:
        conn.close()
