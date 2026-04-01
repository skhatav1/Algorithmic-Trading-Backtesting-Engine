"""Walk-forward evaluation helpers."""

from __future__ import annotations

from typing import Callable, Dict

import pandas as pd

from backtester.engine.backtest_engine import BacktestResult


EngineBuilder = Callable[[pd.DataFrame], BacktestResult]


def run_walkforward(
    bars: pd.DataFrame,
    engine_builder: EngineBuilder,
    split_ratio: float = 0.7,
) -> Dict[str, object]:
    """Run in-sample and out-of-sample backtests with chronological split.

    Parameters
    ----------
    bars:
        Full bar DataFrame sorted by time.
    engine_builder:
        Callback that receives a bar subset and returns a BacktestResult.
    split_ratio:
        Fraction used for in-sample portion. Out-of-sample receives remainder.
    """
    if not 0.0 < split_ratio < 1.0:
        raise ValueError("split_ratio must be between 0 and 1")
    if len(bars) < 4:
        raise ValueError("Need at least 4 bars for walk-forward split")

    ordered = bars.sort_values("timestamp").reset_index(drop=True)
    split_idx = int(len(ordered) * split_ratio)

    # Ensure non-empty partitions.
    split_idx = max(2, min(split_idx, len(ordered) - 2))

    in_sample_bars = ordered.iloc[:split_idx].reset_index(drop=True)
    out_of_sample_bars = ordered.iloc[split_idx:].reset_index(drop=True)

    in_sample_result = engine_builder(in_sample_bars)
    out_of_sample_result = engine_builder(out_of_sample_bars)

    comparison = pd.DataFrame(
        [
            {
                "segment": "in_sample",
                "bars": len(in_sample_bars),
                "total_return": in_sample_result.metrics["total_return"],
                "sharpe": in_sample_result.metrics["sharpe"],
                "max_drawdown": in_sample_result.metrics["max_drawdown"],
                "trades": in_sample_result.trade_count,
            },
            {
                "segment": "out_of_sample",
                "bars": len(out_of_sample_bars),
                "total_return": out_of_sample_result.metrics["total_return"],
                "sharpe": out_of_sample_result.metrics["sharpe"],
                "max_drawdown": out_of_sample_result.metrics["max_drawdown"],
                "trades": out_of_sample_result.trade_count,
            },
        ]
    )

    return {
        "in_sample": {
            "metrics": in_sample_result.metrics,
            "history": in_sample_result.history,
            "trades": in_sample_result.trades,
            "trade_count": in_sample_result.trade_count,
        },
        "out_of_sample": {
            "metrics": out_of_sample_result.metrics,
            "history": out_of_sample_result.history,
            "trades": out_of_sample_result.trades,
            "trade_count": out_of_sample_result.trade_count,
        },
        "comparison_table": comparison,
        "split_timestamp": out_of_sample_bars.iloc[0]["timestamp"],
    }
