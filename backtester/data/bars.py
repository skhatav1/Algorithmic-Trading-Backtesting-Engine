"""Bar data structures used by the event-driven engine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bar:
    """Single OHLCV bar."""

    open: float
    high: float
    low: float
    close: float
    volume: float
