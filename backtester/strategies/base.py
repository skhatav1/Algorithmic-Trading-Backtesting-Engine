"""Base strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from backtester.events.event_types import MarketEvent, SignalEvent


class StrategyBase(ABC):
    """Abstract base class for all strategies.

    Strategy logic receives completed bar history and may emit a signal.
    Signals are target positions (1=long, 0=flat) and are executed next bar open.
    """

    name: str

    @abstractmethod
    def on_bar(
        self,
        market_event: MarketEvent,
        history: pd.DataFrame,
        current_position: int,
    ) -> Optional[SignalEvent]:
        """Process one completed bar and optionally return a signal event."""

    def reset(self) -> None:
        """Reset internal strategy state if needed."""
        return None
