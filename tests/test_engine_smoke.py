"""Smoke test for full backtest run."""

from __future__ import annotations

import numpy as np

from backtester.data.loaders import generate_synthetic_ohlcv
from backtester.engine.backtest_engine import BacktestEngine
from backtester.execution.broker import SimulatedBroker
from backtester.execution.costs import CostModel
from backtester.portfolio.portfolio import Portfolio
from backtester.portfolio.position_sizing import AllInSizer
from backtester.strategies.sma_crossover import SMACrossoverStrategy


def test_engine_smoke_runs_and_outputs_metrics() -> None:
    bars = generate_synthetic_ohlcv(n_bars=220, seed=42)

    strategy = SMACrossoverStrategy(short_window=10, long_window=50)
    portfolio = Portfolio(symbol="TEST", initial_cash=100_000.0, sizer=AllInSizer())
    broker = SimulatedBroker(cost_model=CostModel(commission_bps=1.0, slippage_bps=2.0))

    engine = BacktestEngine(
        bars=bars,
        symbol="TEST",
        strategy=strategy,
        portfolio=portfolio,
        broker=broker,
    )
    result = engine.run()

    assert "equity" in result.history.columns
    assert len(result.history) > 0

    # Finite checks for core metrics.
    assert np.isfinite(result.metrics["total_return"])
    assert np.isfinite(result.metrics["cagr"])
    assert np.isfinite(result.metrics["volatility"])
    assert np.isfinite(result.metrics["max_drawdown"])

    # Trade count is non-negative integer.
    assert isinstance(result.trade_count, int)
    assert result.trade_count >= 0
