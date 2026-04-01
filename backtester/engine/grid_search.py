"""Grid search helpers for SMA walk-forward tuning."""

from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from backtester.engine.backtest_engine import BacktestEngine
from backtester.engine.walkforward import run_walkforward
from backtester.execution.broker import SimulatedBroker
from backtester.execution.costs import CostModel
from backtester.portfolio.portfolio import Portfolio
from backtester.portfolio.position_sizing import PositionSizer
from backtester.strategies.sma_crossover import SMACrossoverStrategy


def _to_int_list(values: List[int]) -> List[int]:
    """Normalize parameter list to unique, sorted integers."""
    return sorted({int(v) for v in values})


def grid_search_sma(
    bars: pd.DataFrame,
    symbol: str,
    cash: float,
    broker_costs: CostModel,
    sizer: PositionSizer,
    param_grid: Dict[str, List[int]],
    split_ratio: float = 0.7,
) -> Dict[str, object]:
    """Run walk-forward grid search for SMA parameters.

    Ranking logic:
    1) Highest out-of-sample Sharpe
    2) Tie-breaker: higher (less negative) out-of-sample max drawdown
    """
    short_values = _to_int_list(param_grid.get("short_window", []))
    long_values = _to_int_list(param_grid.get("long_window", []))
    if not short_values or not long_values:
        raise ValueError("param_grid must include non-empty short_window and long_window lists")

    rows: List[Dict[str, object]] = []

    for short_window, long_window in product(short_values, long_values):
        if short_window >= long_window:
            continue

        def engine_builder(subset_bars: pd.DataFrame):
            strategy = SMACrossoverStrategy(short_window=short_window, long_window=long_window)
            portfolio = Portfolio(symbol=symbol, initial_cash=cash, sizer=deepcopy(sizer))
            broker = SimulatedBroker(
                cost_model=CostModel(
                    commission_bps=broker_costs.commission_bps,
                    slippage_bps=broker_costs.slippage_bps,
                )
            )
            engine = BacktestEngine(
                bars=subset_bars,
                symbol=symbol,
                strategy=strategy,
                portfolio=portfolio,
                broker=broker,
            )
            return engine.run()

        wf_result = run_walkforward(bars=bars, engine_builder=engine_builder, split_ratio=split_ratio)
        in_metrics = wf_result["in_sample"]["metrics"]
        out_metrics = wf_result["out_of_sample"]["metrics"]

        rows.append(
            {
                "short_window": short_window,
                "long_window": long_window,
                "in_sample_sharpe": in_metrics["sharpe"],
                "out_of_sample_sharpe": out_metrics["sharpe"],
                "in_sample_total_return": in_metrics["total_return"],
                "out_of_sample_total_return": out_metrics["total_return"],
                "out_of_sample_max_drawdown": out_metrics["max_drawdown"],
            }
        )

    if not rows:
        raise ValueError("No valid SMA parameter combinations after filtering short<long")

    results_frame = pd.DataFrame(rows)

    rank_frame = results_frame.copy()
    rank_frame["_rank_sharpe"] = rank_frame["out_of_sample_sharpe"].replace([np.inf, -np.inf], np.nan).fillna(-np.inf)
    rank_frame["_rank_mdd"] = rank_frame["out_of_sample_max_drawdown"].replace([np.inf, -np.inf], np.nan).fillna(-np.inf)
    rank_frame = rank_frame.sort_values(["_rank_sharpe", "_rank_mdd"], ascending=[False, False]).reset_index(drop=True)

    best_row = rank_frame.iloc[0]
    best_params = {
        "short_window": int(best_row["short_window"]),
        "long_window": int(best_row["long_window"]),
    }

    grid_csv_path = "grid_results.csv"
    results_frame.to_csv(grid_csv_path, index=False)

    return {
        "results": results_frame,
        "grid_csv_path": grid_csv_path,
        "best_params": best_params,
        "best_out_of_sample_metrics": {
            "sharpe": float(best_row["out_of_sample_sharpe"]),
            "max_drawdown": float(best_row["out_of_sample_max_drawdown"]),
            "total_return": float(best_row["out_of_sample_total_return"]),
        },
    }
