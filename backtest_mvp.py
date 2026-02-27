"""
Backtesting MVP for a single symbol using OHLCV data.

Strategy:
- Simple Moving Average (SMA) crossover.
- Signal is decided at end of bar t using close[t].
- Order is executed at open[t+1] (next bar open).

This script intentionally prioritizes readability over advanced architecture.
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


try:
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False


REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def generate_synthetic_data(n_bars: int = 600, seed: int = 42) -> pd.DataFrame:
    """
    Generate deterministic synthetic OHLCV data.

    Why this exists:
    - So the backtester always runs, even if no CSV is provided.
    - Fixed seed means reproducible outputs for learners.
    """
    rng = np.random.default_rng(seed)

    # Business-day timestamps keep the series realistic for daily bars.
    timestamps = pd.date_range(start="2020-01-01", periods=n_bars, freq="B")

    # Build a random-walk-like close price with slight upward drift.
    daily_returns = rng.normal(loc=0.0004, scale=0.012, size=n_bars)
    close = 100.0 * np.cumprod(1.0 + daily_returns)

    # Open is near previous close with small overnight noise.
    open_prices = np.empty_like(close)
    open_prices[0] = close[0] * (1.0 + rng.normal(0.0, 0.002))
    for i in range(1, n_bars):
        open_prices[i] = close[i - 1] * (1.0 + rng.normal(0.0, 0.003))

    # High/low envelope around open/close to form valid OHLC candles.
    high = np.maximum(open_prices, close) * (1.0 + rng.uniform(0.0, 0.01, size=n_bars))
    low = np.minimum(open_prices, close) * (1.0 - rng.uniform(0.0, 0.01, size=n_bars))

    # Synthetic volume in a plausible range.
    volume = rng.integers(100_000, 2_000_000, size=n_bars)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )

    return df


def load_data(csv_path: Optional[str]) -> pd.DataFrame:
    """
    Load OHLCV data from CSV, or generate synthetic data if no path is given.

    Returns
    -------
    pd.DataFrame
        DataFrame sorted by timestamp with required columns.
    """
    if csv_path is None:
        print("No CSV provided. Using synthetic OHLCV data (fixed seed).")
        df = generate_synthetic_data()
    else:
        df = pd.read_csv(csv_path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. "
            f"Expected columns: {REQUIRED_COLUMNS}"
        )

    # Keep only needed columns in a known order.
    df = df[REQUIRED_COLUMNS].copy()

    # Convert timestamp to datetime and sort.
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if df["timestamp"].isna().any():
        raise ValueError("Some timestamp values could not be parsed as datetime.")

    df = df.sort_values("timestamp").reset_index(drop=True)

    # Ensure numeric columns are numeric.
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[numeric_cols].isna().any().any():
        raise ValueError("Some OHLCV numeric values are invalid (NaN after parsing).")

    # Basic price sanity checks.
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive.")

    return df


def compute_indicators(df: pd.DataFrame, short_window: int, long_window: int) -> pd.DataFrame:
    """
    Add SMA indicators.

    Notes for beginners:
    - SMA is the simple average of recent closing prices.
    - We use min_periods=window to avoid partially formed averages.
    """
    if short_window <= 0 or long_window <= 0:
        raise ValueError("short_window and long_window must be positive integers.")
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window.")
    if len(df) < long_window + 2:
        raise ValueError(
            "Not enough rows for long_window and next-open execution. "
            f"Need at least {long_window + 2} rows."
        )

    out = df.copy()
    out["sma_short"] = out["close"].rolling(window=short_window, min_periods=short_window).mean()
    out["sma_long"] = out["close"].rolling(window=long_window, min_periods=long_window).mean()
    return out


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate position intent from SMA crossover.

    Signal definition:
    - 1 means "want to be long"
    - 0 means "want to be flat"

    Crucially, this signal uses only information available at bar close t.
    Execution happens at next bar open in run_backtest.
    """
    out = df.copy()

    # Long when short SMA is above long SMA. Otherwise flat.
    out["signal"] = np.where(out["sma_short"] > out["sma_long"], 1, 0)

    # Before both SMAs exist, force flat.
    out.loc[out[["sma_short", "sma_long"]].isna().any(axis=1), "signal"] = 0
    out["signal"] = out["signal"].astype(int)

    return out


