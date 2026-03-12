"""Tests for BatchResult model."""

from __future__ import annotations

import pytest

from jrpcx._batch import BatchResult
from jrpcx._exceptions import MethodNotFoundError
from jrpcx._models import ErrorData, Response


def _ok(rid: int, result: object) -> Response:
    return Response(id=rid, result=result)


def _err(rid: int, code: int = -32601, msg: str = "Not found") -> Response:
    return Response(id=rid, error=ErrorData(code=code, message=msg))


class TestBatchResult:
    def test_all_returns_copy(self) -> None:
        responses = [_ok(1, "a"), _ok(2, "b")]
        br = BatchResult(responses)
        assert br.all() == responses
        assert br.all() is not responses

    def test_successes(self) -> None:
        br = BatchResult([_ok(1, "a"), _err(2), _ok(3, "c")])
        assert len(br.successes) == 2
        assert br.successes[0].result == "a"
        assert br.successes[1].result == "c"

    def test_errors(self) -> None:
        br = BatchResult([_ok(1, "a"), _err(2), _err(3)])
        assert len(br.errors) == 2
        assert br.errors[0].id == 2
        assert br.errors[1].id == 3

    def test_has_errors_true(self) -> None:
        br = BatchResult([_ok(1, "a"), _err(2)])
        assert br.has_errors is True

    def test_has_errors_false(self) -> None:
        br = BatchResult([_ok(1, "a"), _ok(2, "b")])
        assert br.has_errors is False

    def test_by_id_found(self) -> None:
        br = BatchResult([_ok(1, "a"), _ok(2, "b"), _ok(3, "c")])
        resp = br.by_id(2)
        assert resp is not None
        assert resp.result == "b"

    def test_by_id_not_found(self) -> None:
        br = BatchResult([_ok(1, "a")])
        assert br.by_id(999) is None

    def test_values_all_success(self) -> None:
        br = BatchResult([_ok(1, "a"), _ok(2, "b")])
        assert br.values() == ["a", "b"]

    def test_values_raises_on_error(self) -> None:
        br = BatchResult([_ok(1, "a"), _err(2)])
        with pytest.raises(MethodNotFoundError):
            br.values()

    def test_len(self) -> None:
        br = BatchResult([_ok(1, "a"), _ok(2, "b"), _ok(3, "c")])
        assert len(br) == 3

    def test_iter(self) -> None:
        responses = [_ok(1, "a"), _ok(2, "b")]
        br = BatchResult(responses)
        assert list(br) == responses

    def test_getitem(self) -> None:
        br = BatchResult([_ok(1, "a"), _ok(2, "b")])
        assert br[0].result == "a"
        assert br[1].result == "b"

    def test_repr(self) -> None:
        br = BatchResult([_ok(1, "a"), _err(2), _ok(3, "c")])
        assert repr(br) == "BatchResult(2 ok, 1 errors)"

    def test_empty_batch(self) -> None:
        br = BatchResult([])
        assert br.all() == []
        assert br.successes == []
        assert br.errors == []
        assert br.has_errors is False
        assert br.values() == []
        assert len(br) == 0
