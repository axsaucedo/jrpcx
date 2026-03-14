"""Tests for jrpcx._transports interface."""

import pytest

from jrpcx._transports import AsyncBaseTransport, BaseTransport


class TestBaseTransport:
    def test_handle_request_not_implemented(self) -> None:
        transport = BaseTransport()
        with pytest.raises(NotImplementedError):
            transport.handle_request(b"test")

    def test_close_is_noop(self) -> None:
        transport = BaseTransport()
        transport.close()  # should not raise

    def test_context_manager(self) -> None:
        transport = BaseTransport()
        with transport as t:
            assert t is transport


class ConcreteTransport(BaseTransport):
    def __init__(self) -> None:
        self.closed = False
        self.last_request: bytes | None = None

    def handle_request(self, request: bytes) -> bytes:
        self.last_request = request
        return b'{"jsonrpc":"2.0","result":"ok","id":1}'

    def close(self) -> None:
        self.closed = True


class TestConcreteTransport:
    def test_handle_request(self) -> None:
        transport = ConcreteTransport()
        result = transport.handle_request(b"hello")
        assert result == b'{"jsonrpc":"2.0","result":"ok","id":1}'
        assert transport.last_request == b"hello"

    def test_context_manager_closes(self) -> None:
        transport = ConcreteTransport()
        with transport:
            pass
        assert transport.closed


class TestAsyncBaseTransport:
    @pytest.mark.asyncio
    async def test_handle_async_request_not_implemented(self) -> None:
        transport = AsyncBaseTransport()
        with pytest.raises(NotImplementedError):
            await transport.handle_async_request(b"test")

    @pytest.mark.asyncio
    async def test_aclose_is_noop(self) -> None:
        transport = AsyncBaseTransport()
        await transport.aclose()  # should not raise

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        transport = AsyncBaseTransport()
        async with transport as t:
            assert t is transport
