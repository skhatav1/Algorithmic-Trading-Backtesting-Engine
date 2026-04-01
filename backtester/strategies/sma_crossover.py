"""Simple moving average crossover strategy."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtester.events.event_types import MarketEvent, SignalEvent
from backtester.strategies.base import StrategyBase


class SMACrossoverStrategy(StrategyBase):
    """Long when short SMA > long SMA, otherwise flat."""

    def __init__(self, short_window: int = 10, long_window: int = 50) -> None:
        if short_window <= 0 or long_window <= 0:
            raise ValueError("short_window and long_window must be > 0")
        if short_window >= long_window:
            raise ValueError("short_window must be smaller than long_window")

        self.short_window = short_window
        self.long_window = long_window
        self.name = "sma"

    def on_bar(
        self,
        market_event: MarketEvent,
        history: pd.DataFrame,
        current_position: int,
    ) -> Optional[SignalEvent]:
        close_series = history["close"]

        # Not enough bars yet for both SMAs -> target flat.
        if len(close_series) < self.long_window:
            target = 0
        else:
            sma_short = close_series.tail(self.short_window).mean()
            sma_long = close_series.tail(self.long_window).mean()
            target = 1 if sma_short > sma_long else 0

        return SignalEvent(
            timestamp=market_event.timestamp,
            symbol=market_event.symbol,
            target_position=target,
            reference_price=float(market_event.bar.close),
            strategy_name=self.name,
        )
