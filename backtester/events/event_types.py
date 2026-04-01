"""Concrete event models for market data, signals, orders, and fills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from backtester.data.bars import Bar
from backtester.events.base import Event, EventType

Side = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class MarketEvent(Event):
    """Event emitted when a new completed bar is available."""

    index: int
    timestamp: pd.Timestamp
    symbol: str
    bar: Bar

    def __init__(self, index: int, timestamp: pd.Timestamp, symbol: str, bar: Bar) -> None:
        super().__init__(EventType.MARKET)
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "bar", bar)


@dataclass(frozen=True)
class SignalEvent(Event):
    """Event produced by a strategy that requests a target position."""

    timestamp: pd.Timestamp
    symbol: str
    target_position: int
    reference_price: float
    strategy_name: str

    def __init__(
        self,
        timestamp: pd.Timestamp,
        symbol: str,
        target_position: int,
        reference_price: float,
        strategy_name: str,
    ) -> None:
        super().__init__(EventType.SIGNAL)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "target_position", target_position)
        object.__setattr__(self, "reference_price", reference_price)
        object.__setattr__(self, "strategy_name", strategy_name)


@dataclass(frozen=True)
class OrderEvent(Event):
    """Event created by the portfolio for execution at the next market open."""

    timestamp: pd.Timestamp
    symbol: str
    side: Side
    quantity: int

    def __init__(self, timestamp: pd.Timestamp, symbol: str, side: Side, quantity: int) -> None:
        super().__init__(EventType.ORDER)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "quantity", quantity)


@dataclass(frozen=True)
class FillEvent(Event):
    """Event representing an executed order with effective price and costs."""

    timestamp: pd.Timestamp
    symbol: str
    side: Side
    quantity: int
    fill_price: float
    gross_price: float
    commission_paid: float
    slippage_paid: float

    def __init__(
        self,
        timestamp: pd.Timestamp,
        symbol: str,
        side: Side,
        quantity: int,
        fill_price: float,
        gross_price: float,
        commission_paid: float,
        slippage_paid: float,
    ) -> None:
        super().__init__(EventType.FILL)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "fill_price", fill_price)
        object.__setattr__(self, "gross_price", gross_price)
        object.__setattr__(self, "commission_paid", commission_paid)
        object.__setattr__(self, "slippage_paid", slippage_paid)
