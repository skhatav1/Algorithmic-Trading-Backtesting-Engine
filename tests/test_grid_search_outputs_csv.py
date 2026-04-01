"""Tests for SMA grid search outputs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.data.loaders import generate_synthetic_ohlcv
from backtester.engine.grid_search import grid_search_sma
from backtester.execution.costs import CostModel
from backtester.portfolio.position_sizing import AllInSizer


def test_grid_search_outputs_csv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    bars = generate_synthetic_ohlcv(n_bars=220, seed=42)

    out = grid_search_sma(
        bars=bars,
        symbol="TEST",
        cash=100_000.0,
        broker_costs=CostModel(commission_bps=1.0, slippage_bps=2.0),
        sizer=AllInSizer(),
        param_grid={"short_window": [5, 10], "long_window": [30, 50]},
        split_ratio=0.7,
    )

    csv_path = tmp_path / "grid_results.csv"
    assert csv_path.exists()

    frame = pd.read_csv(csv_path)
    assert len(frame) > 0

    rank = frame.copy()
    rank["_rank_sharpe"] = rank["out_of_sample_sharpe"].replace([np.inf, -np.inf], np.nan).fillna(-np.inf)
    rank["_rank_mdd"] = rank["out_of_sample_max_drawdown"].replace([np.inf, -np.inf], np.nan).fillna(-np.inf)
    rank = rank.sort_values(["_rank_sharpe", "_rank_mdd"], ascending=[False, False]).reset_index(drop=True)

    expected_short = int(rank.iloc[0]["short_window"])
    expected_long = int(rank.iloc[0]["long_window"])

    assert out["best_params"]["short_window"] == expected_short
    assert out["best_params"]["long_window"] == expected_long
