"""Tests for typed error deserialization via __init_subclass__."""

from __future__ import annotations

import pytest

import jrpcx
from jrpcx._exceptions import (
    _ERROR_CODE_MAP,
    ServerError,
    error_class_for_code,
)
from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports._mock import MockTransport


class TestTypedErrorRegistration:
    def test_subclass_with_code_auto_registers(self) -> None:
        class CustomError(ServerError):
            CODE = -32050

        assert _ERROR_CODE_MAP[-32050] is CustomError
        assert error_class_for_code(-32050) is CustomError

    def test_subclass_without_code_not_registered(self) -> None:
        class PlainError(ServerError):
            pass

        # Should not add any new entries for PlainError
        assert PlainError not in _ERROR_CODE_MAP.values()

    def test_multiple_custom_errors(self) -> None:
        class ErrorA(ServerError):
            CODE = -32051

        class ErrorB(ServerError):
            CODE = -32052

        assert error_class_for_code(-32051) is ErrorA
        assert error_class_for_code(-32052) is ErrorB

    def test_custom_error_raised_by_client(self) -> None:
        class InsufficientFundsError(ServerError):
            CODE = -32001

        def handler(req: Request) -> Response:
            return Response(
                id=req.id,
                error=ErrorData(code=-32001, message="Not enough funds"),
            )

        transport = MockTransport(handler)
        client = jrpcx.Client("http://test", transport=transport)
        with pytest.raises(InsufficientFundsError) as exc_info:
            client.transfer(100)
        assert exc_info.value.code == -32001
        assert "Not enough funds" in str(exc_info.value)
        client.close()

    def test_custom_error_with_data(self) -> None:
        class RateLimitError(ServerError):
            CODE = -32002

        def handler(req: Request) -> Response:
            return Response(
                id=req.id,
                error=ErrorData(
                    code=-32002,
                    message="Rate limited",
                    data={"retry_after": 30},
                ),
            )

        transport = MockTransport(handler)
        client = jrpcx.Client("http://test", transport=transport)
        with pytest.raises(RateLimitError) as exc_info:
            client.submit_request()
        assert exc_info.value.data == {"retry_after": 30}
        client.close()

    def test_standard_errors_still_work(self) -> None:
        """Built-in error codes should still map to built-in classes."""
        assert error_class_for_code(-32601) is jrpcx.MethodNotFoundError
        assert error_class_for_code(-32602) is jrpcx.InvalidParamsError
        assert error_class_for_code(-32603) is jrpcx.InternalError
