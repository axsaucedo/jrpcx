"""Batch request support for jrpcx.

Provides BatchResult for handling batch responses, and BatchCollector /
AsyncBatchCollector context managers for building batch requests.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from jrpcx._models import Response
from jrpcx._types import JSONParams, RequestID

if TYPE_CHECKING:
    from jrpcx._transports import AsyncBaseTransport, BaseTransport


class BatchResult:
    """Rich container for batch JSON-RPC responses.

    Provides filtering, lookup, and error checking for batch results.
    """

    def __init__(self, responses: list[Response]) -> None:
        self._responses = responses
        self._by_id: dict[RequestID, Response] = {}
        for resp in responses:
            if resp.id is not None:
                self._by_id[resp.id] = resp

    def all(self) -> list[Response]:
        """Return all responses in order."""
        return list(self._responses)

    @property
    def successes(self) -> list[Response]:
        """Return only successful responses."""
        return [r for r in self._responses if r.is_success]

    @property
    def errors(self) -> list[Response]:
        """Return only error responses."""
        return [r for r in self._responses if r.is_error]

    @property
    def has_errors(self) -> bool:
        """Return True if any response is an error."""
        return any(r.is_error for r in self._responses)

    def by_id(self, request_id: RequestID) -> Response | None:
        """Look up a response by its request ID."""
        return self._by_id.get(request_id)

    def values(self) -> list[Any]:
        """Return result values from all responses.

        Raises the first error encountered as a ServerError.
        """
        results: list[Any] = []
        for resp in self._responses:
            resp.raise_for_error()
            results.append(resp.result)
        return results

    def __len__(self) -> int:
        return len(self._responses)

    def __iter__(self) -> Any:
        return iter(self._responses)

    def __getitem__(self, index: int) -> Response:
        return self._responses[index]

    def __repr__(self) -> str:
        ok = len(self.successes)
        err = len(self.errors)
        return f"BatchResult({ok} ok, {err} errors)"


# --- Batch request payload builders ---


def _build_request_payload(
    method: str,
    params: JSONParams,
    request_id: RequestID,
) -> dict[str, Any]:
    """Build a single JSON-RPC request dict (with id)."""
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id,
    }
    if params is not None:
        payload["params"] = params
    return payload


def _build_notification_payload(
    method: str,
    params: JSONParams,
) -> dict[str, Any]:
    """Build a JSON-RPC notification dict (no id)."""
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params is not None:
        payload["params"] = params
    return payload


def _resolve_params(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> JSONParams:
    """Convert positional/keyword arguments to JSON-RPC params."""
    if args and kwargs:
        raise TypeError(
            "Cannot mix positional and keyword arguments "
            "in JSON-RPC calls"
        )
    if kwargs:
        return kwargs
    if args:
        return list(args)
    return None


def _parse_batch_response(data: bytes) -> list[Response]:
    """Parse batch response bytes into a list of Response objects."""
    from jrpcx._exceptions import InvalidResponseError, ProtocolError

    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ProtocolError(f"Invalid JSON in batch response: {exc}") from exc

    if not isinstance(parsed, list):
        raise InvalidResponseError(
            f"Expected JSON array for batch response, got {type(parsed).__name__}"
        )

    return [Response.from_dict(item) for item in parsed]


# --- Proxy helpers for batch collectors ---


class _BatchMethodProxy:
    """Proxy for `batch.method_name(...)` inside a batch context."""

    def __init__(
        self,
        collector: BatchCollector,
        name: str,
    ) -> None:
        self._collector = collector
        self._name = name

    def __getattr__(self, name: str) -> _BatchMethodProxy:
        return _BatchMethodProxy(
            self._collector, f"{self._name}.{name}"
        )

    def __call__(self, *args: Any, **kwargs: Any) -> RequestID:
        params = _resolve_params(args, kwargs)
        return self._collector.call(self._name, params)


class _AsyncBatchMethodProxy:
    """Proxy for `batch.method_name(...)` inside an async batch context."""

    def __init__(
        self,
        collector: AsyncBatchCollector,
        name: str,
    ) -> None:
        self._collector = collector
        self._name = name

    def __getattr__(self, name: str) -> _AsyncBatchMethodProxy:
        return _AsyncBatchMethodProxy(
            self._collector, f"{self._name}.{name}"
        )

    def __call__(self, *args: Any, **kwargs: Any) -> RequestID:
        params = _resolve_params(args, kwargs)
        return self._collector.call(self._name, params)


class _BatchNotifyProxy:
    """Proxy for `batch.notify.method(...)` — adds notifications to batch."""

    def __init__(
        self,
        collector: BatchCollector | AsyncBatchCollector,
        name: str | None = None,
    ) -> None:
        self._collector = collector
        self._name = name

    def __getattr__(self, name: str) -> _BatchNotifyProxy:
        full_name = f"{self._name}.{name}" if self._name else name
        return _BatchNotifyProxy(self._collector, full_name)

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        if self._name is None:
            raise TypeError(
                "Cannot call notify directly. "
                "Use batch.notify.method_name(...)"
            )
        params = _resolve_params(args, kwargs)
        self._collector.add_notification(self._name, params)


# --- Batch collectors ---

_BATCH_RESERVED = frozenset(
    {"call", "notify", "results", "add_notification"}
)


class BatchCollector:
    """Sync batch request collector — used as context manager.

    Collects JSON-RPC requests, sends them as a batch on __exit__.
    Supports proxy-style method calls.
    """

    def __init__(
        self,
        transport: BaseTransport,
        id_generator: Iterator[RequestID],
    ) -> None:
        self._transport = transport
        self._id_generator = id_generator
        self._requests: list[dict[str, Any]] = []
        self._results: BatchResult | None = None

    def call(
        self,
        method: str,
        params: JSONParams = None,
    ) -> RequestID:
        """Add an RPC call to the batch. Returns the request ID."""
        request_id = next(self._id_generator)
        self._requests.append(
            _build_request_payload(method, params, request_id)
        )
        return request_id

    def add_notification(
        self,
        method: str,
        params: JSONParams = None,
    ) -> None:
        """Add a notification (no response expected) to the batch."""
        self._requests.append(
            _build_notification_payload(method, params)
        )

    @property
    def notify(self) -> _BatchNotifyProxy:
        """Proxy for adding notifications: ``batch.notify.method(...)``."""
        return _BatchNotifyProxy(self)

    @property
    def results(self) -> BatchResult:
        """Access batch results after the context manager exits."""
        if self._results is None:
            raise RuntimeError(
                "Batch results not available yet. "
                "Use 'with client.batch() as batch:' and access "
                "batch.results after the with block."
            )
        return self._results

    def __getattr__(self, name: str) -> _BatchMethodProxy:
        if name.startswith("_") or name in _BATCH_RESERVED:
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{name}'"
            )
        return _BatchMethodProxy(self, name)

    def __enter__(self) -> BatchCollector:
        return self

    def __exit__(self, *args: Any) -> None:
        if args[0] is not None:
            return
        if not self._requests:
            self._results = BatchResult([])
            return
        batch_bytes = json.dumps(self._requests).encode()
        response_bytes = self._transport.handle_request(batch_bytes)
        # Server may return 204 for all-notification batches
        if not response_bytes or response_bytes.strip() == b"":
            self._results = BatchResult([])
            return
        self._results = BatchResult(_parse_batch_response(response_bytes))


class AsyncBatchCollector:
    """Async batch request collector — used as async context manager.

    Collects JSON-RPC requests, sends them as a batch on __aexit__.
    Supports proxy-style method calls.
    """

    def __init__(
        self,
        transport: AsyncBaseTransport,
        id_generator: Iterator[RequestID],
    ) -> None:
        self._transport = transport
        self._id_generator = id_generator
        self._requests: list[dict[str, Any]] = []
        self._results: BatchResult | None = None

    def call(
        self,
        method: str,
        params: JSONParams = None,
    ) -> RequestID:
        """Add an RPC call to the batch. Returns the request ID."""
        request_id = next(self._id_generator)
        self._requests.append(
            _build_request_payload(method, params, request_id)
        )
        return request_id

    def add_notification(
        self,
        method: str,
        params: JSONParams = None,
    ) -> None:
        """Add a notification to the batch."""
        self._requests.append(
            _build_notification_payload(method, params)
        )

    @property
    def notify(self) -> _BatchNotifyProxy:
        """Proxy for adding notifications: ``batch.notify.method(...)``."""
        return _BatchNotifyProxy(self)

    @property
    def results(self) -> BatchResult:
        """Access batch results after the async context manager exits."""
        if self._results is None:
            raise RuntimeError(
                "Batch results not available yet. "
                "Use 'async with client.batch() as batch:' and access "
                "batch.results after the async with block."
            )
        return self._results

    def __getattr__(self, name: str) -> _AsyncBatchMethodProxy:
        if name.startswith("_") or name in _BATCH_RESERVED:
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{name}'"
            )
        return _AsyncBatchMethodProxy(self, name)

    async def __aenter__(self) -> AsyncBatchCollector:
        return self

    async def __aexit__(self, *args: Any) -> None:
        if args[0] is not None:
            return
        if not self._requests:
            self._results = BatchResult([])
            return
        batch_bytes = json.dumps(self._requests).encode()
        response_bytes = await self._transport.handle_async_request(
            batch_bytes
        )
        if not response_bytes or response_bytes.strip() == b"":
            self._results = BatchResult([])
            return
        self._results = BatchResult(_parse_batch_response(response_bytes))
