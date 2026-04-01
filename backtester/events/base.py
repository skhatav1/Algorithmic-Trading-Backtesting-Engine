"""Base event type and event constants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):
    """Supported event categories in the engine."""

    MARKET = "MARKET"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"


@dataclass(frozen=True)
class Event:
    """Base class for all events."""

    event_type: EventType
