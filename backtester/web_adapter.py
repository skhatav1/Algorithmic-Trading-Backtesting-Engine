"""Adapter used by the web dashboard API."""

from __future__ import annotations

import json
import math
import sys
from io import StringIO
from typing import Any, Dict

import pandas as pd

from backtester.data.loaders import _validate_ohlcv_frame, generate_synthetic_ohlcv
from backtester.engine.backtest_engine import BacktestEngine
from backtester.execution.broker import SimulatedBroker
from backtester.execution.costs import CostModel
from backtester.portfolio.portfolio import Portfolio
from backtester.portfolio.position_sizing import AllInSizer, FixedFractionSizer
from backtester.strategies.mean_reversion import MeanReversionStrategy
from backtester.strategies.sma_crossover import SMACrossoverStrategy


MAX_CSV_BYTES = 1_500_000
MAX_SYNTHETIC_BARS = 2_000


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy values and non-finite floats into valid JSON values."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return json_safe(value.item())
    return value


def _to_float(value: Any, default: float) -> float:
    """Parse a numeric request field with a fallback."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    """Parse an integer request field with a fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_bars(payload: Dict[str, Any]) -> pd.DataFrame:
    """Load browser-provided CSV data or deterministic synthetic data."""
    csv_text = str(payload.get("csv_text") or "").strip()
    if csv_text:
        if len(csv_text.encode("utf-8")) > MAX_CSV_BYTES:
            raise ValueError("CSV is too large for the live demo. Please use a smaller file.")
        return _validate_ohlcv_frame(pd.read_csv(StringIO(csv_text)))

    n_bars = min(MAX_SYNTHETIC_BARS, max(60, _to_int(payload.get("synthetic_bars"), 600)))
    seed = _to_int(payload.get("seed"), 42)
    return generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)


def _build_strategy(payload: Dict[str, Any]):
    """Create a strategy from request parameters."""
    strategy_name = str(payload.get("strategy") or "sma")
    if strategy_name == "sma":
        return SMACrossoverStrategy(
            short_window=_to_int(payload.get("short_window"), 10),
            long_window=_to_int(payload.get("long_window"), 50),
        )
    if strategy_name == "mean_reversion":
        return MeanReversionStrategy(
            lookback=_to_int(payload.get("lookback"), 20),
            entry_z=_to_float(payload.get("entry_z"), 1.0),
            exit_z=_to_float(payload.get("exit_z"), 0.25),
        )
    raise ValueError(f"Unsupported strategy: {strategy_name}")


def _build_sizer(payload: Dict[str, Any]):
    """Create a position sizer from request parameters."""
    if str(payload.get("sizer") or "all_in") == "fixed_fraction":
        return FixedFractionSizer(fraction=_to_float(payload.get("fraction"), 0.1))
    return AllInSizer()


def run_backtest_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the core backtester and convert outputs to browser-friendly JSON."""
    bars = _load_bars(payload)
    strategy = _build_strategy(payload)
    initial_cash = _to_float(payload.get("cash"), 100_000.0)
    portfolio = Portfolio(symbol="DEMO", initial_cash=initial_cash, sizer=_build_sizer(payload))
    broker = SimulatedBroker(
        cost_model=CostModel(
            commission_bps=_to_float(payload.get("commission_bps"), 1.0),
            slippage_bps=_to_float(payload.get("slippage_bps"), 2.0),
        )
    )
    engine = BacktestEngine(
        bars=bars,
        symbol="DEMO",
        strategy=strategy,
        portfolio=portfolio,
        broker=broker,
    )
    result = engine.run()

    history = result.history.copy()
    history["timestamp"] = history["timestamp"].astype(str)
    trades = result.trades.copy()
    if not trades.empty:
        trades["timestamp"] = trades["timestamp"].astype(str)

    equity_points = [
        {
            "timestamp": row["timestamp"],
            "equity": float(row["equity"]),
            "cash": float(row["cash"]),
            "shares": int(row["shares"]),
            "returns": float(row["returns"]),
        }
        for row in history.to_dict(orient="records")
    ]

    return {
        "metrics": result.metrics,
        "trade_count": result.trade_count,
        "bars": int(len(bars)),
        "equity_curve": equity_points,
        "trades": trades.to_dict(orient="records"),
    }


def main() -> None:
    """CLI bridge for the Node Vercel function."""
    payload = json.loads(sys.stdin.read() or "{}")
    result = run_backtest_from_payload(payload)
    print(json.dumps({"ok": True, "result": json_safe(result)}, allow_nan=False))


if __name__ == "__main__":
    main()
