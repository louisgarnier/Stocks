import pandas as pd
from backend.scripts.consolidation_core import calculate_zigzag, is_stock_data_quality

PARAMS = {"zigzag_deviation": 6.0, "min_days_between_swings": 2, "max_daily_change": 30.0,
          "min_volume_threshold": 5000, "max_volatility_filter": 150.0}

def _osc_df(n=40):
    # oscillating series that must produce >=2 peaks and >=2 troughs
    prices = []
    for i in range(n):
        prices.append(100 + (8 if i % 8 < 4 else -8))
    return pd.DataFrame({
        "time": pd.to_datetime(pd.date_range("2026-01-01", periods=n)),
        "open": prices, "high": [p + 1 for p in prices], "low": [p - 1 for p in prices],
        "close": prices, "volume": [1_000_000] * n})

def test_zigzag_finds_swings():
    pts = calculate_zigzag(_osc_df(), PARAMS)
    assert len([p for p in pts if p["type"] == "peak"]) >= 1
    assert len([p for p in pts if p["type"] == "trough"]) >= 1

def test_quality_rejects_low_volume():
    df = _osc_df(); df["volume"] = 10
    ok, reason = is_stock_data_quality(df, PARAMS)
    assert ok is False and "low_volume" in reason
