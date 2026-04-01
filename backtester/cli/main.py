"""CLI entrypoint for running backtests."""

from __future__ import annotations

import argparse
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

import pandas as pd

from backtester.analytics.metrics import compute_benchmark_comparison
from backtester.analytics.report import (
    build_text_report,
    maybe_plot_equity,
    save_equity_csv,
    save_results_json,
    save_results_txt,
    save_trades_csv,
)
from backtester.config import BacktestConfig
from backtester.data.loaders import generate_synthetic_ohlcv, load_benchmark_close_csv, load_csv_ohlcv
from backtester.engine.backtest_engine import BacktestEngine, BacktestResult
from backtester.engine.grid_search import grid_search_sma
from backtester.engine.walkforward import run_walkforward
from backtester.execution.broker import SimulatedBroker
from backtester.execution.costs import CostModel
from backtester.portfolio.portfolio import Portfolio
from backtester.portfolio.position_sizing import AllInSizer, FixedFractionSizer, PositionSizer
from backtester.strategies.base import StrategyBase
from backtester.strategies.mean_reversion import MeanReversionStrategy
from backtester.strategies.sma_crossover import SMACrossoverStrategy


def build_strategy(args: argparse.Namespace) -> StrategyBase:
    """Create strategy object from CLI args."""
    if args.strategy == "sma":
        return SMACrossoverStrategy(short_window=args.short, long_window=args.long)
    if args.strategy == "mean_reversion":
        return MeanReversionStrategy(lookback=args.lookback, entry_z=args.entry_z, exit_z=args.exit_z)
    raise ValueError(f"Unsupported strategy: {args.strategy}")


def build_sizer(args: argparse.Namespace) -> PositionSizer:
    """Create position sizer from CLI args."""
    if args.sizer == "all_in":
        return AllInSizer()
    if args.sizer == "fixed_fraction":
        return FixedFractionSizer(fraction=args.fraction)
    raise ValueError(f"Unsupported sizer: {args.sizer}")


def _parse_int_grid(raw: str) -> List[int]:
    """Parse comma-separated integer grid values."""
    values = [token.strip() for token in raw.split(",") if token.strip()]
    parsed = [int(value) for value in values]
    if not parsed:
        raise ValueError("Grid list cannot be empty")
    return parsed


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Event-driven backtester")
    parser.add_argument("--csv", type=str, default=None, help="Path to OHLCV CSV")
    parser.add_argument("--benchmark_csv", type=str, default=None, help="Path to benchmark CSV (timestamp, close)")
    parser.add_argument("--symbol", type=str, default="TEST", help="Symbol label for reporting")
    parser.add_argument("--strategy", choices=["sma", "mean_reversion"], default="sma")

    # SMA params
    parser.add_argument("--short", type=int, default=10, help="SMA short window")
    parser.add_argument("--long", type=int, default=50, help="SMA long window")

    # Mean reversion params
    parser.add_argument("--lookback", type=int, default=20, help="Mean reversion lookback")
    parser.add_argument("--entry_z", type=float, default=1.0, help="Entry z-score threshold")
    parser.add_argument("--exit_z", type=float, default=0.25, help="Exit z-score threshold")

    parser.add_argument("--cash", type=float, default=100_000.0, help="Initial cash")
    parser.add_argument("--commission_bps", type=float, default=1.0, help="Commission in bps")
    parser.add_argument("--slippage_bps", type=float, default=2.0, help="Slippage in bps")

    parser.add_argument("--sizer", choices=["all_in", "fixed_fraction"], default="all_in")
    parser.add_argument("--fraction", type=float, default=0.10, help="Fixed-fraction size (0 to 1]")

    parser.add_argument("--synthetic_bars", type=int, default=600, help="Bars for synthetic mode")
    parser.add_argument("--seed", type=int, default=42, help="Seed for synthetic mode")

    parser.add_argument("--walkforward", action="store_true", help="Run walk-forward in/out-sample evaluation")
    parser.add_argument("--split_ratio", type=float, default=0.7, help="In-sample split ratio for walk-forward")
    parser.add_argument("--grid_search", action="store_true", help="Run SMA walk-forward grid search")
    parser.add_argument("--short_grid", type=str, default="5,10,20", help="SMA short grid, comma separated")
    parser.add_argument("--long_grid", type=str, default="30,50,100", help="SMA long grid, comma separated")

    parser.add_argument("--no_plot", action="store_true", help="Disable equity plot")
    parser.add_argument("--log_level", type=str, default="INFO", help="Logging level")

    return parser.parse_args()


def namespace_to_config(args: argparse.Namespace) -> BacktestConfig:
    """Convert CLI args to serializable config object."""
    strategy_params: Dict[str, float]
    if args.strategy == "sma":
        strategy_params = {"short": args.short, "long": args.long}
    else:
        strategy_params = {
            "lookback": args.lookback,
            "entry_z": args.entry_z,
            "exit_z": args.exit_z,
        }

    return BacktestConfig(
        csv_path=args.csv,
        strategy_name=args.strategy,
        initial_cash=args.cash,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        plot=not args.no_plot,
        strategy_params=strategy_params,
        sizer_name=args.sizer,
        fixed_fraction=args.fraction,
    )


def _run_engine(
    bars: pd.DataFrame,
    symbol: str,
    strategy: StrategyBase,
    cash: float,
    commission_bps: float,
    slippage_bps: float,
    sizer: PositionSizer,
) -> BacktestResult:
    """Build engine components and run one backtest."""
    portfolio = Portfolio(symbol=symbol, initial_cash=cash, sizer=deepcopy(sizer))
    broker = SimulatedBroker(cost_model=CostModel(commission_bps=commission_bps, slippage_bps=slippage_bps))
    engine = BacktestEngine(
        bars=bars,
        symbol=symbol,
        strategy=strategy,
        portfolio=portfolio,
        broker=broker,
    )
    return engine.run()


