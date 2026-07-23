"""Dashboard aggregate endpoint (Epic V). One call = every card's payload."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from backend.api.utils.trading_days import freshness_level
from backend.database.connection import get_db_connection
from backend.scripts.portfolio_history_compute import get_fx_rate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])

WINDOWS = {"1M": 30, "3M": 91, "6M": 182, "1Y": 365, "MAX": 100000}


def _latest_two_closes(conn, symbol):
    rows = conn.execute(
        "SELECT close FROM market_data WHERE symbol=? ORDER BY time DESC LIMIT 2",
        (symbol,)).fetchall()
    c0 = rows[0][0] if rows else None
    c1 = rows[1][0] if len(rows) > 1 else None
    return c0, c1


@router.get("/dashboard")
def get_dashboard(window: str = Query("6M")):
    conn = get_db_connection()
    try:
        raw_fx = get_fx_rate(conn)
        if raw_fx is None:
            logger.warning("⚠️ [Dashboard] EURUSD=X rate unavailable — USD legs valued at parity; "
                            "net worth may be inaccurate")
        fx = raw_fx or 1.0

        positions = conn.execute(
            "SELECT p.symbol, p.quantity, p.cost_basis_price, COALESCE(p.currency,'USD') AS ccy, "
            "       f.sector, u.name "
            "FROM positions_ibkr p "
            "LEFT JOIN fundamentals f ON f.symbol=p.symbol "
            "LEFT JOIN tracked_universe u ON u.symbol=p.symbol "
            "WHERE p.quantity > 0").fetchall()

        holdings, total_eur, prev_total_eur, cost_eur, usd_eur = [], 0.0, 0.0, 0.0, 0.0
        for sym, qty, cost, ccy, sector, name in positions:
            c0, c1 = _latest_two_closes(conn, sym)
            if c0 is None:
                continue
            rate = fx if ccy == "USD" else 1.0
            mv = qty * c0 / rate
            holdings.append({"symbol": sym, "name": name, "qty": qty, "close": c0,
                             "prev_close": c1, "ccy": ccy, "sector": sector or "Other",
                             "mv_eur": mv, "cost_eur": (qty * cost / rate) if cost else None})
            total_eur += mv
            prev_total_eur += qty * (c1 if c1 is not None else c0) / rate
            if cost:
                cost_eur += qty * cost / rate
            if ccy == "USD":
                usd_eur += mv

        cash_eur, cash_by_ccy = 0.0, {}
        for ccy, amount in conn.execute("SELECT currency, amount FROM cash_balances"):
            if ccy == "EUR":
                in_eur = amount
            elif ccy == "USD":
                in_eur = amount / fx
                usd_eur += in_eur
            else:
                logger.warning(f"⚠️ [Dashboard] cash balance in unsupported currency {ccy} ignored")
                continue
            if in_eur:
                cash_by_ccy[ccy] = cash_by_ccy.get(ccy, 0.0) + in_eur
                cash_eur += in_eur
        total_with_cash = total_eur + cash_eur

        day_change = total_eur - prev_total_eur
        net_worth = {
            "value_eur": round(total_with_cash, 2),
            "cash_eur": round(cash_eur, 2),
            "day_change_eur": round(day_change, 2),
            "day_change_pct": round(day_change / (prev_total_eur + cash_eur) * 100, 2)
                              if (prev_total_eur + cash_eur) else 0.0,
            "unrealized_pnl_eur": round(total_eur - cost_eur, 2) if cost_eur else None,
            "positions": len(holdings),
            "usd_exposure_pct": round(usd_eur / total_with_cash * 100, 1) if total_with_cash else 0.0,
        }

        def _bucket(key_fn, extra=None):
            agg = {}
            for h in holdings:
                agg[key_fn(h)] = agg.get(key_fn(h), 0.0) + h["mv_eur"]
            for label, v in (extra or {}).items():
                agg[label] = agg.get(label, 0.0) + v
            return sorted(
                ({"label": k, "value_eur": round(v, 2),
                  "pct": round(v / total_with_cash * 100, 1) if total_with_cash else 0.0}
                 for k, v in agg.items()),
                key=lambda x: -x["value_eur"])
        cash_bucket = {"Cash": cash_eur} if cash_eur else None
        allocation = {"sector": _bucket(lambda h: h["sector"], cash_bucket),
                      "position": _bucket(lambda h: h["symbol"], cash_bucket),
                      "currency": _bucket(lambda h: h["ccy"], cash_by_ccy)}

        cutoff = (datetime.now() - timedelta(days=WINDOWS.get(window.upper(), 182))).date().isoformat()
        hist = conn.execute(
            "SELECT date, value_eur FROM portfolio_value_history WHERE date >= ? ORDER BY date",
            (cutoff,)).fetchall()
        bench = conn.execute(
            "SELECT time, close FROM market_data WHERE symbol='^GSPC' AND time >= ? ORDER BY time",
            (cutoff,)).fetchall()

        def _normalize(series):
            if not series or not series[0][1]:
                return []
            base = series[0][1]
            return [{"date": d, "value": round(v / base * 100, 2)} for d, v in series]
        performance = {"portfolio": _normalize(hist), "benchmark": _normalize(bench)}

        movers = sorted(
            ({"symbol": h["symbol"], "close": h["close"], "prev_close": h["prev_close"],
              "change_pct": round((h["close"] / h["prev_close"] - 1) * 100, 2),
              "day_pnl_eur": round(h["qty"] * (h["close"] - h["prev_close"])
                                   / (fx if h["ccy"] == "USD" else 1.0), 2)}
             for h in holdings if h["prev_close"]),
            key=lambda m: -abs(m["change_pct"]))

        sell = []
        for h in holdings:
            fired = [r[0] for r in conn.execute(
                "SELECT signal_type FROM holding_signals WHERE symbol=? AND fired=1",
                (h["symbol"],)).fetchall()]
            if fired:
                ret = (round((h["mv_eur"] / h["cost_eur"] - 1) * 100, 1)
                       if h.get("cost_eur") else None)
                sell.append({"symbol": h["symbol"], "quantity": h["qty"],
                             "return_pct": ret, "fired": fired, "n_fired": len(fired)})
        sell.sort(key=lambda s: -s["n_fired"])

        buy = [dict(r) for r in conn.execute(
            "SELECT symbol, name, verdict, score_total, gates_passed FROM research_overview "
            "WHERE verdict IN ('strong_buy','buy') ORDER BY score_total DESC LIMIT 6")]

        def _one(sql):
            row = conn.execute(sql).fetchone()
            return row[0] if row else None
        def _chip(kind, date_sql, checked_sql):
            data_date = _one(date_sql)
            checked_at = _one(checked_sql) if checked_sql else None
            now = datetime.now(timezone.utc)
            return {"date": data_date, "checked_at": checked_at,
                    "level": freshness_level(kind, data_date, checked_at, now)}

        # Chips must reflect the last SUCCESSFUL refresh, not the last attempt:
        # a failed sync writes a sync_runs row too, so an unfiltered MAX(finished_at)
        # would falsely bump the "checked" line (and, for IBKR whose data date IS the
        # run time, the whole chip) to green right after a sync that changed nothing.
        # 'partial' counts — it means the step's data was written (e.g. positions/trades
        # ok, only best-effort cash failed).
        OK = "status IN ('success','partial')"
        as_of = {
            "prices": _chip("prices",
                "SELECT MAX(time) FROM market_data",
                f"SELECT MAX(finished_at) FROM sync_runs WHERE action='market_data' AND {OK}"),
            "signals": _chip("signals",
                "SELECT MAX(date) FROM screen_signals",
                f"SELECT MAX(finished_at) FROM sync_runs WHERE action IN ('screen','analytics') AND {OK}"),
            "fundamentals": _chip("fundamentals",
                "SELECT MAX(fetched_at) FROM fundamentals",
                f"SELECT MAX(finished_at) FROM sync_runs WHERE action='fundamentals' AND {OK}"),
            "ibkr": _chip("ibkr",
                f"SELECT MAX(finished_at) FROM sync_runs WHERE action='ibkr' AND {OK}",
                f"SELECT MAX(finished_at) FROM sync_runs WHERE action='ibkr' AND {OK}"),
        }

        return {"as_of": as_of, "fx_rate": raw_fx, "net_worth": net_worth,
                "allocation": allocation, "performance": performance,
                "movers": movers, "actions": {"sell": sell, "buy": buy}}
    finally:
        conn.close()
