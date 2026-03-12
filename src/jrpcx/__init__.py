"""jrpcx — Modern Python JSON-RPC 2.0 Client."""

from jrpcx._batch import BatchResult
from jrpcx._client import AsyncJSONRPCClient, JSONRPCClient
from jrpcx._config import Timeout
from jrpcx._exceptions import (
    ApplicationError,
    ConnectionError,
    HTTPStatusError,
    InternalError,
    InvalidParamsError,
    InvalidRequestError,
    InvalidResponseError,
    JSONRPCError,
    MethodNotFoundError,
    ParseError,
    ProtocolError,
    ServerError,
    TimeoutError,
    TransportError,
)
from jrpcx._logging import log_request, log_response
from jrpcx._middleware import (
    AsyncMiddleware,
    AsyncMiddlewareHandler,
    Middleware,
    MiddlewareHandler,
)
from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports import AsyncBaseTransport, BaseTransport
from jrpcx._transports._http import AsyncHTTPTransport, HTTPTransport
from jrpcx._transports._mock import AsyncMockTransport, MockTransport
from jrpcx._types import USE_CLIENT_DEFAULT

Client = JSONRPCClient
AsyncClient = AsyncJSONRPCClient

__all__ = [
    "USE_CLIENT_DEFAULT",
    "ApplicationError",
    "AsyncBaseTransport",
    "AsyncClient",
    "AsyncHTTPTransport",
    "AsyncJSONRPCClient",
    "AsyncMiddleware",
    "AsyncMiddlewareHandler",
    "AsyncMockTransport",
    "BaseTransport",
    "BatchResult",
    "Client",
    "ConnectionError",
    "ErrorData",
    "HTTPStatusError",
    "HTTPTransport",
    "InternalError",
    "InvalidParamsError",
    "InvalidRequestError",
    "InvalidResponseError",
    "JSONRPCClient",
    "JSONRPCError",
    "MethodNotFoundError",
    "Middleware",
    "MiddlewareHandler",
    "MockTransport",
    "ParseError",
    "ProtocolError",
    "Request",
    "Response",
    "ServerError",
    "Timeout",
    "TimeoutError",
    "TransportError",
    "log_request",
    "log_response",
]
