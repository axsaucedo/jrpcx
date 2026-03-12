"""JSON-RPC 2.0 client implementations."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from jrpcx._config import Timeout, TimeoutTypes
from jrpcx._exceptions import InvalidResponseError, ProtocolError
from jrpcx._id_generators import sequential
from jrpcx._models import Response
from jrpcx._transports import AsyncBaseTransport, BaseTransport
from jrpcx._transports._http import AsyncHTTPTransport, HTTPTransport
from jrpcx._types import (
    USE_CLIENT_DEFAULT,
    JSONParams,
    RequestID,
    _UseClientDefault,
)


class BaseJSONRPCClient:
    """Shared business logic for sync and async JSON-RPC clients."""

    _RESERVED_NAMES: frozenset[str] = frozenset(
        {"call", "close", "aclose", "send", "send_request", "notify", "batch"}
    )

    def __init__(
        self,
        url: str,
        *,
        transport: BaseTransport | AsyncBaseTransport | None = None,
        timeout: TimeoutTypes = None,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        id_generator: Iterator[RequestID] | None = None,
        event_hooks: dict[
            str, list[Callable[..., Any]]
        ]
        | None = None,
    ) -> None:
        self._url = url
        self._transport = transport
        self._timeout = (
            Timeout(timeout)
            if isinstance(timeout, (int, float))
            else timeout
        )
        self._headers = headers
        self._auth = auth
        self._id_generator = id_generator or sequential()
        self._closed = False
        self._event_hooks: dict[str, list[Callable[..., Any]]] = {
            "request": [],
            "response": [],
            "error": [],
        }
        if event_hooks:
            for key, hooks in event_hooks.items():
                if key not in self._event_hooks:
                    raise ValueError(
                        f"Unknown event hook: {key!r}. "
                        f"Valid: {list(self._event_hooks)}"
                    )
                self._event_hooks[key] = list(hooks)

    def _fire_hooks(
        self, event: str, *args: Any
    ) -> None:
        for hook in self._event_hooks.get(event, []):
            hook(*args)

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

    def _build_notification_bytes(
        self,
        method: str,
        params: JSONParams = None,
    ) -> bytes:
        """Build a JSON-RPC notification (no id, no response expected)."""
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        return json.dumps(payload).encode()

    def _parse_response(self, data: bytes) -> Response:
        """Parse JSON-RPC response bytes into a Response object."""
        try:
            parsed = json.loads(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProtocolError(
                f"Invalid JSON in response: {exc}"
            ) from exc

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


# --- Proxy helpers ---


class _MethodProxy:
    """Proxy for `client.method_name(...)` calls."""

    def __init__(
        self,
        client: JSONRPCClient,
        name: str,
    ) -> None:
        self._client = client
        self._name = name

    def __getattr__(self, name: str) -> _MethodProxy:
        return _MethodProxy(
            self._client, f"{self._name}.{name}"
        )

    def __call__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        params = _resolve_params(args, kwargs)
        return self._client.call(self._name, params)


class _AsyncMethodProxy:
    """Proxy for `await client.method_name(...)` calls."""

    def __init__(
        self,
        client: AsyncJSONRPCClient,
        name: str,
    ) -> None:
        self._client = client
        self._name = name

    def __getattr__(self, name: str) -> _AsyncMethodProxy:
        return _AsyncMethodProxy(
            self._client, f"{self._name}.{name}"
        )

    def __call__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        params = _resolve_params(args, kwargs)
        return self._client.call(self._name, params)


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


# --- Notify proxies ---


class _NotifyProxy:
    """Proxy for `client.notify.method(...)` — sends notifications (no response)."""

    def __init__(
        self,
        client: JSONRPCClient,
        name: str | None = None,
    ) -> None:
        self._client = client
        self._name = name

    def __getattr__(self, name: str) -> _NotifyProxy:
        full_name = f"{self._name}.{name}" if self._name else name
        return _NotifyProxy(self._client, full_name)

    def __call__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self._name is None:
            raise TypeError(
                "Cannot call notify directly. "
                "Use client.notify.method_name(...)"
            )
        params = _resolve_params(args, kwargs)
        self._client._send_notification(self._name, params)


class _AsyncNotifyProxy:
    """Proxy for `await client.notify.method(...)` — sends async notifications."""

    def __init__(
        self,
        client: AsyncJSONRPCClient,
        name: str | None = None,
    ) -> None:
        self._client = client
        self._name = name

    def __getattr__(self, name: str) -> _AsyncNotifyProxy:
        full_name = f"{self._name}.{name}" if self._name else name
        return _AsyncNotifyProxy(self._client, full_name)

    def __call__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self._name is None:
            raise TypeError(
                "Cannot call notify directly. "
                "Use client.notify.method_name(...)"
            )
        params = _resolve_params(args, kwargs)
        return self._client._send_notification(self._name, params)


# --- Sync client ---


class JSONRPCClient(BaseJSONRPCClient):
    """Synchronous JSON-RPC 2.0 client with proxy-first API."""

    def __init__(
        self,
        url: str,
        *,
        transport: BaseTransport | None = None,
        timeout: TimeoutTypes = None,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        id_generator: Iterator[RequestID] | None = None,
        event_hooks: dict[
            str, list[Callable[..., Any]]
        ]
        | None = None,
    ) -> None:
        super().__init__(
            url,
            transport=transport,
            timeout=timeout,
            headers=headers,
            auth=auth,
            id_generator=id_generator,
            event_hooks=event_hooks,
        )
        if transport is not None:
            self._sync_transport: BaseTransport = transport
        else:
            httpx_timeout = (
                self._timeout.read
                if isinstance(self._timeout, Timeout)
                else self._timeout
            )
            self._sync_transport = HTTPTransport(
                url,
                headers=headers,
                auth=auth,
                timeout=httpx_timeout,
            )

    def _get_transport(self) -> BaseTransport:
        return self._sync_transport

    def call(
        self,
        method: str,
        params: JSONParams = None,
        *,
        timeout: TimeoutTypes | _UseClientDefault = USE_CLIENT_DEFAULT,
    ) -> Any:
        """Make a JSON-RPC call and return the result."""
        self._ensure_open()
        request_bytes, _ = self._build_request_bytes(
            method, params
        )
        self._fire_hooks("request", method, params)
        transport = self._get_transport()
        try:
            response_bytes = transport.handle_request(
                request_bytes
            )
        except Exception as exc:
            self._fire_hooks("error", exc)
            raise
        response = self._parse_response(response_bytes)
        self._fire_hooks("response", response)
        response.raise_for_error()
        return response.result

    def _send_notification(
        self,
        method: str,
        params: JSONParams = None,
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        self._ensure_open()
        request_bytes = self._build_notification_bytes(method, params)
        self._fire_hooks("request", method, params)
        transport = self._get_transport()
        try:
            transport.handle_request(request_bytes)
        except Exception as exc:
            self._fire_hooks("error", exc)
            raise

    @property
    def notify(self) -> _NotifyProxy:
        """Proxy namespace for sending notifications.

        Usage: ``client.notify.method_name(params)``
        """
        return _NotifyProxy(self)

    def __getattr__(self, name: str) -> _MethodProxy:
        if name.startswith("_") or name in self._RESERVED_NAMES:
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{name}'"
            )
        return _MethodProxy(self, name)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._sync_transport is not None:
                self._sync_transport.close()

    def __enter__(self) -> JSONRPCClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# --- Async client ---


class AsyncJSONRPCClient(BaseJSONRPCClient):
    """Asynchronous JSON-RPC 2.0 client with proxy-first API."""

    def __init__(
        self,
        url: str,
        *,
        transport: AsyncBaseTransport | None = None,
        timeout: TimeoutTypes = None,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        id_generator: Iterator[RequestID] | None = None,
        event_hooks: dict[
            str, list[Callable[..., Any]]
        ]
        | None = None,
    ) -> None:
        super().__init__(
            url,
            transport=transport,
            timeout=timeout,
            headers=headers,
            auth=auth,
            id_generator=id_generator,
            event_hooks=event_hooks,
        )
        if transport is not None:
            self._async_transport: AsyncBaseTransport = transport
        else:
            httpx_timeout = (
                self._timeout.read
                if isinstance(self._timeout, Timeout)
                else self._timeout
            )
            self._async_transport = AsyncHTTPTransport(
                url,
                headers=headers,
                auth=auth,
                timeout=httpx_timeout,
            )

    def _get_transport(self) -> AsyncBaseTransport:
        return self._async_transport

    async def call(
        self,
        method: str,
        params: JSONParams = None,
        *,
        timeout: TimeoutTypes | _UseClientDefault = USE_CLIENT_DEFAULT,
    ) -> Any:
        """Make an async JSON-RPC call and return the result."""
        self._ensure_open()
        request_bytes, _ = self._build_request_bytes(
            method, params
        )
        self._fire_hooks("request", method, params)
        transport = self._get_transport()
        try:
            response_bytes = (
                await transport.handle_async_request(
                    request_bytes
                )
            )
        except Exception as exc:
            self._fire_hooks("error", exc)
            raise
        response = self._parse_response(response_bytes)
        self._fire_hooks("response", response)
        response.raise_for_error()
        return response.result

    async def _send_notification(
        self,
        method: str,
        params: JSONParams = None,
    ) -> None:
        """Send an async JSON-RPC notification (no response expected)."""
        self._ensure_open()
        request_bytes = self._build_notification_bytes(method, params)
        self._fire_hooks("request", method, params)
        transport = self._get_transport()
        try:
            await transport.handle_async_request(request_bytes)
        except Exception as exc:
            self._fire_hooks("error", exc)
            raise

    @property
    def notify(self) -> _AsyncNotifyProxy:
        """Proxy namespace for sending async notifications.

        Usage: ``await client.notify.method_name(params)``
        """
        return _AsyncNotifyProxy(self)

    def __getattr__(self, name: str) -> _AsyncMethodProxy:
        if name.startswith("_") or name in self._RESERVED_NAMES:
            raise AttributeError(
                f"'{type(self).__name__}' has no attribute '{name}'"
            )
        return _AsyncMethodProxy(self, name)

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            if self._async_transport is not None:
                await self._async_transport.aclose()

    async def __aenter__(self) -> AsyncJSONRPCClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

