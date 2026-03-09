# jrpcx — Implementation Plan

> **Document Type:** Architecture Decision Record & Implementation Plan
> **Project:** jrpcx — Modern Python JSON-RPC 2.0 client library
> **Status:** Pending Review
>
> **Source Documents:**
> 1. [CODEBASE_LEARNINGS.md](./CODEBASE_LEARNINGS.md) — Cross-codebase synthesis
> 2. [FEATURES_ROADMAP.md](./FEATURES_ROADMAP.md) — Phased feature roadmap
> 3. [EXPLORATORY_RESEARCH.md](./EXPLORATORY_RESEARCH.md) — Initial research

---

## Overview

This document presents architectural decisions for jrpcx with **multiple options, pros/cons, and tradeoffs** for each decision area. Each section identifies the recommended approach with rationale. This plan covers Phase 0 (MVP) implementation.

---

## 1. Project Setup

### Decision 1.1: Project Layout

**Option A: Flat src layout** ⭐ Recommended

```
src/jrpcx/
├── __init__.py          # Public API exports
├── py.typed             # PEP 561 marker
├── _client.py           # BaseJSONRPCClient, JSONRPCClient, AsyncJSONRPCClient
├── _models.py           # Request, Response
├── _exceptions.py       # Exception hierarchy
├── _types.py            # Type aliases
├── _config.py           # Timeout, USE_CLIENT_DEFAULT sentinel
└── _transports/
    ├── __init__.py      # BaseTransport, AsyncBaseTransport
    ├── _http.py         # HTTPTransport, AsyncHTTPTransport
    └── _mock.py         # MockTransport
```

Pros:
- Simple, easy to navigate — everything in one package
- Matches httpx's layout (familiar to target users)
- Private modules with underscore prefix; public API via `__init__.py`
- Small codebase doesn't need deeper nesting yet

Cons:
- Could get crowded as features grow
- Less separation between concerns

**Option B: Nested package layout**

```
src/jrpcx/
├── __init__.py
├── client/
│   ├── __init__.py
│   ├── _base.py
│   ├── _sync.py
│   └── _async.py
├── models/
│   ├── __init__.py
│   ├── _request.py
│   └── _response.py
├── transports/
│   ├── __init__.py
│   ├── _base.py
│   ├── _http.py
│   └── _mock.py
├── _types.py
└── _exceptions.py
```

Pros:
- Clear separation of concerns
- Scales well as codebase grows
- Each directory is a logical unit

Cons:
- Over-engineering for a small library
- More files to navigate, more __init__.py boilerplate
- Deeper import paths internally

**Recommendation: Option A** — Flat layout is the right fit for an MVP with ~10 files. httpx uses this pattern. We can restructure later if the codebase outgrows it. YAGNI applies.

---

### Decision 1.2: Dependency Strategy

**Option A: httpx as required dependency**

Pros:
- Simplest install: `pip install jrpcx` works immediately
- No extras confusion for new users
- httpx is mature, well-maintained, widely used
- Connection pooling, HTTP/2, async — all for free

Cons:
- Forces httpx on all users (even if they use aiohttp)
- Tighter coupling — breaking httpx changes affect us
- Heavier install footprint (~15 packages transitively)

**Option B: httpx as optional extra** ⭐ Recommended

Users install: `pip install jrpcx[httpx]` or `pip install jrpcx[aiohttp]`

Pros:
- Core library is pure Python with zero dependencies
- Transport-agnostic design enforced at the packaging level
- Users choose their HTTP backend
- Lighter default install
- Matches pjrpc's backend pattern

