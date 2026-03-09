# jsonrpcclient (Python): Comprehensive Codebase Analysis

## Executive Summary

**jsonrpcclient** is a radically minimal Python library for constructing JSON-RPC 2.0 requests and parsing responses. At only 260 lines of source code with zero external dependencies, it is a pure message builder/parser with no transport layer — the defining characteristic of its v4.0 rewrite. The library follows a functional programming style with pure functions, immutable NamedTuple response types, composable ID generators, and full type annotations. It is the most focused JSON-RPC client library in our research set: it does one thing (message construction/parsing) and does it well.

**Repository**: [explodinglabs/jsonrpcclient](https://github.com/explodinglabs/jsonrpcclient)
**Version Analyzed**: 4.0.3 (February 2023)
**Language**: Python 3.6+
**License**: MIT
**Author**: Beau Barker (Exploding Labs)

---

## 1. Project Overview

### Purpose & Philosophy

jsonrpcclient exists to answer a single question: *how do I build a JSON-RPC 2.0 request dict and parse a JSON-RPC 2.0 response?* It deliberately excludes everything else.

The library underwent a **complete rewrite in v4.0** (September 2021), stripping away all transport backends (AiohttpClient, TornadoClient, Socket client, ZMQ client, config modules, logging) in favor of pure message construction and parsing. This was a conscious architectural decision: let users choose their own transport, and provide only the JSON-RPC message layer.

### Design Principles

- **Transport-agnostic**: No HTTP client, no WebSocket client — just message building
- **Functional approach**: Pure functions, immutable data structures, function composition
- **Zero dependencies**: Nothing beyond the Python standard library
- **Type-safe**: Full Python 3.6+ type annotations, mypy validated
- **Radical simplicity**: 260 lines across 6 source files

### Project Metrics

| Metric | Value |
|--------|-------|
| **Total Source Lines** | 260 |
| **Source Files** | 6 |
| **Public Functions** | 14 |
| **Public Classes** | 3 (Ok, Error, Sentinel) |
| **External Dependencies** | 0 |
| **Test Files** | 4 |
| **Test Functions** | 13 |
| **Python Version Support** | 3.6–3.11 |
| **Dev Dependencies** | pytest, pytest-cov, tox |
| **Build System** | setuptools (pyproject.toml) |
| **Linter** | ruff (line-length: 88, indent-width: 4) |
| **Type Checker** | mypy (python_version: 3.7) |

---

## 2. Architecture and Code Organization

### Directory Structure

```
jsonrpcclient/
├── __init__.py          (32 lines)  — Public API exports
├── requests.py          (75 lines)  — Request/notification construction
├── responses.py         (63 lines)  — Response parsing (Ok/Error)
├── id_generators.py     (61 lines)  — ID generation strategies (4 types)
├── sentinels.py         (21 lines)  — Sentinel pattern (NOID)
└── utils.py             (8 lines)   — Function composition utility

tests/
├── test_requests.py     (89 lines)  — Request construction tests
├── test_responses.py    (49 lines)  — Response parsing tests
├── test_id_generators.py(25 lines)  — ID generator tests
└── test_sentinels.py    (7 lines)   — Sentinel repr test
```

### Separation of Concerns

| Module | Responsibility |
|--------|----------------|
| `requests.py` | Build JSON-RPC request/notification dicts |
| `responses.py` | Parse response dicts into Ok/Error objects |
| `id_generators.py` | Generate request IDs (4 strategies) |
| `sentinels.py` | Sentinel pattern for non-None "no value" |
| `utils.py` | Function composition utility |
| `__init__.py` | Public API surface (re-exports) |

### Architectural Patterns

**Pure/Impure Function Separation**: The core pattern throughout:

```
request_pure()          ← Pure function: all inputs explicit, including id_generator
    ↓
request_impure()        ← Partially applied: binds a specific id_generator
    ↓
request() / request_hex() / request_uuid()  ← Convenient public API with default generators
    ↓
request_json() / request_json_hex() / ...   ← Composed with json.dumps
```

**Function Composition**: The `compose()` utility chains functions together. JSON-string variants are composed from dict-returning functions + `json.dumps`:

```python
# utils.py — the entire file
from functools import reduce
from typing import Any, Callable

def compose(*funcs: Callable[..., Any]) -> Callable[..., Any]:
    return reduce(lambda f, g: lambda *a, **kw: f(g(*a, **kw)), funcs)

# Usage in requests.py
request_json = compose(json.dumps, request_natural)
notification_json = compose(json.dumps, notification)
```

**Partial Application**: Default ID generators are bound using `functools.partial`:

```python
request_natural = partial(request_impure, decimal())
request_hex_gen = partial(request_impure, hexadecimal())
request_random_gen = partial(request_impure, random())
request_uuid_gen = partial(request_impure, uuid())
```

---

## 3. API Surface

### Public API (exported from `__init__.py`)

**Request Construction** (10 functions):

| Function | Returns | ID Strategy |
|----------|---------|-------------|
| `request(method, params, id)` | `Dict` | Auto-increment decimal (1, 2, 3...) |
| `request_hex(method, params, id)` | `Dict` | Auto-increment hexadecimal |
| `request_random(method, params, id)` | `Dict` | Random 8-char string |
| `request_uuid(method, params, id)` | `Dict` | UUID v4 |
| `request_json(...)` | `str` | JSON string, decimal IDs |
| `request_json_hex(...)` | `str` | JSON string, hex IDs |
| `request_json_random(...)` | `str` | JSON string, random IDs |
| `request_json_uuid(...)` | `str` | JSON string, UUID IDs |
| `notification(method, params)` | `Dict` | N/A (no ID) |
| `notification_json(method, params)` | `str` | N/A (no ID) |

**Response Parsing** (2 functions):

| Function | Input | Returns |
|----------|-------|---------|
| `parse(deserialized)` | `Dict` or `List[Dict]` | `Ok`, `Error`, or `Iterable[Ok\|Error]` |
| `parse_json(json_string)` | `str` | `Ok`, `Error`, or `Iterable[Ok\|Error]` |

**Response Types** (2 NamedTuples):

| Type | Fields | Purpose |
|------|--------|---------|
| `Ok` | `result: Any`, `id: Any` | Successful response |
| `Error` | `code: int`, `message: str`, `data: Any`, `id: Any` | Error response |

### Usage Patterns

#### Simple Request-Response
```python
from jsonrpcclient import request, parse_json
import requests

# Build the request dict
req = request("ping")
# => {'jsonrpc': '2.0', 'method': 'ping', 'id': 1}

# Send via YOUR transport
response = requests.post("http://example.com/rpc", json=req)

# Parse the response
parsed = parse_json(response.text)
# => Ok(result='pong', id=1)
```

#### With Parameters
```python
req = request("multiply", params=[2, 3], id=99)
# => {'jsonrpc': '2.0', 'method': 'multiply', 'params': [2, 3], 'id': 99}

req = request("get_user", params={"id": 123})
# => {'jsonrpc': '2.0', 'method': 'get_user', 'params': {'id': 123}, 'id': 2}
```

#### Notifications (Fire-and-Forget)
```python
from jsonrpcclient import notification

notif = notification("log_event", params={"event": "user_login"})
# => {'jsonrpc': '2.0', 'method': 'log_event', 'params': {'event': 'user_login'}}
# No 'id' field — server MUST NOT reply
```

#### Batch Requests (Manual)
```python
import json
batch = [
    request("get_user", params={"id": 1}, id=1),
    request("get_user", params={"id": 2}, id=2),
    notification("log", params={"msg": "batch sent"}),
]
batch_json = json.dumps(batch)
# Send batch_json, parse response with parse_json()
```

#### Error Handling
```python
from jsonrpcclient import parse, Ok, Error

response = parse(response_dict)
if isinstance(response, Ok):
    print(f"Success: {response.result}")
elif isinstance(response, Error):
    print(f"Error {response.code}: {response.message}")

# Python 3.10+ pattern matching
match response:
    case Ok(result, id):
        print(f"Result: {result}")
    case Error(code, message, data, id):
        print(f"Error {code}: {message}")
```

---

## 4. Request Construction

### Core Implementation

**Notifications** — the simplest case, no ID:

```python
def notification_pure(method: str, params=None) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": method,
        **({"params": params} if params else {}),  # Omit params if empty
    }
```

**Requests** — adds ID generation logic:

```python
def request_pure(
    id_generator: Iterator[Any],
    method: str,
    params: Union[Dict[str, Any], Tuple[Any, ...]],
    id: Any,
) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "method": method,
        **({"params": list(params) if isinstance(params, tuple) else params} if params else {}),
        "id": id if id is not NOID else next(id_generator),
    }
```

### Parameter Handling

- **Omission**: If `params` is `None`/empty, the `params` key is omitted entirely (cleaner JSON)
- **Dict params**: Passed through as-is → named parameters
- **Tuple/list params**: Tuples converted to lists → positional parameters
- **Conditional inclusion**: Uses `**({} if ... else ...)` spread pattern for clean dict construction

### NOID Sentinel Pattern

The library uses a custom sentinel to distinguish "no ID provided" from "ID is explicitly None":

```python
class Sentinel:
    def __init__(self, name: str):
        self.name = name
    def __repr__(self) -> str:
        return f"<{sys.intern(str(self.name)).rsplit('.', 1)[-1]}>"

NOID = Sentinel("NoId")
```

This is important because JSON-RPC 2.0 allows `null` IDs in some contexts. Using `NOID` as the default parameter value means:
- `request("foo")` → auto-generate ID
- `request("foo", id=None)` → explicit null ID
- `request("foo", id=42)` → explicit integer ID

---

## 5. Response Parsing

### Response Types

Two immutable NamedTuples with custom `__repr__`:

```python
class Ok(NamedTuple):
    result: Any
    id: Any

class Error(NamedTuple):
    code: int
    message: str
    data: Any
    id: Any
```

NamedTuples provide: immutability, named field access, tuple unpacking, clean repr, and Python 3.10+ pattern matching support.

### Parsing Logic

```python
def to_response(response: Dict[str, Any]) -> Response:
    return (
        Ok(response["result"], response["id"])
        if "result" in response
        else Error(
            response["error"]["code"],
            response["error"]["message"],
            response["error"].get("data"),
            response["id"],
        )
    )

def parse(deserialized: Deserialized) -> Union[Response, Iterable[Response]]:
    if isinstance(deserialized, str):
        raise TypeError("Use parse_json on strings")
    return (
        map(to_response, deserialized)
        if isinstance(deserialized, list)
        else to_response(deserialized)
    )
```

**Key design decisions**:
- **Ok vs Error detection**: Presence of `"result"` key determines success (per JSON-RPC 2.0 spec)
- **Lazy batch parsing**: Batch responses return a `map()` iterator, not a materialized list — memory efficient for large batches
- **Type guard**: Rejects strings with a clear error message directing users to `parse_json()`
- **Optional error data**: Uses `.get("data")` to default to `None` when absent

### Batch Response Handling

```python
batch_response = [
    {"jsonrpc": "2.0", "result": "pong", "id": 1},
    {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid"}, "id": 2},
]
parsed = parse(batch_response)  # Returns map object (lazy)
responses = list(parsed)        # [Ok(result='pong', id=1), Error(...)]
```

Note: No built-in batch request constructor exists. Users manually build `[request(...), request(...)]` arrays.

---

## 6. ID Generation Strategies

Four built-in generators in `id_generators.py`, all implemented as infinite iterators:

### Decimal (Default)
```python
def decimal(start: int = 1) -> Iterator[int]:
    yield from count(start)  # 1, 2, 3, 4, ...
```

### Hexadecimal
```python
def hexadecimal(start: int = 1) -> Iterator[str]:
    for i in count(start):
        yield format(i, "x")  # "1", "2", ..., "9", "a", "b", ...
```

### Random
```python
def random(length: int = 8, chars: str = digits + ascii_lowercase) -> Iterator[str]:
    while True:
        yield "".join(choice(chars) for _ in range(length))
        # e.g., "a1b2c3d4" (8-char alphanumeric, ~1 in million collision chance)
```

### UUID
```python
def uuid() -> Iterator[str]:
    while True:
        yield str(uuid4())
        # e.g., "9bfe2c93-717e-4a45-b91b-55422c5af4ff"
```

### Custom ID Generators

Users can create their own by implementing any `Iterator[Any]`:

```python
from jsonrpcclient.requests import request_impure

def my_generator():
    while True:
        yield f"custom-{uuid4().hex[:8]}"

gen = my_generator()
req = request_impure(gen, "foo")
```

### Design Characteristics

- All generators are **infinite iterators** (never exhausted)
- Generators are **stateful** — each `next()` advances the counter
- Not resettable — this can complicate testing (global state between tests)
- Each public `request_*` variant binds its own generator instance via `functools.partial`

---

## 7. Error Handling

### Philosophy: Values, Not Exceptions

**jsonrpcclient does not throw exceptions on JSON-RPC errors.** It returns `Error` objects as values. This is a deliberate functional design choice:

- Better for batch processing (mix of successes and failures)
- Forces explicit error handling — no silent exception swallowing
- More composable — results can be filtered, mapped, collected
- No try/catch ceremony needed

### Error Representation

```python
class Error(NamedTuple):
    code: int          # JSON-RPC error code
    message: str       # Error message from server
    data: Any          # Optional additional data (defaults to None)
    id: Any            # Request ID for correlation
```

### Standard JSON-RPC 2.0 Error Codes

The library doesn't enforce or define error code constants, but follows the spec:

| Code | Meaning |
|------|---------|
| `-32700` | Parse error |
| `-32600` | Invalid Request |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32000` to `-32099` | Server error (reserved range) |

### Limitations

- **No response validation**: Doesn't validate JSON-RPC 2.0 structure. Assumes well-formed responses.
- **Missing fields cause KeyError**: If a response lacks required fields (`code`, `message`, `id`), parsing crashes with a raw `KeyError` — no graceful degradation.
- **No error code constants**: Users must use raw integers for comparison.
- **No typed exception hierarchy**: Unlike pjrpc which provides `JsonRpcError` subclasses, jsonrpcclient returns flat `Error` tuples.

---

## 8. Type Safety / Type Annotations

### Coverage

Full Python 3.6+ type hints across the entire codebase:

```python
# requests.py
def request_pure(
    id_generator: Iterator[Any],
    method: str,
    params: Union[Dict[str, Any], Tuple[Any, ...]],
    id: Any,
) -> Dict[str, Any]: ...

# responses.py
def parse(deserialized: Deserialized) -> Union[Response, Iterable[Response]]: ...

# id_generators.py
def decimal(start: int = 1) -> Iterator[int]: ...
def hexadecimal(start: int = 1) -> Iterator[str]: ...
def random(length: int = 8, chars: str = ...) -> Iterator[str]: ...
def uuid() -> Iterator[str]: ...
```

### Type Aliases

```python
Deserialized = Union[Dict[str, Any], List[Dict[str, Any]]]
Response = Union[Ok, Error]
```

### Mypy Configuration

```toml
[tool.mypy]
python_version = "3.7"
exclude = ['^examples\/requests_client_py310\.py$']
```

### Strengths and Gaps

**Strengths:**
- All function signatures are annotated
- NamedTuples provide structural typing for responses
- Type aliases make complex types readable
- mypy validation in CI

**Gaps:**
- Heavy use of `Any` — `result`, `id`, `params` are all `Any`
- No generic type parameters for result types (can't do `Ok[UserData]`)
- `parse()` return type `Union[Response, Iterable[Response]]` makes it hard to use without runtime type checks
- No `TypeGuard` or discriminated union support

---

## 9. Testing Patterns

### Test Structure

| Test File | Lines | Tests | Coverage |
|-----------|-------|-------|----------|
| `test_requests.py` | 89 | 5 test functions (parameterized) | Notifications, requests, auto-IDs, JSON output |
| `test_responses.py` | 49 | 5 test functions | Ok/Error repr, parsing, type guard, JSON parsing |
| `test_id_generators.py` | 25 | 3 test functions | Hex, random, UUID generators |
| `test_sentinels.py` | 7 | 1 test function | Sentinel repr |

### Testing Style

**Parameterized tests** using `@pytest.mark.parametrize`:

```python
@pytest.mark.parametrize(
    "method, params, expected",
    [
        ("foo", None, {"jsonrpc": "2.0", "method": "foo"}),
        ("foo", (1,), {"jsonrpc": "2.0", "method": "foo", "params": [1]}),
        ("foo", {"bar": 1}, {"jsonrpc": "2.0", "method": "foo", "params": {"bar": 1}}),
    ],
)
def test_notification(method, params, expected):
    assert notification(method, params) == expected
```

**Pure unit tests** — no mocks, no fixtures, no I/O:

```python
def test_parse():
    assert parse({"jsonrpc": "2.0", "result": "pong", "id": 1}) == Ok("pong", 1)

def test_parse_string():
    with pytest.raises(TypeError):
        parse('{"jsonrpc": "2.0", "result": "pong", "id": 1}')
```

### Coverage Assessment

**Well covered:**
- ✅ All core request/notification construction paths
- ✅ Auto-incrementing ID behavior
- ✅ JSON serialization variants
- ✅ Response parsing for Ok and Error
- ✅ Type guard (string rejection)
- ✅ Hex, random, UUID generators
- ✅ Sentinel repr

**Missing coverage:**
- ⚠️ Batch response parsing (list input to `parse()`)
- ⚠️ Error responses with `data` field populated
- ⚠️ `request_hex`, `request_random`, `request_uuid` variants
- ⚠️ `request_json_hex`, `request_json_random`, `request_json_uuid` variants
- ⚠️ Malformed response handling (missing keys)
- ⚠️ Edge cases: empty params, None ID, large batch responses
- ⚠️ Decimal ID generator (tested indirectly via request auto-increment)

### Testing Tools

- **pytest** with parameterized tests
- **pytest-cov** for coverage reporting
- **tox** for multi-version testing
- **No integration tests** — consistent with the library's pure-function philosophy

---

## 10. Strengths and Weaknesses

### Strengths ✅

1. **Radical Simplicity**: 260 lines, zero dependencies, single responsibility. Easy to understand, audit, and maintain in minutes.

2. **Transport Agnosticism**: Works with any HTTP library (requests, httpx, aiohttp), any protocol (HTTP, WebSocket, raw sockets), and any framework. Users bring their own transport.

3. **Functional Purity**: Pure functions with immutable data structures. No hidden state, side effects (except stateful ID generators), or global configuration. Highly composable and testable.

4. **Strong Type Annotations**: Full Python 3.6+ type hints, mypy validated, NamedTuple response types with structural typing.

5. **Flexible ID Generation**: Four built-in strategies, easily extensible with custom generators via the iterator protocol. Proper sentinel pattern for "no ID provided" vs "ID is None".

6. **Elegant API Design**: `request()` → `Dict`, `request_json()` → `str`. Variants for different ID strategies. Composition over configuration.

7. **First-Class Notifications**: Explicit `notification()` function, clean JSON output (omitted params when empty).

8. **Error-as-Value Pattern**: Returns `Error` objects instead of raising exceptions. Better for batch processing, forces explicit handling, no try/catch needed.

9. **Pattern Matching Ready**: NamedTuple responses support Python 3.10+ structural pattern matching (`match response: case Ok(r, i): ...`).

10. **Production Proven**: Used in real systems (blockchain/crypto clients), MIT licensed, actively maintained.

### Weaknesses ⚠️

1. **No Batch Request Constructor**: Users must manually construct `[request(), request()]` arrays and serialize with `json.dumps`. A `batch()` helper would improve ergonomics.

2. **Lazy Batch Parsing is Surprising**: `parse([...])` returns a `map` object, not a list. `len(parse([...]))` throws `TypeError`. This violates principle of least surprise.

3. **No Response Validation**: Doesn't validate JSON-RPC 2.0 structure. Malformed responses (missing `code`, `message`, `id` keys) cause raw `KeyError` exceptions.

4. **Heavy `Any` Typing**: `result: Any`, `id: Any`, `params: Any` — type safety is structural but not deep. No generic type parameters for result types.

5. **Non-Resettable ID Generators**: Generators are stateful singletons (via `partial`). Can't reset between tests; global counter persists across calls within a process.

6. **No Request-Response Correlation**: No built-in mechanism to match batch responses to their corresponding requests by ID.

7. **Unfamiliar Sentinel Pattern**: `NOID` is non-obvious to new users who expect `None` as the default. Documentation is minimal in-code.

8. **No Error Code Constants**: Users must use raw integers (`-32601`) instead of named constants (`METHOD_NOT_FOUND`).

9. **Minimal In-Code Documentation**: Few docstrings, no inline examples. The code is self-documenting through type annotations, but newcomers need external documentation.

10. **Implicit Tuple→List Conversion**: `params=(1, 2)` silently becomes `params=[1, 2]`. Correct per JSON spec, but could be more explicit.

---

## 11. Key Design Patterns for jrpcx

### Pattern 1: Transport-Agnostic Message Layer

jsonrpcclient's defining pattern — separate message construction from transport entirely:

```
User Code → request() → Dict → json.dumps() → Transport → response text → parse_json() → Ok/Error
```

**Relevance**: jrpcx should adopt this clean separation. The core library should build/parse messages; transport adapters should be separate, pluggable modules.

### Pattern 2: Pure/Impure Function Split

```python
# Pure — all dependencies injected, fully testable
request_pure(id_generator, method, params, id) → Dict

# Impure — convenient defaults via partial application
request = partial(request_impure, decimal())
```

**Relevance**: This pattern is excellent for testing and composition. jrpcx should expose both pure (injectable) and convenient (defaulted) APIs.

### Pattern 3: Sentinel for Absent Values

```python
NOID = Sentinel("NoId")  # Not None — None might be valid
```

**Relevance**: jrpcx (in Java/Kotlin) can use sealed types or `Optional` more naturally, but the underlying insight is important: distinguish "not provided" from "explicitly null."

### Pattern 4: Error-as-Value (Not Exception)

```python
response = parse(data)
if isinstance(response, Ok): ...
elif isinstance(response, Error): ...
```

**Relevance**: In Java, this maps to sealed interfaces or `Either<Error, Ok>` patterns. Consider whether jrpcx should return result types vs throw exceptions — jsonrpcclient's approach is superior for batch processing.

### Pattern 5: Function Composition for Variants

```python
request_json = compose(json.dumps, request)
```

**Relevance**: In Java/Kotlin, this maps to method chaining or decorator patterns. The principle of building complex APIs from simple composable pieces is universal.

### Pattern 6: Iterator-Based ID Generation

```python
def decimal(start=1) -> Iterator[int]:
    yield from count(start)
```

**Relevance**: jrpcx should support pluggable ID generation via a similar interface (`Supplier<RequestId>` in Java). Multiple strategies (sequential, UUID, custom) should be trivially swappable.

---

## 12. Relevance to jrpcx

### What to Adopt

| Pattern | How to Apply in jrpcx |
|---------|-----------------------|
| **Transport agnosticism** | Core jrpcx module should be pure message building/parsing. Transport adapters (HTTP, WebSocket) as separate, optional modules. |
| **Pluggable ID generation** | Provide a `IdGenerator` interface with built-in implementations (sequential, UUID, random). Allow custom generators. |
| **Immutable response types** | Use Java records or sealed interfaces for `Ok`/`Error` response types. Immutability is essential. |
| **Error-as-value for batch** | For batch responses, return a list of result types rather than throwing on first error. Individual results can be Ok or Error. |
| **First-class notifications** | Notifications should be a distinct type/method, not a request with a null ID. |
| **Conditional param omission** | Omit `params` key when no parameters provided (cleaner JSON, spec-compliant). |
| **Composition over configuration** | Build complex APIs from simple, composable primitives rather than configuration objects. |
| **Sentinel / explicit absence** | Use `Optional<T>` or sealed types to distinguish "not provided" from "explicitly null" for ID and params. |

### What to Improve Upon

| jsonrpcclient Limitation | jrpcx Improvement |
|--------------------------|-------------------|
| **No batch request builder** | Provide a fluent `BatchRequest.builder()` API that constructs the array and tracks ID→request mapping. |
| **Lazy map() for batch responses** | Return a concrete `List<Response>` with indexed access and ID-based lookup. |
| **No response validation** | Validate JSON-RPC 2.0 structure before parsing. Return clear errors for malformed responses. |
| **Heavy `Any` typing** | Use Java generics for result types: `Ok<T>` where T is the deserialized result type. |
| **No error code constants** | Define an enum or constants class for standard JSON-RPC error codes. |
| **No request-response correlation** | Batch API should correlate responses to requests by ID automatically. |
| **No retry/timeout** | Transport adapters should support configurable retry and timeout policies. |
| **Stateful global ID generators** | ID generators should be instance-scoped (per-client), not global singletons. |
| **No request validation** | Validate method names, param types before constructing requests. Fail fast on invalid input. |

### What to Avoid

| Anti-Pattern | Why |
|-------------|-----|
| **Returning different types from same function** | `parse()` returns `Response` for single, `Iterable[Response]` for batch — confusing. jrpcx should have separate `parseOne()` / `parseBatch()` or always return a list. |
| **Silent type coercion** | Tuple→list conversion is implicit. jrpcx should be explicit about parameter type handling. |
| **No graceful error degradation** | Missing response fields cause raw `KeyError`. jrpcx should always return structured errors, never leak implementation exceptions. |
| **Minimal documentation** | jrpcx should have comprehensive Javadoc on all public APIs with usage examples. |

### Architectural Lessons

1. **Simplicity wins**: jsonrpcclient proves that a JSON-RPC client library can be incredibly small and still be useful. jrpcx's core message layer should aspire to similar simplicity.

2. **Transport is not the library's job**: The v4.0 rewrite that stripped all transport backends was the right call. jrpcx should follow suit — core module handles messages, adapters handle transport.

3. **Functional patterns translate well**: Pure functions, immutable types, and composition work in any language. Java records, sealed interfaces, and functional interfaces can express the same patterns.

4. **ID generation is a first-class concern**: Four built-in strategies with a pluggable interface is the right level of flexibility. jrpcx should match or exceed this.

5. **Error handling philosophy matters**: The error-as-value approach is particularly strong for batch processing. jrpcx should support both patterns: error-as-value for batch operations, optional exception-throwing for single requests where it's more ergonomic.

---

## Appendix A: Version History (Key Milestones)

| Version | Date | Changes |
|---------|------|---------|
| **4.0.3** | Feb 2023 | Build system migration to pyproject.toml |
| **4.0.2** | Nov 2021 | Documentation updates |
| **4.0.1** | Sep 2021 | FAQ page added |
| **4.0.0** | Sep 2021 | **Complete rewrite** — removed all transport backends, functional API, NamedTuple responses |
| **3.x** | Pre-2021 | Full transport layer (AiohttpClient, TornadoClient, Socket, ZMQ), config modules, logging |

The v3→v4 transition is a case study in intentional simplification. The library went from batteries-included to single-purpose message builder, gaining clarity and reducing maintenance burden.

## Appendix B: Real-World Integration Example

```python
from jsonrpcclient import request, parse_json, Ok
import httpx

class EthereumClient:
    """Example: Ethereum JSON-RPC client built on jsonrpcclient"""
    
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.Client()

    def call(self, method: str, params: list = None, id: int = 1):
        req = request(method, params=params or [], id=id)
        response = self.client.post(self.url, json=req)
        return parse_json(response.text)

    def get_balance(self, address: str, block: str = "latest"):
        result = self.call("eth_getBalance", [address, block])
        if isinstance(result, Ok):
            return int(result.result, 16)
        raise RuntimeError(f"RPC Error: {result.message}")
```

This shows jsonrpcclient's ideal use case: a thin message layer inside a domain-specific client library.

## Appendix C: API Quick Reference

| Function | Returns | Purpose |
|----------|---------|---------|
| `request(method, params, id)` | `Dict` | Auto-increment decimal ID |
| `request_hex(...)` | `Dict` | Auto-increment hex ID |
| `request_random(...)` | `Dict` | Random 8-char string ID |
| `request_uuid(...)` | `Dict` | UUID v4 ID |
| `request_json(...)` | `str` | JSON string, decimal ID |
| `notification(method, params)` | `Dict` | No ID (fire-and-forget) |
| `notification_json(...)` | `str` | JSON string notification |
| `parse(dict_or_list)` | `Ok\|Error\|Iterable` | Parse response dict(s) |
| `parse_json(string)` | `Ok\|Error\|Iterable` | Parse JSON string response |
| `id_generators.decimal()` | `Iterator[int]` | 1, 2, 3, ... |
| `id_generators.hexadecimal()` | `Iterator[str]` | 1, 2, ..., a, b, ... |
| `id_generators.random()` | `Iterator[str]` | Random 8-char strings |
| `id_generators.uuid()` | `Iterator[str]` | UUID v4 strings |

---

**Report Generated**: July 2025
**Library Version**: 4.0.3
**Python Support**: 3.6+
**License**: MIT
