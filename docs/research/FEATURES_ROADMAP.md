# jrpcx — Features Roadmap

> **Document Type:** Feature roadmap and implementation plan
> **Project:** jrpcx — Modern Python JSON-RPC 2.0 client library
> **Status:** Active
>
> **Source Documents:**
> 1. [CODEBASE_LEARNINGS.md](./CODEBASE_LEARNINGS.md) — Cross-codebase synthesis and recommended architecture
> 2. [RESEARCH_SUMMARY.md](./RESEARCH_SUMMARY.md) — httpx architecture recommendations
> 3. [EXPLORATORY_RESEARCH.md](./EXPLORATORY_RESEARCH.md) — Initial research and selection criteria

---

## 1. Vision Statement

**jrpcx aims to be the "httpx for JSON-RPC"** — a modern, fully-typed, sync+async Python client that makes JSON-RPC 2.0 as easy as making HTTP requests with httpx.

The Python ecosystem currently lacks a JSON-RPC 2.0 client that combines httpx's ergonomic API design, full type safety, pluggable transports, and first-class testing support. Existing solutions are either minimal message builders that leave transport to the caller (jsonrpcclient), or full-featured frameworks that bundle client and server with heavyweight dependencies (pjrpc).

jrpcx fills this gap: a **client-only** library that feels natural to any Python developer who has used httpx, with the protocol correctness of jrpc2, the feature richness of pjrpc, and the simplicity of jsonrpcclient — all in a single, well-typed package targeting Python 3.12+.

```python
# The 80% use case — proxy-first, one line
client = jrpcx.Client("https://rpc.example.com")
result = client.eth_blockNumber()

# With parameters — positional or keyword
balance = client.eth_getBalance("0x...", "latest")

# Notifications
client.notify.log_event(level="info", msg="started")

# Async
async with jrpcx.AsyncClient("https://rpc.example.com", timeout=10.0) as client:
    block = await client.eth_blockNumber()
    balance = await client.eth_getBalance("0x...", "latest")

# Explicit call for dynamic/reserved method names
result = client.call("close", params)
```

> **API Design Update (from review discussions):**
> - **Proxy-first** is the default interface: `client.method()` via `__getattr__`
> - **`.call()` fallback** for reserved names and dynamic method strings
> - **Notifications** via `client.notify.method()` namespace
> - **Type returns**: Raw `Any` for Phase 0/1; `result_type=` as Phase 2 stretch
> - **Lifecycle**: Both context manager and explicit create/close patterns supported
> - **Batch**: Deferred to Phase 2

---

## 2. Design Goals (Prioritised)

| Priority | Goal | Rationale |
|----------|------|-----------|
| **1** | **Simple, intuitive API (httpx-inspired ergonomics)** | The 80% use case must be trivially easy. Correct usage is the easiest path — a "pit of success" API. Inspired by httpx's developer experience and ybbus/jsonrpc's ergonomic simplicity. |
| **2** | **Full JSON-RPC 2.0 spec compliance** | Every protocol feature (requests, responses, notifications, batches, error codes, params flexibility) must be correctly implemented per the [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification). No shortcuts. |
| **3** | **Sync and async support with minimal code duplication** | Both `JSONRPCClient` and `AsyncJSONRPCClient` from a shared `BaseJSONRPCClient`. All business logic (config, request building, response parsing, error handling) in the base class; only the I/O boundary differs. Proven by httpx and pjrpc. |
| **4** | **Pluggable transport layer (HTTP default, extensible)** | Transport abstraction is the single most universal pattern across all 6 analysed libraries. `BaseTransport` / `AsyncBaseTransport` interface enables HTTP, WebSocket, Unix socket, and mock transports behind a unified API. |
| **5** | **Testing-first design (MockTransport built-in)** | `MockTransport` ships as a first-class public API, not a test utility. Testing without a network must be trivial — a handler function receives a `Request` and returns a `Response`. Inspired by httpx's `MockTransport` and jrpc2's `channel.Direct()`. |
| **6** | **Comprehensive type safety (mypy --strict compatible)** | 100% type annotations on all public and private APIs. Comprehensive type aliases (`ParamsType`, `RequestID`, `TimeoutTypes`). `@overload` decorators where return types vary. PEP 561 `py.typed` marker. mypy strict mode enabled from day one. |
| **7** | **Zero or minimal required dependencies** | Core library is pure Python with no required dependencies. HTTP transport available via optional extras (`jrpcx[httpx]`). Development tools (pytest, mypy, ruff) are dev-only. |
| **8** | **Production-ready (connection pooling, timeouts, retries)** | Sensible defaults out of the box: 30-second timeout, connection pooling via httpx, sequential ID generation starting at 1. Override anything, but defaults should be production-safe. |

---

## 3. Phase 0: Foundation (MVP)

> **Goal:** The absolute minimum to be usable — make a sync or async JSON-RPC 2.0 call, get a typed result or error, and test it without a network.
>
> **Success Criteria:** Can make sync+async JSON-RPC calls with error handling; MockTransport tests pass; mypy --strict passes on all code.

### 3.1 Project Scaffolding

