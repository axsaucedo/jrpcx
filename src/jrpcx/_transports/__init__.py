"""Transport interface for jrpcx.

Defines abstract base classes for sync and async transports.
Transport operates on bytes — keeping the interface minimal and transport-agnostic.
"""

from __future__ import annotations

from typing import Any


class BaseTransport:
    """Synchronous transport interface."""

    def handle_request(self, request: bytes) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> BaseTransport:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncBaseTransport:
    """Asynchronous transport interface."""

    async def handle_async_request(self, request: bytes) -> bytes:
        raise NotImplementedError

    async def aclose(self) -> None:
        pass

    async def __aenter__(self) -> AsyncBaseTransport:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()
