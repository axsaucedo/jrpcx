"""Tests for batch request support."""

from __future__ import annotations

import json
from typing import Any

import pytest

import jrpcx
from jrpcx._batch import BatchResult
from jrpcx._exceptions import MethodNotFoundError
from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport


def _ok(rid: int, result: object) -> Response:
    return Response(id=rid, result=result)


def _err(rid: int, code: int = -32601, msg: str = "Not found") -> Response:
    return Response(id=rid, error=ErrorData(code=code, message=msg))


# --- BatchResult tests ---


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


# --- Mock transport for batch tests ---


class BatchMockTransport(MockTransport):
    """Mock transport that handles batch (JSON array) requests."""

    def __init__(self) -> None:
        self.raw_requests: list[Any] = []

        def handler(req: Request) -> Response:
            return Response(id=req.id, result="ok")

        super().__init__(handler)

    def handle_request(self, request: bytes) -> bytes:
        data = json.loads(request)
        self.raw_requests.append(data)
        if isinstance(data, list):
            responses = []
            for item in data:
                if item.get("id") is None:
                    continue
                method = item.get("method", "")
                params = item.get("params")
                if method == "add" and isinstance(params, list):
                    responses.append({
                        "jsonrpc": "2.0",
                        "result": params[0] + params[1],
                        "id": item["id"],
                    })
                elif method == "error":
                    responses.append({
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": "Not found"},
                        "id": item["id"],
                    })
                else:
                    responses.append({
                        "jsonrpc": "2.0",
                        "result": params,
                        "id": item["id"],
                    })
            return json.dumps(responses).encode()
        return super().handle_request(request)


class AsyncBatchMockTransport(AsyncMockTransport):
    """Async mock transport that handles batch requests."""

    def __init__(self) -> None:
        self.raw_requests: list[Any] = []

        def handler(req: Request) -> Response:
            return Response(id=req.id, result="ok")

        super().__init__(handler)

    async def handle_async_request(self, request: bytes) -> bytes:
        data = json.loads(request)
        self.raw_requests.append(data)
        if isinstance(data, list):
            responses = []
            for item in data:
                if item.get("id") is None:
                    continue
                method = item.get("method", "")
                params = item.get("params")
                if method == "add" and isinstance(params, list):
                    responses.append({
                        "jsonrpc": "2.0",
                        "result": params[0] + params[1],
                        "id": item["id"],
                    })
                elif method == "error":
                    responses.append({
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": "Not found"},
                        "id": item["id"],
                    })
                else:
                    responses.append({
                        "jsonrpc": "2.0",
                        "result": params,
                        "id": item["id"],
                    })
            return json.dumps(responses).encode()
        return await super().handle_async_request(request)


# --- Sync batch collector tests ---


class TestSyncBatch:
    def test_batch_proxy_dispatch(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch:
            batch.echo("hello")
            batch.add(1, 2)
        assert len(batch.results) == 2
        assert batch.results[0].result == ["hello"]
        assert batch.results[1].result == 3
        client.close()

    def test_batch_explicit_call(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch:
            id1 = batch.call("echo", ["hello"])
            id2 = batch.call("add", [10, 20])
        assert batch.results.by_id(id1) is not None
        assert batch.results.by_id(id1).result == ["hello"]  # type: ignore[union-attr]
        assert batch.results.by_id(id2).result == 30  # type: ignore[union-attr]
        client.close()

    def test_batch_nested_proxy(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch:
            batch.system.listMethods()
        raw = transport.raw_requests[0]
        assert raw[0]["method"] == "system.listMethods"
        client.close()

    def test_batch_with_notification(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch:
            batch.echo("hello")
            batch.notify.log("event")
        raw = transport.raw_requests[0]
        assert len(raw) == 2
        assert "id" in raw[0]
        assert "id" not in raw[1]
        assert len(batch.results) == 1
        client.close()

    def test_batch_returns_request_ids(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch:
            id1 = batch.echo("a")
            id2 = batch.echo("b")
        assert id1 != id2
        client.close()

    def test_batch_results_before_exit_raises(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        batch = client.batch()
        with pytest.raises(RuntimeError, match="not available yet"):
            batch.results  # noqa: B018
        client.close()

    def test_empty_batch(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch:
            pass
        assert len(batch.results) == 0
        client.close()

    def test_batch_with_errors(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch:
            batch.echo("ok")
            batch.error()
        assert batch.results.has_errors is True
        assert len(batch.results.successes) == 1
        assert len(batch.results.errors) == 1
        client.close()

    def test_batch_on_closed_client_raises(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        client.close()
        with pytest.raises(RuntimeError, match="Client has been closed"):
            client.batch()

    def test_batch_private_attr_raises(self) -> None:
        transport = BatchMockTransport()
        client = jrpcx.Client("http://test", transport=transport)
        with client.batch() as batch, pytest.raises(AttributeError):
            batch._private  # noqa: B018
        client.close()


# --- Async batch collector tests ---


class TestAsyncBatch:
    @pytest.mark.asyncio
    async def test_async_batch_proxy(self) -> None:
        transport = AsyncBatchMockTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        async with client.batch() as batch:
            batch.echo("hello")
            batch.add(1, 2)
        assert len(batch.results) == 2
        assert batch.results[1].result == 3
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_batch_explicit_call(self) -> None:
        transport = AsyncBatchMockTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        async with client.batch() as batch:
            id1 = batch.call("add", [5, 5])
        assert batch.results.by_id(id1).result == 10  # type: ignore[union-attr]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_batch_with_notification(self) -> None:
        transport = AsyncBatchMockTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        async with client.batch() as batch:
            batch.echo("test")
            batch.notify.log("event")
        raw = transport.raw_requests[0]
        assert len(raw) == 2
        assert "id" not in raw[1]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_async_empty_batch(self) -> None:
        transport = AsyncBatchMockTransport()
        client = jrpcx.AsyncClient("http://test", transport=transport)
        async with client.batch() as batch:
            pass
        assert len(batch.results) == 0
        await client.aclose()
