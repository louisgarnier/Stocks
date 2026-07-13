"""Cash balances from the Flex CashReport section → cash_balances table → net worth."""
import json
import sqlite3
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.scripts.fetch_flex_trades import parse_cash_from_xml, save_cash_balances

client = TestClient(app)


# --- parsing ----------------------------------------------------------------

def test_parse_cash_skips_base_summary(flex_xml_minimal):
    balances = parse_cash_from_xml(flex_xml_minimal)
    assert sorted(b["currency"] for b in balances) == ["EUR", "USD"]


def test_parse_cash_prefers_settled_cash(flex_xml_minimal):
    balances = {b["currency"]: b for b in parse_cash_from_xml(flex_xml_minimal)}
    assert balances["EUR"]["amount"] == 1500.25
    assert balances["USD"]["amount"] == 1850.00      # endingSettledCash, not endingCash
    assert balances["EUR"]["report_date"] == "20260131"


def test_parse_cash_no_section_returns_empty():
    xml = ('<?xml version="1.0"?><FlexQueryResponse><FlexStatements count="1">'
           '<FlexStatement accountId="T"/></FlexStatements></FlexQueryResponse>')
    assert parse_cash_from_xml(xml) == []


# --- persistence --------------------------------------------------------------

def test_save_cash_replaces_previous_snapshot(temp_db):
    save_cash_balances([{"currency": "EUR", "amount": 999.0, "report_date": "20260130"}])
    save_cash_balances([
        {"currency": "EUR", "amount": 1500.25, "report_date": "20260131"},
        {"currency": "USD", "amount": 1850.00, "report_date": "20260131"},
    ])
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute("SELECT currency, amount FROM cash_balances ORDER BY currency").fetchall()
    conn.close()
    assert rows == [("EUR", 1500.25), ("USD", 1850.00)]


def test_save_cash_empty_list_keeps_existing(temp_db):
    """A Flex response without CashReport must not wipe the last known snapshot."""
    save_cash_balances([{"currency": "EUR", "amount": 1500.25, "report_date": "20260131"}])
    save_cash_balances([])
    conn = sqlite3.connect(str(temp_db))
    rows = conn.execute("SELECT currency, amount FROM cash_balances").fetchall()
    conn.close()
    assert rows == [("EUR", 1500.25)]


# --- dashboard integration ------------------------------------------------------

def _seed_position_and_cash(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
                 "VALUES ('TEST', 10, 100.0, 'USD')")
    conn.execute("INSERT INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
                 "VALUES ('TEST','Test Corp','USD',?,1,datetime('now'))", (json.dumps(["test"]),))
    for d, px, fx in (("2026-07-08", 110.0, 1.10), ("2026-07-09", 121.0, 1.10)):
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('TEST',?,?,?,?,?,1000)", (d, px, px, px, px))
        conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                     "VALUES ('EURUSD=X',?,?,?,?,?,0)", (d, fx, fx, fx, fx))
    conn.execute("INSERT INTO cash_balances (currency, amount, report_date) VALUES ('EUR', 1500.0, '20260709')")
    conn.execute("INSERT INTO cash_balances (currency, amount, report_date) VALUES ('USD', 1100.0, '20260709')")
    conn.commit(); conn.close()


def test_net_worth_includes_cash(temp_db):
    _seed_position_and_cash(temp_db)
    b = client.get("/api/dashboard").json()
    # Stocks: 10*121/1.10 = 1100 EUR. Cash: 1500 EUR + 1100/1.10 = 1000 EUR → 2500 EUR.
    assert abs(b["net_worth"]["cash_eur"] - 2500.0) < 0.1
    assert abs(b["net_worth"]["value_eur"] - 3600.0) < 0.1
    # Day change is stock-driven only: 10*(121-110)/1.10 = 100 EUR.
    assert abs(b["net_worth"]["day_change_eur"] - 100.0) < 0.1


def test_net_worth_without_cash_rows(temp_db):
    """No cash_balances rows → cash_eur is 0.0 and value_eur is stocks only."""
    conn = sqlite3.connect(str(temp_db))
    conn.execute("INSERT INTO positions_ibkr (symbol, quantity, cost_basis_price, currency) "
                 "VALUES ('TEST', 10, 100.0, 'USD')")
    conn.execute("INSERT INTO tracked_universe (symbol, name, currency, sources, enabled, added_at) "
                 "VALUES ('TEST','Test Corp','USD',?,1,datetime('now'))", (json.dumps(["test"]),))
    conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                 "VALUES ('TEST','2026-07-09',121,121,121,121,1000)")
    conn.execute("INSERT INTO market_data (symbol,time,open,high,low,close,volume) "
                 "VALUES ('EURUSD=X','2026-07-09',1.10,1.10,1.10,1.10,0)")
    conn.commit(); conn.close()
    b = client.get("/api/dashboard").json()
    assert b["net_worth"]["cash_eur"] == 0.0
    assert abs(b["net_worth"]["value_eur"] - 1100.0) < 0.1
