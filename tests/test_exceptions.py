"""Tests for jrpcx._exceptions module."""

import pytest

from jrpcx._exceptions import (
    ApplicationError,
    ConnectionError,
    ErrorCode,
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
    error_class_for_code,
)


class TestErrorCode:
    def test_standard_codes(self) -> None:
        assert ErrorCode.PARSE_ERROR == -32700
        assert ErrorCode.INVALID_REQUEST == -32600
        assert ErrorCode.METHOD_NOT_FOUND == -32601
        assert ErrorCode.INVALID_PARAMS == -32602
        assert ErrorCode.INTERNAL_ERROR == -32603

    def test_server_error_range(self) -> None:
        assert ErrorCode.SERVER_ERROR_MIN == -32099
        assert ErrorCode.SERVER_ERROR_MAX == -32000


class TestExceptionHierarchy:
    def test_transport_errors_are_jsonrpc_errors(self) -> None:
        assert issubclass(TransportError, JSONRPCError)
        assert issubclass(TimeoutError, TransportError)
        assert issubclass(ConnectionError, TransportError)
        assert issubclass(HTTPStatusError, TransportError)

    def test_protocol_errors_are_jsonrpc_errors(self) -> None:
        assert issubclass(ProtocolError, JSONRPCError)
        assert issubclass(ParseError, ProtocolError)
        assert issubclass(InvalidRequestError, ProtocolError)
        assert issubclass(InvalidResponseError, ProtocolError)

    def test_server_errors_are_jsonrpc_errors(self) -> None:
        assert issubclass(ServerError, JSONRPCError)
        assert issubclass(MethodNotFoundError, ServerError)
        assert issubclass(InvalidParamsError, ServerError)
        assert issubclass(InternalError, ServerError)
        assert issubclass(ApplicationError, ServerError)


class TestJSONRPCError:
    def test_basic_construction(self) -> None:
        exc = JSONRPCError("something went wrong")
        assert str(exc) == "something went wrong"
        assert exc.code is None
        assert exc.data is None
        assert exc.request is None
        assert exc.response is None

    def test_with_all_fields(self) -> None:
        exc = JSONRPCError(
            "method not found",
            code=-32601,
            data={"detail": "no such method"},
        )
        assert exc.code == -32601
        assert exc.data == {"detail": "no such method"}

    def test_is_catchable_as_exception(self) -> None:
        with pytest.raises(JSONRPCError):
            raise JSONRPCError("error")


class TestSpecificExceptions:
    def test_parse_error_default_code(self) -> None:
        exc = ParseError()
        assert exc.code == ErrorCode.PARSE_ERROR
        assert str(exc) == "Parse error"

    def test_method_not_found_default_code(self) -> None:
        exc = MethodNotFoundError()
        assert exc.code == ErrorCode.METHOD_NOT_FOUND

    def test_invalid_params_default_code(self) -> None:
        exc = InvalidParamsError()
        assert exc.code == ErrorCode.INVALID_PARAMS

    def test_internal_error_default_code(self) -> None:
        exc = InternalError()
        assert exc.code == ErrorCode.INTERNAL_ERROR

    def test_invalid_request_default_code(self) -> None:
        exc = InvalidRequestError()
        assert exc.code == ErrorCode.INVALID_REQUEST

    def test_custom_message_override(self) -> None:
        exc = MethodNotFoundError("custom message")
        assert str(exc) == "custom message"
        assert exc.code == ErrorCode.METHOD_NOT_FOUND

    def test_http_status_error(self) -> None:
        exc = HTTPStatusError("Bad Gateway", status_code=502)
        assert exc.status_code == 502
        assert str(exc) == "Bad Gateway"


class TestErrorClassForCode:
    def test_standard_codes(self) -> None:
        assert error_class_for_code(-32601) is MethodNotFoundError
        assert error_class_for_code(-32602) is InvalidParamsError
        assert error_class_for_code(-32603) is InternalError
        assert error_class_for_code(-32700) is ParseError
        assert error_class_for_code(-32600) is InvalidRequestError

    def test_server_error_range(self) -> None:
        assert error_class_for_code(-32000) is ApplicationError
        assert error_class_for_code(-32050) is ApplicationError
        assert error_class_for_code(-32099) is ApplicationError

    def test_unknown_code(self) -> None:
        assert error_class_for_code(-1) is ServerError
        assert error_class_for_code(42) is ServerError
