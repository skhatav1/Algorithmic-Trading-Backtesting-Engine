"""Simple risk helpers for order validation."""

from __future__ import annotations


def clamp_quantity(quantity: int) -> int:
    """Ensure quantity is never negative."""
    return max(0, int(quantity))
