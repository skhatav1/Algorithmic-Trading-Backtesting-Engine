"""Unit tests for analytics metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.analytics.metrics import compute_metrics


def test_compute_metrics_known_series() -> None:
    equity = pd.Series([100.0, 110.0, 105.0, 120.0])
    metrics = compute_metrics(equity)

    # Total return should be 20%.
    assert np.isclose(metrics["total_return"], 0.20)

    # Max drawdown occurs from 110 to 105 = -4.54545...
    expected_mdd = (105.0 / 110.0) - 1.0
    assert np.isclose(metrics["max_drawdown"], expected_mdd)

    # Sharpe should match annualized mean/std from daily returns.
    rets = equity.pct_change().dropna()
    expected_vol = rets.std(ddof=0) * np.sqrt(252)
    expected_ann = rets.mean() * 252
    expected_sharpe = expected_ann / expected_vol
    assert np.isclose(metrics["volatility"], expected_vol)
    assert np.isclose(metrics["sharpe"], expected_sharpe)
