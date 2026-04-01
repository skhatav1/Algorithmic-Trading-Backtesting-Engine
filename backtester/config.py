"""Configuration objects for backtest runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class BacktestConfig:
    """Container for top-level run settings used by CLI and reporting."""

    csv_path: Optional[str] = None
    strategy_name: str = "sma"
    initial_cash: float = 100_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    plot: bool = True
    strategy_params: Dict[str, float] = field(default_factory=dict)
    sizer_name: str = "all_in"
    fixed_fraction: float = 0.10
