"""Batch request support for jrpcx.

Provides BatchResult for handling batch responses, and BatchCollector /
AsyncBatchCollector context managers for building batch requests.
"""

from __future__ import annotations

from typing import Any

from jrpcx._models import Response
from jrpcx._types import RequestID


class BatchResult:
    """Rich container for batch JSON-RPC responses.

    Provides filtering, lookup, and error checking for batch results.
    """

    def __init__(self, responses: list[Response]) -> None:
        self._responses = responses
        self._by_id: dict[RequestID, Response] = {}
        for resp in responses:
            if resp.id is not None:
                self._by_id[resp.id] = resp

    def all(self) -> list[Response]:
        """Return all responses in order."""
        return list(self._responses)

    @property
    def successes(self) -> list[Response]:
        """Return only successful responses."""
        return [r for r in self._responses if r.is_success]

    @property
    def errors(self) -> list[Response]:
        """Return only error responses."""
        return [r for r in self._responses if r.is_error]

    @property
    def has_errors(self) -> bool:
        """Return True if any response is an error."""
        return any(r.is_error for r in self._responses)

    def by_id(self, request_id: RequestID) -> Response | None:
        """Look up a response by its request ID."""
        return self._by_id.get(request_id)

    def values(self) -> list[Any]:
        """Return result values from all responses.

        Raises the first error encountered as a ServerError.
        """
        results: list[Any] = []
        for resp in self._responses:
            resp.raise_for_error()
            results.append(resp.result)
        return results

    def __len__(self) -> int:
        return len(self._responses)

    def __iter__(self) -> Any:
        return iter(self._responses)

    def __getitem__(self, index: int) -> Response:
        return self._responses[index]

    def __repr__(self) -> str:
        ok = len(self.successes)
        err = len(self.errors)
        return f"BatchResult({ok} ok, {err} errors)"
