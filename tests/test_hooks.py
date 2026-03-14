"""Tests for event hooks."""

from __future__ import annotations

from typing import Any

import pytest

from jrpcx._client import (
    AsyncJSONRPCClient,
    JSONRPCClient,
)
from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports._mock import (
    AsyncMockTransport,
    MockTransport,
)


def echo_handler(request: Request) -> Response:
    return Response(id=request.id, result=request.params)


def error_handler(request: Request) -> Response:
    return Response(
        id=request.id,
        error=ErrorData(code=-32601, message="not found"),
    )


class TestSyncEventHooks:
    def test_request_hook(self) -> None:
        log: list[tuple[str, Any]] = []
        transport = MockTransport(echo_handler)
        client = JSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "request": [
                    lambda m, p: log.append(("request", m))
                ]
            },
        )
        client.call("echo", [1])
        assert log == [("request", "echo")]

    def test_response_hook(self) -> None:
        responses: list[Response] = []
        transport = MockTransport(echo_handler)
        client = JSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "response": [
                    lambda r: responses.append(r)
                ]
            },
        )
        client.call("echo", [42])
        assert len(responses) == 1
        assert responses[0].result == [42]

    def test_error_hook_on_transport_error(self) -> None:
        errors: list[Exception] = []

        def bad_handler(request: Request) -> Response:
            raise RuntimeError("transport failure")

        transport = MockTransport(bad_handler)
        client = JSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "error": [lambda e: errors.append(e)]
            },
        )
        with pytest.raises(RuntimeError, match="transport"):
            client.call("test")
        assert len(errors) == 1
        assert isinstance(errors[0], RuntimeError)

    def test_multiple_hooks_fire_in_order(self) -> None:
        order: list[int] = []
        transport = MockTransport(echo_handler)
        client = JSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "request": [
                    lambda m, p: order.append(1),
                    lambda m, p: order.append(2),
                    lambda m, p: order.append(3),
                ]
            },
        )
        client.call("echo")
        assert order == [1, 2, 3]

    def test_invalid_hook_key_raises(self) -> None:
        transport = MockTransport(echo_handler)
        with pytest.raises(ValueError, match="Unknown event hook"):
            JSONRPCClient(
                "http://localhost",
                transport=transport,
                event_hooks={"invalid": []},
            )

    def test_hooks_via_proxy(self) -> None:
        log: list[str] = []
        transport = MockTransport(echo_handler)
        client = JSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "request": [
                    lambda m, p: log.append(m)
                ]
            },
        )
        client.echo(1)
        assert log == ["echo"]


class TestAsyncEventHooks:
    @pytest.mark.asyncio
    async def test_request_hook(self) -> None:
        log: list[str] = []
        transport = AsyncMockTransport(echo_handler)
        client = AsyncJSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "request": [
                    lambda m, p: log.append(m)
                ]
            },
        )
        await client.call("echo", [1])
        assert log == ["echo"]

    @pytest.mark.asyncio
    async def test_response_hook(self) -> None:
        responses: list[Response] = []
        transport = AsyncMockTransport(echo_handler)
        client = AsyncJSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "response": [
                    lambda r: responses.append(r)
                ]
            },
        )
        await client.call("echo", ["async"])
        assert len(responses) == 1
        assert responses[0].result == ["async"]

    @pytest.mark.asyncio
    async def test_error_hook(self) -> None:
        errors: list[Exception] = []

        def bad_handler(request: Request) -> Response:
            raise RuntimeError("async failure")

        transport = AsyncMockTransport(bad_handler)
        client = AsyncJSONRPCClient(
            "http://localhost",
            transport=transport,
            event_hooks={
                "error": [lambda e: errors.append(e)]
            },
        )
        with pytest.raises(RuntimeError, match="async"):
            await client.call("test")
        assert len(errors) == 1
