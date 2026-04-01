"""Mean reversion strategy based on rolling z-score."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from backtester.events.event_types import MarketEvent, SignalEvent
from backtester.strategies.base import StrategyBase


class MeanReversionStrategy(StrategyBase):
    """Long when price is far below rolling mean; flatten on reversion/high z-score."""

    def __init__(self, lookback: int = 20, entry_z: float = 1.0, exit_z: float = 0.25) -> None:
        if lookback <= 1:
            raise ValueError("lookback must be > 1")
        if entry_z <= 0 or exit_z < 0:
            raise ValueError("entry_z must be > 0 and exit_z must be >= 0")

        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.name = "mean_reversion"

    def on_bar(
        self,
        market_event: MarketEvent,
        history: pd.DataFrame,
        current_position: int,
    ) -> Optional[SignalEvent]:
        close_series = history["close"]

        if len(close_series) < self.lookback:
            target = 0
        else:
            window = close_series.tail(self.lookback)
            rolling_mean = float(window.mean())
            rolling_std = float(window.std(ddof=0))

            if rolling_std <= 0:
                target = current_position
            else:
                z_score = (float(close_series.iloc[-1]) - rolling_mean) / rolling_std

                # Long-only behavior:
                # - Enter long when price is sufficiently below mean.
                # - Exit when it has reverted near mean or moved too high.
                if current_position == 0 and z_score <= -self.entry_z:
                    target = 1
                elif current_position == 1 and abs(z_score) <= self.exit_z:
                    target = 0
                elif current_position == 1 and z_score >= self.entry_z:
                    target = 0
                else:
                    target = current_position

        return SignalEvent(
            timestamp=market_event.timestamp,
            symbol=market_event.symbol,
            target_position=int(target),
            reference_price=float(market_event.bar.close),
            strategy_name=self.name,
        )
