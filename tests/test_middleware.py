"""Tests for middleware support."""

from __future__ import annotations

from typing import Any

import pytest

import jrpcx
from jrpcx._middleware import (
    MiddlewareHandler,
    build_middleware_chain,
)
from jrpcx._models import Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport


def _echo_handler(req: Request) -> Response:
    return Response(id=req.id, result=req.params)


# --- Middleware chain unit tests ---


class TestMiddlewareChain:
    def test_single_middleware(self) -> None:
        calls: list[str] = []

        def mw(request: Request, call_next: MiddlewareHandler) -> Response:
            calls.append("before")
            response = call_next(request)
            calls.append("after")
            return response

        chain = build_middleware_chain([mw], _echo_handler)
        resp = chain(Request(method="test", params=["hello"], id=1))
        assert resp.result == ["hello"]
        assert calls == ["before", "after"]

    def test_chain_ordering(self) -> None:
        """First middleware in list is outermost (called first)."""
        order: list[str] = []

        def mw_a(req: Request, call_next: MiddlewareHandler) -> Response:
            order.append("A-before")
            resp = call_next(req)
            order.append("A-after")
            return resp

        def mw_b(req: Request, call_next: MiddlewareHandler) -> Response:
            order.append("B-before")
            resp = call_next(req)
            order.append("B-after")
            return resp

        chain = build_middleware_chain([mw_a, mw_b], _echo_handler)
        chain(Request(method="test", id=1))
        assert order == ["A-before", "B-before", "B-after", "A-after"]

    def test_request_modification(self) -> None:
        """Middleware can modify the request before passing it on."""

        def uppercase_mw(req: Request, call_next: MiddlewareHandler) -> Response:
            modified = Request(
                method=req.method.upper(), params=req.params, id=req.id
            )
            return call_next(modified)

        chain = build_middleware_chain([uppercase_mw], _echo_handler)
        resp = chain(Request(method="test", id=1))
        # The echo handler returns params, but the method was uppercased
        assert resp.result is None  # no params

    def test_response_modification(self) -> None:
        """Middleware can modify the response."""

        def wrap_mw(req: Request, call_next: MiddlewareHandler) -> Response:
            resp = call_next(req)
            return Response(id=resp.id, result={"wrapped": resp.result})

        chain = build_middleware_chain([wrap_mw], _echo_handler)
        resp = chain(Request(method="test", params="data", id=1))
        assert resp.result == {"wrapped": "data"}

    def test_short_circuit(self) -> None:
        """Middleware can short-circuit without calling next."""

        def block_mw(req: Request, call_next: MiddlewareHandler) -> Response:
            return Response(id=req.id, result="blocked")

        chain = build_middleware_chain([block_mw], _echo_handler)
        resp = chain(Request(method="test", params="data", id=1))
        assert resp.result == "blocked"


# --- Client integration tests ---


class TestSyncMiddleware:
    def test_middleware_intercepts_calls(self) -> None:
        calls: list[str] = []

        def logging_mw(req: Request, call_next: MiddlewareHandler) -> Response:
            calls.append(f"→ {req.method}")
            resp = call_next(req)
            calls.append(f"← {resp.result}")
            return resp

        transport = MockTransport(_echo_handler)
        client = jrpcx.Client(
            "http://test", transport=transport, middleware=[logging_mw]
        )
        result = client.echo("hello")
        assert result == ["hello"]
        assert calls == ["→ echo", "← ['hello']"]
        client.close()

    def test_multiple_middleware(self) -> None:
        order: list[str] = []

        def mw_a(req: Request, call_next: MiddlewareHandler) -> Response:
            order.append("A")
            return call_next(req)

        def mw_b(req: Request, call_next: MiddlewareHandler) -> Response:
            order.append("B")
            return call_next(req)

        transport = MockTransport(_echo_handler)
        client = jrpcx.Client(
            "http://test", transport=transport, middleware=[mw_a, mw_b]
        )
        client.echo("test")
        assert order == ["A", "B"]
        client.close()

    def test_no_middleware(self) -> None:
        transport = MockTransport(_echo_handler)
        client = jrpcx.Client("http://test", transport=transport)
        result = client.echo("test")
        assert result == ["test"]
        client.close()


class TestAsyncMiddleware:
    @pytest.mark.asyncio
    async def test_async_middleware(self) -> None:
        calls: list[str] = []

        async def logging_mw(req: Request, call_next: Any) -> Response:
            calls.append(f"→ {req.method}")
            resp = await call_next(req)
            calls.append(f"← {resp.result}")
            return resp

        transport = AsyncMockTransport(_echo_handler)
        client = jrpcx.AsyncClient(
            "http://test", transport=transport, middleware=[logging_mw]
        )
        result = await client.echo("hello")
        assert result == ["hello"]
        assert calls == ["→ echo", "← ['hello']"]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_short_circuit(self) -> None:
        async def block_mw(req: Request, call_next: Any) -> Response:
            return Response(id=req.id, result="blocked")

        transport = AsyncMockTransport(_echo_handler)
        client = jrpcx.AsyncClient(
            "http://test", transport=transport, middleware=[block_mw]
        )
        result = await client.echo("test")
        assert result == "blocked"
        await client.aclose()


# --- Integration with real server ---


class TestMiddlewareIntegration:
    def test_middleware_with_real_server(self, rpc_url: str) -> None:
        calls: list[str] = []

        def tracker(req: Request, call_next: MiddlewareHandler) -> Response:
            calls.append(req.method)
            return call_next(req)

        with jrpcx.Client(rpc_url, middleware=[tracker]) as client:
            client.add(1, 2)
            client.echo("hello")
        assert calls == ["add", "echo"]
