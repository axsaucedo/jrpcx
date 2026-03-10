"""Mock transports for testing jrpcx clients without network access."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from jrpcx._models import Request, Response
from jrpcx._transports import AsyncBaseTransport, BaseTransport

SyncHandler = Callable[[Request], Response]
AsyncHandler = (
    Callable[[Request], Response] | Callable[[Request], Awaitable[Response]]
)


class MockTransport(BaseTransport):
    """Sync mock transport that delegates to a handler function.

    The handler receives a Request and returns a Response.
    """

    def __init__(self, handler: SyncHandler) -> None:
        self._handler = handler

    def handle_request(self, request: bytes) -> bytes:
        data = json.loads(request)
        req = Request(
            method=data["method"],
            params=data.get("params"),
            id=data.get("id"),
        )
        resp = self._handler(req)
        result: dict[str, Any] = {"jsonrpc": "2.0", "id": resp.id}
        if resp.error is not None:
            result["error"] = resp.error.to_dict()
        else:
            result["result"] = resp.result
        return json.dumps(result).encode()


class AsyncMockTransport(AsyncBaseTransport):
    """Async mock transport that delegates to a handler function.

    Handler can be sync or async.
    """

    def __init__(self, handler: AsyncHandler) -> None:
        self._handler = handler

    async def handle_async_request(self, request: bytes) -> bytes:
        data = json.loads(request)
        req = Request(
            method=data["method"],
            params=data.get("params"),
            id=data.get("id"),
        )
        result_resp = self._handler(req)
        if isinstance(result_resp, Awaitable):
            resp = await result_resp
        else:
            resp = result_resp
        result: dict[str, Any] = {"jsonrpc": "2.0", "id": resp.id}
        if resp.error is not None:
            result["error"] = resp.error.to_dict()
        else:
            result["result"] = resp.result
        return json.dumps(result).encode()