Cons:
- Worse first-run experience (`pip install jrpcx` alone can't make HTTP calls)
- Need to handle ImportError gracefully with good error messages
- Documentation must explain extras clearly

**Option C: stdlib only (urllib + asyncio)**

Pros:
- Zero external dependencies
- Maximum compatibility
- Smallest install size

Cons:
- urllib lacks connection pooling, async support, HTTP/2
- Building a good async HTTP client on stdlib is enormous effort
- Essentially reinventing httpx — not our goal
- No production user would want this

**Recommendation: Option B** — Optional extras enforce clean transport abstraction at the architecture level. Good error messages when httpx isn't installed bridge the UX gap. We ship HTTPTransport as the default but users can swap it.

---

### Decision 1.3: Build System

**Option A: hatchling** ⭐ Recommended

Pros:
- Modern, fast, well-supported
- Good src-layout support
- Used by many modern Python projects
- uv has excellent hatchling integration

Cons:
- Less familiar than setuptools for some

**Option B: setuptools**

Pros:
- Universal familiarity
- Most documentation/examples use it

Cons:
- More verbose configuration
- Slower than hatchling
- Legacy baggage (setup.cfg, setup.py, etc.)

**Option C: flit**

Pros:
- Extremely simple for pure-Python packages
- Minimal configuration

Cons:
- Limited customisation options
- Less common in modern projects
- Can't handle complex build steps if needed later

**Recommendation: Option A (hatchling)** — Modern, fast, works well with uv. Clean pyproject.toml configuration.

---

## 2. Sync/Async Architecture

### Decision 2.1: Duality Pattern

**Option A: Class hierarchy (httpx pattern)** ⭐ Recommended

```python
class BaseJSONRPCClient:
    """Shared logic: config, request building, response parsing, error handling."""
    def _build_request(self, method: str, params: JSONParams) -> Request: ...
    def _parse_response(self, raw: bytes) -> Response: ...
    def _handle_error(self, response: Response) -> None: ...

class JSONRPCClient(BaseJSONRPCClient):
    """Sync client — only I/O methods differ."""
    def call(self, method: str, params: JSONParams = None) -> Any: ...
    def notify(self, method: str, params: JSONParams = None) -> None: ...
    def __enter__(self): ...
    def __exit__(self, ...): ...

class AsyncJSONRPCClient(BaseJSONRPCClient):
    """Async client — only I/O methods differ."""
    async def call(self, method: str, params: JSONParams = None) -> Any: ...
    async def notify(self, method: str, params: JSONParams = None) -> None: ...
    async def __aenter__(self): ...
    async def __aexit__(self, ...): ...
```

Pros:
- Proven pattern (httpx, pjrpc both use it)
- Minimal code duplication (~10% for I/O boundary methods)
- Clean type signatures — IDE/mypy know exactly what each client returns
- Easy to test — shared logic tested once via BaseClient
- Familiar to Python developers who use httpx
- No magic, no code generation — straightforward OOP

Cons:
- Some method signature duplication (sync call vs async call)
- Two classes to maintain (but shared logic means changes in one place)

**Option B: Code generation (unasync)**

```python
# Write async version only, auto-generate sync via unasync
class AsyncJSONRPCClient:
    async def call(self, ...) -> Any: ...

# Generated at build time:
class JSONRPCClient:
    def call(self, ...) -> Any: ...
```

Pros:
- Zero code duplication — write once, generate both
- Guarantees sync/async parity

Cons:
- Build-time complexity (must run unasync as build step)
- Generated code harder to debug
- IDE tooling may not understand generated files
- unasync handles simple cases but struggles with complex async patterns
- Adds a build dependency

**Option C: anyio-based unified client**

```python
class JSONRPCClient:
    def call(self, ...) -> Any:
        return anyio.from_thread.run(self._async_call, method, params)
    async def acall(self, ...) -> Any:
        return await self._async_call(method, params)
```

Pros:
- Single class serves both sync and async
- anyio abstracts over asyncio/trio

Cons:
- Runtime overhead for sync calls (event loop management)
- Surprising behaviour (sync call may start/stop event loop)
- anyio becomes a required dependency
- Thread-safety concerns with `from_thread.run`
- Less familiar pattern — confusing for users
- Type signatures are messier (same method, different behavior)

**Recommendation: Option A (class hierarchy)** — Battle-tested by httpx, clean type safety, no magic, no build dependencies. The small amount of I/O duplication is worth the clarity.

---

## 3. Transport Layer

### Decision 3.1: Transport Interface Design

**Option A: Abstract class with handle_request** ⭐ Recommended

```python
from abc import ABC, abstractmethod

class BaseTransport(ABC):
    @abstractmethod
    def handle_request(self, request: Request) -> Response: ...
    def close(self) -> None: ...

class AsyncBaseTransport(ABC):
    @abstractmethod
    async def handle_async_request(self, request: Request) -> Response: ...
    async def aclose(self) -> None: ...
```

Pros:
- Matches httpx's transport pattern (familiar)
- Abstract class enforces implementation of required methods
- Request/Response objects as parameters (rich, typed)
- Clear sync/async separation
- Easy to mock, easy to extend

Cons:
- ABC adds slight overhead vs Protocol
- Two separate base classes (sync + async)

**Option B: typing.Protocol (structural subtyping)**

```python
from typing import Protocol

class Transport(Protocol):
    def send(self, payload: bytes) -> bytes: ...
    def close(self) -> None: ...

class AsyncTransport(Protocol):
    async def send(self, payload: bytes) -> bytes: ...
    async def close(self) -> None: ...
```

Pros:
- Structural typing — anything with the right methods works
- No inheritance required
- More Pythonic for simple interfaces

Cons:
- Works with raw bytes, not rich Request/Response objects
- Less discoverable — users must know the Protocol exists
- No inheritance guidance (ABC tells you what to implement)
- Harder to provide default implementations (close() etc.)

**Option C: Callable-based (transport as function)**

```python
TransportHandler = Callable[[Request], Response]
AsyncTransportHandler = Callable[[Request], Awaitable[Response]]
```

Pros:
- Maximum simplicity — transport is just a function
- Trivial to create test transports (lambdas)
- No classes needed

Cons:
- No lifecycle management (open/close)
- Can't hold state (connection pools, sessions)
- Doesn't compose well for complex transports
- Harder to type properly

**Recommendation: Option A (abstract class)** — Provides the right balance of structure and flexibility. Request/Response objects as parameters enable rich transports. ABC guides implementers. Matches httpx pattern.

---

### Decision 3.2: Default HTTP Backend

**Option A: httpx** ⭐ Recommended

Pros:
- Modern, actively maintained, excellent async support
- Built-in connection pooling, HTTP/2, timeouts
- Clean API — easy to wrap
- Both sync (httpx.Client) and async (httpx.AsyncClient)
- Already the inspiration for jrpcx's design

Cons:
- Adds ~15 transitive dependencies
- httpx breaking changes could affect us (mitigated by version pinning)

**Option B: aiohttp (async) + requests (sync)**

Pros:
- Both are mature, widely used
- aiohttp has excellent async performance

Cons:
- Two different libraries to wrap and maintain
- Different APIs, different behaviour
- requests lacks HTTP/2, connection pooling requires sessions
- More code to maintain

**Option C: stdlib (urllib.request + asyncio)**

Pros:
- Zero dependencies

Cons:
- No async HTTP in stdlib
- No connection pooling
- No HTTP/2
- Enormous effort for minimal benefit

**Recommendation: Option A (httpx)** — httpx provides sync+async from a single library, excellent connection pooling, and is the design inspiration for jrpcx.

---

## 4. Request/Response Models

### Decision 4.1: Model Implementation

**Option A: dataclasses** ⭐ Recommended

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Request:
    method: str
    params: JSONParams = None
    id: RequestID | None = None

    def to_dict(self) -> dict[str, Any]: ...
    def to_json(self) -> str: ...
    @property
    def is_notification(self) -> bool: ...
```

Pros:
- Stdlib — zero dependencies
- Frozen for immutability (requests shouldn't mutate)
- Slots for memory efficiency
- Clean, explicit field definitions
- Easy to serialize, type-check, compare

Cons:
- No built-in validation (must validate manually)
- No automatic JSON serialization (need to_dict/to_json methods)

**Option B: Pydantic models**

```python
from pydantic import BaseModel

class Request(BaseModel):
    method: str
    params: JSONParams = None
    id: RequestID | None = None
    model_config = ConfigDict(frozen=True)
```

Pros:
- Automatic validation
- Built-in JSON serialization (.model_dump_json())
- Rich schema support

Cons:
- Adds pydantic as a required dependency (heavy: ~10MB)
- Overkill for simple request/response objects
- Validation overhead on every object creation
- Couples us to pydantic's API changes

**Option C: Custom classes (httpx style)**

```python
class Request:
    def __init__(self, method: str, params: JSONParams = None, id: RequestID | None = None):
        self._method = method
        self._params = params
        self._id = id
    @property
    def method(self) -> str: return self._method
    ...
```

Pros:
- Full control over implementation
- Can add lazy loading, caching, complex logic
- Matches httpx exactly

Cons:
- More boilerplate (properties, __repr__, __eq__, __hash__)
- Reinvents what dataclasses provide

**Option D: attrs**

Pros:
- Similar to dataclasses but with validators, converters
- Lightweight dependency
- Excellent immutability support

Cons:
- External dependency for marginal benefit over dataclasses
- Another API to learn

**Recommendation: Option A (dataclasses)** — Stdlib, zero deps, frozen+slots for correctness and performance. Simple enough for our needs. Can upgrade to custom classes later if we need lazy loading or complex behaviour.

---

### Decision 4.2: ID Generation Strategy

**Option A: Auto-incrementing integer (default)**

```python
class _IDGenerator:
    def __init__(self, start: int = 1):
        self._counter = itertools.count(start)
    def __call__(self) -> int:
        return next(self._counter)
```

Pros:
- Simple, deterministic, easy to debug
- Matches JSON-RPC convention
- No collisions within a client instance

Cons:
- Not globally unique across clients
- Predictable (security concern in some contexts)

**Option B: UUID**

```python
def uuid_id_generator() -> str:
    return str(uuid.uuid4())
```

Pros:
- Globally unique
- No collision risk across clients

Cons:
- Verbose (36 chars per ID in JSON)
- Non-deterministic (harder to test, debug)
- Overkill for most use cases

**Option C: Pluggable callable (user provides)** ⭐ Recommended

```python
class JSONRPCClient:
    def __init__(self, url: str, *, id_generator: Callable[[], RequestID] | None = None):
        self._id_generator = id_generator or _AutoIncrementID()
```

Pros:
- Auto-increment as default (simple, deterministic)
- User can swap to UUID, hex, random, or any custom strategy
- Inspired by jsonrpcclient's multiple ID strategies
- Maximum flexibility with sensible default

Cons:
- Slightly more complex API surface

**Recommendation: Option C (pluggable with auto-increment default)** — Sensible default plus user flexibility. Ship with built-in generators: `auto_increment_id` (default), `uuid_id`, `random_id`.

---

## 5. Error Handling

### Decision 5.1: Exception Hierarchy

**Option A: Flat hierarchy**

```python
class JSONRPCError(Exception): ...
class TransportError(JSONRPCError): ...
class ServerError(JSONRPCError): ...
```

Pros:
- Simple, few classes to learn
- Easy to catch broadly

Cons:
- Can't distinguish MethodNotFound from InvalidParams
- Users must inspect error codes manually
- Less Pythonic (Python favours specific exceptions)

**Option B: Deep hierarchy** ⭐ Recommended

```python
class JSONRPCError(Exception):
    """Base exception — all jrpcx errors inherit from this."""
    request: Request | None
    response: Response | None

class TransportError(JSONRPCError):
    """Network/HTTP layer failures."""

class TimeoutError(TransportError):
    """Request timed out."""

class ConnectionError(TransportError):
    """Failed to connect."""

class HTTPStatusError(TransportError):
    """Non-2xx HTTP status from server."""
    status_code: int

class ProtocolError(JSONRPCError):
    """JSON-RPC protocol violations."""

class InvalidResponseError(ProtocolError):
    """Response doesn't conform to JSON-RPC 2.0."""

class ServerError(JSONRPCError):
    """JSON-RPC error response from server."""
    code: int
    message: str
    data: Any

class ParseError(ServerError):
    """Server couldn't parse request JSON (-32700)."""

class InvalidRequestError(ServerError):
    """Request object is not valid JSON-RPC (-32600)."""

class MethodNotFoundError(ServerError):
    """Method does not exist (-32601)."""

class InvalidParamsError(ServerError):
    """Invalid method parameters (-32602)."""

class InternalError(ServerError):
    """Internal JSON-RPC error (-32603)."""

class ApplicationError(ServerError):
    """Application-defined error (custom codes)."""
```

Pros:
- Granular exception handling (`except MethodNotFoundError:`)
- Standard error codes mapped to exception classes
- Matches httpx's depth
- Pythonic — specific exceptions for specific conditions
- Users can catch broad (`except JSONRPCError:`) or narrow

Cons:
- More classes to maintain
- Users need to learn the hierarchy

**Option C: Code-based with dynamic registration (pjrpc style)**

```python
class ServerError(JSONRPCError):
    code: int
    message: str

# Users register their own:
@register_error(-32001)
class CustomAppError(ServerError): ...
```

Pros:
- Extensible — users define their own error classes
- Automatic deserialization from error codes

Cons:
- Magic registration pattern can be confusing
- Harder to discover available exceptions
- Can combine with Option B (register custom codes on top of standard hierarchy)

**Recommendation: Option B (deep hierarchy) + registration for custom codes** — Ship with standard JSON-RPC error codes pre-mapped. Allow users to register custom error codes → exception classes via a simple API. Best of both worlds.

---

### Decision 5.2: Error Context Preservation

**Option A: Always attach request + response**

Pros:
- Maximum debugging context
- Can always reconstruct what happened

Cons:
- Response may not exist (transport failure)
- Circular reference concerns

**Option B: Attach when available** ⭐ Recommended

```python
class JSONRPCError(Exception):
    def __init__(self, message: str, *, request: Request | None = None, response: Response | None = None):
        self.request = request
        self.response = response
```

Pros:
- Request always available (we built it)
- Response available when we got one (ServerError)
- Response is None for transport errors (correct — no response exists)
- No artificial data

Cons:
- Users must check for None

**Recommendation: Option B** — Attach what's available. Request is always set; response only when we received one.

---

## 6. Batch Operations

### Decision 6.1: Batch API Design

**Option A: Context manager (pjrpc style)**

```python
with client.batch() as batch:
    batch.call("method1", params1)
    batch.call("method2", params2)
results = batch.results  # access after context exits
```

Pros:
- Clean, Pythonic syntax
- Automatic send on context exit
- Familiar pattern (file handling, DB transactions)

Cons:
- Results not available inside the context
- Implicit send timing can be surprising
- Async version needs `async with`

**Option B: Explicit builder** ⭐ Recommended

```python
batch = client.batch()
batch.add("method1", params1)
batch.add("method2", params2)
results = batch.execute()  # sync
results = await batch.execute()  # async
```

Pros:
- Explicit send timing (no surprise)
- Results available immediately after execute()
- Can inspect batch before sending
- Works well with both sync and async

Cons:
- One more step (explicit execute)
- User might forget to call execute()

**Option C: List-based (functional style)**

```python
results = client.batch([
    ("method1", params1),
    ("method2", params2),
])
```

Pros:
- Simplest API — one method call
- Easy to construct programmatically

Cons:
- Less flexible (can't mix calls and notifications easily)
- Harder to add per-request options
- Tuple syntax not as readable

**Recommendation: Option B (explicit builder)** — Clear control flow, explicit timing, works well with sync/async. Also provide Option C as a convenience shorthand for simple cases.

---

## 7. Configuration

### Decision 7.1: Timeout Model

**Option A: Single float**

```python
client = JSONRPCClient(url, timeout=30.0)
```

Pros:
- Dead simple
- Covers 95% of use cases

Cons:
- Can't distinguish connect vs read timeouts
- Power users want granularity

**Option B: Timeout object (httpx style)** ⭐ Recommended

```python
from jrpcx import Timeout

client = JSONRPCClient(url, timeout=Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0))
# OR simple shorthand:
client = JSONRPCClient(url, timeout=30.0)  # sets all to 30s
```

Pros:
- Simple case is still simple (single float)
- Power users get granularity
- httpx-compatible concept

Cons:
- More types to define
- Slightly more complex implementation

**Option C: Transport-delegated**

Pros:
- Separation of concerns — transport manages timeouts

Cons:
- Client can't provide per-request timeout overrides
- Less control for users

**Recommendation: Option B** — Accept both `float` and `Timeout` object. Single float covers 95% of cases; Timeout object for fine-grained control.

---

### Decision 7.2: Default Override Pattern

**Option A: USE_CLIENT_DEFAULT sentinel (httpx pattern)** ⭐ Recommended

```python
_USE_CLIENT_DEFAULT = object()

