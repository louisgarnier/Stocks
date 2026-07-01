from backend.scripts.fundamentals_fetch import compute_quality_gates

GATES = {"gross_margin":0.60,"roe":0.15,"roic":0.10,"levered_fcf_margin":0.20,
         "interest_cover":3.0,"eps_5y_growth":0.10,"free_cashflow":0}

def test_all_gates_pass():
    info = {"grossMargins":0.65,"returnOnEquity":0.30,"freeCashflow":300.0,"totalRevenue":1000.0}
    income = {"EBIT":400.0,"Tax Provision":80.0,"Pretax Income":400.0,"Interest Expense":20.0,
              "Diluted EPS": [1.0, 1.2, 1.5, 1.8]}  # oldest->newest
    balance = {"Total Debt":200.0,"Stockholders Equity":800.0,"Cash And Cash Equivalents":100.0}
    r = compute_quality_gates(info, income, balance, GATES)
    assert r["gross_margin"] == 0.65
    assert round(r["roic"], 3) == round(400*(1-0.20)/(200+800-100), 3)  # 320/900
    assert r["roic_method"] == "nopat"
    assert round(r["interest_cover"], 1) == 20.0
    assert round(r["levered_fcf_margin"], 2) == 0.30
    assert r["eps_5y_growth"] > 0.10
    assert r["gates_passed"] == 7 and r["gates_total"] == 7

def test_roce_fallback_when_tax_missing():
    info = {"grossMargins":0.65,"returnOnEquity":0.30,"freeCashflow":300.0,"totalRevenue":1000.0}
    income = {"EBIT":400.0,"Interest Expense":20.0,"Diluted EPS":[1.0,1.8]}  # no tax, no cash
    balance = {"Total Debt":200.0,"Stockholders Equity":800.0}
    r = compute_quality_gates(info, income, balance, GATES)
    assert r["roic_method"] == "roce"
    assert round(r["roic"], 3) == round(400/(200+800), 3)  # EBIT/(debt+equity)

def test_missing_fields_null_and_counted():
    info = {"grossMargins":0.65,"returnOnEquity":0.30,"freeCashflow":300.0,"totalRevenue":1000.0}
    r = compute_quality_gates(info, {}, {}, GATES)  # no statements
    assert r["roic"] is None and r["interest_cover"] is None and r["eps_5y_growth"] is None
    assert "roic" in r["fields_missing"]
    assert r["gates_passed"] == 4  # gross_margin, roe, fcf, levered_fcf_margin still pass
