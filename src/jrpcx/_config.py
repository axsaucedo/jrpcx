"""Timeout configuration for jrpcx."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Timeout:
    """Timeout configuration with granular control.

    Accepts a simple float (applied to all timeouts) or individual values.
    """

    connect: float | None = None
    read: float | None = None
    write: float | None = None
    pool: float | None = None

    def __init__(
        self,
        timeout: float | None = None,
        *,
        connect: float | None = None,
        read: float | None = None,
        write: float | None = None,
        pool: float | None = None,
    ) -> None:
        # If a single float is given, apply it to all fields
        if timeout is not None:
            c = connect if connect is not None else timeout
            r = read if read is not None else timeout
            w = write if write is not None else timeout
            p = pool if pool is not None else timeout
            object.__setattr__(self, "connect", c)
            object.__setattr__(self, "read", r)
            object.__setattr__(self, "write", w)
            object.__setattr__(self, "pool", p)
        else:
            object.__setattr__(self, "connect", connect)
            object.__setattr__(self, "read", read)
            object.__setattr__(self, "write", write)
            object.__setattr__(self, "pool", pool)


# Timeout types — can be float shorthand or Timeout object
TimeoutTypes = float | Timeout | None
