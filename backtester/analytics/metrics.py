"""Performance metric calculations."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


def compute_metrics(equity_curve: pd.Series, periods_per_year: int = 252) -> Dict[str, float]:
    """Compute core backtest metrics from an equity curve.

    Risk-free rate is assumed to be zero for Sharpe/Sortino.
    """
    if len(equity_curve) < 2:
        raise ValueError("Need at least 2 equity points to compute metrics")

    equity = equity_curve.astype(float)
    daily_returns = equity.pct_change().dropna()

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)

    years = len(equity) / float(periods_per_year)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0) if years > 0 else np.nan

    volatility = float(daily_returns.std(ddof=0) * np.sqrt(periods_per_year)) if len(daily_returns) > 0 else np.nan
    annual_return = float(daily_returns.mean() * periods_per_year) if len(daily_returns) > 0 else np.nan
    sharpe = float(annual_return / volatility) if volatility and np.isfinite(volatility) and volatility > 0 else np.nan

    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min())

    downside = daily_returns[daily_returns < 0]
    downside_vol = float(downside.std(ddof=0) * np.sqrt(periods_per_year)) if len(downside) > 0 else np.nan
    sortino = (
        float(annual_return / downside_vol)
        if downside_vol and np.isfinite(downside_vol) and downside_vol > 0
        else np.nan
    )

    calmar = float(cagr / abs(max_drawdown)) if max_drawdown < 0 else np.nan

    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "sortino": sortino,
        "calmar": calmar,
    }


def _compute_alpha_beta(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int = 252,
) -> Dict[str, float]:
    """Compute alpha and beta from aligned strategy/benchmark return series.

    Beta is covariance(strategy, benchmark) / variance(benchmark).
    Alpha is annualized mean excess return over beta-adjusted benchmark.
    """
    merged = pd.concat(
        [strategy_returns.rename("strategy"), benchmark_returns.rename("benchmark")],
        axis=1,
    ).dropna()

    if len(merged) < 2:
        return {"alpha": float("nan"), "beta": float("nan"), "correlation": float("nan")}

    strat = merged["strategy"].to_numpy(dtype=float)
    bench = merged["benchmark"].to_numpy(dtype=float)

    var_bench = float(np.var(bench, ddof=0))
    cov = float(np.cov(strat, bench, ddof=0)[0, 1])

    beta = cov / var_bench if var_bench > 0 else np.nan
    mean_strat = float(np.mean(strat))
    mean_bench = float(np.mean(bench))

    if np.isfinite(beta):
        alpha = (mean_strat - beta * mean_bench) * periods_per_year
    else:
        alpha = np.nan

    correlation = float(np.corrcoef(strat, bench)[0, 1]) if np.std(strat) > 0 and np.std(bench) > 0 else np.nan

    return {"alpha": float(alpha), "beta": float(beta), "correlation": correlation}


def compute_benchmark_comparison(
    strategy_history: pd.DataFrame,
    benchmark_close: pd.DataFrame,
    initial_cash: float,
    periods_per_year: int = 252,
) -> Dict[str, Any]:
    """Align strategy vs benchmark and compute comparison stats.

    Parameters
    ----------
    strategy_history:
        Must contain columns: timestamp, equity.
    benchmark_close:
        Must contain columns: timestamp, close.
    initial_cash:
        Starting value used to build benchmark equity curve.

    Returns
    -------
    dict
        merged_frame: aligned strategy + benchmark frame
        benchmark_metrics: standard performance metrics on benchmark equity
        relative_metrics: alpha, beta, correlation
    """
    required_strategy = ["timestamp", "equity"]
    required_benchmark = ["timestamp", "close"]

    missing_strategy = [col for col in required_strategy if col not in strategy_history.columns]
    missing_benchmark = [col for col in required_benchmark if col not in benchmark_close.columns]
    if missing_strategy:
        raise ValueError(f"strategy_history missing columns: {missing_strategy}")
    if missing_benchmark:
        raise ValueError(f"benchmark_close missing columns: {missing_benchmark}")

    strategy = strategy_history[required_strategy].copy()
    strategy["timestamp"] = pd.to_datetime(strategy["timestamp"], errors="coerce")
    strategy = strategy.dropna(subset=["timestamp"]).sort_values("timestamp")

    benchmark = benchmark_close[required_benchmark].copy()
    benchmark["timestamp"] = pd.to_datetime(benchmark["timestamp"], errors="coerce")
    benchmark = benchmark.dropna(subset=["timestamp"]).sort_values("timestamp")

    merged = strategy.merge(
        benchmark.rename(columns={"close": "benchmark_close"}),
        how="inner",
        on="timestamp",
    )
    if len(merged) < 2:
        raise ValueError("Not enough overlapping timestamps between strategy and benchmark.")

    merged["strategy_returns"] = merged["equity"].pct_change().fillna(0.0)
    merged["benchmark_returns"] = merged["benchmark_close"].pct_change().fillna(0.0)
    merged["benchmark_equity"] = initial_cash * (1.0 + merged["benchmark_returns"]).cumprod()

    benchmark_metrics = compute_metrics(merged["benchmark_equity"], periods_per_year=periods_per_year)
    relative_metrics = _compute_alpha_beta(
        strategy_returns=merged["strategy_returns"],
        benchmark_returns=merged["benchmark_returns"],
        periods_per_year=periods_per_year,
    )

    return {
        "merged_frame": merged,
        "benchmark_metrics": benchmark_metrics,
        "relative_metrics": relative_metrics,
    }
