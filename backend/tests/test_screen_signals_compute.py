import pandas as pd
from backend.scripts.screen_signals_compute import compute_signals

def test_momentum_and_flags_exact():
    # 70 ascending closes so momentum is positive; volume flat except last day spike
    closes = [100 + i for i in range(70)]
    vols = [1_000_000] * 69 + [3_000_000]
    df = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=70).astype(str),
        "high": [c + 1 for c in closes], "low": [c - 1 for c in closes],
        "close": closes, "volume": vols,
    })
    ind = {"ma_50": 150.0, "ma_100": 140.0, "ma_150": 130.0, "ma_200": 120.0}
    r = compute_signals(df, ind)
    c = closes[-1]
    assert round(r["momentum_5d"], 2) == round((c - closes[-6]) / closes[-6] * 100, 2)
    assert round(r["multi_factor_momentum"], 2) == round(
        0.4*r["momentum_5d"] + 0.3*r["momentum_20d"] + 0.3*r["momentum_60d"], 2)
    assert r["volume_spike"] == 1               # 3M > 1.5 * ~1M
    assert r["above_ma50"] == 1                 # close 169 > 150
    assert r["ma_cross_status"] == "All Bullish"  # 150>140>130
    assert r["near_52w_high"] == 1              # last close is the high
