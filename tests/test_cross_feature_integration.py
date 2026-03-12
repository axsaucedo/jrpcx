"""Cross-feature integration tests for Phase 2.

Tests interactions between batch, middleware, retry, notifications,
typed errors, result_type, and custom serialization.
"""

from __future__ import annotations

import decimal
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest

import jrpcx
from jrpcx._logging import log_request, log_response
from jrpcx._models import Request, Response
from jrpcx.middleware import ExponentialBackoff, FixedBackoff, async_retry, retry

# --- Helpers ---


@dataclass
class AddResult:
    """Typed result for add RPC."""

    value: int

    def __init__(self, raw: Any) -> None:
        self.value = int(raw)


class CustomError(jrpcx.ServerError):
    """Custom typed error for a user-defined code."""

    CODE = -1001


# --- Middleware + Real Server ---


class TestMiddlewareIntegration:
    def test_logging_middleware_with_real_server(
        self, rpc_url: str, caplog: Any
    ) -> None:
        logger = logging.getLogger("test.cross.log")
        with (
            caplog.at_level(logging.DEBUG, logger="test.cross.log"),
            jrpcx.Client(
                rpc_url,
                event_hooks={
                    "request": [log_request(logger)],
                    "response": [log_response(logger)],
                },
            ) as client,
        ):
            result = client.add(10, 20)
        assert result == 30
        assert len(caplog.records) >= 2

    def test_middleware_chain_ordering(self, rpc_url: str) -> None:
        order: list[str] = []

        def mw_a(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            order.append("a-before")
            resp = call_next(request)
            order.append("a-after")
            return resp

        def mw_b(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            order.append("b-before")
            resp = call_next(request)
            order.append("b-after")
            return resp

        with jrpcx.Client(rpc_url, middleware=[mw_a, mw_b]) as client:
            client.echo("test")

        assert order == ["a-before", "b-before", "b-after", "a-after"]

    def test_middleware_can_modify_response(self, rpc_url: str) -> None:
        def double_result(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            resp = call_next(request)
            if resp.result is not None and isinstance(resp.result, (int, float)):
                return Response(id=resp.id, result=resp.result * 2)
            return resp

        with jrpcx.Client(rpc_url, middleware=[double_result]) as client:
            result = client.add(3, 4)
        assert result == 14  # (3+4) * 2

    @pytest.mark.asyncio
    async def test_async_middleware_chain(self, rpc_url: str) -> None:
        order: list[str] = []

        async def async_mw(
            request: Request,
            call_next: Callable[[Request], Awaitable[Response]],
        ) -> Response:
            order.append("before")
            resp = await call_next(request)
            order.append("after")
            return resp

        async with jrpcx.AsyncClient(rpc_url, middleware=[async_mw]) as client:
            result = await client.add(5, 5)
        assert result == 10
        assert order == ["before", "after"]


# --- Retry + Real Server ---


class TestRetryIntegration:
    def test_retry_succeeds_first_try(self, rpc_url: str) -> None:
        call_count = 0

        def counting_mw(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            nonlocal call_count
            call_count += 1
            return call_next(request)

        with jrpcx.Client(
            rpc_url,
            middleware=[retry(max_retries=2, backoff=FixedBackoff(0)), counting_mw],
        ) as client:
            result = client.echo("ok")
        assert result == ["ok"]
        assert call_count == 1

    def test_retry_does_not_retry_json_rpc_errors_by_default(
        self, rpc_url: str
    ) -> None:
        call_count = 0

        def counting_mw(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            nonlocal call_count
            call_count += 1
            return call_next(request)

        with jrpcx.Client(
            rpc_url,
            middleware=[retry(max_retries=3, backoff=FixedBackoff(0)), counting_mw],
        ) as client, pytest.raises(jrpcx.MethodNotFoundError):
            client.error()
        # JSON-RPC method not found should NOT be retried by default
        assert call_count == 1

    def test_retry_with_retry_codes(self, rpc_url: str) -> None:
        call_count = 0

        def counting_mw(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            nonlocal call_count
            call_count += 1
            return call_next(request)

        with jrpcx.Client(
            rpc_url,
            middleware=[
                retry(max_retries=2, backoff=FixedBackoff(0), retry_codes=[-32601]),
                counting_mw,
            ],
        ) as client, pytest.raises(jrpcx.MethodNotFoundError):
            client.error()
        # Should retry 2 times + 1 initial = 3 total
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_succeeds(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(
            rpc_url,
            middleware=[async_retry(max_retries=2, backoff=FixedBackoff(0))],
        ) as client:
            result = await client.add(1, 2)
        assert result == 3


# --- Typed Errors ---


class TestTypedErrorIntegration:
    def test_custom_error_raised(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with pytest.raises(CustomError) as exc_info:
                client.custom_error()
            assert exc_info.value.code == -1001

    @pytest.mark.asyncio
    async def test_async_custom_error_raised(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(rpc_url) as client:
            with pytest.raises(CustomError):
                await client.custom_error()


# --- result_type ---


class TestResultTypeIntegration:
    def test_result_type_with_real_server(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            result = client.call("add", [3, 7], result_type=AddResult)
        assert isinstance(result, AddResult)
        assert result.value == 10

    def test_result_type_none_returns_raw(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            result = client.call("add", [3, 7])
        assert result == 10

    @pytest.mark.asyncio
    async def test_async_result_type(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(rpc_url) as client:
            result = await client.call("add", [5, 5], result_type=AddResult)
        assert isinstance(result, AddResult)
        assert result.value == 10


# --- Custom Serialization ---


class DecimalEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)


class TestSerializationIntegration:
    def test_decimal_serialization(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url, json_encoder=DecimalEncoder) as client:
            result = client.add(decimal.Decimal("1.5"), decimal.Decimal("2.5"))
        assert result == 4.0

    @pytest.mark.asyncio
    async def test_async_decimal_serialization(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(rpc_url, json_encoder=DecimalEncoder) as client:
            result = await client.add(decimal.Decimal("3.0"), decimal.Decimal("7.0"))
        assert result == 10.0


# --- Notification + Batch Combo ---


class TestNotificationBatchCombo:
    def test_notifications_in_batch(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.notify.echo("ignored")
                batch.add(1, 2)
                batch.notify.echo("also-ignored")
                batch.echo("kept")
            # Only non-notifications get responses
            assert len(batch.results) == 2
            assert batch.results[0].result == 3
            assert batch.results[1].result == ["kept"]

    def test_all_notifications_batch(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                batch.notify.echo("a")
                batch.notify.echo("b")
            assert len(batch.results) == 0

    @pytest.mark.asyncio
    async def test_async_notifications_in_batch(self, rpc_url: str) -> None:
        async with jrpcx.AsyncClient(rpc_url) as client:
            async with client.batch() as batch:
                batch.add(10, 20)
                batch.notify.echo("fire-and-forget")
            assert len(batch.results) == 1
            assert batch.results[0].result == 30


# --- Batch + Middleware ---


class TestBatchMiddleware:
    def test_batch_with_middleware(self, rpc_url: str) -> None:
        calls: list[str] = []

        def tracking_mw(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            calls.append(request.method)
            return call_next(request)

        with jrpcx.Client(rpc_url, middleware=[tracking_mw]) as client:
            # Regular call goes through middleware
            client.echo("test")
            assert len(calls) == 1

            # Batch sends as a single request, middleware won't see individual methods
            with client.batch() as batch:
                batch.add(1, 2)
                batch.echo("hello")

            # Batch goes through transport directly.
            # The important thing is it works correctly.
            assert len(batch.results) == 2
            assert batch.results[0].result == 3


# --- Edge Cases ---


class TestEdgeCases:
    def test_empty_batch_with_middleware(self, rpc_url: str) -> None:
        def noop_mw(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            return call_next(request)

        with jrpcx.Client(rpc_url, middleware=[noop_mw]) as client:
            with client.batch() as batch:
                pass
            assert len(batch.results) == 0

    def test_large_batch(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client:
            with client.batch() as batch:
                for i in range(50):
                    batch.add(i, i)
            assert len(batch.results) == 50
            for i, resp in enumerate(batch.results.all()):
                assert resp.result == i * 2

    def test_middleware_not_applied_to_notifications(self, rpc_url: str) -> None:
        """Notifications bypass middleware since they have no Response."""
        calls: list[str] = []

        def tracking_mw(
            request: Request,
            call_next: Callable[[Request], Response],
        ) -> Response:
            calls.append(request.method)
            return call_next(request)

        with jrpcx.Client(rpc_url, middleware=[tracking_mw]) as client:
            client.notify.echo("test")
        # Notifications bypass middleware chain (no response to process)
        assert calls == []

    def test_multiple_backoff_strategies(self) -> None:
        """Verify backoff strategy factories don't error on creation."""
        r1 = retry(max_retries=3, backoff=FixedBackoff(0.1))
        r2 = retry(max_retries=3, backoff=ExponentialBackoff(base=0.1))
        assert callable(r1)
        assert callable(r2)

    def test_result_type_with_error_still_raises(self, rpc_url: str) -> None:
        with jrpcx.Client(rpc_url) as client, pytest.raises(jrpcx.ServerError):
            client.call("error", result_type=AddResult)