class JSONRPCClient:
    def call(self, method, *, timeout=_USE_CLIENT_DEFAULT):
        if timeout is _USE_CLIENT_DEFAULT:
            timeout = self._timeout  # use client default
        elif timeout is None:
            timeout = None  # explicitly no timeout
        # else: use the provided value
```

Pros:
- Cleanly distinguishes "not provided" from "explicitly None"
- `None` means "no timeout" (not "use default")
- httpx-proven pattern
- Type-safe

Cons:
- Non-obvious pattern for newcomers
- Extra sentinel type in public API

**Option B: None means use default**

```python
def call(self, method, *, timeout=None):
    timeout = timeout if timeout is not None else self._timeout
```

Pros:
- Simple, familiar
- No sentinel type

Cons:
- Can't express "explicitly disable timeout" (None is overloaded)
- Ambiguous: does `timeout=None` mean "use default" or "no timeout"?

**Recommendation: Option A** — The sentinel pattern eliminates ambiguity. Worth the slight complexity.

---

## 8. Testing Strategy

### Decision 8.1: Test Infrastructure

**Option A: MockTransport only** ⭐ Recommended for Phase 0

```python
def handler(request: Request) -> Response:
    if request.method == "add":
        a, b = request.params
        return Response(result=a + b, id=request.id)
    return Response(error={"code": -32601, "message": "Not found"}, id=request.id)

