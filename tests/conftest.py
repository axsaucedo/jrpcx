"""Shared fixtures for jrpcx test suite."""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

# --- JSON-RPC method handlers ---

def _dispatch(method: str, params: Any) -> Any:
    """Dispatch a JSON-RPC method to a handler."""
    handlers: dict[str, Any] = {
        "echo": _handle_echo,
        "add": _handle_add,
        "greet": _handle_greet,
        "no_params": _handle_no_params,
        "slow": _handle_slow,
        "error": _handle_error,
        "custom_error": _handle_custom_error,
    }
    handler = handlers.get(method)
    if handler is None:
        return {"__error__": {"code": -32601, "message": f"Method not found: {method}"}}
    return handler(params)


def _handle_echo(params: Any) -> Any:
    return params


def _handle_add(params: Any) -> Any:
    if isinstance(params, list) and len(params) == 2:
        return params[0] + params[1]
    if isinstance(params, dict):
        return params["a"] + params["b"]
    return {"__error__": {"code": -32602, "message": "Expected [a, b] or {a, b}"}}


def _handle_greet(params: Any) -> Any:
    if isinstance(params, dict) and "name" in params:
        return f"Hello, {params['name']}"
    if isinstance(params, list) and len(params) == 1:
        return f"Hello, {params[0]}"
    return {"__error__": {"code": -32602, "message": "Expected {name} or [name]"}}


def _handle_no_params(params: Any) -> Any:
    return "ok"


def _handle_slow(params: Any) -> Any:
    seconds = 2.0
    if isinstance(params, list) and len(params) >= 1:
        seconds = float(params[0])
    elif isinstance(params, dict) and "seconds" in params:
        seconds = float(params["seconds"])
    time.sleep(seconds)
    return "ok"


def _handle_error(params: Any) -> Any:
    return {"__error__": {"code": -32601, "message": "Method not found"}}


def _handle_custom_error(params: Any) -> Any:
    return {"__error__": {"code": -1001, "message": "Custom application error"}}


# --- HTTP Request Handler ---

class JSONRPCHandler(BaseHTTPRequestHandler):
    """Handle JSON-RPC 2.0 requests."""

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self._send_error(-32700, "Parse error", None)
            return

        # Handle batch requests (JSON array)
        if isinstance(request, list):
            self._handle_batch(request)
            return

        method = request.get("method")
        params = request.get("params")
        request_id = request.get("id")

        # Notification: no id field means no response
        if request_id is None:
            _dispatch(method, params)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        result = _dispatch(method, params)

        if isinstance(result, dict) and "__error__" in result:
            error = result["__error__"]
            response: dict[str, Any] = {
                "jsonrpc": "2.0",
                "error": {"code": error["code"], "message": error["message"]},
                "id": request_id,
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id,
            }

        self._send_json(response)

    def _handle_batch(self, requests: list[Any]) -> None:
        """Handle a batch of JSON-RPC requests."""
        if not requests:
            self._send_error(-32600, "Invalid Request: empty batch", None)
            return

        responses: list[dict[str, Any]] = []
        for req in requests:
            if not isinstance(req, dict):
                responses.append({
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid Request"},
                    "id": None,
                })
                continue

            method = req.get("method")
            params = req.get("params")
            request_id = req.get("id")

            # Notifications in batch produce no response
            if request_id is None:
                _dispatch(method, params)
                continue

            result = _dispatch(method, params)
            if isinstance(result, dict) and "__error__" in result:
                error = result["__error__"]
                responses.append({
                    "jsonrpc": "2.0",
                    "error": {"code": error["code"], "message": error["message"]},
                    "id": request_id,
                })
            else:
                responses.append({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id,
                })

        # If all were notifications, return 204 No Content
        if not responses:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self._send_json_raw(responses)

    def _send_json(self, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json_raw(self, data: Any) -> None:
        """Send arbitrary JSON (used for batch array responses)."""
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str, request_id: Any) -> None:
        self._send_json({
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        })

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress request logging


# --- Fixtures ---

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def rpc_server() -> Any:
    """Start a JSON-RPC server on a random port for the test session."""
    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), JSONRPCHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


@pytest.fixture(scope="session")
def rpc_url(rpc_server: Any) -> str:
    """Return the URL of the test JSON-RPC server."""
    host, port = rpc_server.server_address
    return f"http://{host}:{port}"
