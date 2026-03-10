"""JSON-RPC 2.0 client implementations."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from jrpcx._config import Timeout, TimeoutTypes
from jrpcx._exceptions import InvalidResponseError, ProtocolError
from jrpcx._id_generators import sequential
from jrpcx._models import Response
from jrpcx._transports import AsyncBaseTransport, BaseTransport
from jrpcx._types import JSONParams, RequestID, _UseClientDefault


class BaseJSONRPCClient:
    """Shared business logic for sync and async JSON-RPC clients."""

    _RESERVED_NAMES: frozenset[str] = frozenset(
        {"call", "close", "aclose", "send", "send_request"}
    )

    def __init__(
        self,
        url: str,
        *,
        transport: BaseTransport | AsyncBaseTransport | None = None,
        timeout: TimeoutTypes = None,
        id_generator: Iterator[RequestID] | None = None,
    ) -> None:
        self._url = url
        self._transport = transport
        self._timeout = (
            Timeout(timeout)
            if isinstance(timeout, (int, float))
            else timeout
        )
        self._id_generator = id_generator or sequential()
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    def _next_id(self) -> RequestID:
        return next(self._id_generator)

    def _build_request_bytes(
        self,
        method: str,
        params: JSONParams = None,
    ) -> tuple[bytes, RequestID]:
        """Build a JSON-RPC request and return (bytes, id)."""
        request_id = self._next_id()
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": request_id,
        }
        if params is not None:
            payload["params"] = params
        return json.dumps(payload).encode(), request_id

    def _parse_response(self, data: bytes) -> Response:
        """Parse JSON-RPC response bytes into a Response object."""
        try:
            parsed = json.loads(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProtocolError(f"Invalid JSON in response: {exc}") from exc

        if not isinstance(parsed, dict):
            raise InvalidResponseError(
                f"Expected JSON object, got {type(parsed).__name__}"
            )

        return Response.from_dict(parsed)

    def _resolve_timeout(
        self,
        timeout: TimeoutTypes | _UseClientDefault,
    ) -> TimeoutTypes:
        """Resolve per-request timeout, falling back to client default."""
        if isinstance(timeout, _UseClientDefault):
            return self._timeout
        return timeout

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Client has been closed")
