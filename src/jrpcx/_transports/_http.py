"""HTTP transports using httpx."""

from __future__ import annotations

import httpx

from jrpcx._exceptions import ConnectionError as RPCConnectionError
from jrpcx._exceptions import HTTPStatusError, TimeoutError, TransportError
from jrpcx._transports import AsyncBaseTransport, BaseTransport

_JSON_RPC_CONTENT_TYPE = "application/json"
_JSON_RPC_HEADERS = {"Content-Type": _JSON_RPC_CONTENT_TYPE}


class HTTPTransport(BaseTransport):
    """Synchronous HTTP transport using httpx."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = url
        merged_headers = {**_JSON_RPC_HEADERS, **(headers or {})}
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client(
                headers=merged_headers,
                auth=auth,
                timeout=timeout,
            )
            self._owns_client = True

    def handle_request(self, request: bytes) -> bytes:
        try:
            response = self._client.post(
                self._url,
                content=request,
                headers=_JSON_RPC_HEADERS,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise RPCConnectionError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPStatusError(
                f"HTTP {exc.response.status_code}: "
                f"{exc.response.reason_phrase}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        return response.content

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class AsyncHTTPTransport(AsyncBaseTransport):
    """Asynchronous HTTP transport using httpx."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = url
        merged_headers = {**_JSON_RPC_HEADERS, **(headers or {})}
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(
                headers=merged_headers,
                auth=auth,
                timeout=timeout,
            )
            self._owns_client = True

    async def handle_async_request(self, request: bytes) -> bytes:
        try:
            response = await self._client.post(
                self._url,
                content=request,
                headers=_JSON_RPC_HEADERS,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise RPCConnectionError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPStatusError(
                f"HTTP {exc.response.status_code}: "
                f"{exc.response.reason_phrase}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        return response.content

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
