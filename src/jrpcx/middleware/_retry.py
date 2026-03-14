"""Retry middleware with configurable backoff strategies."""

from __future__ import annotations

import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from jrpcx._exceptions import TransportError
from jrpcx._models import Request, Response

# Backoff strategy protocol: takes attempt number (0-based), returns seconds
BackoffStrategy = Callable[[int], float]


@dataclass(frozen=True, slots=True)
class FixedBackoff:
    """Fixed delay between retries."""

    delay: float = 1.0

    def __call__(self, attempt: int) -> float:
        return self.delay


@dataclass(frozen=True, slots=True)
class ExponentialBackoff:
    """Exponential backoff: base * (multiplier ** attempt), capped at max_delay."""

    base: float = 0.5
    multiplier: float = 2.0
    max_delay: float = 30.0

    def __call__(self, attempt: int) -> float:
        delay = self.base * (self.multiplier**attempt)
        return min(delay, self.max_delay)


@dataclass(frozen=True, slots=True)
class FibonacciBackoff:
    """Fibonacci backoff: delays follow fibonacci sequence scaled by base."""

    base: float = 1.0
    max_delay: float = 30.0

    def __call__(self, attempt: int) -> float:
        a, b = 0, 1
        for _ in range(attempt):
            a, b = b, a + b
        delay = self.base * b
        return min(delay, self.max_delay)


def _add_jitter(delay: float, jitter: float) -> float:
    """Add random jitter to a delay value."""
    if jitter <= 0:
        return delay
    return delay + random.uniform(0, jitter)


def retry(
    *,
    max_retries: int = 3,
    backoff: BackoffStrategy | None = None,
    jitter: float = 0.0,
    retry_on: tuple[type[Exception], ...] | None = None,
    retry_codes: set[int] | None = None,
) -> Any:
    """Create a retry middleware.

    Args:
        max_retries: Maximum number of retry attempts.
        backoff: Backoff strategy (default: ExponentialBackoff).
        jitter: Maximum random jitter in seconds to add to each delay.
        retry_on: Exception types to retry on (default: TransportError).
        retry_codes: JSON-RPC error codes to retry on. If a ServerError
            has one of these codes, it will be retried.

    Returns:
        A middleware function that retries failed requests.
    """
    if backoff is None:
        backoff = ExponentialBackoff()
    if retry_on is None:
        retry_on = (TransportError,)

    def sync_middleware(
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = call_next(request)
                # Check if response has an error code we should retry
                if (
                    retry_codes
                    and response.is_error
                    and response.error is not None
                    and response.error.code in retry_codes
                    and attempt < max_retries
                ):
                    delay = _add_jitter(backoff(attempt), jitter)
                    time.sleep(delay)
                    continue
                return response
            except Exception as exc:
                if isinstance(exc, retry_on) and attempt < max_retries:
                    last_exc = exc
                    delay = _add_jitter(backoff(attempt), jitter)
                    time.sleep(delay)
                    continue
                raise
        # Should not reach here, but just in case
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Retry exhausted without result")  # pragma: no cover

    return sync_middleware


def async_retry(
    *,
    max_retries: int = 3,
    backoff: BackoffStrategy | None = None,
    jitter: float = 0.0,
    retry_on: tuple[type[Exception], ...] | None = None,
    retry_codes: set[int] | None = None,
) -> Any:
    """Create an async retry middleware."""
    import asyncio

    if backoff is None:
        backoff = ExponentialBackoff()
    if retry_on is None:
        retry_on = (TransportError,)

    async def async_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = await call_next(request)
                if (
                    retry_codes
                    and response.is_error
                    and response.error is not None
                    and response.error.code in retry_codes
                    and attempt < max_retries
                ):
                    delay = _add_jitter(backoff(attempt), jitter)
                    await asyncio.sleep(delay)
                    continue
                return response
            except Exception as exc:
                if isinstance(exc, retry_on) and attempt < max_retries:
                    last_exc = exc
                    delay = _add_jitter(backoff(attempt), jitter)
                    await asyncio.sleep(delay)
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Retry exhausted without result")  # pragma: no cover

    return async_middleware