def run_backtest(
    df: pd.DataFrame,
    initial_cash: float,
    commission_bps: float,
    slippage_bps: float,
) -> Tuple[pd.DataFrame, int]:
    """
    Simulate portfolio path with next-open execution and trading costs.

    Assumptions:
    - Single symbol
    - Long-only, all-in/all-out position sizing
    - No fractional shares
    - At most one trade action per bar open

    Cost model (applied per trade side):
    - Buy effective price  = open * (1 + slippage + commission)
    - Sell effective price = open * (1 - slippage - commission)

    Both slippage and commission are in basis points (bps), where 1 bps = 0.01%.
    """
    if initial_cash <= 0:
        raise ValueError("initial_cash must be > 0")
    if commission_bps < 0 or slippage_bps < 0:
        raise ValueError("commission_bps and slippage_bps must be >= 0")

    commission_rate = commission_bps / 10_000.0
    slippage_rate = slippage_bps / 10_000.0

    out = df.copy()

    cash = float(initial_cash)
    shares = 0
    trade_count = 0

    cash_history: List[float] = []
    shares_history: List[int] = []
    equity_history: List[float] = []

    n = len(out)
    for t in range(n):
        # Decide action at this bar open based on *previous* bar's signal.
        # This enforces no lookahead bias.
        desired_position = int(out.loc[t - 1, "signal"]) if t > 0 else 0

        open_px = float(out.loc[t, "open"])

        # Enter long (all-in) if desired and currently flat.
        if desired_position == 1 and shares == 0:
            effective_buy_price = open_px * (1.0 + slippage_rate + commission_rate)
            # Integer shares only.
            qty = int(cash // effective_buy_price)
            if qty > 0:
                cash -= qty * effective_buy_price
                shares += qty
                trade_count += 1

        # Exit long if desired flat and currently long.
        elif desired_position == 0 and shares > 0:
            effective_sell_price = open_px * (1.0 - slippage_rate - commission_rate)
            cash += shares * effective_sell_price
            shares = 0
            trade_count += 1

        # End-of-bar mark-to-market uses close price.
        close_px = float(out.loc[t, "close"])
        equity = cash + shares * close_px

        cash_history.append(cash)
        shares_history.append(shares)
        equity_history.append(equity)

    out["cash"] = cash_history
    out["shares"] = shares_history
    out["equity"] = equity_history

    # Strategy daily return for reference (NaN at first row -> fill 0).
    out["strategy_return"] = out["equity"].pct_change().fillna(0.0)

    return out, trade_count


def compute_metrics(equity_curve_series: pd.Series) -> Dict[str, float]:
    """
    Compute basic performance metrics from equity curve.

    Uses 252 trading days/year for annualization.
    Risk-free rate is assumed 0.
    """
    if len(equity_curve_series) < 2:
        raise ValueError("Need at least 2 equity points to compute metrics.")

    equity = equity_curve_series.astype(float)
    daily_ret = equity.pct_change().dropna()

    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0

    n_days = len(equity)
    years = n_days / 252.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else np.nan

    vol = daily_ret.std(ddof=0) * np.sqrt(252.0) if len(daily_ret) > 0 else np.nan
    mean_ret = daily_ret.mean() * 252.0 if len(daily_ret) > 0 else np.nan

    if vol is not None and np.isfinite(vol) and vol > 0:
        sharpe = mean_ret / vol
    else:
        sharpe = np.nan

    # Drawdown: (equity / running_max) - 1
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    max_drawdown = float(drawdown.min())

    return {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "volatility": float(vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_drawdown),
    }


def print_report(metrics: Dict[str, float], trade_count: int) -> None:
    """Print a small terminal report."""
    print("\n=== Backtest Report ===")
    print(f"Total Return : {metrics['total_return'] * 100:.2f}%")
    print(f"CAGR         : {metrics['cagr'] * 100:.2f}%")
    print(f"Volatility   : {metrics['volatility'] * 100:.2f}%")
    print(f"Sharpe Ratio : {metrics['sharpe']:.3f}")
    print(f"Max Drawdown : {metrics['max_drawdown'] * 100:.2f}%")
    print(f"Trades       : {trade_count}")


def save_results_json(metrics: Dict[str, float], params: Dict[str, float], path: str = "results.json") -> None:
    """Save metrics and run parameters to a JSON file."""
    payload = {
        "metrics": metrics,
        "parameters": params,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def maybe_plot_equity(df: pd.DataFrame) -> None:
    """Plot equity curve if matplotlib is available."""
    if not HAS_MATPLOTLIB:
        print("matplotlib not available; skipping plot.")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(df["timestamp"], df["equity"], label="Equity Curve")
    plt.title("Backtest Equity Curve")
    plt.xlabel("Time")
    plt.ylabel("Portfolio Value")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Beginner-friendly SMA crossover backtesting MVP")
    parser.add_argument("--csv", type=str, default=None, help="Path to OHLCV CSV file")
    parser.add_argument("--short", type=int, default=10, help="Short SMA window")
    parser.add_argument("--long", type=int, default=50, help="Long SMA window")
    parser.add_argument("--cash", type=float, default=100_000.0, help="Initial cash")
    parser.add_argument(
        "--commission_bps",
        type=float,
        default=1.0,
        help="Commission in basis points (per trade side)",
    )
    parser.add_argument(
        "--slippage_bps",
        type=float,
        default=2.0,
        help="Slippage in basis points (per trade side)",
    )
    parser.add_argument(
        "--no_plot",
        action="store_true",
        help="Disable equity curve plot even if matplotlib is installed",
    )

    args = parser.parse_args()

    df = load_data(args.csv)
    df = compute_indicators(df, short_window=args.short, long_window=args.long)
    df = generate_signals(df)

    bt_df, trade_count = run_backtest(
        df=df,
        initial_cash=args.cash,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
    )

    metrics = compute_metrics(bt_df["equity"])
    print_report(metrics, trade_count)

    params = {
        "csv": args.csv,
        "short_window": args.short,
        "long_window": args.long,
        "initial_cash": args.cash,
        "commission_bps": args.commission_bps,
        "slippage_bps": args.slippage_bps,
    }
    save_results_json(metrics=metrics, params=params, path="results.json")
    print("Saved results to results.json")

    if not args.no_plot:
        maybe_plot_equity(bt_df)


if __name__ == "__main__":
    main()
