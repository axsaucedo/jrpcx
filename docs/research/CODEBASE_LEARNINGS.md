# Codebase Learnings: Cross-Library Synthesis for jrpcx

> **Purpose:** Synthesises key learnings from 6 codebase analyses to inform the design and implementation of jrpcx — a Python JSON-RPC 2.0 client inspired by httpx.
>
> **Source Documents:**
> 1. [HTTPX_ANALYSIS.md](./HTTPX_ANALYSIS.md) — httpx (Python HTTP client, design inspiration)
> 2. [JSONRPCCLIENT_CODEBASE.md](./JSONRPCCLIENT_CODEBASE.md) — jsonrpcclient (Python, minimal message builder)
> 3. [PJRPC_RESEARCH_REPORT.md](./PJRPC_RESEARCH_REPORT.md) — pjrpc (Python, full-featured JSON-RPC)
> 4. [YBBUS_JSONRPC_CODEBASE.md](./YBBUS_JSONRPC_CODEBASE.md) — ybbus/jsonrpc (Go, lightweight client)
> 5. [JRPC2_RESEARCH_REPORT.md](./JRPC2_RESEARCH_REPORT.md) — jrpc2 (Go, production-grade)
> 6. [JAYSON_RESEARCH_REPORT.md](./JAYSON_RESEARCH_REPORT.md) — jayson (JS, multi-transport)

---

## 1. Executive Summary

Six JSON-RPC and HTTP client libraries across three language ecosystems (Python, Go, JavaScript) were analysed to identify proven patterns, innovative solutions, and anti-patterns for jrpcx. Each library occupies a distinct point on the simplicity–features spectrum:

| Library | Language | Philosophy | Key Lesson for jrpcx |
|---------|----------|-----------|----------------------|
| **httpx** | Python | Modern HTTP client with sync/async duality | **Primary architectural template** — class hierarchy, transport abstraction, type safety, testing patterns |
| **jsonrpcclient** | Python | Radical minimalism (260 lines, zero deps) | **Message layer purity** — functional approach, pluggable ID generators, error-as-value pattern |
| **pjrpc** | Python | Full-featured JSON-RPC framework | **Feature richness model** — proxy pattern, typed error deserialization, retry middleware, batch context managers |
| **ybbus/jsonrpc** | Go | Lightweight, zero-dependency client | **Ergonomic API design** — variadic params with reflection, `CallFor` convenience, interface-first design |
| **jrpc2** | Go | Production-grade, protocol-correct | **Transport abstraction gold standard** — Channel interface, in-memory testing, notification barrier, handler adaptation |
| **jayson** | JS | Multi-transport, spec-compliant | **Transport flexibility** — template method pattern, event system, browser compatibility, batch callback splitting |

**The core insight:** jrpcx should combine httpx's architectural elegance with jsonrpcclient's message-layer purity, pjrpc's feature richness, and jrpc2's transport abstraction. The result should feel as natural as `httpx.Client()` but speak JSON-RPC 2.0 natively.

---

## 2. Cross-Codebase Pattern Comparison

### 2.1 Sync/Async Duality

