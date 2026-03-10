"""Tests for jrpcx._models module."""

import json

import pytest

from jrpcx._exceptions import (
    InvalidResponseError,
    MethodNotFoundError,
    ServerError,
)
from jrpcx._models import UNSET, ErrorData, Request, Response, _Unset


class TestUnset:
    def test_singleton(self) -> None:
        assert _Unset() is _Unset()
        assert _Unset() is UNSET

    def test_repr(self) -> None:
        assert repr(UNSET) == "UNSET"

    def test_falsy(self) -> None:
        assert not UNSET

    def test_is_not_none(self) -> None:
        assert UNSET is not None


class TestErrorData:
    def test_construction(self) -> None:
        err = ErrorData(code=-32601, message="Method not found")
        assert err.code == -32601
        assert err.message == "Method not found"
        assert err.data is None

    def test_with_data(self) -> None:
        err = ErrorData(code=-32602, message="Invalid params", data={"field": "x"})
        assert err.data == {"field": "x"}

    def test_to_dict(self) -> None:
        err = ErrorData(code=-32601, message="Method not found")
        assert err.to_dict() == {"code": -32601, "message": "Method not found"}

    def test_to_dict_with_data(self) -> None:
        err = ErrorData(code=-32601, message="Method not found", data="extra")
        d = err.to_dict()
        assert d["data"] == "extra"

    def test_from_dict(self) -> None:
        err = ErrorData.from_dict({"code": -32601, "message": "not found"})
        assert err.code == -32601
        assert err.message == "not found"

    def test_frozen(self) -> None:
        err = ErrorData(code=-32601, message="test")
        with pytest.raises(AttributeError):
            err.code = 0  # type: ignore[misc]


class TestRequest:
    def test_basic_request(self) -> None:
        req = Request(method="eth_blockNumber", id=1)
        assert req.method == "eth_blockNumber"
        assert req.params is None
        assert req.id == 1
        assert not req.is_notification

    def test_notification(self) -> None:
        req = Request(method="log_event")
        assert req.is_notification
        assert req.id is None

    def test_with_list_params(self) -> None:
        req = Request(method="add", params=[1, 2], id=1)
        assert req.params == [1, 2]

    def test_with_dict_params(self) -> None:
        req = Request(method="greet", params={"name": "Alice"}, id=1)
        assert req.params == {"name": "Alice"}

    def test_to_dict_basic(self) -> None:
        req = Request(method="test", id=1)
        d = req.to_dict()
        assert d == {"jsonrpc": "2.0", "method": "test", "id": 1}
        assert "params" not in d

    def test_to_dict_with_params(self) -> None:
        req = Request(method="add", params=[1, 2], id=1)
        d = req.to_dict()
        assert d["params"] == [1, 2]

    def test_to_dict_notification(self) -> None:
        req = Request(method="notify")
        d = req.to_dict()
        assert "id" not in d
        assert d == {"jsonrpc": "2.0", "method": "notify"}

    def test_to_json(self) -> None:
        req = Request(method="test", id=1)
        parsed = json.loads(req.to_json())
        assert parsed == {"jsonrpc": "2.0", "method": "test", "id": 1}

    def test_frozen(self) -> None:
        req = Request(method="test", id=1)
        with pytest.raises(AttributeError):
            req.method = "other"  # type: ignore[misc]

    def test_string_id(self) -> None:
        req = Request(method="test", id="abc-123")
        assert req.to_dict()["id"] == "abc-123"


class TestResponse:
    def test_success_response(self) -> None:
        resp = Response(id=1, result="0x10d4f")
        assert resp.is_success
        assert not resp.is_error
        assert resp.result == "0x10d4f"

    def test_error_response(self) -> None:
        err = ErrorData(code=-32601, message="Method not found")
        resp = Response(id=1, error=err)
        assert resp.is_error
        assert not resp.is_success

    def test_null_result_is_success(self) -> None:
        resp = Response(id=1, result=None)
        assert resp.is_success
        assert resp.result is None

    def test_unset_result_is_not_success(self) -> None:
        resp = Response(id=1)
        assert not resp.is_success
        assert isinstance(resp.result, _Unset)

    def test_raise_for_error_no_error(self) -> None:
        resp = Response(id=1, result="ok")
        resp.raise_for_error()  # should not raise

    def test_raise_for_error_method_not_found(self) -> None:
        err = ErrorData(code=-32601, message="Method not found")
        resp = Response(id=1, error=err)
        with pytest.raises(MethodNotFoundError) as exc_info:
            resp.raise_for_error()
        assert exc_info.value.code == -32601

    def test_raise_for_error_unknown_code(self) -> None:
        err = ErrorData(code=-1, message="Unknown")
        resp = Response(id=1, error=err)
        with pytest.raises(ServerError):
            resp.raise_for_error()

    def test_from_dict_success(self) -> None:
        data = {"jsonrpc": "2.0", "result": 42, "id": 1}
        resp = Response.from_dict(data)
        assert resp.result == 42
        assert resp.id == 1
        assert resp.is_success

    def test_from_dict_error(self) -> None:
        data = {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": 1,
        }
        resp = Response.from_dict(data)
        assert resp.is_error
        assert resp.error is not None
        assert resp.error.code == -32601

    def test_from_dict_null_result(self) -> None:
        data = {"jsonrpc": "2.0", "result": None, "id": 1}
        resp = Response.from_dict(data)
        assert resp.result is None
        assert resp.is_success

    def test_from_dict_invalid_version(self) -> None:
        data = {"jsonrpc": "1.0", "result": 42, "id": 1}
        with pytest.raises(InvalidResponseError):
            Response.from_dict(data)

    def test_from_dict_missing_version(self) -> None:
        data = {"result": 42, "id": 1}
        with pytest.raises(InvalidResponseError):
            Response.from_dict(data)

    def test_from_dict_null_id(self) -> None:
        data = {"jsonrpc": "2.0", "result": "ok", "id": None}
        resp = Response.from_dict(data)
        assert resp.id is None

    def test_elapsed(self) -> None:
        from datetime import timedelta

        resp = Response(id=1, result="ok", elapsed=timedelta(milliseconds=150))
        assert resp.elapsed is not None
        assert resp.elapsed.total_seconds() == pytest.approx(0.15)
