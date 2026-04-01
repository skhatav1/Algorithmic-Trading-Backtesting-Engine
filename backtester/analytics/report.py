"""Result reporting utilities."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import pandas as pd

try:
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False


def build_text_report(
    metrics: Dict[str, float],
    trade_count: int,
    benchmark_metrics: Optional[Dict[str, float]] = None,
    relative_metrics: Optional[Dict[str, float]] = None,
    walkforward_summary: Optional[Dict[str, Dict[str, float]]] = None,
) -> str:
    """Build a human-readable report string."""
    lines = [
        "=== Backtest Report ===",
        f"Total Return : {metrics['total_return'] * 100:.2f}%",
        f"CAGR         : {metrics['cagr'] * 100:.2f}%",
        f"Volatility   : {metrics['volatility'] * 100:.2f}%",
        f"Sharpe Ratio : {metrics['sharpe']:.3f}",
        f"Max Drawdown : {metrics['max_drawdown'] * 100:.2f}%",
        f"Sortino      : {metrics['sortino']:.3f}",
        f"Calmar       : {metrics['calmar']:.3f}",
        f"Trades       : {trade_count}",
    ]

    if benchmark_metrics is not None and relative_metrics is not None:
        lines.extend(
            [
                "",
                "=== Benchmark Comparison ===",
                f"Benchmark Return : {benchmark_metrics['total_return'] * 100:.2f}%",
                f"Benchmark Sharpe : {benchmark_metrics['sharpe']:.3f}",
                f"Alpha (annual)   : {relative_metrics['alpha']:.5f}",
                f"Beta             : {relative_metrics['beta']:.5f}",
                f"Correlation      : {relative_metrics['correlation']:.5f}",
            ]
        )

    if walkforward_summary is not None:
        in_sample = walkforward_summary["in_sample"]["metrics"]
        out_sample = walkforward_summary["out_of_sample"]["metrics"]
        lines.extend(
            [
                "",
                "=== Walk-Forward ===",
                f"In-sample Sharpe : {in_sample['sharpe']:.3f}",
                f"Out-sample Sharpe: {out_sample['sharpe']:.3f}",
                f"In-sample Return : {in_sample['total_return'] * 100:.2f}%",
                f"Out-sample Return: {out_sample['total_return'] * 100:.2f}%",
            ]
        )

    return "\n".join(lines)


def save_results_json(payload: Dict[str, Any], path: str = "results.json") -> None:
    """Save run payload (metrics, params, extras) to JSON."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def save_results_txt(report_text: str, path: str = "results.txt") -> None:
    """Save plain-text summary report."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report_text + "\n")


def save_equity_csv(equity_frame: pd.DataFrame, path: str = "equity_curve.csv") -> None:
    """Save equity history to CSV."""
    equity_frame.to_csv(path, index=False)


def save_trades_csv(trades_frame: pd.DataFrame, path: str = "trades.csv") -> None:
    """Save trade log to CSV using user-facing column names."""
    out = trades_frame.copy()
    if out.empty:
        out = pd.DataFrame(columns=["timestamp", "side", "qty", "price", "commission", "slippage"])
    else:
        out = out.rename(
            columns={
                "quantity": "qty",
                "fill_price": "price",
                "commission_paid": "commission",
                "slippage_paid": "slippage",
            }
        )
        out = out[["timestamp", "side", "qty", "price", "commission", "slippage"]]
    out.to_csv(path, index=False)


def maybe_plot_equity(equity_frame: pd.DataFrame, no_plot: bool = False) -> None:
    """Plot equity curve when matplotlib is available and plotting is enabled."""
    if no_plot or not HAS_MATPLOTLIB:
        return

    plt.figure(figsize=(10, 5))
    plt.plot(equity_frame["timestamp"], equity_frame["equity"], label="Equity")
    plt.title("Equity Curve")
    plt.xlabel("Time")
    plt.ylabel("Portfolio Value")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()
