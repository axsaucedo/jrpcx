"""Tests for retry middleware."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

import jrpcx
from jrpcx._exceptions import TransportError
from jrpcx._models import ErrorData, Request, Response
from jrpcx._transports._mock import AsyncMockTransport, MockTransport
from jrpcx.middleware import (
    ExponentialBackoff,
    FibonacciBackoff,
    FixedBackoff,
    async_retry,
    retry,
)

# --- Backoff strategy tests ---


class TestBackoffStrategies:
    def test_fixed_backoff(self) -> None:
        b = FixedBackoff(delay=2.0)
        assert b(0) == 2.0
        assert b(1) == 2.0
        assert b(5) == 2.0

    def test_exponential_backoff(self) -> None:
        b = ExponentialBackoff(base=1.0, multiplier=2.0, max_delay=10.0)
        assert b(0) == 1.0
        assert b(1) == 2.0
        assert b(2) == 4.0
        assert b(3) == 8.0
        assert b(4) == 10.0  # capped

    def test_exponential_backoff_defaults(self) -> None:
        b = ExponentialBackoff()
        assert b(0) == 0.5
        assert b(1) == 1.0
        assert b(2) == 2.0

    def test_fibonacci_backoff(self) -> None:
        b = FibonacciBackoff(base=1.0, max_delay=20.0)
        assert b(0) == 1.0
        assert b(1) == 1.0
        assert b(2) == 2.0
        assert b(3) == 3.0
        assert b(4) == 5.0
        assert b(5) == 8.0

    def test_fibonacci_backoff_capped(self) -> None:
        b = FibonacciBackoff(base=5.0, max_delay=30.0)
        assert b(0) == 5.0
        assert b(5) == 30.0  # 8 * 5 = 40, capped at 30


# --- Sync retry tests ---


class TestSyncRetry:
    @patch("jrpcx.middleware._retry.time.sleep")
    def test_retry_on_transport_error(self, mock_sleep: Any) -> None:
        attempts = 0

        def flaky_handler(req: Request) -> Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise TransportError("connection failed")
            return Response(id=req.id, result="ok")

        transport = MockTransport(flaky_handler)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            middleware=[retry(max_retries=3, backoff=FixedBackoff(0.1))],
        )
        result = client.echo("test")
        assert result == "ok"
        assert attempts == 3
        assert mock_sleep.call_count == 2
        client.close()

    @patch("jrpcx.middleware._retry.time.sleep")
    def test_retry_exhausted(self, mock_sleep: Any) -> None:
        def always_fail(req: Request) -> Response:
            raise TransportError("down")

        transport = MockTransport(always_fail)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            middleware=[retry(max_retries=2, backoff=FixedBackoff(0.01))],
        )
        with pytest.raises(TransportError, match="down"):
            client.echo("test")
        assert mock_sleep.call_count == 2
        client.close()

    @patch("jrpcx.middleware._retry.time.sleep")
    def test_retry_on_specific_error_codes(self, mock_sleep: Any) -> None:
        attempts = 0

        def error_then_ok(req: Request) -> Response:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                return Response(
                    id=req.id,
                    error=ErrorData(code=-32000, message="busy"),
                )
            return Response(id=req.id, result="done")

        transport = MockTransport(error_then_ok)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            middleware=[
                retry(
                    max_retries=3,
                    retry_codes={-32000},
                    backoff=FixedBackoff(0.01),
                )
            ],
        )
        result = client.echo("test")
        assert result == "done"
        assert attempts == 2
        client.close()

    def test_no_retry_on_non_retryable_error(self) -> None:
        attempts = 0

        def value_error(req: Request) -> Response:
            nonlocal attempts
            attempts += 1
            raise ValueError("bad")

        transport = MockTransport(value_error)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            middleware=[retry(max_retries=3)],
        )
        with pytest.raises(ValueError, match="bad"):
            client.echo("test")
        assert attempts == 1
        client.close()

    def test_successful_call_no_retry(self) -> None:
        def ok_handler(req: Request) -> Response:
            return Response(id=req.id, result="ok")

        transport = MockTransport(ok_handler)
        client = jrpcx.Client(
            "http://test",
            transport=transport,
            middleware=[retry(max_retries=3)],
        )
        result = client.echo("test")
        assert result == "ok"
        client.close()


# --- Async retry tests ---


class TestAsyncRetry:
    @pytest.mark.asyncio
    async def test_async_retry_on_transport_error(self) -> None:
        attempts = 0

        def flaky(req: Request) -> Response:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise TransportError("fail")
            return Response(id=req.id, result="ok")

        transport = AsyncMockTransport(flaky)
        client = jrpcx.AsyncClient(
            "http://test",
            transport=transport,
            middleware=[
                async_retry(max_retries=3, backoff=FixedBackoff(0.01))
            ],
        )
        result = await client.echo("test")
        assert result == "ok"
        assert attempts == 2
        await client.aclose()


# --- Integration test ---


class TestRetryIntegration:
    def test_retry_with_real_server(self, rpc_url: str) -> None:
        """Retry middleware should not interfere with successful calls."""
        with jrpcx.Client(
            rpc_url, middleware=[retry(max_retries=2)]
        ) as client:
            assert client.add(1, 2) == 3
            assert client.echo("hello") == ["hello"]
