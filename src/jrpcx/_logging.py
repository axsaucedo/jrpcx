"""Logging helpers for jrpcx event hooks."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from jrpcx._models import Response


def log_request(
    logger: logging.Logger,
    level: int = logging.DEBUG,
) -> Callable[..., None]:
    """Create a request hook that logs JSON-RPC method calls.

    Usage::

        client = jrpcx.Client(
            url,
            event_hooks={
                "request": [jrpcx.log_request(logging.getLogger("jrpcx"))],
            },
        )
    """

    def hook(method: str, params: Any) -> None:
        logger.log(level, "→ JSON-RPC request: %s(%s)", method, _summarize(params))

    return hook


def log_response(
    logger: logging.Logger,
    level: int = logging.DEBUG,
) -> Callable[..., None]:
    """Create a response hook that logs JSON-RPC responses.

    Usage::

        client = jrpcx.Client(
            url,
            event_hooks={
                "response": [jrpcx.log_response(logging.getLogger("jrpcx"))],
            },
        )
    """

    def hook(response: Response) -> None:
        if response.is_error and response.error is not None:
            logger.log(
                level,
                "← JSON-RPC error [%d]: %s",
                response.error.code,
                response.error.message,
            )
        else:
            logger.log(
                level,
                "← JSON-RPC result: %s",
                _summarize(response.result),
            )

    return hook


def _summarize(value: Any, max_length: int = 80) -> str:
    """Summarize a value for logging, truncating if too long."""
    text = repr(value)
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text
