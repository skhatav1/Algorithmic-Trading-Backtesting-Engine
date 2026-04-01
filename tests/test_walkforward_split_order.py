"""Tests for chronological walk-forward splitting."""

from __future__ import annotations

import pandas as pd

from backtester.data.loaders import generate_synthetic_ohlcv
from backtester.engine.backtest_engine import BacktestEngine, BacktestResult
from backtester.engine.walkforward import run_walkforward
from backtester.execution.broker import SimulatedBroker
from backtester.execution.costs import CostModel
from backtester.portfolio.portfolio import Portfolio
from backtester.portfolio.position_sizing import AllInSizer
from backtester.strategies.sma_crossover import SMACrossoverStrategy


def test_walkforward_split_order() -> None:
    bars = generate_synthetic_ohlcv(n_bars=120, seed=7)

    def engine_builder(subset_bars: pd.DataFrame) -> BacktestResult:
        strategy = SMACrossoverStrategy(short_window=10, long_window=30)
        portfolio = Portfolio(symbol="TEST", initial_cash=100_000.0, sizer=AllInSizer())
        broker = SimulatedBroker(cost_model=CostModel(commission_bps=1.0, slippage_bps=2.0))
        engine = BacktestEngine(
            bars=subset_bars,
            symbol="TEST",
            strategy=strategy,
            portfolio=portfolio,
            broker=broker,
        )
        return engine.run()

    wf = run_walkforward(bars=bars, engine_builder=engine_builder, split_ratio=0.7)

    in_hist = wf["in_sample"]["history"]
    out_hist = wf["out_of_sample"]["history"]

    assert len(in_hist) > 0
    assert len(out_hist) > 0
    assert in_hist["timestamp"].max() < out_hist["timestamp"].min()
