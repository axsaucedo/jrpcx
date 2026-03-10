"""Tests for public API exports."""

from __future__ import annotations

import jrpcx


class TestPublicAPI:
    """Verify all expected names are importable from jrpcx."""

    def test_client_aliases(self) -> None:
        assert jrpcx.Client is jrpcx.JSONRPCClient
        assert jrpcx.AsyncClient is jrpcx.AsyncJSONRPCClient

    def test_all_exports(self) -> None:
        expected = {
            "Client",
            "AsyncClient",
            "JSONRPCClient",
            "AsyncJSONRPCClient",
            "Request",
            "Response",
            "ErrorData",
            "Timeout",
            "USE_CLIENT_DEFAULT",
            "BaseTransport",
            "AsyncBaseTransport",
            "HTTPTransport",
            "AsyncHTTPTransport",
            "MockTransport",
            "AsyncMockTransport",
            "JSONRPCError",
            "TransportError",
            "TimeoutError",
            "ConnectionError",
            "HTTPStatusError",
            "ProtocolError",
            "ParseError",
            "InvalidRequestError",
            "InvalidResponseError",
            "ServerError",
            "MethodNotFoundError",
            "InvalidParamsError",
            "InternalError",
            "ApplicationError",
        }
        actual = set(jrpcx.__all__)
        assert actual == expected

    def test_all_names_importable(self) -> None:
        for name in jrpcx.__all__:
            obj = getattr(jrpcx, name)
            assert obj is not None, f"{name} is None"
