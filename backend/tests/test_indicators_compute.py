"""Tests for pure indicator computation functions."""
import numpy as np
import pandas as pd

from backend.scripts.indicators_compute import compute_basic_indicators, compute_mrsi


def _flat_df(close=100.0, days=300, volume=1_000_000):
    """Build a synthetic OHLCV DataFrame with constant close/volume."""
    return pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist(),
        "open": [close] * days,
        "high": [close + 1] * days,
        "low": [close - 1] * days,
        "close": [close] * days,
        "adj_close": [close] * days,
        "volume": [volume] * days,
    })


def test_ma_constant_series():
    """MA50 / MA100 / MA150 / MA200 of constant 100 should equal 100 once windows fill."""
    df = _flat_df(close=100, days=250)
    out = compute_basic_indicators(df)

    assert pd.isna(out["ma_50"].iloc[48])  # one less than 50 → still NaN
    assert out["ma_50"].iloc[49] == 100
    assert out["ma_100"].iloc[99] == 100
    assert out["ma_150"].iloc[149] == 100
    assert out["ma_200"].iloc[199] == 100


def test_bb_constant_series_zero_width():
    """Bollinger Band width of constant series is ~0 (stddev = 0)."""
    df = _flat_df(close=100, days=50)
    out = compute_basic_indicators(df)
    assert out["bb_upper_20"].iloc[25] == 100
    assert out["bb_lower_20"].iloc[25] == 100
    width = out["bb_width"].iloc[25]
    assert width == 0 or pd.isna(width)


def test_rsi_uptrend_approaches_100():
    """Strict uptrend → RSI approaches 100."""
    days = 60
    df = pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist(),
        "open": list(range(100, 100 + days)),
        "high": [c + 0.5 for c in range(100, 100 + days)],
        "low": [c - 0.5 for c in range(100, 100 + days)],
        "close": list(range(100, 100 + days)),
        "adj_close": list(range(100, 100 + days)),
        "volume": [1_000_000] * days,
    })
    out = compute_basic_indicators(df)
    assert out["rsi_14"].iloc[-1] > 95


def test_rsi_downtrend_approaches_0():
    """Strict downtrend → RSI approaches 0."""
    days = 60
    closes = list(range(200, 200 - days, -1))
    df = pd.DataFrame({
        "time": pd.date_range("2025-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist(),
        "open": closes,
        "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes],
        "close": closes,
        "adj_close": closes,
        "volume": [1_000_000] * days,
    })
    out = compute_basic_indicators(df)
    assert out["rsi_14"].iloc[-1] < 5


def test_atr_constant_range():
    """ATR of bars with constant high-low range = that range."""
    df = _flat_df(close=100, days=50)  # high-low = 2
    out = compute_basic_indicators(df)
    assert abs(out["atr_14"].iloc[-1] - 2) < 0.01


def test_volume_ma_constant():
    """Volume MA(20) of constant 1M = 1M."""
    df = _flat_df(volume=1_000_000, days=30)
    out = compute_basic_indicators(df)
    assert out["volume_ma_20"].iloc[-1] == 1_000_000


def test_mrsi_outperforming_stock_positive():
    """If stock outperforms benchmark over 252 days, MRSI is positive at the end."""
    days = 300
    times = pd.date_range("2024-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist()
    stock = pd.DataFrame({"time": times, "adj_close": np.linspace(100, 200, days)})
    bench = pd.DataFrame({"time": times, "adj_close": [100] * days})

    mrsi = compute_mrsi(stock, bench)
    assert mrsi.iloc[-1] > 0


def test_mrsi_underperforming_stock_negative():
    """If stock underperforms benchmark over 252 days, MRSI is negative at the end."""
    days = 300
    times = pd.date_range("2024-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist()
    stock = pd.DataFrame({"time": times, "adj_close": [100] * days})
    bench = pd.DataFrame({"time": times, "adj_close": np.linspace(100, 200, days)})

    mrsi = compute_mrsi(stock, bench)
    assert mrsi.iloc[-1] < 0


def test_mrsi_flat_relative_centered_at_zero():
    """If stock and benchmark move identically, MRSI is ~0."""
    days = 300
    times = pd.date_range("2024-01-01", periods=days, freq="D").strftime("%Y-%m-%d").tolist()
    series = list(np.linspace(100, 150, days))
    stock = pd.DataFrame({"time": times, "adj_close": series})
    bench = pd.DataFrame({"time": times, "adj_close": series})

    mrsi = compute_mrsi(stock, bench)
    assert abs(mrsi.iloc[-1]) < 0.01
