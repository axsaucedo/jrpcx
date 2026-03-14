"""Middleware support for jrpcx.

Middleware intercepts JSON-RPC calls at the Request/Response level,
enabling cross-cutting concerns like retry, logging, auth, etc.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from jrpcx._models import Request, Response

# Sync middleware types
MiddlewareHandler = Callable[[Request], Response]
Middleware = Callable[[Request, MiddlewareHandler], Response]

# Async middleware types
AsyncMiddlewareHandler = Callable[[Request], Awaitable[Response]]
AsyncMiddleware = Callable[[Request, AsyncMiddlewareHandler], Awaitable[Response]]

# Union type for client constructor
AnyMiddleware = Middleware | AsyncMiddleware


def build_middleware_chain(
    middlewares: list[Middleware],
    inner: MiddlewareHandler,
) -> MiddlewareHandler:
    """Build a sync middleware chain wrapping the inner handler.

    Middlewares are applied left-to-right: the first middleware in the
    list is the outermost (called first, returns last).
    """
    handler = inner
    for mw in reversed(middlewares):
        handler = _wrap_sync(mw, handler)
    return handler


def build_async_middleware_chain(
    middlewares: list[AsyncMiddleware],
    inner: AsyncMiddlewareHandler,
) -> AsyncMiddlewareHandler:
    """Build an async middleware chain wrapping the inner handler."""
    handler = inner
    for mw in reversed(middlewares):
        handler = _wrap_async(mw, handler)
    return handler


def _wrap_sync(
    middleware: Middleware,
    next_handler: MiddlewareHandler,
) -> MiddlewareHandler:
    def wrapped(request: Request) -> Response:
        return middleware(request, next_handler)

    return wrapped


def _wrap_async(
    middleware: AsyncMiddleware,
    next_handler: AsyncMiddlewareHandler,
) -> AsyncMiddlewareHandler:
    async def wrapped(request: Request) -> Response:
        return await middleware(request, next_handler)

    return wrapped


__all__: list[str] = [
    "AnyMiddleware",
    "AsyncMiddleware",
    "AsyncMiddlewareHandler",
    "Middleware",
    "MiddlewareHandler",
    "build_async_middleware_chain",
    "build_middleware_chain",
]
