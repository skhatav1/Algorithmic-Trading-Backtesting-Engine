"""Trading cost model for commission and slippage in basis points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

Side = Literal["BUY", "SELL"]


@dataclass
class CostModel:
    """Simple linear bps cost model.

    Commission and slippage are both interpreted in basis points (1 bps = 0.01%).
    """

    commission_bps: float = 1.0
    slippage_bps: float = 2.0

    def __post_init__(self) -> None:
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("commission_bps and slippage_bps must be >= 0")

    @property
    def commission_rate(self) -> float:
        """Commission as decimal rate."""
        return self.commission_bps / 10_000.0

    @property
    def slippage_rate(self) -> float:
        """Slippage as decimal rate."""
        return self.slippage_bps / 10_000.0

    def effective_price(self, side: Side, gross_open_price: float) -> Tuple[float, float, float]:
        """Return effective fill price plus commission/slippage cash impact per share."""
        if gross_open_price <= 0:
            raise ValueError("gross_open_price must be positive")

        commission_per_share = gross_open_price * self.commission_rate
        slippage_per_share = gross_open_price * self.slippage_rate

        if side == "BUY":
            fill_price = gross_open_price + commission_per_share + slippage_per_share
        elif side == "SELL":
            fill_price = gross_open_price - commission_per_share - slippage_per_share
        else:
            raise ValueError(f"Unsupported side: {side}")

        return fill_price, commission_per_share, slippage_per_share
