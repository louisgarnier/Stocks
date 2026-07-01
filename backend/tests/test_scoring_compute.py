from backend.scripts.scoring_compute import score_symbol

WEIGHTS = {"above_ma50":10,"above_ma200":10,"volume_spike":7,"breakout":12,
           "consolidation_quality":10,"momentum_60d_positive":10,"near_52w_high":5}

def test_fundamental_score_is_gates_over_7():
    fund = {"gates_passed": 6, "gates_total": 7}
    sig = {"above_ma50":1,"above_ma200":1,"volume_spike":0,"momentum_60d":8.0,"near_52w_high":1}
    r = score_symbol(fund, sig, cons=None, brk=None, weights=WEIGHTS)
    assert round(r["score_fund"], 1) == round(6/7*100, 1)
    assert 0 <= r["score_tech"] <= 100
    assert r["verdict"] in ("strong_buy","buy","watch","neutral","avoid")

def test_breakout_and_consolidation_add_tech_points():
    sig = {"above_ma50":1,"above_ma200":0,"volume_spike":1,"momentum_60d":5.0,"near_52w_high":0}
    cons = {"quality_score": 80.0}
    brk = {"breakout_direction": "bullish"}
    r = score_symbol({"gates_passed":3,"gates_total":7}, sig, cons, brk, WEIGHTS)
    assert "breakout" in r["tech_flags"]
    assert "consolidation_quality" in r["tech_flags"]
