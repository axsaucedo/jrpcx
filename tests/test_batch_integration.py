"""Integration tests for batch requests against real test server."""

from __future__ import annotations

import pytest

import jrpcx
from jrpcx._exceptions import MethodNotFoundError


class TestBatchIntegration:
    def test_batch_echo_and_add(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.echo("hello")
                batch.add(10, 20)
            assert len(batch.results) == 2
            assert batch.results[0].result == ["hello"]
            assert batch.results[1].result == 30

    def test_batch_with_error(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.echo("ok")
                batch.error()
            assert batch.results.has_errors is True
            assert len(batch.results.successes) == 1
            assert len(batch.results.errors) == 1

    def test_batch_values_raises_on_error(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.echo("ok")
                batch.error()
            with pytest.raises(MethodNotFoundError):
                batch.results.values()

    def test_batch_by_id(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                id1 = batch.call("add", [1, 2])
                id2 = batch.call("add", [3, 4])
            assert batch.results.by_id(id1) is not None
            assert batch.results.by_id(id1).result == 3  # type: ignore[union-attr]
            assert batch.results.by_id(id2).result == 7  # type: ignore[union-attr]

    def test_batch_with_notification(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.echo("hello")
                batch.notify.echo("notification")
            # Only the non-notification gets a response
            assert len(batch.results) == 1
            assert batch.results[0].result == ["hello"]

    def test_batch_with_kwargs(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.greet(name="Alice")
                batch.greet(name="Bob")
            assert batch.results[0].result == "Hello, Alice"
            assert batch.results[1].result == "Hello, Bob"

    def test_empty_batch(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                pass
            assert len(batch.results) == 0

    def test_batch_multiple_methods(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.echo("test")
                batch.add(1, 1)
                batch.greet(name="World")
                batch.no_params()
            assert len(batch.results) == 4
            assert batch.results[0].result == ["test"]
            assert batch.results[1].result == 2
            assert batch.results[2].result == "Hello, World"
            assert batch.results[3].result == "ok"


class TestAsyncBatchIntegration:
    @pytest.mark.asyncio
    async def test_async_batch_echo_and_add(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(rpc_url) as client:
            async with client.batch() as batch:
                batch.echo("hello")
                batch.add(5, 5)
            assert len(batch.results) == 2
            assert batch.results[1].result == 10

    @pytest.mark.asyncio
    async def test_async_batch_with_error(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(rpc_url) as client:
            async with client.batch() as batch:
                batch.echo("ok")
                batch.error()
            assert batch.results.has_errors is True

    @pytest.mark.asyncio
    async def test_async_batch_with_notification(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(rpc_url) as client:
            async with client.batch() as batch:
                batch.add(1, 2)
                batch.notify.log("test")
            assert len(batch.results) == 1
            assert batch.results[0].result == 3
