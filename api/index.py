"""Vercel Python entrypoint for the browser dashboard API."""

from __future__ import annotations

import json
import math
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "public" / "index.html"


def json_safe(value: Any) -> Any:
    """Convert non-finite values into valid JSON values without importing pandas."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return json_safe(value.item())
    return value


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    """Write a JSON response for Vercel's Python runtime."""
    body = json.dumps(json_safe(payload), allow_nan=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, status: int, html: str) -> None:
    """Write an HTML response for the dashboard page."""
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    """HTTP handler used by Vercel."""

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            if INDEX_HTML.exists():
                _html_response(self, 200, INDEX_HTML.read_text(encoding="utf-8"))
                return
            _html_response(
                self,
                200,
                "<!doctype html><title>Backtester</title><h1>Quant Backtesting Dashboard</h1>",
            )
            return
        _json_response(self, 404, {"ok": False, "error": "Not found"})

    def do_OPTIONS(self) -> None:
        _json_response(self, 200, {"ok": True})

    def do_POST(self) -> None:
        try:
            from backtester.web_adapter import run_backtest_from_payload

            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = run_backtest_from_payload(payload)
            _json_response(self, 200, {"ok": True, "result": result})
        except Exception as exc:
            _json_response(self, 400, {"ok": False, "error": str(exc)})
