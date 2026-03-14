"""Exception hierarchy for jrpcx.

All exceptions carry request/response context for debugging.
Maps JSON-RPC 2.0 error codes to specific exception classes.
"""

from __future__ import annotations

from typing import Any


class ErrorCode:
    """Standard JSON-RPC 2.0 error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_MIN = -32099
    SERVER_ERROR_MAX = -32000


class JSONRPCError(Exception):
    """Base exception for all jrpcx errors."""

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        data: Any = None,
        request: Any = None,
        response: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data
        self.request = request
        self.response = response


# --- Transport errors (network/HTTP layer) ---


class TransportError(JSONRPCError):
    """Network or HTTP-level transport failure."""


class TimeoutError(TransportError):
    """Request timed out."""


class ConnectionError(TransportError):
    """Failed to establish connection."""


class HTTPStatusError(TransportError):
    """Server returned a non-2xx HTTP status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: int | None = None,
        data: Any = None,
        request: Any = None,
        response: Any = None,
    ) -> None:
        super().__init__(
            message, code=code, data=data, request=request, response=response
        )
        self.status_code = status_code


# --- Protocol errors (JSON-RPC protocol violations) ---


class ProtocolError(JSONRPCError):
    """JSON-RPC protocol violation."""


class ParseError(ProtocolError):
    """Server couldn't parse JSON (-32700)."""

    def __init__(
        self,
        message: str = "Parse error",
        **kwargs: Any,
    ) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code=ErrorCode.PARSE_ERROR, **kwargs)


class InvalidRequestError(ProtocolError):
    """Not a valid JSON-RPC request (-32600)."""

    def __init__(
        self,
        message: str = "Invalid request",
        **kwargs: Any,
    ) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code=ErrorCode.INVALID_REQUEST, **kwargs)


class InvalidResponseError(ProtocolError):
    """Response doesn't conform to JSON-RPC 2.0."""


# Registry: error code → exception class (populated by __init_subclass__ and below)
_ERROR_CODE_MAP: dict[int, type[ServerError]] = {}


# --- Server errors (JSON-RPC error responses) ---


class ServerError(JSONRPCError):
    """Server returned a JSON-RPC error response.

    Subclass with a CODE class attribute to auto-register for typed
    error deserialization::

        class InsufficientFundsError(jrpcx.ServerError):
            CODE = -32001
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        code = getattr(cls, "CODE", None)
        if code is not None and isinstance(code, int):
            _ERROR_CODE_MAP[code] = cls


class MethodNotFoundError(ServerError):
    """Method not found (-32601)."""

    def __init__(
        self,
        message: str = "Method not found",
        **kwargs: Any,
    ) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code=ErrorCode.METHOD_NOT_FOUND, **kwargs)


class InvalidParamsError(ServerError):
    """Invalid method parameters (-32602)."""

    def __init__(
        self,
        message: str = "Invalid params",
        **kwargs: Any,
    ) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code=ErrorCode.INVALID_PARAMS, **kwargs)


class InternalError(ServerError):
    """Internal JSON-RPC error (-32603)."""

    def __init__(
        self,
        message: str = "Internal error",
        **kwargs: Any,
    ) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code=ErrorCode.INTERNAL_ERROR, **kwargs)


class ApplicationError(ServerError):
    """Custom server error code (typically -32000 to -32099)."""


# Add standard error codes to registry (these use __init_subclass__ but
# don't have CODE class attrs, so we add them manually)
_ERROR_CODE_MAP.update({
    ErrorCode.METHOD_NOT_FOUND: MethodNotFoundError,
    ErrorCode.INVALID_PARAMS: InvalidParamsError,
    ErrorCode.INTERNAL_ERROR: InternalError,
    ErrorCode.PARSE_ERROR: ParseError,  # type: ignore[dict-item]
    ErrorCode.INVALID_REQUEST: InvalidRequestError,  # type: ignore[dict-item]
})


def error_class_for_code(code: int) -> type[ServerError]:
    """Return the exception class for a JSON-RPC error code."""
    if code in _ERROR_CODE_MAP:
        return _ERROR_CODE_MAP[code]
    if ErrorCode.SERVER_ERROR_MIN <= code <= ErrorCode.SERVER_ERROR_MAX:
        return ApplicationError
    return ServerError
