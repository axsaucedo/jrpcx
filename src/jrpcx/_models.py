"""JSON-RPC 2.0 request and response models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from jrpcx._exceptions import error_class_for_code
from jrpcx._types import JSONParams, RequestID

_JSONRPC_VERSION = "2.0"


class _Unset:
    """Sentinel distinguishing 'result absent' from 'result is null'."""

    _instance: _Unset | None = None

    def __new__(cls) -> _Unset:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()


@dataclass(frozen=True, slots=True)
class ErrorData:
    """Structured error data from a JSON-RPC error response."""

    code: int
    message: str
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErrorData:
        return cls(
            code=data["code"],
            message=data["message"],
            data=data.get("data"),
        )


@dataclass(frozen=True, slots=True)
class Request:
    """JSON-RPC 2.0 request object."""

    method: str
    params: JSONParams = None
    id: RequestID | None = None

    @property
    def is_notification(self) -> bool:
        return self.id is None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": _JSONRPC_VERSION, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        if self.id is not None:
            d["id"] = self.id
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass(slots=True)
class Response:
    """JSON-RPC 2.0 response object."""

    id: RequestID | None
    result: Any = field(default_factory=lambda: UNSET)
    error: ErrorData | None = None
    elapsed: timedelta | None = None

    @property
    def is_success(self) -> bool:
        return not isinstance(self.result, _Unset) and self.error is None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def raise_for_error(self) -> None:
        """Raise a ServerError if this response contains an error."""
        if self.error is None:
            return
        exc_class = error_class_for_code(self.error.code)
        raise exc_class(
            self.error.message,
            code=self.error.code,
            data=self.error.data,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Response:
        if "jsonrpc" not in data or data["jsonrpc"] != _JSONRPC_VERSION:
            from jrpcx._exceptions import InvalidResponseError

            raise InvalidResponseError(
                f"Invalid or missing jsonrpc version: {data.get('jsonrpc')}"
            )

        error_data = None
        if "error" in data:
            error_data = ErrorData.from_dict(data["error"])

        result: Any = UNSET
        if "result" in data:
            result = data["result"]

        return cls(
            id=data.get("id"),
            result=result,
            error=error_data,
        )
