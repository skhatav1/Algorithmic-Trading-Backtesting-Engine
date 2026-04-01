"""Tests for benchmark alignment and alpha/beta calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.analytics.metrics import compute_benchmark_comparison


def test_benchmark_alignment() -> None:
    timestamps = pd.date_range("2022-01-03", periods=6, freq="B")

    strategy_history = pd.DataFrame(
        {
            "timestamp": timestamps,
            "equity": [100_000, 100_500, 100_200, 101_000, 100_900, 101_400],
        }
    )

    # Benchmark intentionally misses one timestamp to validate inner join alignment.
    benchmark = pd.DataFrame(
        {
            "timestamp": [timestamps[0], timestamps[1], timestamps[3], timestamps[4], timestamps[5]],
            "close": [300.0, 302.0, 301.0, 305.0, 307.0],
        }
    )

    out = compute_benchmark_comparison(
        strategy_history=strategy_history,
        benchmark_close=benchmark,
        initial_cash=100_000.0,
    )

    merged = out["merged_frame"]
    assert len(merged) == 5
    assert "benchmark_equity" in merged.columns

    relative = out["relative_metrics"]
    assert np.isfinite(relative["alpha"])
    assert np.isfinite(relative["beta"])
    assert np.isfinite(relative["correlation"])
