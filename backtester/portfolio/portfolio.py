"""Portfolio model for long-only single-symbol backtests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from backtester.events.event_types import FillEvent, OrderEvent, SignalEvent
from backtester.portfolio.position_sizing import PositionSizer
from backtester.portfolio.risk import clamp_quantity


@dataclass
class TradeRecord:
    """One executed fill record."""

    timestamp: pd.Timestamp
    side: str
    quantity: int
    fill_price: float
    commission_paid: float
    slippage_paid: float


class Portfolio:
    """Tracks cash, shares, equity, and trade history."""

    def __init__(self, symbol: str, initial_cash: float, sizer: PositionSizer) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be > 0")

        self.symbol = symbol
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.shares = 0
        self.sizer = sizer

        self._history: List[Dict[str, float]] = []
        self._trades: List[TradeRecord] = []

    @property
    def current_position(self) -> int:
        """Return 1 when long, else 0."""
        return 1 if self.shares > 0 else 0

    @property
    def trade_count(self) -> int:
        """Number of fills executed."""
        return len(self._trades)

    @property
    def trades(self) -> List[TradeRecord]:
        """Trade records for reporting/debugging."""
        return list(self._trades)

    def trades_frame(self) -> pd.DataFrame:
        """Return trade log as a DataFrame for CSV export."""
        if not self._trades:
            return pd.DataFrame(
                columns=["timestamp", "side", "quantity", "fill_price", "commission_paid", "slippage_paid"]
            )

        rows = [
            {
                "timestamp": trade.timestamp,
                "side": trade.side,
                "quantity": trade.quantity,
                "fill_price": trade.fill_price,
                "commission_paid": trade.commission_paid,
                "slippage_paid": trade.slippage_paid,
            }
            for trade in self._trades
        ]
        return pd.DataFrame(rows)

    def current_equity(self, mark_price: float) -> float:
        """Mark-to-market equity at given price."""
        return float(self.cash + self.shares * mark_price)

    def process_fill(self, fill: FillEvent) -> None:
        """Apply a fill event to cash and share holdings."""
        qty = clamp_quantity(fill.quantity)
        if qty == 0:
            return

        if fill.side == "BUY":
            self.cash -= qty * fill.fill_price
            self.shares += qty
        elif fill.side == "SELL":
            qty_to_sell = min(qty, self.shares)
            self.cash += qty_to_sell * fill.fill_price
            self.shares -= qty_to_sell
        else:
            raise ValueError(f"Unsupported fill side: {fill.side}")

        self._trades.append(
            TradeRecord(
                timestamp=fill.timestamp,
                side=fill.side,
                quantity=qty,
                fill_price=fill.fill_price,
                commission_paid=fill.commission_paid,
                slippage_paid=fill.slippage_paid,
            )
        )

    def generate_order_from_signal(self, signal: SignalEvent) -> Optional[OrderEvent]:
        """Convert target-position signal into long/flat order.

        Buy quantity is determined by the active position sizer.
        Sell quantity closes the entire current long position.
        """
        if signal.target_position not in (0, 1):
            raise ValueError("signal.target_position must be 0 or 1")

        if signal.target_position == self.current_position:
            return None

        if signal.target_position == 1 and self.current_position == 0:
            equity = self.current_equity(signal.reference_price)
            qty = self.sizer.size_buy(
                cash=self.cash,
                equity=equity,
                reference_price=signal.reference_price,
            )
            qty = clamp_quantity(qty)
            if qty == 0:
                return None
            return OrderEvent(
                timestamp=signal.timestamp,
                symbol=signal.symbol,
                side="BUY",
                quantity=qty,
            )

        if signal.target_position == 0 and self.current_position == 1:
            qty = clamp_quantity(self.shares)
            if qty == 0:
                return None
            return OrderEvent(
                timestamp=signal.timestamp,
                symbol=signal.symbol,
                side="SELL",
                quantity=qty,
            )

        return None

    def mark_to_market(self, timestamp: pd.Timestamp, close_price: float) -> None:
        """Store end-of-bar portfolio state in history."""
        equity = self.current_equity(mark_price=close_price)
        self._history.append(
            {
                "timestamp": timestamp,
                "cash": float(self.cash),
                "shares": int(self.shares),
                "equity": float(equity),
                "close": float(close_price),
            }
        )

    def history_frame(self) -> pd.DataFrame:
        """Return portfolio history as DataFrame with returns column."""
        frame = pd.DataFrame(self._history)
        if frame.empty:
            return frame

        frame["returns"] = frame["equity"].pct_change().fillna(0.0)
        return frame
