"""Tests for the web backtest adapter."""

from __future__ import annotations

from backtester.web_adapter import run_backtest_from_payload


def test_web_api_payload_runs_backtest() -> None:
    result = run_backtest_from_payload(
        {
            "strategy": "sma",
            "short_window": 10,
            "long_window": 50,
            "cash": 100_000,
            "commission_bps": 1,
            "slippage_bps": 2,
            "synthetic_bars": 120,
        }
    )

    assert result["bars"] == 120
    assert "total_return" in result["metrics"]
    assert len(result["equity_curve"]) == 120