| Item | Detail |
|------|--------|
| **Build tool** | [uv](https://github.com/astral-sh/uv) for project management, dependency resolution, and virtual environments |
| **Project config** | `pyproject.toml` with metadata, dependencies, optional extras, tool configs (mypy, ruff, pytest) |
| **Source layout** | `src/jrpcx/` — src-layout per modern Python packaging best practices |
| **Python version** | 3.12+ — leverage modern type syntax (`X | Y` unions, `type` statements) |
| **PEP 561** | `py.typed` marker file for type checker discoverability |
| **CI** | GitHub Actions: lint (ruff), type check (mypy --strict), test (pytest), coverage |

```
jrpcx/
├── pyproject.toml
├── src/
│   └── jrpcx/
│       ├── __init__.py          # Public API exports
│       ├── _client.py           # BaseJSONRPCClient, JSONRPCClient, AsyncJSONRPCClient
│       ├── _models.py           # Request, Response
│       ├── _errors.py           # JSONRPCError, base exception
│       ├── _types.py            # Type aliases
│       ├── _config.py           # Timeout, USE_CLIENT_DEFAULT sentinel
│       ├── _transports/
│       │   ├── __init__.py      # BaseTransport, AsyncBaseTransport
│       │   ├── _http.py         # HTTPTransport, AsyncHTTPTransport
│       │   └── _mock.py         # MockTransport, AsyncMockTransport
│       └── py.typed             # PEP 561 marker
└── tests/
    ├── conftest.py
    ├── test_client.py
    ├── test_async_client.py
    ├── test_models.py
    ├── test_errors.py
    └── test_transports.py
```

### 3.2 Core Types Module (`_types.py`)

Define the foundational type aliases used throughout the library. Inspired by httpx's comprehensive type alias strategy and pjrpc's `JsonT` / `MaybeSet[T]` patterns.

```python
from typing import Any, Union

# JSON-RPC value types
JSONValue = Union[str, int, float, bool, None, dict[str, Any], list[Any]]

# Method parameter types — positional (list) or named (dict)
JSONParams = Union[dict[str, Any], list[Any], None]

# Request ID — spec allows string or integer
RequestID = Union[str, int]

# Generic result type (consider Generic[T] in future phases)
MethodResult = Any

# Timeout configuration
TimeoutTypes = Union[float, "Timeout", None]
```

**Key decisions:**
- `RequestID = Union[str, int]` — supports both string and integer IDs per spec (avoids ybbus's integer-only anti-pattern)
- `JSONParams` includes `None` — when `None`, the `params` key is omitted entirely from the request JSON (jsonrpcclient pattern)
- Start simple with `MethodResult = Any`; add generic `T` support in Phase 1

### 3.3 Request Model (`_models.py`)

Build JSON-RPC 2.0 request objects. Inspired by httpx's rich first-class request objects and pjrpc's clean dataclass models.

```python
@dataclass(frozen=True, slots=True)
class Request:
    method: str
    params: JSONParams = None
    id: RequestID | None = None  # None = notification

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-RPC 2.0 request dict.
        Omits 'params' key when params is None (jsonrpcclient pattern).
        Omits 'id' key for notifications.
        """
        ...

    def to_json(self) -> str:
        """Serialise to JSON string."""
        ...

    @property
    def is_notification(self) -> bool:
        """True if this is a notification (no id)."""
        ...
```

**Implementation notes:**
- Frozen dataclass for immutability (requests should not be mutated after creation)
- `to_dict()` always includes `"jsonrpc": "2.0"` — the version field is not user-configurable
- Conditional `params` omission: cleaner JSON when no params are provided
- Notification detection: `id is None` distinguishes notifications from regular requests

### 3.4 Response Model (`_models.py`)

Parse JSON-RPC 2.0 responses, extract result or error. Inspired by httpx's rich response objects with `raise_for_status()` and pjrpc's `UNSET` sentinel pattern.

```python
@dataclass(slots=True)
class Response:
    id: RequestID | None
    result: Any = UNSET           # UNSET sentinel, not None
    error: ErrorData | None = None
    elapsed: timedelta | None = None
    _http_response: Any = None    # Underlying HTTP response (if applicable)

    @property
    def is_success(self) -> bool:
        """True if the response contains a result (no error)."""
        ...

    @property
    def is_error(self) -> bool:
        """True if the response contains an error."""
        ...

    def raise_for_error(self) -> None:
        """Raise JSONRPCError if this response contains an error."""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Response":
        """Parse a JSON-RPC 2.0 response dict. Validates structure."""
        ...
```

**Key decisions:**
- `UNSET` sentinel (from pjrpc) distinguishes "result field absent" from "result is `null`" — important because `null` is a valid JSON-RPC result
- `raise_for_error()` follows httpx's `raise_for_status()` pattern — opt-in exception raising
- `elapsed` tracks request duration for metrics/debugging
- `_http_response` preserves the underlying transport response for advanced use cases

### 3.5 ID Generation (`_id_generators.py`)

Auto-incrementing (default), UUID, and custom ID generators. Instance-scoped per client to avoid the global singleton anti-pattern found in jsonrpcclient.

```python
def sequential(start: int = 1) -> Iterator[RequestID]:
    """Auto-incrementing integer IDs starting at 1.
    Starts at 1, not 0, to avoid JSON null equivalence (jrpc2 insight).
    """
    ...

def uuid4() -> Iterator[RequestID]:
    """Random UUID4 string IDs."""
    ...

def random_id(length: int = 8) -> Iterator[RequestID]:
    """Random hex string IDs of specified length."""
    ...
```

**Key decisions:**
- Sequential IDs start at 1, not 0 — avoids conflation with JSON `null` in some parsers (jrpc2 insight)
- Generators are instance-scoped (per-client), not module-level singletons — test isolation by default
- Any `Iterator[RequestID]` works as a custom generator — maximum flexibility

### 3.6 Base Transport Interface (`_transports/__init__.py`)

The transport interface defines the contract between the client and the network layer. Inspired by httpx's `BaseTransport` and jrpc2's minimal `Channel` interface.

```python
class BaseTransport:
    """Sync transport interface. Implement handle_request to create custom transports."""

    def handle_request(self, request: bytes) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "BaseTransport": ...
    def __exit__(self, *args: Any) -> None: ...


class AsyncBaseTransport:
    """Async transport interface."""

    async def handle_async_request(self, request: bytes) -> bytes:
        raise NotImplementedError

    async def aclose(self) -> None:
        pass

    async def __aenter__(self) -> "AsyncBaseTransport": ...
    async def __aexit__(self, *args: Any) -> None: ...
```

**Design rationale:**
- Transport operates on **bytes**, not domain objects — keeps the interface minimal and transport-agnostic
- `close()` / `aclose()` for resource cleanup (connections, pools)
- Context manager support for lifecycle management
- Separate sync/async interfaces (not dual-mode) — matches httpx's pattern and avoids runtime protocol detection

### 3.7 HTTP Transport (`_transports/_http.py`)

Default transport using httpx as the HTTP backend. Ships as an optional dependency via `jrpcx[httpx]`.

```python
class HTTPTransport(BaseTransport):
    """Sync HTTP transport using httpx."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        auth: tuple[str, str] | None = None,
    ) -> None: ...

    def handle_request(self, request: bytes) -> bytes:
        """POST JSON-RPC request to the configured URL."""
        ...

    def close(self) -> None:
        """Close the underlying httpx.Client and its connection pool."""
        ...


class AsyncHTTPTransport(AsyncBaseTransport):
    """Async HTTP transport using httpx.AsyncClient."""
    # Mirror of HTTPTransport with async I/O
    ...
```

**Implementation notes:**
- Uses `httpx.Client` / `httpx.AsyncClient` internally — inherits connection pooling, HTTP/2, keep-alive
- Sets `Content-Type: application/json` header by default
- Validates HTTP status codes — non-2xx raises `TransportError`
- Connection pooling enabled by default via httpx's pool management

### 3.8 Sync Client — Proxy-First (`_client.py`)

The primary user-facing API. **Proxy-first**: `client.method()` is the default interface via `__getattr__`. `.call()` is the fallback for dynamic/reserved names. `.notify` namespace for notifications.

```python
class JSONRPCClient(BaseJSONRPCClient):
    """Synchronous JSON-RPC 2.0 client. Proxy-first API."""

    def __getattr__(self, name: str) -> "_MethodProxy":
        """Proxy dispatch: client.method() → call("method")."""
        ...

    @property
    def notify(self) -> "_NotifyProxy":
        """Notification namespace: client.notify.method()."""
        ...

    def call(
        self,
        method: str,
        params: JSONParams = None,
        *,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
    ) -> Response:
        """Explicit call for dynamic or reserved method names."""
        ...

    def close(self) -> None: ...
    def __enter__(self) -> "JSONRPCClient": ...
    def __exit__(self, *args: Any) -> None: ...
```

**Usage:**
```python
# Proxy-first (default)
with jrpcx.Client("https://rpc.example.com") as client:
    result = client.eth_blockNumber()                # __getattr__ dispatch
    balance = client.eth_getBalance("0x...", "latest")
    client.notify.log_event(level="info")            # notification
    result = client.call("close", params)            # reserved name fallback

# Non-context-manager
client = jrpcx.Client("https://rpc.example.com")
client.eth_blockNumber()
client.close()
```

### 3.9 Async Client — Proxy-First (`_client.py`)

Mirrors the sync client with `async`/`await`. Shares all business logic via `BaseJSONRPCClient`. Same proxy-first API.

```python
class AsyncJSONRPCClient(BaseJSONRPCClient):
    """Asynchronous JSON-RPC 2.0 client. Proxy-first API."""

    def __getattr__(self, name: str) -> "_AsyncMethodProxy":
        """Proxy dispatch: await client.method()."""
        ...

    @property
    def notify(self) -> "_AsyncNotifyProxy":
        """Notification namespace: await client.notify.method()."""
        ...

    async def call(
        self,
        method: str,
        params: JSONParams = None,
        *,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
    ) -> Response: ...

    async def aclose(self) -> None: ...
    async def __aenter__(self) -> "AsyncJSONRPCClient": ...
    async def __aexit__(self, *args: Any) -> None: ...
```

**Usage:**
```python
async with jrpcx.AsyncClient("https://rpc.example.com") as client:
    result = await client.eth_blockNumber()
    client.notify.log_event(level="info")
```

### 3.10 Basic Error Handling (`_errors.py`)

The foundation of the error hierarchy. Every exception carries request/response context, following httpx's pattern.

```python
class JSONRPCError(Exception):
    """Base exception for all jrpcx errors.
    Always carries the original request and response context.
    """
    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        data: Any = None,
        request: Request | None = None,
        response: Response | None = None,
    ) -> None: ...

class TransportError(JSONRPCError):
    """Network or HTTP-level transport failure."""
    pass

class ProtocolError(JSONRPCError):
    """JSON-RPC protocol violation (malformed request/response)."""
    pass

class ServerError(JSONRPCError):
    """Server returned a JSON-RPC error response."""
    pass
```

**Phase 0 scope:** Three base exception classes. The full hierarchy (with specific error codes) comes in Phase 1.

### 3.11 MockTransport (`_transports/_mock.py`)

First-class testing support without network access. Ships as part of the public API.

```python
class MockTransport(BaseTransport):
    """Mock transport for testing. Handler receives a Request, returns a Response."""

    def __init__(self, handler: Callable[[Request], Response]) -> None: ...

    def handle_request(self, request: bytes) -> bytes:
        """Deserialise request, call handler, serialise response."""
        ...


class AsyncMockTransport(AsyncBaseTransport):
    """Async mock transport for testing."""

    def __init__(
        self,
        handler: Callable[[Request], Response] | Callable[[Request], Awaitable[Response]],
    ) -> None: ...
```

**Usage:**
```python
def handler(request: jrpcx.Request) -> jrpcx.Response:
    if request.method == "eth_blockNumber":
        return jrpcx.Response(id=request.id, result="0x10d4f")
    return jrpcx.Response(
        id=request.id,
        error=ErrorData(code=-32601, message="Method not found"),
    )

transport = jrpcx.MockTransport(handler)
client = jrpcx.Client("https://rpc.example.com", transport=transport)
assert client.call("eth_blockNumber").result == "0x10d4f"
```

### 3.12 Context Manager Support

Both clients support `with` / `async with` for resource lifecycle management. Follows httpx's `ClientState` enum pattern: `UNOPENED → OPENED → CLOSED`.

```python
# Sync
with jrpcx.Client("https://rpc.example.com") as client:
    result = client.call("method")
# Transport closed, connections released

# Async
async with jrpcx.AsyncClient("https://rpc.example.com") as client:
    result = await client.call("method")
# Transport closed, connections released
```

**Behaviour:**
- Calling methods on a closed client raises `RuntimeError`
- State transitions are enforced: UNOPENED → OPENED → CLOSED (no reopening)

---

## 4. Phase 1: Core Features (v0.1.0)

> **Goal:** Building on the foundation to deliver a feature-complete core library suitable for real-world use.
>
> **Success Criteria:** Proxy, hooks, client configuration all working with full test coverage; mypy --strict passes; comprehensive pytest suite with >90% coverage.
>
> **Note:** Batch requests and notifications moved to Phase 2 per design review.

### 4.1 Notification Support (Deferred to Phase 2)

Fire-and-forget requests with no response expected. Per the JSON-RPC 2.0 spec, notifications omit the `id` field and the server MUST NOT reply.

```python
# Proxy-first notification via .notify namespace
client.notify.log_event(level="info", message="User logged in")

# Async
await client.notify.log_event(level="info", message="User logged in")
```

**Implementation:**
- `client.notify` returns a `_NotifyProxy` that dispatches via `__getattr__`
- Builds a `Request` with `id=None`
- Transport sends the request but does not wait for or parse a response
- Returns `None` — there is no response to return

### 4.2 Batch Requests (Deferred to Phase 2)

Send multiple JSON-RPC requests in a single HTTP call. Two API styles inspired by pjrpc's batch design.

**Context manager API (primary — recommended for most users):**
```python
with client.batch() as batch:
    batch.call("eth_blockNumber")
    batch.call("eth_getBalance", ["0x...", "latest"])
    batch.notify("log_access")

# After exiting the context manager, all calls are sent as a single batch
responses = batch.responses

# Rich response helpers (inspired by ybbus)
responses.has_errors        # True if any response is an error
responses.successes         # List of successful responses
responses.errors            # List of error responses
responses.by_id(1)          # Lookup response by request ID
responses.results()         # List of result values (raises on first error)
responses.iter_responses()  # Iterate all responses (no raising)
```

**Direct API (advanced — for programmatic batch construction):**
```python
requests = [
    jrpcx.Request(method="eth_blockNumber", id=1),
    jrpcx.Request(method="eth_getBalance", params=["0x...", "latest"], id=2),
]
responses = client.send_batch(requests)
```

**Key decisions:**
- Context manager collects calls, sends on `__exit__` — natural Python pattern
- Response correlation by ID — responses may arrive in any order per spec
- Partial failure support: `iter_responses()` yields all; `results()` raises on first error (avoiding pjrpc's all-or-nothing anti-pattern)
- Notifications in batches produce no corresponding response — properly excluded from results

### 4.3 Full Exception Hierarchy

Complete error hierarchy mapping all JSON-RPC 2.0 error codes. Combines httpx's context-preserving exceptions with pjrpc's typed error deserialization.

```
JSONRPCError (base — carries request + response context)
├── TransportError (network/HTTP layer failures)
│   ├── TimeoutError (request timed out)
│   ├── ConnectionError (failed to connect)
│   └── HTTPStatusError (non-2xx HTTP status)
├── ProtocolError (JSON-RPC protocol violations)
│   ├── ParseError (-32700: server couldn't parse JSON)
│   ├── InvalidRequestError (-32600: not a valid JSON-RPC request)
│   └── InvalidResponseError (response doesn't conform to JSON-RPC 2.0)
└── ServerError (JSON-RPC error responses from the server)
    ├── MethodNotFoundError (-32601)
    ├── InvalidParamsError (-32602)
    ├── InternalError (-32603)
    └── ApplicationError (custom server error codes, -32000 to -32099)
```

**Every exception carries context:**
```python
try:
    response = client.call("nonexistent_method")
except jrpcx.MethodNotFoundError as exc:
    print(exc.code)       # -32601
    print(exc.message)    # "Method not found"
    print(exc.data)       # Optional server-provided detail
    print(exc.request)    # The Request that was sent
    print(exc.response)   # The Response that was received
```

**Error code constants (inspired by jrpc2 and jayson):**
```python
class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_MIN = -32099
    SERVER_ERROR_MAX = -32000
```

### 4.4 Proxy Pattern (Now the Default)

**Updated from design review:** The proxy pattern is now the **default** client interface, not a separate accessor. `client.method()` dispatches via `__getattr__`. `.call()` is the explicit fallback for reserved/dynamic names.

```python
with jrpcx.Client("https://rpc.example.com") as client:
    # Proxy-first (default):
    result = client.eth_blockNumber()                    # __getattr__ dispatch
    result = client.eth_getBalance("0x...", "latest")    # positional params

    # Nested namespaces:
    result = client.system.listMethods()                 # "system.listMethods"

    # Notifications via .notify namespace:
    client.notify.log_event(level="info")                # notification

    # Explicit call fallback for reserved names:
    result = client.call("close", params)                # can't use client.close()
```

**Implementation:**
- Client itself is the proxy via `__getattr__` — no separate `.proxy` accessor needed
- `__getattr__` returns a `_MethodProxy` callable
- `_MethodProxy.__call__` delegates to `client.call()`
- Reserved names (`call`, `notify`, `close`) protected from `__getattr__`
- Nested attribute access builds dotted method names (`system.listMethods`)
- Works with both sync and async clients

### 4.5 Client Configuration

Configuration management following httpx's `USE_CLIENT_DEFAULT` sentinel pattern. Client-level defaults with per-request overrides.

```python
client = jrpcx.Client(
    "https://rpc.example.com",
    headers={"Authorization": "Bearer token123"},
    timeout=10.0,
    auth=("user", "pass"),
)

# Per-request overrides
response = client.call("slow_method", timeout=60.0)   # Override timeout
response = client.call("fast_method")                  # Uses client default (10.0)
response = client.call("no_timeout", timeout=None)     # Explicitly disable timeout
```

**`USE_CLIENT_DEFAULT` sentinel:**
```python
class UseClientDefault:
    """Sentinel: use the value configured on the client."""
    pass

USE_CLIENT_DEFAULT = UseClientDefault()
```

This elegantly solves the "not provided vs explicitly `None`" problem: `timeout=USE_CLIENT_DEFAULT` means "use client default"; `timeout=None` means "no timeout"; `timeout=10.0` means "use 10 seconds".

### 4.6 Connection Pooling

Delegated to the underlying httpx transport. No custom pooling logic — httpx handles it well.

```python
# Connection reuse happens automatically within a context manager
with jrpcx.Client("https://rpc.example.com") as client:
    # All calls reuse the same connection pool
    for i in range(100):
        client.call("method", [i])
```

**Behaviour:**
- `Client` uses a single `httpx.Client` internally — connections are pooled by default
- Pool limits configurable via transport kwargs (max connections, max keepalive)
- Connections released on `close()` / context manager exit

### 4.7 Request/Response Event Hooks

Lightweight extensibility for cross-cutting concerns. Informational only — hooks observe but cannot abort or modify requests. Inspired by httpx's event hooks.

```python
def log_request(request: jrpcx.Request) -> None:
    print(f"→ {request.method}({request.params})")

def log_response(response: jrpcx.Response) -> None:
    print(f"← {response.result} ({response.elapsed})")

def track_errors(error: jrpcx.JSONRPCError) -> None:
    metrics.increment("rpc.errors", tags={"method": error.request.method})

client = jrpcx.Client(
    "https://rpc.example.com",
    event_hooks={
        "request": [log_request],
        "response": [log_response],
        "error": [track_errors],
    },
)
```

**Hook points:**
| Hook | Fires | Arguments | Use Cases |
|------|-------|-----------|-----------|
| `request` | Before sending | `Request` | Logging, metrics, debugging |
| `response` | After receiving | `Response` | Logging, metrics, latency tracking |
| `error` | On exception | `JSONRPCError` | Error alerting, metrics |

### 4.8 Comprehensive Type Annotations

Full mypy --strict compatibility from Phase 1 onwards. Every public and private API is annotated.

```python
# Type aliases for all complex parameter types
ParamsType = dict[str, Any] | list[Any] | None
RequestID = str | int
TimeoutTypes = float | Timeout | None
HeaderTypes = dict[str, str] | list[tuple[str, str]]
AuthTypes = tuple[str, str] | None

# @overload for return type precision
@overload
def send(self, request: Request) -> Response: ...
@overload
def send(self, request: BatchRequest) -> BatchResponse: ...
def send(self, request: Request | BatchRequest) -> Response | BatchResponse: ...

# Protocol for structural typing (IDGenerator, Transport)
class IDGenerator(Protocol):
    def __next__(self) -> RequestID: ...
    def __iter__(self) -> Iterator[RequestID]: ...
```

### 4.9 Basic Retry Support

Configurable retries on transport errors. Simple retry with fixed delay — advanced backoff strategies come in Phase 2.

```python
client = jrpcx.Client(
    "https://rpc.example.com",
    retries=3,           # Retry up to 3 times on TransportError
    retry_delay=1.0,     # Wait 1 second between retries
)
```

**Retry behaviour:**
- Only retries on `TransportError` (network failures, timeouts) — not on `ServerError` (the server responded, just with an error)
- Configurable max retries and fixed delay
- Respects per-request timeout (total time including retries must not exceed timeout)

### 4.10 Full Test Suite

Comprehensive pytest test suite with >90% coverage target.

```
tests/
├── conftest.py              # Shared fixtures, MockTransport helpers
├── test_client.py           # Sync client: call, close, context manager
├── test_async_client.py     # Async client: call, aclose, async context manager
├── test_models.py           # Request/Response: construction, serialization, parsing
├── test_batch.py            # Batch: context manager, direct, response helpers
├── test_errors.py           # Exception hierarchy, error code mapping, context preservation
├── test_transports.py       # Transport interface, HTTP transport, MockTransport
├── test_proxy.py            # Proxy pattern, nested namespaces
├── test_hooks.py            # Event hooks firing, ordering
├── test_id_generators.py    # Sequential, UUID, random, custom generators
├── test_config.py           # Configuration merging, USE_CLIENT_DEFAULT sentinel
└── test_notifications.py    # Fire-and-forget, batch notification handling
```

---

## 5. Phase 2: Production Features (v0.2.0)

> **Goal:** Making jrpcx production-deployable with batch requests, middleware, advanced retry, authentication, and observability.
>
> **Success Criteria:** Production deployable with batch, retry, middleware, auth, logging; all features tested; docs cover production deployment patterns.

### 5.0 Batch Requests & Notifications (Moved from Phase 1)

#### Notification Support

```python
client.notify.log_event(level="info", message="User logged in")
await client.notify.log_event(level="info", message="User logged in")
```

#### Batch Requests

Send multiple JSON-RPC requests in a single HTTP call. Two API styles inspired by pjrpc's batch design.

**Context manager API (primary — recommended for most users):**
```python
with client.batch() as batch:
    batch.call("eth_blockNumber")
    batch.call("eth_getBalance", ["0x...", "latest"])
    batch.notify.log_access()

responses = batch.responses
responses.has_errors        # True if any response is an error
responses.successes         # List of successful responses
responses.errors            # List of error responses
responses.by_id(1)          # Lookup response by request ID
responses.results()         # List of result values (raises on first error)
```

**Direct API (advanced — for programmatic batch construction):**
```python
requests = [
    jrpcx.Request(method="eth_blockNumber", id=1),
    jrpcx.Request(method="eth_getBalance", params=["0x...", "latest"], id=2),
]
responses = client.send_batch(requests)
```

### 5.1 Middleware Support

Full request/response interception chain for cross-cutting concerns. Inspired by pjrpc's middleware with **intuitive left-to-right ordering** (fixing pjrpc's counterintuitive reverse order).

```python
def logging_middleware(
    request: jrpcx.Request,
    handler: jrpcx.MiddlewareHandler,
) -> jrpcx.Response:
    print(f"→ {request.method}")
    response = handler(request)
    print(f"← {response.result}")
    return response

def auth_middleware(
    request: jrpcx.Request,
    handler: jrpcx.MiddlewareHandler,
) -> jrpcx.Response:
    # Inject auth header before sending
    request = request.with_meta(headers={"Authorization": "Bearer token"})
    return handler(request)

client = jrpcx.Client(
    "https://rpc.example.com",
    middlewares=[logging_middleware, auth_middleware],
    # Execution order: logging → auth → send → auth → logging
    # First registered wraps outermost — left-to-right ordering
)
```

**Middleware interface:**
```python
MiddlewareHandler = Callable[[Request], Response]
Middleware = Callable[[Request, MiddlewareHandler], Response]
```

**Capabilities:**
- Modify requests before sending (inject headers, transform params)
- Modify responses after receiving (transform results, inject metadata)
- Short-circuit the chain (return cached response, reject requests)
- Retry on failure (wrap `handler()` in a retry loop)
- Async middleware variant for `AsyncClient`

### 5.2 Typed Error Deserialization

Map JSON-RPC error codes to custom exception classes via auto-registration. Inspired by pjrpc's `TypedError.__init_subclass__` pattern.

```python
# Define custom error types — auto-registered by error code
class InsufficientFundsError(jrpcx.ServerError):
    CODE = -32001
    MESSAGE = "Insufficient funds"

class RateLimitedError(jrpcx.ServerError):
    CODE = -32002
    MESSAGE = "Rate limited"

# Now these exceptions are raised automatically
try:
    client.call("eth_sendTransaction", [tx])
except InsufficientFundsError as exc:
    print(f"Need more funds: {exc.data}")
except RateLimitedError:
    time.sleep(60)
    # retry...
```

**Implementation:**
- `TypedError.__init_subclass__` auto-registers each subclass in a global `{code: class}` registry
- When parsing a JSON-RPC error response, look up the error code in the registry
- If found, raise the registered exception class; otherwise, raise generic `ServerError`
- Registration is module-level — define your error classes once, catch them everywhere

### 5.3 Advanced Retry with Backoff Strategies

Production-grade retry middleware with multiple backoff algorithms. Inspired by pjrpc's retry middleware.

```python
from jrpcx.middleware import retry, ExponentialBackoff, FibonacciBackoff

# Exponential backoff with jitter
client = jrpcx.Client(
    "https://rpc.example.com",
    middlewares=[
        retry(
            max_retries=5,
            backoff=ExponentialBackoff(base=1.0, multiplier=2.0, max_delay=30.0),
            jitter=True,             # Add random jitter to prevent thundering herd
            retry_on=(TransportError, TimeoutError),  # Which errors to retry
            retry_codes=[-32603],    # Retry on specific JSON-RPC error codes
        ),
    ],
)
```

**Backoff strategies:**
| Strategy | Formula | Use Case |
|----------|---------|----------|
| `FixedBackoff(delay)` | `delay` | Simple, predictable retry intervals |
| `ExponentialBackoff(base, multiplier, max_delay)` | `min(base * multiplier^attempt, max_delay)` | Standard production retry |
| `FibonacciBackoff(max_delay)` | `fib(attempt)` capped at `max_delay` | Gentler initial ramp than exponential |
| Custom `Callable[[int], float]` | User-defined | Full control |

### 5.4 Request/Response Logging Hooks

Structured logging integration for debugging and observability.

```python
import logging

client = jrpcx.Client(
    "https://rpc.example.com",
    event_hooks={
        "request": [jrpcx.log_request(logging.getLogger("jrpcx"))],
        "response": [jrpcx.log_response(logging.getLogger("jrpcx"))],
    },
)
```

**Built-in logging helpers:**
- `log_request(logger, level=DEBUG)` — logs method, params (sanitised), request ID
- `log_response(logger, level=DEBUG)` — logs result summary, error (if any), elapsed time
- Sensitive parameter redaction via configurable sanitiser

### 5.5 Custom Serialization

Pluggable JSON encoder/decoder for custom types. Inspired by pjrpc and jayson's reviver/replacer pattern.

```python
import decimal
import json

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        return super().default(obj)

client = jrpcx.Client(
    "https://rpc.example.com",
    json_encoder=DecimalEncoder,
    json_decoder=None,  # Use default decoder
)
```

**Capabilities:**
- Custom `json.JSONEncoder` subclass for serialization
- Custom `json.JSONDecoder` subclass for deserialization
- `object_hook` function for response parsing (transform specific types)
- `use_decimal=True` option for precision-preserving number handling (ybbus insight)

### 5.6 Authentication Support

First-class authentication with multiple strategies. Inspired by httpx's auth patterns.

```python
# Basic auth
client = jrpcx.Client("https://rpc.example.com", auth=("user", "pass"))

# Bearer token
client = jrpcx.Client("https://rpc.example.com", auth=jrpcx.BearerAuth("token123"))

# Custom auth (e.g., API key in header)
client = jrpcx.Client(
    "https://rpc.example.com",
    auth=jrpcx.HeaderAuth({"X-API-Key": "secret"}),
)

# Custom auth callable
def my_auth(request: jrpcx.Request) -> jrpcx.Request:
    return request.with_meta(headers={"Authorization": compute_signature(request)})

client = jrpcx.Client("https://rpc.example.com", auth=my_auth)
```

### 5.7 Timeout Configuration

Granular timeout control inspired by httpx's `Timeout` object.

```python
# Simple: single timeout for everything
client = jrpcx.Client("https://rpc.example.com", timeout=10.0)

# Granular: separate connect, read, write, pool timeouts
client = jrpcx.Client(
    "https://rpc.example.com",
    timeout=jrpcx.Timeout(
        connect=5.0,
        read=30.0,
        write=10.0,
        pool=5.0,
    ),
)

# Disable timeout (not recommended for production)
client = jrpcx.Client("https://rpc.example.com", timeout=None)
```

### 5.8 Client Session Management

Keep-alive and connection reuse configuration.

```python
client = jrpcx.Client(
    "https://rpc.example.com",
    pool_limits=jrpcx.PoolLimits(
        max_connections=100,
        max_keepalive_connections=20,
    ),
    keepalive_expiry=30.0,  # Close idle connections after 30 seconds
)
```

---

## 6. Phase 3: Advanced Features (v1.0.0)

> **Goal:** The full-featured v1.0.0 release with stable API, advanced transports, and comprehensive tooling.
>
> **Success Criteria:** Feature-complete v1.0 with stable API surface, comprehensive documentation site, CLI tool, all transports working.

### 6.1 WebSocket Transport

Bidirectional JSON-RPC over WebSocket connections. Inspired by jayson's multi-transport architecture.

```python
# WebSocket transport (optional: jrpcx[websocket])
async with jrpcx.AsyncClient(
    "wss://rpc.example.com/ws",
    transport=jrpcx.WebSocketTransport(),
) as client:
    result = await client.call("subscribe", ["newHeads"])
```

**Capabilities:**
- Persistent bidirectional connection
- Concurrent in-flight requests with ID-based correlation
- Auto-reconnect with configurable backoff
- Server push / subscription support
- Available via optional extras: `pip install jrpcx[websocket]`

### 6.2 Server-Sent Events Transport

One-way streaming transport for subscription-based APIs.

```python
async with jrpcx.AsyncClient(
    "https://rpc.example.com/sse",
    transport=jrpcx.SSETransport(),
) as client:
    async for event in client.subscribe("newBlocks"):
        print(event.result)
```

### 6.3 Service Namespace Support

`Service.Method` notation for organized API surfaces. Inspired by jrpc2's service handler mapping.

```python
# Service-aware proxy
with jrpcx.Client("https://rpc.example.com") as client:
    # These are equivalent:
    client.call("Math.Add", [1, 2])
    client.service("Math").call("Add", [1, 2])
    client.proxy.Math.Add(1, 2)
```

**Implementation:**
- Proxy object supports nested attribute access, building dotted method names
- Optional `service_separator` config (default: `"."`) for servers using different separators
- Service namespaces are purely client-side sugar — the wire format is always `"Service.Method"`

### 6.4 Request ID Strategies

Full suite of pluggable ID generation strategies. Inspired by jsonrpcclient's 4 built-in generators and jrpc2's monotonic counter.

```python
import jrpcx

# Built-in strategies
client = jrpcx.Client(url, id_generator=jrpcx.id_generators.sequential(start=1))  # 1, 2, 3, ...
client = jrpcx.Client(url, id_generator=jrpcx.id_generators.uuid4())              # UUID strings
client = jrpcx.Client(url, id_generator=jrpcx.id_generators.random_hex(8))        # Random hex
client = jrpcx.Client(url, id_generator=jrpcx.id_generators.random_int())         # Random integers

# Custom: any Iterator[RequestID]
def custom_ids() -> Iterator[jrpcx.RequestID]:
    for i in itertools.count(1):
        yield f"req-{i:06d}"

client = jrpcx.Client(url, id_generator=custom_ids())
```

### 6.5 Response Streaming for Large Results

Streaming support for memory-efficient large response handling. Inspired by httpx's streaming response pattern.

```python
async with client.stream("get_large_dataset", params) as response:
    async for chunk in response.iter_bytes():
        process(chunk)
```

### 6.6 Metrics/Observability Hooks

Built-in hooks for production observability.

```python
client = jrpcx.Client(
    "https://rpc.example.com",
    event_hooks={
        "request": [jrpcx.hooks.track_inflight],
        "response": [jrpcx.hooks.record_latency],
        "error": [jrpcx.hooks.count_errors],
    },
)

# Access metrics
print(client.metrics.total_requests)
print(client.metrics.avg_latency)
print(client.metrics.error_rate)
```

### 6.7 OpenTelemetry Integration

Distributed tracing and metrics via OpenTelemetry. Available as optional extras: `pip install jrpcx[otel]`.

```python
from jrpcx.contrib.otel import OpenTelemetryMiddleware

client = jrpcx.Client(
    "https://rpc.example.com",
    middlewares=[OpenTelemetryMiddleware(tracer)],
)

# Each call creates a span:
# - span.name = "jrpcx.call eth_blockNumber"
# - span.attributes = {"rpc.method": "eth_blockNumber", "rpc.jsonrpc.version": "2.0"}
# - span.status = OK / ERROR
```

### 6.8 CLI Tool

Command-line tool for quick JSON-RPC calls, inspired by jrpc2's `jcall`. Available via `pip install jrpcx[cli]`.

```bash
# Simple call
$ jrpcx call https://rpc.example.com eth_blockNumber
"0x10d4f"

# With parameters
$ jrpcx call https://rpc.example.com eth_getBalance '["0x...", "latest"]'
"0x1234"

# Notification
$ jrpcx notify https://rpc.example.com log_event '{"level": "info"}'

# Batch
$ jrpcx batch https://rpc.example.com \
    'eth_blockNumber' \
    'eth_getBalance ["0x...", "latest"]'

# Pretty-printed output
$ jrpcx call --pretty https://rpc.example.com eth_getBlock '[1, true]'

# Custom headers
$ jrpcx call --header "Authorization: Bearer token" https://rpc.example.com method
```

---

## 7. Phase 4: Ecosystem (Post v1.0)

> **Goal:** Build community and ecosystem around jrpcx with plugins, additional transports, and integrations.
>
> **Success Criteria:** Active community contributions; pytest plugin published; additional transports available.

### 7.1 pytest Plugin (`pytest-jrpcx`)

Dedicated pytest plugin for testing JSON-RPC servers. Inspired by pjrpc's pytest integration.

```python
# conftest.py
@pytest.fixture
def jrpcx_mock():
    """Auto-configured MockTransport with assertion helpers."""
    ...

# test_my_app.py
def test_rpc_call(jrpcx_mock):
    jrpcx_mock.expect("eth_blockNumber").respond_with(result="0x10d4f")
    jrpcx_mock.expect("eth_getBalance").respond_with(
        error={"code": -32601, "message": "Method not found"}
    )

    client = jrpcx.Client("https://rpc.example.com", transport=jrpcx_mock.transport)
    assert client.call("eth_blockNumber").result == "0x10d4f"

    jrpcx_mock.assert_all_called()
    jrpcx_mock.assert_call_count("eth_blockNumber", 1)
```

### 7.2 ASGI/WSGI Test Transport

Test against FastAPI/Flask JSON-RPC servers without network. Inspired by httpx's ASGI/WSGI transport.

```python
from jrpcx.transports import ASGITransport, WSGITransport

# Test against a FastAPI app
transport = ASGITransport(app=fastapi_app, path="/jsonrpc")
client = jrpcx.AsyncClient("http://testserver", transport=transport)
result = await client.call("my_method", params)

# Test against a Flask app
transport = WSGITransport(app=flask_app, path="/jsonrpc")
client = jrpcx.Client("http://testserver", transport=transport)
result = client.call("my_method", params)
```

### 7.3 Additional Transports

Expand transport coverage for specialised use cases.

| Transport | Use Case | Optional Extras |
|-----------|----------|----------------|
| **TCP** | Raw TCP connections (e.g., LSP) | `jrpcx[tcp]` |
| **Unix Socket** | Local IPC communication | `jrpcx[unix]` |
| **IPC** | Inter-process communication (e.g., geth IPC) | `jrpcx[ipc]` |
| **stdio** | Stdin/stdout (e.g., LSP, MCP) | `jrpcx[stdio]` |

### 7.4 Connection Pooling with Load Balancing

Client-side load balancing across multiple JSON-RPC endpoints.

```python
client = jrpcx.Client(
    endpoints=[
        "https://rpc1.example.com",
        "https://rpc2.example.com",
        "https://rpc3.example.com",
    ],
    load_balancer=jrpcx.RoundRobin(),  # or: Random(), LeastConnections()
    health_check_interval=30.0,
)
```

### 7.5 Request Queuing and Rate Limiting

Client-side rate limiting to respect server limits.

```python
client = jrpcx.Client(
    "https://rpc.example.com",
    rate_limit=jrpcx.RateLimit(
        max_requests=100,
        period=60.0,       # 100 requests per minute
    ),
)
```

### 7.6 Documentation Site

Comprehensive documentation site built with MkDocs Material.

- **Getting Started**: Installation, first call, basic usage
- **User Guide**: Configuration, error handling, batching, notifications, proxy, testing
- **Advanced Guide**: Middleware, custom transports, retry strategies, authentication
- **API Reference**: Auto-generated from docstrings, fully typed
- **Cookbook**: Common patterns, real-world examples (Ethereum RPC, LSP, MCP)
- **Migration Guide**: From jsonrpcclient, from pjrpc, from raw httpx

---

## 8. Feature-to-Inspiration Matrix

Every feature traced back to its design inspiration. This ensures jrpcx learns from proven implementations rather than inventing from scratch.

| Feature | Phase | Inspired By | Notes |
|---------|-------|-------------|-------|
| Sync/Async class hierarchy | 0 | **httpx** (BaseClient pattern) | Three-tier: BaseJSONRPCClient → JSONRPCClient / AsyncJSONRPCClient. All business logic in base class. |
| Transport abstraction | 0 | **httpx** + **jrpc2** | httpx's `BaseTransport` interface + jrpc2's minimal `Channel` contract. Bytes in, bytes out. |
| MockTransport | 0 | **httpx** | Handler function receives `Request`, returns `Response`. First-class public API, not a test utility. |
| Rich Request/Response objects | 0 | **httpx** + **pjrpc** | Frozen dataclasses with methods (`.to_dict()`, `.raise_for_error()`). UNSET sentinel from pjrpc. |
| ID generation (sequential default) | 0 | **jsonrpcclient** + **jrpc2** | Start at 1, not 0 (jrpc2 insight). Instance-scoped, not global singletons. |
| Context manager lifecycle | 0 | **httpx** | `ClientState` enum: UNOPENED → OPENED → CLOSED. Prevents use-after-close. |
| `USE_CLIENT_DEFAULT` sentinel | 0 | **httpx** + **pjrpc** | Distinguishes "not provided" from "explicitly None". Critical for config merging. |
| Type aliases | 0 | **httpx** | `ParamsType`, `RequestID`, `TimeoutTypes`, `HeaderTypes` — accept multiple input types, normalise internally. |
| Params omission | 0 | **jsonrpcclient** | Omit `params` key entirely when `None` — cleaner JSON on the wire. |
| Notification support | 1 | **jsonrpcclient** + **pjrpc** | `client.notify("method", params)` — request without `id`, no response expected. |
| Batch via context manager | 1 | **pjrpc** | `with client.batch() as b: b.call(...)` — natural Python pattern. |
| Batch response helpers | 1 | **ybbus** + **jayson** | `.by_id()`, `.successes`, `.errors`, `.has_errors`, `.results()` / `.iter_responses()`. |
| Full exception hierarchy | 1 | **httpx** + **pjrpc** | Transport → Protocol → Server branches. Every exception carries request/response context. |
| Error code constants | 1 | **jrpc2** + **jayson** | `ErrorCode.PARSE_ERROR`, `ErrorCode.METHOD_NOT_FOUND`, etc. |
| Proxy pattern | 1 | **pjrpc** | `client.proxy.method_name()` via `__getattr__`. Nested for dotted methods. |
| Event hooks | 1 | **httpx** | `event_hooks={"request": [fn], "response": [fn]}` — informational, no interception. |
| Basic retry | 1 | **pjrpc** | Fixed delay retry on `TransportError`. Advanced backoff in Phase 2. |
| Typed error deserialization | 2 | **pjrpc** | `TypedError.__init_subclass__` auto-registers by error code. `except CustomError` just works. |
| Middleware chain | 2 | **pjrpc** (pattern) | Left-to-right ordering (fixing pjrpc's counterintuitive reverse order). Full interception. |
| Advanced retry/backoff | 2 | **pjrpc** | Exponential, Fibonacci, periodic backoff with jitter. Configurable retry conditions. |
| Custom JSON encoding | 2 | **pjrpc** + **jayson** | Pluggable `json_encoder` / `json_decoder`. Reviver/replacer pattern. |
| Authentication | 2 | **httpx** | Bearer, Basic, custom callable. Generator-based multi-step auth flow. |
| Granular timeouts | 2 | **httpx** | `Timeout(connect=5, read=30, write=10, pool=5)` — not just a single float. |
| ID strategies (full suite) | 3 | **jsonrpcclient** | Sequential, UUID, random hex, random int. Any `Iterator[RequestID]` for custom. |
| Service namespaces | 3 | **jrpc2** | `Service.Method` notation. Configurable separator. |
| WebSocket transport | 3 | **jayson** | Persistent bidirectional connection with ID-based correlation and auto-reconnect. |
| CLI tool | 3 | **jrpc2** (`jcall`) | `jrpcx call url method params` — quick command-line testing. |
| Response streaming | 3 | **httpx** | `client.stream()` for memory-efficient large responses. |
| OpenTelemetry integration | 3 | Original | Distributed tracing spans per JSON-RPC call. |
| pytest plugin | 4 | **pjrpc** | `pytest-jrpcx` with expect/assert helpers, auto-configured MockTransport. |
| ASGI/WSGI transport | 4 | **httpx** | Test against FastAPI/Flask servers without network. |
| Load balancing | 4 | Original | Client-side round-robin / random across multiple endpoints. |
| Rate limiting | 4 | Original | Client-side request throttling to respect server limits. |

---

## 9. Dependency Strategy

### Required Dependencies

**None.** The core `jrpcx` package is pure Python with zero required dependencies. The core types module, request/response models, error hierarchy, ID generators, and transport interfaces all use only the standard library.

### Optional Extras

Install only what you need:

| Extra | Dependency | Provides | Install |
|-------|-----------|----------|---------|
| `httpx` | [httpx](https://www.python-httpx.org/) | HTTP transport (sync + async) | `pip install jrpcx[httpx]` |
| `websocket` | [websockets](https://websockets.readthedocs.io/) | WebSocket transport | `pip install jrpcx[websocket]` |
| `cli` | [click](https://click.palletsprojects.com/) + [rich](https://rich.readthedocs.io/) | Command-line tool | `pip install jrpcx[cli]` |
| `otel` | [opentelemetry-api](https://opentelemetry.io/) | OpenTelemetry tracing | `pip install jrpcx[otel]` |
| `all` | All of the above | Everything | `pip install jrpcx[all]` |

### Development Dependencies

| Tool | Purpose |
|------|---------|
| [pytest](https://docs.pytest.org/) | Test framework |
| [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | Async test support |
| [mypy](https://mypy-lang.org/) | Static type checking (--strict) |
| [ruff](https://docs.astral.sh/ruff/) | Linting and formatting |
| [coverage](https://coverage.readthedocs.io/) | Code coverage (>90% target) |
| [uv](https://github.com/astral-sh/uv) | Project management, dependency resolution |

### pyproject.toml Structure

```toml
[project]
name = "jrpcx"
requires-python = ">=3.12"
dependencies = []  # Zero required dependencies

[project.optional-dependencies]
httpx = ["httpx>=0.27"]
websocket = ["websockets>=12.0"]
cli = ["click>=8.0", "rich>=13.0"]
otel = ["opentelemetry-api>=1.20"]
all = ["jrpcx[httpx,websocket,cli,otel]"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "mypy>=1.8", "ruff>=0.2", "coverage>=7.0"]
```

---

## 10. Non-Goals

Things jrpcx explicitly will **NOT** do. These boundaries keep the library focused and prevent scope creep.

| Non-Goal | Rationale |
|----------|-----------|
| **Server implementation** | jrpcx is a **client-only** library. Server-side JSON-RPC is a fundamentally different problem (routing, handler registration, middleware, framework integration). Libraries like pjrpc already serve this space. Keeping client-only means a smaller, simpler, better-tested codebase. |
| **JSON-RPC 1.0 support** | jrpcx targets JSON-RPC **2.0 only**. The 1.0 spec has different semantics (no `jsonrpc` field, different error format, no batching). Supporting both adds complexity and ambiguity with no meaningful benefit — 2.0 is the universal standard. |
| **REST/HTTP API support** | jrpcx speaks JSON-RPC protocol only. For general HTTP API calls, use httpx directly. jrpcx transports HTTP but doesn't expose HTTP semantics (status codes, redirects, cookies) as primary API concepts. |
| **Schema generation** | No OpenAPI or OpenRPC spec generation. This is a server-side concern. Clients discover APIs via documentation, not generated schemas. |
| **Parameter validation** | jrpcx does not validate method parameters against a schema. It serialises whatever the caller provides. Validation is the caller's responsibility — jrpcx trusts its users. |
| **Code generation** | No stub generation from OpenRPC specs or server introspection. If this is needed, a separate tool can generate typed client wrappers that use jrpcx under the hood. |
| **Backward compatibility below Python 3.12** | Modern type syntax, `slots=True` dataclasses, and other 3.12+ features are used throughout. No compatibility shims for older Python versions. |

---

## 11. Success Criteria

How we know each phase is "done" — concrete, measurable gates that must be met before advancing.

### Phase 0: Foundation (MVP)

| Criterion | Measurement |
|-----------|------------|
| **Sync calls work** | `JSONRPCClient.call("method", params)` returns a `Response` with correct `.result` |
| **Async calls work** | `AsyncJSONRPCClient.call("method", params)` returns a `Response` with correct `.result` |
| **Error handling works** | JSON-RPC error responses are parsed into `JSONRPCError` with code, message, data |
| **MockTransport tests pass** | Full test suite runs against `MockTransport` with zero network I/O |
| **Type safety** | `mypy --strict` passes on all source code with zero errors |
| **Context managers** | `with Client()` and `async with AsyncClient()` properly open and close transports |
| **Request format** | Serialised requests are valid JSON-RPC 2.0 (validated against spec) |
| **Response parsing** | All valid JSON-RPC 2.0 responses parse correctly; invalid responses raise `ProtocolError` |
| **ID generation** | Sequential IDs start at 1, increment correctly, are unique per client |

### Phase 1: Core Features (v0.1.0)

| Criterion | Measurement |
|-----------|------------|
| **Notifications** | `client.notify()` sends request without `id`; no response expected or parsed |
| **Batch requests** | Context manager API collects and sends batch; responses correlated by ID |
| **Batch partial failure** | Can iterate all responses even when some are errors |
| **Proxy pattern** | `client.proxy.method()` dispatches to `client.call("method")` |
| **Nested proxy** | `client.proxy.service.method()` sends `"service.method"` |
| **Exception hierarchy** | All standard JSON-RPC error codes mapped to specific exception classes |
| **Event hooks** | Hooks fire in order for request, response, and error events |
| **Test coverage** | >90% line coverage measured by `coverage` |
| **mypy --strict** | Zero errors on all source code |
| **Full test suite** | All tests pass (sync, async, batch, errors, proxy, hooks, ID generators) |

### Phase 2: Production Features (v0.2.0)

| Criterion | Measurement |
|-----------|------------|
| **Middleware** | Custom middleware can intercept, modify, and retry requests |
| **Middleware ordering** | Left-to-right execution (first registered = outermost) |
| **Typed errors** | Custom `TypedError` subclasses catch by error code automatically |
| **Retry with backoff** | Exponential backoff retries on configurable error conditions |
| **Authentication** | Bearer, Basic, and custom auth all work correctly |
| **Granular timeouts** | `Timeout(connect, read, write, pool)` respected by transport |
| **Custom serialization** | Custom JSON encoder/decoder used for request/response serialization |
| **Production load test** | Handles 1000+ concurrent requests without resource leaks |

### Phase 3: Advanced Features (v1.0.0)

| Criterion | Measurement |
|-----------|------------|
| **API stability** | Public API surface is frozen — no breaking changes post-v1.0 |
| **WebSocket transport** | Bidirectional JSON-RPC over WebSocket with concurrent requests |
| **Service namespaces** | `client.proxy.Service.Method()` sends `"Service.Method"` |
| **CLI tool** | `jrpcx call url method params` works from command line |
| **Documentation** | Complete docs site with getting started, user guide, API reference, cookbook |
| **ID strategies** | All 4+ built-in strategies work; custom `Iterator[RequestID]` accepted |
| **All tests pass** | Full suite (unit, integration, type check, lint) green in CI |

---

*This document serves as the implementation plan for jrpcx. Each phase builds on the previous one, and each feature is grounded in patterns proven across 6 production-grade libraries in Python, Go, and JavaScript. For the underlying research, see the [Research Index](./RESEARCH_INDEX.md).*
