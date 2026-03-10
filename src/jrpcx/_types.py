"""Core type aliases and sentinels for jrpcx."""

from __future__ import annotations

from typing import Any

# JSON-RPC value types
JSONValue = str | int | float | bool | None | dict[str, Any] | list[Any]

# Method parameter types — positional (list) or named (dict)
JSONParams = dict[str, Any] | list[Any] | None

# Request ID — spec allows string or integer
RequestID = str | int

# Generic result type
MethodResult = Any


class _UseClientDefault:
    """Sentinel indicating a parameter should use the client's default value.

    Distinguishes 'not provided' from explicitly passing None.
    """

    _instance: _UseClientDefault | None = None

    def __new__(cls) -> _UseClientDefault:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "USE_CLIENT_DEFAULT"

    def __bool__(self) -> bool:
        return False


USE_CLIENT_DEFAULT = _UseClientDefault()
