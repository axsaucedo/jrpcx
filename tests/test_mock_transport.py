"""Tests for MockTransport and AsyncMockTransport."""

import json

import pytest

from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport


def echo_handler(request: Request) -> Response:
    return Response(id=request.id, result=request.params)


def error_handler(request: Request) -> Response:
    return Response(
        id=request.id,
        error=ErrorData(code=-32601, message="Method not found"),
    )


class TestMockTransport:
    def test_basic_request(self) -> None:
        transport = MockTransport(echo_handler)
        req = json.dumps(
            {"jsonrpc": "2.0", "method": "echo", "params": [1, 2], "id": 1}
        ).encode()
        resp_bytes = transport.handle_request(req)
        resp = json.loads(resp_bytes)
        assert resp["result"] == [1, 2]
        assert resp["id"] == 1

    def test_error_response(self) -> None:
        transport = MockTransport(error_handler)
        req = json.dumps(
            {"jsonrpc": "2.0", "method": "bad", "id": 1}
        ).encode()
        resp_bytes = transport.handle_request(req)
        resp = json.loads(resp_bytes)
        assert resp["error"]["code"] == -32601

    def test_no_params(self) -> None:
        transport = MockTransport(echo_handler)
        req = json.dumps(
            {"jsonrpc": "2.0", "method": "test", "id": 1}
        ).encode()
        resp_bytes = transport.handle_request(req)
        resp = json.loads(resp_bytes)
        assert resp["result"] is None

    def test_context_manager(self) -> None:
        with MockTransport(echo_handler) as transport:
            req = json.dumps(
                {"jsonrpc": "2.0", "method": "test", "params": "hi", "id": 1}
            ).encode()
            resp = json.loads(transport.handle_request(req))
            assert resp["result"] == "hi"


class TestAsyncMockTransport:
    @pytest.mark.asyncio
    async def test_sync_handler(self) -> None:
        transport = AsyncMockTransport(echo_handler)
        req = json.dumps(
            {"jsonrpc": "2.0", "method": "echo", "params": [3], "id": 1}
        ).encode()
        resp_bytes = await transport.handle_async_request(req)
        resp = json.loads(resp_bytes)
        assert resp["result"] == [3]

    @pytest.mark.asyncio
    async def test_async_handler(self) -> None:
        async def async_echo(request: Request) -> Response:
            return Response(id=request.id, result=request.params)

        transport = AsyncMockTransport(async_echo)
        req = json.dumps(
            {"jsonrpc": "2.0", "method": "echo", "params": "async", "id": 2}
        ).encode()
        resp_bytes = await transport.handle_async_request(req)
        resp = json.loads(resp_bytes)
        assert resp["result"] == "async"

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        async with AsyncMockTransport(echo_handler) as transport:
            req = json.dumps(
                {"jsonrpc": "2.0", "method": "t", "params": 42, "id": 1}
            ).encode()
            resp = json.loads(
                await transport.handle_async_request(req)
            )
            assert resp["result"] == 42
