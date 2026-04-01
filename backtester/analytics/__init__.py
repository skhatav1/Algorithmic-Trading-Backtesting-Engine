"""Analytics helpers for metrics and report output."""

from backtester.analytics.metrics import compute_benchmark_comparison, compute_metrics
from backtester.analytics.report import (
    build_text_report,
    maybe_plot_equity,
    save_equity_csv,
    save_results_json,
    save_results_txt,
    save_trades_csv,
)

__all__ = [
    "compute_metrics",
    "compute_benchmark_comparison",
    "build_text_report",
    "save_results_json",
    "save_results_txt",
    "save_equity_csv",
    "save_trades_csv",
    "maybe_plot_equity",
]
