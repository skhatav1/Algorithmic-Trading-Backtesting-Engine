"""Vercel Python entrypoint for the browser dashboard API."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict

from backtester.web_adapter import json_safe, run_backtest_from_payload


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


class handler(BaseHTTPRequestHandler):
    """HTTP handler used by Vercel."""

    def do_OPTIONS(self) -> None:
        _json_response(self, 200, {"ok": True})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = run_backtest_from_payload(payload)
            _json_response(self, 200, {"ok": True, "result": result})
        except Exception as exc:
            _json_response(self, 400, {"ok": False, "error": str(exc)})
