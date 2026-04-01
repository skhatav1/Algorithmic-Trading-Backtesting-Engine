"""CSV and synthetic data loaders for OHLCV data."""

from __future__ import annotations

import logging
from typing import List

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def _validate_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize OHLCV columns.

    This function does not forward-fill missing timestamps or prices.
    Missing values are treated as data quality issues and raise errors.
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Expected: {REQUIRED_COLUMNS}")

    out = df[REQUIRED_COLUMNS].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")

    if out["timestamp"].isna().any():
        raise ValueError("Invalid timestamps found. Please clean the input CSV.")

    if out["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps found. Please provide unique bar timestamps.")

    numeric_cols: List[str] = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    if out[numeric_cols].isna().any().any():
        raise ValueError("Invalid numeric OHLCV values found (NaN after parsing).")

    if (out[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive.")

    if (out["volume"] < 0).any():
        raise ValueError("Volume must be non-negative.")

    out = out.sort_values("timestamp").reset_index(drop=True)

    # Gaps in timestamps are allowed. We do not fill them by default.
    return out


def load_csv_ohlcv(csv_path: str) -> pd.DataFrame:
    """Load OHLCV data from a CSV file and run strict validation."""
    raw = pd.read_csv(csv_path)
    validated = _validate_ohlcv_frame(raw)
    LOGGER.info("Loaded %s bars from %s", len(validated), csv_path)
    return validated


def load_benchmark_close_csv(csv_path: str) -> pd.DataFrame:
    """Load benchmark close series from CSV.

    Expected columns:
    - timestamp
    - close
    """
    raw = pd.read_csv(csv_path)
    required = ["timestamp", "close"]
    missing = [col for col in required if col not in raw.columns]
    if missing:
        raise ValueError(f"Benchmark CSV missing columns: {missing}. Expected: {required}")

    out = raw[required].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")

    if out["timestamp"].isna().any() or out["close"].isna().any():
        raise ValueError("Benchmark CSV has invalid timestamp/close values.")

    if out["timestamp"].duplicated().any():
        raise ValueError("Benchmark CSV has duplicate timestamps.")

    if (out["close"] <= 0).any():
        raise ValueError("Benchmark close prices must be positive.")

    return out.sort_values("timestamp").reset_index(drop=True)


def generate_synthetic_ohlcv(n_bars: int = 600, seed: int = 42) -> pd.DataFrame:
    """Generate deterministic synthetic OHLCV data for demos and tests."""
    if n_bars < 3:
        raise ValueError("n_bars must be at least 3")

    rng = np.random.default_rng(seed)
    timestamps = pd.date_range(start="2020-01-01", periods=n_bars, freq="B")

    daily_returns = rng.normal(loc=0.0004, scale=0.012, size=n_bars)
    close = 100.0 * np.cumprod(1.0 + daily_returns)

    open_prices = np.empty_like(close)
    open_prices[0] = close[0] * (1.0 + rng.normal(0.0, 0.002))
    for idx in range(1, n_bars):
        open_prices[idx] = close[idx - 1] * (1.0 + rng.normal(0.0, 0.003))

    high = np.maximum(open_prices, close) * (1.0 + rng.uniform(0.0, 0.01, size=n_bars))
    low = np.minimum(open_prices, close) * (1.0 - rng.uniform(0.0, 0.01, size=n_bars))
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
    return _validate_ohlcv_frame(df)
