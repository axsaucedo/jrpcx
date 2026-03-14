"""Tests for non-context-manager lifecycle patterns."""

from __future__ import annotations

import pytest

from jrpcx._client import AsyncJSONRPCClient, JSONRPCClient
from jrpcx._models import Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport


def ok_handler(request: Request) -> Response:
    return Response(id=request.id, result="ok")


class TestSyncLifecycle:
    def test_create_use_close(self, rpc_url: str) -> None:
        client = JSONRPCClient(rpc_url)
        assert not client.is_closed
        result = client.echo("hi")
        assert result == ["hi"]
        client.close()
        assert client.is_closed

    def test_double_close_is_safe(self) -> None:
        transport = MockTransport(ok_handler)
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        client.close()
        client.close()  # should not raise
        assert client.is_closed

    def test_call_after_close_raises(self) -> None:
        transport = MockTransport(ok_handler)
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        client.close()
        with pytest.raises(RuntimeError, match="closed"):
            client.call("test")

    def test_proxy_after_close_raises(self) -> None:
        transport = MockTransport(ok_handler)
        client = JSONRPCClient(
            "http://localhost", transport=transport
        )
        client.close()
        with pytest.raises(RuntimeError, match="closed"):
            client.echo()

    def test_context_manager_closes_on_exit(self) -> None:
        transport = MockTransport(ok_handler)
        with JSONRPCClient(
            "http://localhost", transport=transport
        ) as c:
            c.call("test")
        assert c.is_closed

    def test_context_manager_closes_on_exception(self) -> None:
        transport = MockTransport(ok_handler)
        with (
            pytest.raises(ValueError, match="test"),
            JSONRPCClient(
                "http://localhost", transport=transport
            ) as c,
        ):
            raise ValueError("test")
        assert c.is_closed

    def test_long_lived_service_pattern(
        self, rpc_url: str
    ) -> None:
        """Simulates a long-lived service using the client."""
        client = JSONRPCClient(rpc_url)
        for i in range(5):
            result = client.add(i, 1)
            assert result == i + 1
        client.close()


class TestAsyncLifecycle:
    @pytest.mark.asyncio
    async def test_create_use_aclose(
        self, rpc_url: str
    ) -> None:
        client = AsyncJSONRPCClient(rpc_url)
        assert not client.is_closed
        result = await client.echo("hi")
        assert result == ["hi"]
        await client.aclose()
        assert client.is_closed

    @pytest.mark.asyncio
    async def test_double_aclose_is_safe(self) -> None:
        transport = AsyncMockTransport(ok_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        await client.aclose()
        await client.aclose()
        assert client.is_closed

    @pytest.mark.asyncio
    async def test_call_after_aclose_raises(self) -> None:
        transport = AsyncMockTransport(ok_handler)
        client = AsyncJSONRPCClient(
            "http://localhost", transport=transport
        )
        await client.aclose()
        with pytest.raises(RuntimeError, match="closed"):
            await client.call("test")

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        transport = AsyncMockTransport(ok_handler)
        async with AsyncJSONRPCClient(
            "http://localhost", transport=transport
        ) as c:
            await c.call("test")
        assert c.is_closed

    @pytest.mark.asyncio
    async def test_async_long_lived_pattern(
        self, rpc_url: str
    ) -> None:
        client = AsyncJSONRPCClient(rpc_url)
        for i in range(5):
            result = await client.add(i, 1)
            assert result == i + 1
        await client.aclose()
