"""ID generators for JSON-RPC request IDs."""

from __future__ import annotations

import uuid as _uuid
from collections.abc import Iterator
from secrets import token_hex
from typing import Any

from jrpcx._types import RequestID


def sequential(start: int = 1) -> Iterator[RequestID]:
    """Auto-incrementing integer IDs starting at the given value.

    Starts at 1 by default to avoid conflation with JSON null in some parsers.
    """
    current = start
    while True:
        yield current
        current += 1


def uuid4() -> Iterator[RequestID]:
    """Random UUID4 string IDs."""
    while True:
        yield str(_uuid.uuid4())


def random_id(length: int = 8) -> Iterator[RequestID]:
    """Random hex string IDs of the specified length."""
    while True:
        yield token_hex(length // 2 + length % 2)[:length]


# Default generator factory
def _default_id_generator() -> Iterator[RequestID]:
    """Create the default ID generator (sequential starting at 1)."""
    return sequential(1)


# Type for user-provided ID generator callables
IDGeneratorType = Iterator[RequestID] | Any