| Library | Approach | Code Sharing Mechanism | Duplication Level |
|---------|----------|----------------------|-------------------|
| **httpx** | Class hierarchy: `BaseClient` → `Client` / `AsyncClient` | Shared config, request building, response parsing in BaseClient; only I/O differs | Minimal (~10% duplication for stream methods: `read()`/`aread()`, `iter_bytes()`/`aiter_bytes()`) |
| **pjrpc** | Abstract base classes: `AbstractClient` / `AbstractAsyncClient` | Identical business logic; only `_request()` method differs (sync vs async) | Minimal — abstract interface enforces consistency |
| **jsonrpcclient** | N/A — stateless functions | Pure functions with no I/O; transport is caller's responsibility | None (no async concern) |
| **ybbus** | N/A — Go goroutines | Single synchronous API; concurrency via goroutines at call site | None (Go model) |
| **jrpc2** | Goroutine-based reader + concurrent callers | Single client with dedicated reader goroutine; `Call()` is blocking but concurrent | None (Go's concurrency model handles it) |
| **jayson** | Callbacks (primary) + Promise wrapper (opt-in) | `jayson/promise` module wraps callback API via `es6-promisify`; zero code duplication | None — Promise module is pure wrapper |

**Recommendation for jrpcx:** Adopt httpx's three-tier class hierarchy pattern. `BaseJSONRPCClient` holds all configuration, request building, response parsing, and error handling. `JSONRPCClient` and `AsyncJSONRPCClient` implement only the I/O boundary. This is the most proven Python pattern, used by both httpx and pjrpc.

### 2.2 Transport Abstraction

| Library | Interface | Transports Supported | Extensibility |
|---------|-----------|---------------------|---------------|
| **httpx** | `BaseTransport.handle_request(Request) → Response` + async variant | HTTP/1.1, HTTP/2, WSGI, ASGI, Mock | URL-pattern routing via mount system; easy custom transports |
| **pjrpc** | `AbstractClient._request(str, bool, Mapping) → Optional[str]` | HTTP (requests, aiohttp, httpx), AMQP (aio_pika) | New backends implement single `_request()` method |
| **jsonrpcclient** | None — deliberately omitted | User's responsibility | N/A — maximum flexibility by not choosing |
| **ybbus** | `HTTPClient.Do(req) → (resp, error)` (Go `http.Client` interface) | HTTP only | Inject custom `HTTPClient` for retries, auth, tracing |
| **jrpc2** | `Channel { Send([]byte) error; Recv() ([]byte, error); Close() error }` | Line-delimited, raw JSON, HTTP-header framed, in-memory direct | Custom `Framing` function: `func(io.Reader, io.WriteCloser) Channel` |
| **jayson** | Template method: subclass `Client`, override `_request()` | HTTP, HTTPS, TCP, TLS, WebSocket, Browser (user-provided) | New transport = new subclass overriding `_request()` |

**Recommendation for jrpcx:** Combine httpx's `BaseTransport` interface with jrpc2's minimal contract philosophy. The transport interface should be:
```python
class BaseTransport:
    def handle_request(self, request: Request) -> Response: ...
    def close(self) -> None: ...

class AsyncBaseTransport:
    async def handle_async_request(self, request: Request) -> Response: ...
    async def aclose(self) -> None: ...
```
Ship with `HTTPTransport` (via httpx), `MockTransport` (for testing), and make it trivial to add WebSocket or Unix socket transports later.

### 2.3 Request/Response Models

| Library | Request Type | Response Type | Richness |
|---------|-------------|---------------|----------|
| **httpx** | `Request` object (method, url, headers, content, stream, extensions) | `Response` object (status_code, headers, content, text, json(), elapsed, history, raise_for_status()) | Very rich — first-class objects with lazy loading, streaming, redirect history |
| **pjrpc** | `Request` dataclass (method, params, id) + `BatchRequest` | `Response` dataclass (id, result/error as MaybeSet) with `unwrap_result()`/`unwrap_error()` | Moderate — clean dataclasses with sentinel pattern |
| **jsonrpcclient** | `Dict[str, Any]` (raw dictionary) | `Ok(result, id)` / `Error(code, message, data, id)` NamedTuples | Minimal — immutable tuples, no methods |
| **ybbus** | `RPCRequest` struct (Method, Params, ID, JSONRPC) | `RPCResponse` struct with `GetInt()`/`GetString()`/`GetObject()` helpers | Moderate — typed extraction methods |
| **jrpc2** | `Request` struct with `Method()`, `UnmarshalParams()`, `IsNotification()` | `Response` struct with `UnmarshalResult()`, `Error()`, channel-based sync | Rich — lazy unmarshalling, synchronisation primitives |
| **jayson** | Generated dict via `generateRequest(method, params, id, options)` | Validated via `Utils.Response.isValidResponse()` | Moderate — validation-focused |

**Recommendation for jrpcx:** Create rich `Request` and `Response` objects inspired by httpx's design but tailored for JSON-RPC:
- `Request`: method, params, id, meta (headers, timeout overrides)
- `Response`: result, error, id, elapsed, http_response (underlying), with `raise_for_error()` method
- Use pjrpc's UNSET sentinel pattern for distinguishing "field absent" from "field is null"

### 2.4 Batch Operations

| Library | Batch API Style | Response Handling | ID Correlation |
|---------|----------------|-------------------|----------------|
| **httpx** | N/A (HTTP client, no batch concept) | N/A | N/A |
| **pjrpc** | 3 styles: direct `BatchRequest`, context manager `client.batch()`, proxy `batch.proxy.method()` | Iterate responses; `get_results()` raises on any error | Automatic ID validation, duplicate detection |
| **jsonrpcclient** | Manual: `[request(), request()]` list construction | `parse()` returns lazy `map` iterator of `Ok`/`Error` | None built-in — user matches by ID |
| **ybbus** | `CallBatch(ctx, requests)` with auto-ID; `CallBatchRaw` for manual | `RPCResponses` with `AsMap()`, `GetByID()`, `HasError()` | Auto-ID assignment (0, 1, 2, ...); `AsMap()` for lookup |
| **jrpc2** | `Batch(ctx, []Spec{...})` with Spec struct per request | Ordered response array; notifications omitted | Automatic — responses ordered, notifications excluded |
| **jayson** | Collect raw requests, send as array; 2-arg or 3-arg callback | 3-arg splits into `(err, errors[], successes[])`; 2-arg returns all | Implicit via callback arity |

**Recommendation for jrpcx:** Offer two batch styles (inspired by pjrpc):
1. **Context manager** (primary): `with client.batch() as batch: batch.call("method", params)`
2. **Direct** (advanced): `client.send(BatchRequest([Request(...), Request(...)]))`

Include ybbus-style response helpers: `responses.by_id(id)`, `responses.has_errors`, `responses.results()`. Support partial failure — don't raise on first error; let users iterate.

### 2.5 Error Handling

| Library | Strategy | Hierarchy Depth | Context Preservation |
|---------|----------|----------------|---------------------|
| **httpx** | Exception hierarchy with request/response context | Deep (HTTPError → RequestError → TransportError → TimeoutException → ConnectTimeout, etc.) | Every exception carries `.request`; status errors carry `.response` |
| **pjrpc** | Typed exception deserialization via `TypedError.__init_subclass__` | Moderate (BaseError → JsonRpcError → MethodNotFoundError, etc.) | Custom `TypedError` subclasses auto-register by error code |
| **jsonrpcclient** | Error-as-value: returns `Error` NamedTuple, never raises | Flat (single `Error` type) | Error carries code, message, data, id |
| **ybbus** | Dual return: `(*RPCResponse, error)` — HTTP errors separate from RPC errors | Shallow (`HTTPError` + `RPCError` as separate types) | `HTTPError.Code` for HTTP status; `RPCError.Code/Message/Data` for RPC |
| **jrpc2** | Typed error codes with `ErrCoder` interface; context errors auto-mapped | Moderate (standard codes + custom via `ErrCoder` interface) | `Error.Data` for structured context; automatic context.Canceled → error code |
| **jayson** | 3-layer: transport errors (callback arg 1), RPC errors (arg 2), success (arg 3) | Shallow (predefined code constants) | Transport-specific error properties (e.g., HTTP statusCode) |

**Recommendation for jrpcx:** Combine httpx's exception hierarchy with pjrpc's typed error deserialization:
```
JSONRPCError (base, carries request + response context)
├── TransportError (network/HTTP layer failures)
│   ├── TimeoutError
│   ├── ConnectionError
│   └── HTTPStatusError
├── ProtocolError (JSON-RPC protocol violations)
│   ├── ParseError (-32700)
│   ├── InvalidRequestError (-32600)
│   └── InvalidResponseError
└── ServerError (JSON-RPC error responses)
    ├── MethodNotFoundError (-32601)
    ├── InvalidParamsError (-32602)
    ├── InternalError (-32603)
    └── ApplicationError (custom codes via TypedError registration)
```

### 2.6 Type Safety

| Library | Annotation Coverage | Type Aliases | Generics | Runtime Validation | mypy Config |
|---------|-------------------|-------------|----------|-------------------|-------------|
| **httpx** | 100% — all public and private APIs | Extensive (`URLTypes`, `HeaderTypes`, `TimeoutTypes`, `AuthTypes`, `FileTypes`) | No (Python 3.8+ compatible) | Stream type checking at runtime | Strict |
| **pjrpc** | 100% — mypy strict mode | `JsonT`, `JsonRpcRequestIdT`, `JsonRpcParamsT`, `MaybeSet[T]` | `@overload` for `send()` return type | Content-Type validation | Strict |
| **jsonrpcclient** | 100% — all function signatures | `Deserialized`, `Response` | No | No runtime validation | Basic |
| **ybbus** | N/A (Go struct typing) | Named types (`RPCResponses`, `RPCRequests`) | No (pre-Go 1.18) | `json.Decoder.UseNumber()` | N/A |
| **jrpc2** | N/A (Go typing) | Interface-based (`Handler`, `Assigner`, `ErrCoder`) | No (pre-Go 1.18) | Reflection-based at handler registration | N/A |
| **jayson** | Partial (JS with incomplete TypeScript defs) | None | N/A | `Utils.Response.isValidResponse()` | N/A |

**Recommendation for jrpcx:** Follow httpx's standard — 100% type annotations, comprehensive type aliases, mypy strict mode. Define clear aliases:
```python
JSONValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
ParamsType = Optional[Union[Dict[str, Any], List[Any]]]
RequestID = Union[str, int]
MethodResult = Any  # Consider generic T in future
TimeoutTypes = Union[float, Timeout, None]
```

### 2.7 Testing Patterns

| Library | Primary Testing Mechanism | In-Memory Testing | pytest Integration |
|---------|--------------------------|-------------------|-------------------|
| **httpx** | `MockTransport(handler_func)` — handler receives Request, returns Response | WSGI/ASGI transports for real app testing without network | Works naturally with pytest |
| **pjrpc** | `PjRpcMocker` / `PjRpcAsyncMocker` via pytest integration module | Mocks at JSON-RPC response level | Dedicated `pjrpc.client.integrations.pytest` module |
| **jsonrpcclient** | Pure unit tests — no I/O, no mocks needed | N/A (functions are stateless) | `@pytest.mark.parametrize` for exhaustive cases |
| **ybbus** | `httptest.Server` with channel-based request capture | HTTP server in test process | N/A (Go testing) |
| **jrpc2** | `channel.Direct()` — in-memory bidirectional channel pair | `server.NewLocal(assigner, nil)` for instant server/client | N/A (Go testing) |
| **jayson** | Compliance tests per JSON-RPC spec; multi-transport tests | N/A | N/A (JS testing) |

**Recommendation for jrpcx:** Provide `MockTransport` as a first-class testing tool (httpx pattern):
```python
def handler(request: jrpcx.Request) -> jrpcx.Response:
    if request.method == "eth_blockNumber":
        return jrpcx.Response(result="0x10d4f")
    return jrpcx.Response(error={"code": -32601, "message": "Method not found"})

transport = jrpcx.MockTransport(handler)
client = jrpcx.Client("https://rpc.example.com", transport=transport)
```

### 2.8 Middleware/Extensibility

| Library | Mechanism | Hook Points | Limitations |
|---------|-----------|------------|-------------|
| **httpx** | Event hooks: `{"request": [fn], "response": [fn]}` | Before send, after receive | Informational only — can't abort or redirect |
| **pjrpc** | Middleware chain: `def mw(request, kwargs, /, handler)` | Full interception — can modify, retry, short-circuit | Reverse ordering is counterintuitive |
| **jsonrpcclient** | None — by design | N/A | Extensibility delegated to caller |
| **ybbus** | `HTTPClient` interface injection | HTTP layer only | No protocol-level hooks |
| **jrpc2** | Handler wrapping + custom `Assigner` | Per-handler or dispatch level | No built-in middleware chain |
| **jayson** | EventEmitter: `client.on('request', fn)` + custom JSON reviver/replacer | Before send, after receive, transport-specific events | Limited interception — events are informational |

**Recommendation for jrpcx:** Provide both mechanisms:
1. **Event hooks** (httpx-style, simple): `event_hooks={"request": [log], "response": [track_metrics]}`
2. **Middleware** (pjrpc-style, powerful): `middlewares=[retry_middleware, logging_middleware]` — but with **intuitive left-to-right ordering** (fixing pjrpc's reverse order).

### 2.9 Configuration Management

| Library | Pattern | Default Override Mechanism | Per-Request Override |
|---------|---------|---------------------------|---------------------|
| **httpx** | Constructor kwargs + `USE_CLIENT_DEFAULT` sentinel | Sentinel class distinguishes "not set" from `None` | `client.request(..., timeout=10.0)` overrides client default |
| **pjrpc** | Constructor kwargs + UNSET sentinel + custom JSON encoders | `MaybeSet[T] = Union[UnsetType, T]` | Via `**kwargs` passthrough to backend |
| **jsonrpcclient** | Function parameters (no config object) | All via function args | Every call is independent |
| **ybbus** | `RPCClientOpts` struct with zero-value defaults | `NewClient(url)` vs `NewClientWithOpts(url, opts)` | Context-based (deadlines, cancellation) |
| **jrpc2** | `ClientOptions` / `ServerOptions` structs | Options struct with zero-value defaults | Context per-request |
| **jayson** | Constructor options object | Minimal defaults, optional customisation | Per-request via callback args |

**Recommendation for jrpcx:** Adopt httpx's `USE_CLIENT_DEFAULT` sentinel pattern. This elegantly solves the "not provided vs explicitly None" problem:
```python
class UseClientDefault:
    """Sentinel: use the value configured on the client."""
    pass

USE_CLIENT_DEFAULT = UseClientDefault()

def call(self, method: str, *, timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT):
    if isinstance(timeout, UseClientDefault):
        timeout = self._timeout  # Use client default
```

### 2.10 Connection Management

| Library | Pooling | Context Manager | Lifecycle |
|---------|---------|----------------|-----------|
| **httpx** | Via httpcore; `Limits(max_connections=100, max_keepalive=20)` | `with Client() as client:` / `async with AsyncClient()` | `ClientState` enum: UNOPENED → OPENED → CLOSED |
| **pjrpc** | Delegated to backend (requests.Session, aiohttp.ClientSession) | `with Client(url) as client:` | Auto-created or user-managed sessions |
| **jsonrpcclient** | None — no connections | N/A | N/A |
| **ybbus** | Delegated to Go's `http.Client` | N/A (Go manages via GC) | Stateless per-request |
| **jrpc2** | Channel manages connection; client has reader goroutine | `cli.Close()` + `cli.Wait()` | Single connection per client; clean shutdown via WaitGroup |
| **jayson** | None (HTTP: new connection per request) | N/A | User manages WebSocket lifecycle |

**Recommendation for jrpcx:** Follow httpx exactly — context manager pattern with state tracking:
```python
with jrpcx.Client("https://rpc.example.com") as client:
    result = client.call("method", params)  # Connection reused

async with jrpcx.AsyncClient("https://rpc.example.com") as client:
    result = await client.call("method", params)
```
Delegate actual pooling to the underlying httpx transport.

---

## 3. Common Patterns Across Libraries

These patterns appear in 3+ of the analysed libraries. They represent proven, battle-tested approaches that jrpcx should adopt:

### 3.1 Transport Abstraction (6/6)
Every library either implements transport abstraction or deliberately defers it. This is the single most universal pattern:
- **httpx**: `BaseTransport` interface with mount routing
- **pjrpc**: Abstract `_request()` method across 4 backends
- **jsonrpcclient**: Deliberately omits transport (pure message layer)
- **ybbus**: `HTTPClient` interface for HTTP-layer injection
- **jrpc2**: `Channel` interface (3 methods) with multiple framings
- **jayson**: Template method with transport subclasses

**Takeaway:** Transport abstraction is non-negotiable. It enables testing, extensibility, and protocol independence.

### 3.2 Batch Request Support (5/6)
All libraries except httpx (which is an HTTP client, not RPC) support batch operations:
- **pjrpc**: Context manager + proxy + direct API (3 styles)
- **jsonrpcclient**: Manual list construction + lazy parsing
- **ybbus**: `CallBatch` / `CallBatchRaw` with response helpers
- **jrpc2**: `Batch(ctx, []Spec{})` with notification exclusion
- **jayson**: Array collection + 3-arg callback splitting

**Takeaway:** Batch support is essential. Offer both a convenient context manager and a lower-level direct API.

### 3.3 Rich Error Handling with Codes (6/6)
Every library maps JSON-RPC error codes to structured error types:
- Standard codes (-32700 through -32603) are universally supported
- Error data field preserved across all implementations
- Hierarchy depth varies, but structured errors are universal

**Takeaway:** Implement a complete error hierarchy mapping all standard JSON-RPC error codes, with support for custom application error codes via registration.

### 3.4 Multiple ID Generation Strategies (4/6)
Four libraries offer pluggable ID generation:
- **jsonrpcclient**: decimal, hex, random, UUID — all as infinite iterators
- **pjrpc**: sequential, random, UUID via `id_gen_impl` parameter
- **jrpc2**: Monotonic counter starting at 1 (avoiding null equivalence)
- **jayson**: UUID v4 default, custom via `generator` option

**Takeaway:** Ship with sequential (default), UUID, and random generators. Accept any `Iterator[RequestID]` for custom strategies. Start at 1, not 0, to avoid JSON null equivalence issues (jrpc2's insight).

### 3.5 Context Manager for Resource Lifecycle (4/6)
- **httpx**: `with Client()` / `async with AsyncClient()`
- **pjrpc**: `with Client(url)` for session management
- **pjrpc**: `with client.batch()` for batch collection
- **jrpc2**: `cli.Close()` + `cli.Wait()` (Go equivalent)

**Takeaway:** Context managers are the Pythonic way to manage client lifecycle. Support both `with` and `async with`.

### 3.6 Notification Support (5/6)
All JSON-RPC libraries distinguish notifications (no ID, no response expected):
- **jsonrpcclient**: Explicit `notification()` function
- **pjrpc**: `client.notify("method", params)` — id is None
- **ybbus**: *Missing* — ID always present (anti-pattern)
- **jrpc2**: `Spec{Notify: true}` — clean integration with batches
- **jayson**: `id: null` parameter generates notification

**Takeaway:** First-class notification support via `client.notify("method", params)`.

### 3.7 Type Annotations / Safety (5/6)
All modern libraries prioritise type safety:
- **httpx**: 100% annotations, comprehensive type aliases, mypy strict
- **pjrpc**: 100% annotations, mypy strict, `@overload` decorators
- **jsonrpcclient**: 100% annotations, type aliases, mypy
- **ybbus**: Go struct typing + named collection types
- **jrpc2**: Go interface typing + reflection-based validation

**Takeaway:** Full type annotations from day one. Enable mypy strict mode. Define type aliases for all complex parameter types.

---

## 4. Unique Innovations Worth Adopting

### 4.1 httpx

| Innovation | Description | Adoption Priority |
|-----------|-------------|-------------------|
| **`USE_CLIENT_DEFAULT` sentinel** | Distinguishes "not provided" from "explicitly None" — enables clean per-request overrides without accidentally clearing client defaults | **Must have** |
| **Event hooks** | `event_hooks={"request": [fn], "response": [fn]}` — lightweight extensibility without middleware complexity | **Must have** |
| **Type aliases** | `URLTypes`, `TimeoutTypes`, `HeaderTypes` etc. — accept multiple input types, normalise internally | **Must have** |
| **Generator-based auth flow** | `yield request` / `response = yield` — enables multi-step auth (OAuth, digest) working identically in sync/async | **Nice to have** |
| **MockTransport** | Handler function receives Request, returns Response — testing without network | **Must have** |
| **Transport mounts** | URL-pattern routing to different transports | **Future** |
| **Lazy body loading** | Stream by default, cache on first `read()`, replace stream with replayable `ByteStream` | **Nice to have** |
| **Client state enum** | `UNOPENED → OPENED → CLOSED` prevents use-after-close | **Must have** |

### 4.2 jsonrpcclient

| Innovation | Description | Adoption Priority |
|-----------|-------------|-------------------|
| **Radical simplicity** | 260 lines, zero deps, single responsibility — proves a message layer can be extremely lean | **Philosophy to adopt** |
| **Functional pure/impure split** | `request_pure(id_gen, method, params, id)` (injectable) → `request()` (convenient default) → `request_json()` (composed) | **Pattern to study** |
| **Multiple ID strategies** | 4 built-in generators as infinite iterators; custom via any `Iterator[Any]` | **Must have** |
| **Error-as-value pattern** | Returns `Ok`/`Error` NamedTuples instead of raising — excellent for batch processing | **Consider for batch results** |
| **NOID sentinel** | Distinguishes "no ID" from "ID is None" — important for notifications vs. null-ID requests | **Must have** |
| **Conditional params omission** | Omits `params` key entirely when params is None (cleaner JSON) | **Must have** |

### 4.3 pjrpc

| Innovation | Description | Adoption Priority |
|-----------|-------------|-------------------|
| **Proxy pattern** | `client.proxy.method_name(params)` via `__getattr__` — feels like calling a local function | **Must have** |
| **Typed error deserialization** | `TypedError` with `__init_subclass__` auto-registers by error code; `except MethodNotFoundError` just works | **Must have** |
| **Retry middleware** | `ExponentialBackoff`, `FibonacciBackoff`, `PeriodicBackoff` with jitter support and code-based retry conditions | **Should have** |
| **UNSET sentinel with `MaybeSet[T]`** | Type-safe distinction between "field absent" and "field is null" in responses | **Must have** |
| **Batch context manager with proxy** | `with client.batch() as b: b.proxy.sum(2, 2)` — batches feel natural | **Must have** |
| **Type overloading** | `@overload` for `send(Request) → Response` vs `send(BatchRequest) → BatchResponse` | **Should have** |
| **Custom JSON encoding** | Pluggable `json_encoder`/`json_decoder` at client level | **Should have** |

### 4.4 ybbus/jsonrpc

| Innovation | Description | Adoption Priority |
|-----------|-------------|-------------------|
| **Parameter reflection flexibility** | `Params()` auto-detects struct/array/map vs primitives — wraps appropriately for JSON-RPC | **Adapt for Python** |
| **`CallFor` convenience** | Single method: HTTP call + RPC error check + result parse + unmarshal — collapses common case | **Must have** (as `client.call_for(ResultType, "method", params)`) |
| **Interface-first public API** | Export interface, hide implementation — enables trivial mocking | **Adopt via Protocol** |
| **Batch response helpers** | Named type with `AsMap()`, `GetByID()`, `HasError()` | **Must have** |
| **Dual error return** | Returns both RPC response and HTTP error when both present — preserves full context | **Should have** |
| **`UseNumber()` for precision** | Stores numbers as strings to avoid float64 precision loss | **Consider** |

### 4.5 jrpc2

| Innovation | Description | Adoption Priority |
|-----------|-------------|-------------------|
| **Channel abstraction** | 3-method interface (`Send`, `Recv`, `Close`) — ultimate transport independence | **Inspiration for transport interface** |
| **Notification barrier** | Ensures notifications complete before next batch processes — critical for ordering-sensitive protocols | **Future (server-side concern)** |
| **Handler adaptation** | Reflection at setup, not runtime — supports many function signatures with zero call-time overhead | **Future (if adding server)** |
| **In-memory `channel.Direct()`** | Two-way buffered channels for testing — zero-network integration tests | **Adapt as `MockTransport` pattern** |
| **Error code auto-mapping** | `context.Canceled` → `-32097`, `context.DeadlineExceeded` → `-32096` | **Must have** |
| **Request ID from 1** | Avoids `0` which can conflate with JSON null in some parsers | **Must have** |
| **Inline last-request optimisation** | Last request in batch executes inline to avoid goroutine overhead | **Nice to know (optimisation)** |

### 4.6 jayson

| Innovation | Description | Adoption Priority |
|-----------|-------------|-------------------|
| **3-arg batch callback** | Automatically splits batch responses into `(error, errors[], successes[])` | **Adapt: `BatchResponse.errors` / `BatchResponse.successes` properties** |
| **Transport events** | `client.on('request', fn)` + transport-specific events (`http request`, `tcp socket`) | **Adapt as event hooks with transport events** |
| **Browser compatibility** | `ClientBrowser` with user-provided `callServer` function — zero platform deps | **Future (if targeting browser-like environments)** |
| **Custom JSON reviver/replacer** | Transform non-standard types during serialisation | **Should have** |
| **Streaming JSON parsing** | `stream-json` for memory-efficient large message parsing | **Future** |
| **Spec compliance validation** | `Utils.Response.isValidResponse()` — validates JSON-RPC structure rigorously | **Must have** |

---

## 5. Anti-Patterns and Things to Avoid

### 5.1 pjrpc's Counterintuitive Middleware Order
**Problem:** Middlewares execute in reverse registration order — last added is innermost. `[logging, retry, tracing]` executes as: logging → retry → tracing → send.
**Impact:** Developers expect left-to-right (first-registered-first-executed), leading to subtle bugs.
**jrpcx approach:** Use intuitive left-to-right ordering. First middleware registered wraps outermost.

### 5.2 jayson's Implicit Callback Arity Detection
**Problem:** Behaviour changes based on `function.length` (2 args vs 3 args). Not type-safe, runtime-determined, hard to debug if signature is wrong.
**Impact:** Silent behaviour changes from adding/removing a parameter.
**jrpcx approach:** Use explicit methods or keyword arguments. Never infer behaviour from function signature.

### 5.3 ybbus's HTTP-Only Coupling
**Problem:** Transport layer is hardcoded to HTTP. `RPCRequest` always serialises to HTTP POST. No WebSocket, Unix socket, or in-process support.
**Impact:** Limits use cases; makes testing require actual HTTP server.
**jrpcx approach:** Abstract transport from day one. HTTP is default, but the interface supports any transport.

### 5.4 jsonrpcclient's Lack of Connection Management
**Problem:** Pure function approach means no connection pooling, no session reuse, no resource lifecycle management.
**Impact:** Every request potentially creates a new connection; caller must manage everything.
**jrpcx approach:** Provide connection management by default (via httpx's pool). Function-level API (`jrpcx.call()`) should still work for simple cases but use a temporary client internally.

### 5.5 jrpc2's Limited HTTP Support
**Problem:** `jhttp` package is thin — no Content-Type handling, no auth headers, no cookies, no session management.
**Impact:** HTTP use cases require significant wrapper code.
**jrpcx approach:** HTTP is the primary transport. First-class support for headers, auth, cookies, and all HTTP concerns.

### 5.6 ybbus's No Default Timeout
**Problem:** `http.Client{}` with no timeout — requests can block indefinitely.
**Impact:** Production risk — hung requests consume resources.
**jrpcx approach:** Ship with sensible default timeout (e.g., 30 seconds). Make it configurable via `Timeout` object (inspired by httpx's granular timeout: connect, read, write, pool).

### 5.7 jsonrpcclient's Lazy Batch Parsing
**Problem:** `parse([...])` returns a `map` object, not a list. `len(parse([...]))` throws `TypeError`.
**Impact:** Violates principle of least surprise.
**jrpcx approach:** Always return concrete types. `BatchResponse` should be a list-like object with helper methods.

### 5.8 ybbus's Integer-Only Request IDs
**Problem:** `RPCRequest.ID` is `int` only, but JSON-RPC spec allows string or integer.
**Impact:** Incompatible with servers that use string IDs.
**jrpcx approach:** `RequestID = Union[str, int]` — support both.

### 5.9 pjrpc's Batch All-or-Nothing `get_results()`
**Problem:** `batch.get_results()` raises on the first error, losing successful results.
**Impact:** Can't process partial successes in batch operations.
**jrpcx approach:** Provide both `results()` (raises) and `iter_responses()` (yields all). Add `successes` and `errors` properties for filtered access.

### 5.10 Global/Singleton State in ID Generators
**Problem (jsonrpcclient):** ID generators are module-level singletons via `functools.partial`. State persists between test runs.
**Impact:** Non-deterministic test IDs; can't reset between tests.
**jrpcx approach:** ID generators are instance-scoped (per-client). Each client gets its own generator. Provide `reset()` for testing convenience.

---

## 6. Design Principles for jrpcx

Distilled from all 6 analyses, these are the guiding principles:

### Principle 1: Simplicity First
*Inspired by: httpx + jsonrpcclient*

The 80% use case should be one line:
```python
result = jrpcx.call("https://rpc.example.com", "eth_blockNumber")
```
The 20% power-user case should be intuitive:
```python
async with jrpcx.AsyncClient("https://rpc.example.com", auth=("user", "pass")) as client:
    result = await client.call("eth_getBalance", ["0x...", "latest"])
```
jsonrpcclient proves a message layer can be 260 lines. httpx proves a full client can still feel simple. jrpcx should combine both: simple surface, rich internals.

### Principle 2: Sync/Async Duality Without Code Duplication
*Inspired by: httpx class hierarchy*

One codebase, two APIs:
```
BaseJSONRPCClient (config, request building, response parsing, error handling)
├── JSONRPCClient (sync I/O via transport.handle_request)
└── AsyncJSONRPCClient (async I/O via transport.handle_async_request)
```
All business logic lives in the base class. Only the I/O boundary differs.

### Principle 3: Transport Abstraction for Testability
*Inspired by: httpx BaseTransport + jrpc2 Channel*

The transport interface should be minimal and powerful:
```python
class BaseTransport:
    def handle_request(self, request: Request) -> Response: ...
```
This enables: `MockTransport` for unit testing, `HTTPTransport` for production, future `WebSocketTransport`, `UnixSocketTransport`, etc.

### Principle 4: Rich Typed Request/Response Objects
*Inspired by: httpx + pjrpc*

Not raw dicts. Rich objects with methods, type annotations, and helpful properties:
```python
response = client.call("method", params)
response.result          # The result value
response.error           # Error object or None
response.id              # Request ID for correlation
response.elapsed         # Request duration
response.is_success      # True if no error
response.raise_for_error()  # Raise if error
```

### Principle 5: Comprehensive Type Safety
*Inspired by: httpx standard*

- 100% type annotations on all public and private APIs
- Type aliases for all complex parameter types
- mypy strict mode enabled from day one
- `@overload` decorators where return types vary by input
- `Protocol` classes for structural typing

### Principle 6: Extensibility via Hooks and Middleware
*Inspired by: httpx event hooks + pjrpc middleware*

Two levels of extensibility:
1. **Hooks** (simple, informational): observe requests/responses
2. **Middleware** (powerful, intercepting): modify, retry, short-circuit

Hooks for the 80% case (logging, metrics). Middleware for the 20% case (retry, auth, caching).

### Principle 7: Testing as First-Class Concern
*Inspired by: httpx MockTransport pattern*

Testing without network should be trivial:
```python
transport = jrpcx.MockTransport(lambda req: jrpcx.Response(result=42))
client = jrpcx.Client("https://rpc.example.com", transport=transport)
assert client.call("method").result == 42
```
Ship `MockTransport` as part of the public API, not as a test utility.

### Principle 8: Convention Over Configuration with Smart Defaults
*Inspired by: ybbus zero-value defaults + httpx sensible defaults*

- Default timeout: 30 seconds
- Default ID generator: sequential starting at 1
- Default transport: HTTP via httpx
- Default content type: `application/json`
- Connection pooling: enabled by default
- JSON-RPC version: `"2.0"` always

Override anything, but the defaults should be production-ready.

---

## 7. Recommended Architecture for jrpcx

### 7.1 Class Hierarchy

```
BaseJSONRPCClient
│   ├── config: ClientConfig (timeout, headers, auth, base_url, ...)
│   ├── _id_generator: Iterator[RequestID]
│   ├── _event_hooks: Dict[str, List[Callable]]
│   ├── _middlewares: List[Middleware]
│   ├── _state: ClientState (UNOPENED / OPENED / CLOSED)
│   │
│   ├── build_request(method, params, id?) → Request
│   ├── parse_response(raw_response) → Response
│   ├── _apply_middleware(request, handler) → Response
│   ├── batch() → BatchContext
│   └── @property proxy → Proxy
│
├── JSONRPCClient(BaseJSONRPCClient)
│   ├── _transport: BaseTransport
│   ├── call(method, params?, **kwargs) → Response
│   ├── notify(method, params?) → None
│   ├── send(request) → Response
│   ├── __enter__ / __exit__
│   └── close()
│
└── AsyncJSONRPCClient(BaseJSONRPCClient)
    ├── _transport: AsyncBaseTransport
    ├── async call(method, params?, **kwargs) → Response
    ├── async notify(method, params?) → None
    ├── async send(request) → Response
    ├── async __aenter__ / __aexit__
    └── async aclose()
```

### 7.2 Module Structure

```
jrpcx/
├── __init__.py              # Public API: Client, AsyncClient, Request, Response,
│                            #   MockTransport, call(), async_call(), errors
├── _client.py               # BaseJSONRPCClient, JSONRPCClient, AsyncJSONRPCClient
├── _models.py               # Request, Response, BatchRequest, BatchResponse
├── _errors.py               # Full exception hierarchy + TypedError registration
├── _types.py                # Type aliases (ParamsType, RequestID, TimeoutTypes, etc.)
├── _config.py               # Timeout, ClientConfig, USE_CLIENT_DEFAULT sentinel
├── _proxy.py                # Proxy object (client.proxy.method_name())
├── _batch.py                # BatchContext, BatchResponse with helpers
├── _id_generators.py        # sequential, uuid, random generators
├── _middleware.py            # Middleware protocol, built-in retry middleware
├── _transports/
│   ├── __init__.py          # BaseTransport, AsyncBaseTransport
│   ├── _http.py             # HTTPTransport, AsyncHTTPTransport (via httpx)
│   └── _mock.py             # MockTransport, AsyncMockTransport
├── _serialization.py        # JSON encoding/decoding with custom type support
└── py.typed                 # PEP 561 marker

tests/
├── conftest.py              # Shared fixtures, mock transport helpers
├── test_client.py           # Sync client tests
├── test_async_client.py     # Async client tests
├── test_models.py           # Request/Response model tests
├── test_batch.py            # Batch operation tests
├── test_errors.py           # Error hierarchy tests
├── test_transports.py       # Transport abstraction tests
├── test_middleware.py        # Middleware chain tests
├── test_proxy.py            # Proxy pattern tests
└── test_id_generators.py    # ID generation tests
```

### 7.3 Key Interfaces

```python
# Transport Interface
class BaseTransport:
    def handle_request(self, request: Request) -> Response:
        raise NotImplementedError
    def close(self) -> None:
        pass
    def __enter__(self) -> "BaseTransport": ...
    def __exit__(self, *args) -> None: ...

class AsyncBaseTransport:
    async def handle_async_request(self, request: Request) -> Response:
        raise NotImplementedError
    async def aclose(self) -> None:
        pass
    async def __aenter__(self) -> "AsyncBaseTransport": ...
    async def __aexit__(self, *args) -> None: ...

# Middleware Interface
MiddlewareHandler = Callable[[Request], Response]
Middleware = Callable[[Request, MiddlewareHandler], Response]

# ID Generator Protocol
class IDGenerator(Protocol):
    def __next__(self) -> RequestID: ...
    def __iter__(self) -> Iterator[RequestID]: ...

# Error Registration
class TypedError(JSONRPCError):
    CODE: ClassVar[int]
    MESSAGE: ClassVar[str]
    def __init_subclass__(cls, **kwargs):
        # Auto-register subclass by CODE
        _error_registry[cls.CODE] = cls
```

### 7.4 Convenience API

```python
# Module-level functions (simple use cases)
def call(url: str, method: str, params: ParamsType = None, **kwargs) -> Response:
    """One-shot JSON-RPC call. Creates temporary client."""
    with Client(url, **kwargs) as client:
        return client.call(method, params)

async def async_call(url: str, method: str, params: ParamsType = None, **kwargs) -> Response:
    """One-shot async JSON-RPC call."""
    async with AsyncClient(url, **kwargs) as client:
        return await client.call(method, params)

# Client-based API (connection reuse)
with Client("https://rpc.example.com") as client:
    block = client.call("eth_blockNumber")
    balance = client.call("eth_getBalance", ["0x...", "latest"])

# Proxy API (natural method calls)
with Client("https://rpc.example.com") as client:
    block = client.proxy.eth_blockNumber()
    balance = client.proxy.eth_getBalance("0x...", "latest")

# Batch API
with Client("https://rpc.example.com") as client:
    with client.batch() as batch:
        batch.call("eth_blockNumber")
        batch.call("eth_getBalance", ["0x...", "latest"])
    for response in batch.responses:
        print(response.result)
```

---

## 8. Feature Adoption Matrix

| jrpcx Feature | Primary Inspiration | Secondary Inspiration | Notes |
|---|---|---|---|
| **Sync/Async class hierarchy** | httpx (BaseClient pattern) | pjrpc (AbstractClient pattern) | Three-tier: Base → Sync → Async |
| **Transport abstraction** | httpx (BaseTransport) | jrpc2 (Channel interface) | Minimal interface, ship with HTTP + Mock |
| **MockTransport for testing** | httpx (MockTransport) | jrpc2 (channel.Direct) | Handler function receives Request, returns Response |
| **Request/Response objects** | httpx (rich first-class objects) | pjrpc (dataclass models) | JSON-RPC specific: method, params, result, error, elapsed |
| **`USE_CLIENT_DEFAULT` sentinel** | httpx | pjrpc (UNSET/MaybeSet) | Distinguishes "not provided" from "explicitly None" |
| **Exception hierarchy** | httpx (HTTPError tree) | pjrpc (JsonRpcError subclasses) | Transport + Protocol + Server error branches |
| **Typed error deserialization** | pjrpc (TypedError + `__init_subclass__`) | jrpc2 (ErrCoder interface) | Auto-register custom error types by code |
| **Event hooks** | httpx (`event_hooks` dict) | jayson (EventEmitter) | `{"request": [fn], "response": [fn]}` pattern |
| **Middleware chain** | pjrpc (middleware functions) | — | Fix: use intuitive left-to-right ordering |
| **Retry middleware** | pjrpc (RetryMiddleware + backoff strategies) | — | Exponential, Fibonacci, periodic backoff with jitter |
| **Proxy pattern** | pjrpc (`client.proxy.method()`) | — | `__getattr__`-based dynamic dispatch |
| **Batch context manager** | pjrpc (`with client.batch()`) | — | Collect calls, send on exit, return responses |
| **Batch response helpers** | ybbus (`AsMap`, `GetByID`, `HasError`) | jayson (3-arg split) | `.by_id()`, `.successes`, `.errors`, `.has_errors` |
| **ID generators** | jsonrpcclient (4 strategies as iterators) | pjrpc (sequential, random, UUID) | Instance-scoped, start at 1, pluggable |
| **Type aliases** | httpx (`URLTypes`, `TimeoutTypes`) | pjrpc (`JsonT`, `ParamsType`) | `ParamsType`, `RequestID`, `TimeoutTypes`, etc. |
| **Type annotations (100%)** | httpx (comprehensive) | pjrpc (mypy strict) | mypy strict mode from day one |
| **Connection pooling** | httpx (via httpcore Limits) | — | Delegate to httpx's transport layer |
| **Context manager lifecycle** | httpx (ClientState enum) | pjrpc (session management) | `UNOPENED → OPENED → CLOSED` state machine |
| **Notification support** | jsonrpcclient (`notification()`) | pjrpc (`client.notify()`) | `client.notify("method", params)` — no response |
| **Params omission** | jsonrpcclient (omit key when None) | ybbus (`omitempty` tag) | Omit `params` key entirely when no params provided |
| **Function-level API** | httpx (`httpx.get()`) | jsonrpcclient (stateless functions) | `jrpcx.call(url, method)` for one-shot use |
| **Custom JSON encoding** | pjrpc (json_encoder/json_decoder) | jayson (reviver/replacer) | Pluggable serialisation for custom types |
| **Error code constants** | jrpc2 (const block) | jayson (predefined codes) | `ErrorCode.PARSE_ERROR`, `ErrorCode.METHOD_NOT_FOUND`, etc. |
| **Variadic params convenience** | ybbus (Params reflection) | — | Adapt: `client.call("method", arg1, arg2)` auto-wraps |
| **Response type extraction** | ybbus (`GetInt`, `GetObject`) | — | `response.result_as(MyType)` for typed extraction |
| **Spec compliance validation** | jayson (`isValidResponse`) | jrpc2 (full spec compliance) | Validate all JSON-RPC 2.0 structure on send and receive |

---

*This document serves as the bridge between research and implementation. Each recommendation is grounded in patterns proven across production-grade libraries in Python, Go, and JavaScript.*
