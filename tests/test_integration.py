"""Integration tests using real HTTP transport and test server."""

from __future__ import annotations

import pytest

from jrpcx._client import AsyncJSONRPCClient, JSONRPCClient
from jrpcx._exceptions import MethodNotFoundError
from jrpcx._transports._http import AsyncHTTPTransport, HTTPTransport


class TestSyncIntegration:
    """Sync client integration tests with real HTTP calls."""

    def test_echo(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            result = c.echo("hello")
            assert result == ["hello"]

    def test_echo_dict(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            result = c.echo(data="value")
            assert result == {"data": "value"}

    def test_add_positional(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            result = c.add(3, 4)
            assert result == 7

    def test_add_named(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            result = c.add(a=10, b=20)
            assert result == 30

    def test_greet(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            result = c.greet(name="World")
            assert result == "Hello, World"

    def test_no_params(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            result = c.no_params()
            assert result == "ok"

    def test_error_response(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with (
            JSONRPCClient(rpc_url, transport=transport) as c,
            pytest.raises(MethodNotFoundError),
        ):
            c.error()

    def test_method_not_found(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with (
            JSONRPCClient(rpc_url, transport=transport) as c,
            pytest.raises(MethodNotFoundError),
        ):
            c.nonexistent_method()

    def test_call_fallback(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            result = c.call("add", [5, 6])
            assert result == 11

    def test_multiple_calls(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        with JSONRPCClient(rpc_url, transport=transport) as c:
            assert c.add(1, 2) == 3
            assert c.add(3, 4) == 7
            assert c.greet(name="A") == "Hello, A"

    def test_non_context_manager(self, rpc_url: str) -> None:
        transport = HTTPTransport(rpc_url)
        client = JSONRPCClient(rpc_url, transport=transport)
        try:
            result = client.add(1, 1)
            assert result == 2
        finally:
            client.close()
        assert client.is_closed


class TestAsyncIntegration:
    """Async client integration tests with real HTTP calls."""

    @pytest.mark.asyncio
    async def test_echo(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            result = await c.echo("hello")
            assert result == ["hello"]

    @pytest.mark.asyncio
    async def test_add(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            result = await c.add(3, 4)
            assert result == 7

    @pytest.mark.asyncio
    async def test_greet(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            result = await c.greet(name="Async")
            assert result == "Hello, Async"

    @pytest.mark.asyncio
    async def test_no_params(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            result = await c.no_params()
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_error_response(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            with pytest.raises(MethodNotFoundError):
                await c.error()

    @pytest.mark.asyncio
    async def test_method_not_found(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            with pytest.raises(MethodNotFoundError):
                await c.nonexistent_method()

    @pytest.mark.asyncio
    async def test_call_fallback(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            result = await c.call("add", [5, 6])
            assert result == 11

    @pytest.mark.asyncio
    async def test_multiple_calls(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        async with AsyncJSONRPCClient(
            rpc_url, transport=transport
        ) as c:
            assert await c.add(1, 2) == 3
            assert await c.greet(name="B") == "Hello, B"

    @pytest.mark.asyncio
    async def test_non_context_manager(self, rpc_url: str) -> None:
        transport = AsyncHTTPTransport(rpc_url)
        client = AsyncJSONRPCClient(rpc_url, transport=transport)
        try:
            result = await client.add(1, 1)
            assert result == 2
        finally:
            await client.aclose()
        assert client.is_closed