def _walkforward_json_safe(wf_result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert walk-forward result into JSON-safe payload."""
    comparison_table = wf_result["comparison_table"]
    return {
        "in_sample": {
            "metrics": wf_result["in_sample"]["metrics"],
            "trade_count": wf_result["in_sample"]["trade_count"],
        },
        "out_of_sample": {
            "metrics": wf_result["out_of_sample"]["metrics"],
            "trade_count": wf_result["out_of_sample"]["trade_count"],
        },
        "comparison_table": comparison_table.to_dict(orient="records"),
        "split_timestamp": str(wf_result["split_timestamp"]),
    }


def main() -> None:
    """Run backtest from command line."""
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if args.grid_search and args.strategy != "sma":
        raise ValueError("--grid_search currently supports only --strategy sma")

    config = namespace_to_config(args)

    if args.csv:
        bars = load_csv_ohlcv(args.csv)
    else:
        bars = generate_synthetic_ohlcv(n_bars=args.synthetic_bars, seed=args.seed)

    sizer = build_sizer(args)
    strategy = build_strategy(args)

    walkforward_payload: Optional[Dict[str, Any]] = None
    benchmark_payload: Optional[Dict[str, Any]] = None
    grid_payload: Optional[Dict[str, Any]] = None

    result: BacktestResult

    if args.grid_search:
        short_grid = _parse_int_grid(args.short_grid)
        long_grid = _parse_int_grid(args.long_grid)

        grid_out = grid_search_sma(
            bars=bars,
            symbol=args.symbol,
            cash=args.cash,
            broker_costs=CostModel(commission_bps=args.commission_bps, slippage_bps=args.slippage_bps),
            sizer=sizer,
            param_grid={"short_window": short_grid, "long_window": long_grid},
            split_ratio=args.split_ratio,
        )

        best_params = grid_out["best_params"]
        print(
            f"Best SMA params: short={best_params['short_window']}, "
            f"long={best_params['long_window']}"
        )

        grid_payload = {
            "best_params": best_params,
            "best_out_of_sample_metrics": grid_out["best_out_of_sample_metrics"],
            "grid_csv_path": grid_out["grid_csv_path"],
        }

        # Final evaluation uses out-of-sample partition only with best params.
        ordered = bars.sort_values("timestamp").reset_index(drop=True)
        split_idx = int(len(ordered) * args.split_ratio)
        split_idx = max(2, min(split_idx, len(ordered) - 2))
        out_sample_bars = ordered.iloc[split_idx:].reset_index(drop=True)

        best_strategy = SMACrossoverStrategy(
            short_window=best_params["short_window"],
            long_window=best_params["long_window"],
        )
        result = _run_engine(
            bars=out_sample_bars,
            symbol=args.symbol,
            strategy=best_strategy,
            cash=args.cash,
            commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps,
            sizer=sizer,
        )

    else:
        result = _run_engine(
            bars=bars,
            symbol=args.symbol,
            strategy=strategy,
            cash=args.cash,
            commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps,
            sizer=sizer,
        )

        if args.walkforward:
            def engine_builder(subset_bars: pd.DataFrame) -> BacktestResult:
                local_strategy = build_strategy(args)
                return _run_engine(
                    bars=subset_bars,
                    symbol=args.symbol,
                    strategy=local_strategy,
                    cash=args.cash,
                    commission_bps=args.commission_bps,
                    slippage_bps=args.slippage_bps,
                    sizer=sizer,
                )

            wf_result = run_walkforward(
                bars=bars,
                engine_builder=engine_builder,
                split_ratio=args.split_ratio,
            )
            walkforward_payload = _walkforward_json_safe(wf_result)

    if args.benchmark_csv:
        benchmark_close = load_benchmark_close_csv(args.benchmark_csv)
        benchmark_out = compute_benchmark_comparison(
            strategy_history=result.history,
            benchmark_close=benchmark_close,
            initial_cash=args.cash,
        )
        benchmark_payload = {
            "benchmark_metrics": benchmark_out["benchmark_metrics"],
            "relative_metrics": benchmark_out["relative_metrics"],
            "aligned_rows": int(len(benchmark_out["merged_frame"])),
        }

    report_text = build_text_report(
        metrics=result.metrics,
        trade_count=result.trade_count,
        benchmark_metrics=benchmark_payload["benchmark_metrics"] if benchmark_payload else None,
        relative_metrics=benchmark_payload["relative_metrics"] if benchmark_payload else None,
        walkforward_summary=walkforward_payload if walkforward_payload else None,
    )
    print(report_text)

    payload: Dict[str, Any] = {
        "metrics": result.metrics,
        "parameters": {
            "config": config.__dict__,
            "symbol": args.symbol,
            "strategy": args.strategy,
            "bars": len(bars),
        },
    }
    if benchmark_payload is not None:
        payload["benchmark"] = benchmark_payload
    if walkforward_payload is not None:
        payload["walkforward"] = walkforward_payload
    if grid_payload is not None:
        payload["grid_search"] = grid_payload

    save_results_json(payload)
    save_results_txt(report_text)
    save_equity_csv(result.history)
    save_trades_csv(result.trades)

    maybe_plot_equity(result.history, no_plot=args.no_plot)


if __name__ == "__main__":
    main()
