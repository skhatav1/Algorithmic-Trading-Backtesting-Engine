"""Simulated broker that fills pending orders at next bar open."""

from __future__ import annotations

from typing import List

from backtester.events.event_types import FillEvent, MarketEvent, OrderEvent
from backtester.execution.costs import CostModel


class SimulatedBroker:
    """Queue-based broker for next-open execution.

    Orders submitted after market bar t are filled when bar t+1 arrives.
    """

    def __init__(self, cost_model: CostModel) -> None:
        self.cost_model = cost_model
        self._pending_orders: List[OrderEvent] = []

    def submit_order(self, order: OrderEvent) -> None:
        """Store order for execution on the next MarketEvent."""
        if order.quantity <= 0:
            return
        self._pending_orders.append(order)

    def has_pending_orders(self) -> bool:
        """True when there are not-yet-filled orders."""
        return len(self._pending_orders) > 0

    def process_market_event(self, market_event: MarketEvent) -> List[FillEvent]:
        """Fill all pending orders at current bar open with costs applied."""
        if not self._pending_orders:
            return []

        fills: List[FillEvent] = []
        gross_open_price = float(market_event.bar.open)

        for order in self._pending_orders:
            fill_price, commission_per_share, slippage_per_share = self.cost_model.effective_price(
                side=order.side,
                gross_open_price=gross_open_price,
            )

            fill = FillEvent(
                timestamp=market_event.timestamp,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                fill_price=float(fill_price),
                gross_price=gross_open_price,
                commission_paid=float(commission_per_share * order.quantity),
                slippage_paid=float(slippage_per_share * order.quantity),
            )
            fills.append(fill)

        self._pending_orders.clear()
        return fills
