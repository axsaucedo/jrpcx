"""Tests for JSON-RPC notification support."""

from __future__ import annotations

import json
from typing import Any

import pytest

import jrpcx
from jrpcx._models import Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport

# --- Mock transport that records requests ---


class RecordingTransport(MockTransport):
    """MockTransport that records all requests sent through it."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

        def handler(req: Request) -> Response:
            return Response(id=req.id, result="ok")

        super().__init__(handler)

    def handle_request(self, request: bytes) -> bytes:
        data = json.loads(request)
        self.requests.append(data)
        # For notifications (no id), return minimal response
        if data.get("id") is None:
            return json.dumps(
                {"jsonrpc": "2.0", "result": None, "id": None}
            ).encode()
        return super().handle_request(request)


class AsyncRecordingTransport(AsyncMockTransport):
    """AsyncMockTransport that records all requests."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

        def handler(req: Request) -> Response:
            return Response(id=req.id, result="ok")

        super().__init__(handler)

    async def handle_async_request(self, request: bytes) -> bytes:
        data = json.loads(request)
        self.requests.append(data)
        if data.get("id") is None:
            return json.dumps(
                {"jsonrpc": "2.0", "result": None, "id": None}
            ).encode()
        return await super().handle_async_request(request)


# --- Sync notification tests ---


class TestSyncNotify:
    def test_notify_sends_request_without_id(self) -> None:
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        client.notify.log_event(level="info", message="hello")
        assert len(transport.requests) == 1
        req = transport.requests[0]
        assert req["method"] == "log_event"
        assert req["params"] == {"level": "info", "message": "hello"}
        assert "id" not in req
        client.close()

    def test_notify_with_positional_params(self) -> None:
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        client.notify.add(1, 2)
        req = transport.requests[0]
        assert req["method"] == "add"
        assert req["params"] == [1, 2]
        assert "id" not in req
        client.close()

    def test_notify_without_params(self) -> None:
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        client.notify.shutdown()
        req = transport.requests[0]
        assert req["method"] == "shutdown"
        assert "params" not in req
        assert "id" not in req
        client.close()

    def test_notify_nested_namespace(self) -> None:
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        client.notify.system.shutdown()
        req = transport.requests[0]
        assert req["method"] == "system.shutdown"
        assert "id" not in req
        client.close()

    def test_notify_returns_none(self) -> None:
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        result = client.notify.log_event(message="test")
        assert result is None
        client.close()

    def test_notify_direct_call_raises(self) -> None:
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with pytest.raises(TypeError, match="Cannot call notify directly"):
            client.notify()
        client.close()

    def test_notify_fires_request_hook(self) -> None:
        transport = RecordingTransport()
        hook_calls: list[tuple[str, Any]] = []
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            event_hooks={"request": [lambda m, p: hook_calls.append((m, p))]},
        )
        client.notify.ping()
        assert len(hook_calls) == 1
        assert hook_calls[0] == ("ping", None)
        client.close()

    def test_notify_on_closed_client_raises(self) -> None:
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        client.close()
        with pytest.raises(RuntimeError, match="Client has been closed"):
            client.notify.ping()

    def test_notify_does_not_consume_id(self) -> None:
        """Notifications should not increment the ID generator."""
        transport = RecordingTransport()
        client = jrpcx.Client("http://test", transport=transport)
        client.notify.log("test")
        client.echo("hello")
        # First actual call should get id=1
        call_req = transport.requests[1]
        assert call_req["id"] == 1
        client.close()


# --- Async notification tests ---


class TestAsyncNotify:
    @pytest.mark.asyncio
    async def test_async_notify_sends_without_id(self) -> None:
        transport = AsyncRecordingTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        await client.notify.log_event(level="info")
        req = transport.requests[0]
        assert req["method"] == "log_event"
        assert req["params"] == {"level": "info"}
        assert "id" not in req
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_notify_positional_params(self) -> None:
        transport = AsyncRecordingTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        await client.notify.add(1, 2)
        req = transport.requests[0]
        assert req["params"] == [1, 2]
        assert "id" not in req
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_notify_nested_namespace(self) -> None:
        transport = AsyncRecordingTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        await client.notify.system.shutdown()
        req = transport.requests[0]
        assert req["method"] == "system.shutdown"
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_notify_returns_none(self) -> None:
        transport = AsyncRecordingTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        result = await client.notify.log_event()
        assert result is None
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_notify_direct_call_raises(self) -> None:
        transport = AsyncRecordingTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        with pytest.raises(TypeError, match="Cannot call notify directly"):
            await client.notify()
        await client.aclose()


# --- Integration tests with real server ---


class TestNotifyIntegration:
    def test_notify_to_real_server(self, rpc_url: str) -> None:
        """Notification to real server should not raise."""
        with jrpcx.Client(rpc_url) as client:
            client.notify.echo("hello")

    def test_notify_then_call(self, rpc_url: str) -> None:
        """Notifications should not affect subsequent calls."""
        with jrpcx.Client(rpc_url) as client:
            client.notify.echo("notification")
            result = client.add(1, 2)
            assert result == 3