transport = MockTransport(handler)
client = JSONRPCClient("https://example.com", transport=transport)
result = client.call("add", [1, 2])
assert result == 3
```

Pros:
- Zero network dependency
- Fast (no I/O)
- Deterministic
- Covers all client logic
- Users can use same pattern in their tests

Cons:
- Doesn't test real HTTP integration

**Option B: MockTransport + recording transport**

Pros:
- Record real responses, replay in tests
- Good for integration test development

Cons:
- Complexity for Phase 0
- File management for recorded responses

**Option C: MockTransport + in-process test server**

Pros:
- Tests real HTTP stack end-to-end
- Catches transport bugs

Cons:
- Slower tests
- More infrastructure
- Overkill for Phase 0

**Recommendation: Option A for Phase 0** — MockTransport covers all client logic testing. Add integration tests with a real server in Phase 1.

---

## 9. Type Safety

### Decision 9.1: Result Type Handling

**Option A: Generic Response[T]**

```python
from typing import Generic, TypeVar
T = TypeVar('T')

class Response(Generic[T]):
    result: T | None
    ...

response: Response[int] = client.call("add", [1, 2], result_type=int)
```

Pros:
- Full type safety end-to-end
- IDE autocompletion on results

Cons:
- Complex implementation (runtime type coercion)
- Generics on dataclasses are tricky
- result_type parameter adds noise to every call

**Option B: Explicit unmarshaling** ⭐ Recommended

```python
response = client.call("getUser", {"id": 1})  # returns Any
user = response.result_as(UserData)  # typed extraction
# OR for simple cases:
result = client.call("add", [1, 2])  # returns Any, user casts
```

Pros:
- Simple default (returns Any)
- Opt-in type narrowing via result_as()
- No generics complexity on Response class
- Users can use TypedDict, dataclass, or Pydantic for their types

Cons:
- Requires explicit step for typed results
- result_as() needs a deserialization strategy

**Option C: Raw Any/dict**

```python
result = client.call("add", [1, 2])  # returns Any
```

Pros:
- Simplest possible API
- No type gymnastics

Cons:
- No type safety on results
- User must cast manually

**Recommendation: Option B** — Start with raw Any returns (simple), add `result_as(Type)` for typed extraction. Consider Generic[T] for a future phase when the pattern is proven.

---

## 10. Phase 0: Step-by-Step Implementation Order

### Step 1: Project Scaffolding

**Files:** `pyproject.toml`, `src/jrpcx/__init__.py`, `src/jrpcx/py.typed`, `tests/conftest.py`

- Configure pyproject.toml with hatchling build backend
- Set Python >=3.12
- Add dev dependencies: pytest, pytest-asyncio, mypy, ruff, coverage
- Add optional extras: `httpx = ["httpx>=0.27"]`
- Create empty package structure
- Configure mypy strict mode, ruff rules, pytest settings in pyproject.toml

### Step 2: Types Module

**Files:** `src/jrpcx/_types.py`

- Define: `JSONValue`, `JSONParams`, `RequestID`, `MethodResult`, `TimeoutTypes`
- Define: `USE_CLIENT_DEFAULT` sentinel
- Define: `IDGenerator = Callable[[], RequestID]`
- **Tests:** Type alias smoke tests (mypy reveals on these)

### Step 3: Exception Hierarchy

**Files:** `src/jrpcx/_exceptions.py`, `tests/test_exceptions.py`

- Implement full hierarchy per Decision 5.1 Option B
- Each exception carries optional `request` and `response` context
- `ServerError` subclasses map to standard JSON-RPC codes
- Helper: `_error_code_to_exception(code: int) -> type[ServerError]`
- **Tests:** Creation, inheritance, code mapping, string representation

### Step 4: Request/Response Models

**Files:** `src/jrpcx/_models.py`, `tests/test_models.py`

- `Request`: frozen dataclass with `to_dict()`, `to_json()`, `is_notification`
- `Response`: dataclass with `result`, `error`, `id`, `raise_for_error()`
- `BatchRequest`: list of Request objects with `to_json()`
- `BatchResponse`: list of Response objects with iteration, `by_id()`, `has_errors`
- ID generators: `auto_increment_id()`, `uuid_id()`, `random_id()`
- **Tests:** Serialization, deserialization, notification detection, batch handling

### Step 5: Configuration

**Files:** `src/jrpcx/_config.py`, `tests/test_config.py`

- `Timeout` dataclass (connect, read, write, pool — all optional floats)
- Constructor accepts `float | Timeout | None` and normalises
- **Tests:** Timeout creation from float, from Timeout, None handling

### Step 6: Transport Interface + MockTransport

**Files:** `src/jrpcx/_transports/__init__.py`, `src/jrpcx/_transports/_mock.py`, `tests/test_transports.py`

- `BaseTransport` ABC with `handle_request(Request) -> Response`, `close()`
- `AsyncBaseTransport` ABC with `handle_async_request(Request) -> Response`, `aclose()`
- `MockTransport(handler)` — handler is `Callable[[Request], Response]`
- `AsyncMockTransport(handler)` — async variant
- **Tests:** Mock transport with various handlers, error responses, notifications

### Step 7: Base Client

**Files:** `src/jrpcx/_client.py`

- `BaseJSONRPCClient.__init__(url, *, transport, timeout, headers, id_generator, event_hooks)`
- `_build_request(method, params, id) -> Request`
- `_build_notification(method, params) -> Request`
- `_parse_response(raw_data: dict) -> Response`
- `_handle_response(response: Response) -> Any` — raises on error, returns result
- Depends on: Steps 2-6

### Step 8: Sync Client

**Files:** `src/jrpcx/_client.py` (extend), `tests/test_client.py`

- `JSONRPCClient(BaseJSONRPCClient)` with sync transport
- `call(method, params, *, timeout) -> Any`
- `notify(method, params) -> None`
- `send(request: Request) -> Response`
- `__enter__` / `__exit__` for context manager
- **Tests:** Full test suite with MockTransport — call, notify, errors, timeouts, context manager

### Step 9: Async Client

**Files:** `src/jrpcx/_client.py` (extend), `tests/test_async_client.py`

- `AsyncJSONRPCClient(BaseJSONRPCClient)` with async transport
- `async call(method, params, *, timeout) -> Any`
- `async notify(method, params) -> None`
- `async send(request: Request) -> Response`
- `__aenter__` / `__aexit__`
- **Tests:** Async test suite with AsyncMockTransport

### Step 10: HTTP Transport

**Files:** `src/jrpcx/_transports/_http.py`, `tests/test_http_transport.py`

- `HTTPTransport(httpx.Client)` — wraps httpx for sync HTTP
- `AsyncHTTPTransport(httpx.AsyncClient)` — wraps httpx for async HTTP
- Handles: Content-Type headers, JSON serialization, HTTP error mapping
- Connection pooling via httpx's built-in pool
- Graceful ImportError if httpx not installed
- **Tests:** With MockTransport (unit), optionally with httpbin-like server (integration)

### Step 11: Public API + Convenience Functions

**Files:** `src/jrpcx/__init__.py`

- Export all public symbols
- Convenience functions:
  - `jrpcx.call(url, method, params)` — one-shot sync call
  - `jrpcx.async_call(url, method, params)` — one-shot async call
- Version: `__version__ = "0.1.0"`
- **Tests:** Import smoke tests, convenience function tests

---

## 11. Recommendations Summary

| # | Decision | Recommended | Key Rationale |
|---|----------|-------------|---------------|
| 1.1 | Project layout | Flat src layout | Simple, matches httpx, right for MVP size |
| 1.2 | Dependencies | httpx as optional extra | Enforces transport abstraction, lighter core |
| 1.3 | Build system | hatchling | Modern, fast, great uv integration |
| 2.1 | Sync/async | Class hierarchy | Proven by httpx+pjrpc, clean types, no magic |
| 3.1 | Transport interface | Abstract class | Rich Request/Response params, ABC guidance |
| 3.2 | HTTP backend | httpx | Best sync+async, pooling, HTTP/2 |
| 4.1 | Models | Dataclasses | Stdlib, frozen+slots, zero deps |
| 4.2 | ID generation | Pluggable with auto-increment default | Flexibility + sensible default |
| 5.1 | Exceptions | Deep hierarchy + registration | Granular catching, extensible custom codes |
| 5.2 | Error context | Attach when available | Request always; response when we have one |
| 6.1 | Batch API | Explicit builder + list shorthand | Clear control flow, works sync+async |
| 7.1 | Timeouts | Timeout object (accepts float) | Simple default, granular when needed |
| 7.2 | Defaults | USE_CLIENT_DEFAULT sentinel | Eliminates None ambiguity |
| 8.1 | Testing | MockTransport | Zero network, fast, deterministic |
| 9.1 | Result types | Explicit unmarshaling (result_as) | Simple default, opt-in type safety |

---

## 12. Open Questions

1. **Package name availability:** Is `jrpcx` available on PyPI? If not, alternatives: `jsonrpcx`, `pyrpcx`, `rpcx`
2. **JSON-RPC 1.0 support:** Explicitly excluded per roadmap, but should we allow extension points for it?
3. **Notification responses:** The spec says notifications get no response. Should we validate this or silently ignore unexpected responses?
4. **Batch error semantics:** When some requests in a batch succeed and others fail, should we raise or return all results? (Recommendation: return all, let user iterate)
5. **httpx version pinning:** Minimum httpx version? Recommend `>=0.27` for stable async API
6. **Event hooks in Phase 0 or Phase 1?** The roadmap has them in Phase 1, but they're simple to add in Phase 0

---

*Generated from research on 6 codebases across 3 language ecosystems. See [docs/research/](./docs/research/) for full analysis.*
