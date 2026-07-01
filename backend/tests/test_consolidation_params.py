"""R-2: the hidden consolidation gates must be tunable params (conservative defaults)."""
import pandas as pd
from backend.scripts.consolidation_core import CONSOLIDATION_DEFAULTS
from backend.scripts import consolidation_compute as C


def test_hidden_gates_have_conservative_defaults():
    # defaults must equal the previously-hardcoded values so out-of-the-box
    # behavior (reliable breakouts) is unchanged
    assert CONSOLIDATION_DEFAULTS["min_pct_in_channel"] == 70.0
    assert CONSOLIDATION_DEFAULTS["min_boundary_touches"] == 4
    assert CONSOLIDATION_DEFAULTS["min_pct_closes_in_channel"] == 85.0


def _channel_df(n_in=8, n_out=2):
    """n_in bars sitting inside a ~3% channel [100,103], n_out bars spiking out."""
    rows = []
    for _ in range(n_in):
        rows.append({"time": "2026-01-01", "open": 101, "high": 103.0, "low": 100.0, "close": 101, "volume": 10000})
    for _ in range(n_out):
        rows.append({"time": "2026-01-01", "open": 108, "high": 110.0, "low": 107.0, "close": 108, "volume": 10000})
    return pd.DataFrame(rows)


def test_is_valid_channel_reads_min_pct_in_channel():
    df = _channel_df(n_in=8, n_out=2)  # 80% of bars in channel
    support = {"level": 100.0}
    resistance = {"level": 103.0}  # 3% range, within [2,5]
    params = dict(CONSOLIDATION_DEFAULTS)

    # default gate is 70% -> 80% passes
    assert C._is_valid_channel(df, support, resistance, params) is True

    # raise the (now tunable) gate to 90% -> 80% no longer passes
    params["min_pct_in_channel"] = 90.0
    assert C._is_valid_channel(df, support, resistance, params) is False
