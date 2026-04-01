"""Event-driven backtest engine."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Union

import pandas as pd

from backtester.analytics.metrics import compute_metrics
from backtester.data.bars import Bar
from backtester.events.event_types import FillEvent, MarketEvent, OrderEvent, SignalEvent
from backtester.execution.broker import SimulatedBroker
from backtester.portfolio.portfolio import Portfolio
from backtester.strategies.base import StrategyBase

EventQueueItem = Union[MarketEvent, SignalEvent, OrderEvent, FillEvent]


@dataclass
class BacktestResult:
    """Container for key engine outputs."""

    history: pd.DataFrame
    trades: pd.DataFrame
    metrics: Dict[str, float]
    trade_count: int


class BacktestEngine:
    """Coordinates data events, strategy signals, orders, fills, and portfolio updates."""

    def __init__(
        self,
        bars: pd.DataFrame,
        symbol: str,
        strategy: StrategyBase,
        portfolio: Portfolio,
        broker: SimulatedBroker,
    ) -> None:
        if len(bars) < 2:
            raise ValueError("Need at least 2 bars for next-open execution")

        self.bars = bars.reset_index(drop=True)
        self.symbol = symbol
        self.strategy = strategy
        self.portfolio = portfolio
        self.broker = broker

    def run(self) -> BacktestResult:
        """Run the full backtest and return history + metrics."""
        queue: Deque[EventQueueItem] = deque()

        for idx, row in self.bars.iterrows():
            market_event = MarketEvent(
                index=int(idx),
                timestamp=pd.Timestamp(row["timestamp"]),
                symbol=self.symbol,
                bar=Bar(
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                ),
            )
            queue.append(market_event)

            while queue:
                event = queue.popleft()

                if isinstance(event, MarketEvent):
                    # 1) Fill existing pending orders at this bar open.
                    for fill_event in self.broker.process_market_event(event):
                        self.portfolio.process_fill(fill_event)

                    # 2) Strategy reads completed history up to this bar close.
                    history = self.bars.iloc[: event.index + 1]
                    signal_event = self.strategy.on_bar(
                        market_event=event,
                        history=history,
                        current_position=self.portfolio.current_position,
                    )
                    if signal_event is not None:
                        queue.append(signal_event)

                    # 3) Mark portfolio at this bar close.
                    self.portfolio.mark_to_market(
                        timestamp=event.timestamp,
                        close_price=float(event.bar.close),
                    )

                elif isinstance(event, FillEvent):
                    # FillEvents are normally applied immediately in MarketEvent handling.
                    # This branch is kept for compatibility if fills are ever queued directly.
                    self.portfolio.process_fill(event)

                elif isinstance(event, SignalEvent):
                    if not self.broker.has_pending_orders():
                        order_event = self.portfolio.generate_order_from_signal(event)
                        if order_event is not None:
                            queue.append(order_event)

                elif isinstance(event, OrderEvent):
                    # Order is queued now, then filled on the *next* market event.
                    self.broker.submit_order(event)

        history = self.portfolio.history_frame()
        metrics = compute_metrics(history["equity"])
        trades = self.portfolio.trades_frame()
        return BacktestResult(history=history, trades=trades, metrics=metrics, trade_count=self.portfolio.trade_count)
