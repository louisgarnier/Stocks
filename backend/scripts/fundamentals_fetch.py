"""Fetch fundamentals + compute the 7-gate MOAT quality scorecard."""
import logging
from datetime import datetime, timezone

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
