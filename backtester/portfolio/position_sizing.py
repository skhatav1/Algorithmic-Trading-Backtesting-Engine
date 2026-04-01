"""Position sizing rules."""

from __future__ import annotations

from abc import ABC, abstractmethod


class PositionSizer(ABC):
    """Interface for determining order quantity."""

    @abstractmethod
    def size_buy(self, cash: float, equity: float, reference_price: float) -> int:
        """Return integer buy quantity."""


class AllInSizer(PositionSizer):
    """Invest all available cash on each entry signal."""

    def size_buy(self, cash: float, equity: float, reference_price: float) -> int:
        if reference_price <= 0:
            return 0
        return max(0, int(cash // reference_price))


class FixedFractionSizer(PositionSizer):
    """Invest a fixed fraction of equity on each entry signal."""

    def __init__(self, fraction: float = 0.10) -> None:
        if fraction <= 0 or fraction > 1:
            raise ValueError("fraction must be in (0, 1]")
        self.fraction = fraction

    def size_buy(self, cash: float, equity: float, reference_price: float) -> int:
        if reference_price <= 0:
            return 0
        budget = min(cash, equity * self.fraction)
        return max(0, int(budget // reference_price))
