"""Tests for proxy workflow patterns."""

from __future__ import annotations

import pytest

from jrpcx._client import AsyncJSONRPCClient, JSONRPCClient
from jrpcx._models import Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport


def capture_handler(
    captured: list[str],
) -> object:
    """Return a handler that captures method names."""

    def handler(request: Request) -> Response:
        captured.append(request.method)
        return Response(id=request.id, result=request.params)

    return handler


class TestSyncProxyWorkflows:
    def test_simple_method(self, rpc_url: str) -> None:
        with JSONRPCClient(rpc_url) as c:
            assert c.echo("hello") == ["hello"]

    def test_nested_namespace(self) -> None:
        captured: list[str] = []
        transport = MockTransport(capture_handler(captured))
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        client.system.listMethods()
        assert captured == ["system.listMethods"]

    def test_deep_nested_namespace(self) -> None:
        captured: list[str] = []
        transport = MockTransport(capture_handler(captured))
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        client.a.b.c.d()
        assert captured == ["a.b.c.d"]

    def test_reserved_name_via_call(self, rpc_url: str) -> None:
        with JSONRPCClient(rpc_url) as c:
            result = c.call("echo", ["via_call"])
            assert result == ["via_call"]

    def test_reserved_close_via_call(self) -> None:
        captured: list[str] = []
        transport = MockTransport(capture_handler(captured))
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        client.call("close")
        assert captured == ["close"]

    def test_positional_params(self, rpc_url: str) -> None:
        with JSONRPCClient(rpc_url) as c:
            assert c.add(10, 20) == 30

    def test_keyword_params(self, rpc_url: str) -> None:
        with JSONRPCClient(rpc_url) as c:
            assert c.add(a=5, b=15) == 20

    def test_no_params(self, rpc_url: str) -> None:
        with JSONRPCClient(rpc_url) as c:
            assert c.no_params() == "ok"

    def test_mixed_params_raises(self) -> None:
        transport = MockTransport(
            capture_handler([])  # type: ignore[arg-type]
        )
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        with pytest.raises(TypeError, match="Cannot mix"):
            client.echo(1, name="Alice")

    def test_proxy_getattr_reserved_raises(self) -> None:
        transport = MockTransport(
            capture_handler([])  # type: ignore[arg-type]
        )
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        with pytest.raises(AttributeError, match="call"):
            _ = client.__getattr__("call")

    def test_proxy_private_attr_raises(self) -> None:
        transport = MockTransport(
            capture_handler([])  # type: ignore[arg-type]
        )
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        with pytest.raises(AttributeError):
            _ = client.__getattr__("_internal")


class TestAsyncProxyWorkflows:
    @pytest.mark.asyncio
    async def test_simple_method(self, rpc_url: str) -> None:
        async with AsyncJSONRPCClient(rpc_url) as c:
            assert await c.echo("hello") == ["hello"]

    @pytest.mark.asyncio
    async def test_nested_namespace(self) -> None:
        captured: list[str] = []
        transport = AsyncMockTransport(
            capture_handler(captured)  # type: ignore[arg-type]
        )
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        await client.system.listMethods()
        assert captured == ["system.listMethods"]

    @pytest.mark.asyncio
    async def test_reserved_name_via_call(
        self, rpc_url: str
    ) -> None:
        async with AsyncJSONRPCClient(rpc_url) as c:
            result = await c.call("echo", ["async_call"])
            assert result == ["async_call"]

    @pytest.mark.asyncio
    async def test_positional_params(
        self, rpc_url: str
    ) -> None:
        async with AsyncJSONRPCClient(rpc_url) as c:
            assert await c.add(10, 20) == 30

    @pytest.mark.asyncio
    async def test_keyword_params(
        self, rpc_url: str
    ) -> None:
        async with AsyncJSONRPCClient(rpc_url) as c:
            assert await c.greet(name="Proxy") == "Hello, Proxy"
