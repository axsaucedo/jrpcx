# HTTPX Research Analysis - Executive Summary

## Documents Created

This research package includes three detailed documents:

1. **HTTPX_ANALYSIS.md** (1,272 lines, 37 KB)
   - Comprehensive deep-dive into HTTPX architecture
   - 10 major sections covering all aspects
   - Code examples throughout
   - Patterns applicable to jrpcx

2. **HTTPX_QUICK_REFERENCE.md** (380 lines, 11 KB)
   - Visual quick reference guide
   - Architecture diagrams
   - Pattern summaries
   - Practical examples

3. **RESEARCH_SUMMARY.md** (this file)
   - Executive overview
   - Key findings
   - Recommendations for jrpcx

---

## Key Findings

### 1. The Sync/Async Duality Solution ⭐ MOST IMPORTANT

HTTPX solves the dual API problem through **class hierarchy with minimal duplication**:

```
BaseClient (abstract, shared logic)
├── Client (sync: client.request() → response)
└── AsyncClient (async: await client.request() → response)
```

**Why this works:**
- Configuration and business logic shared in BaseClient
- Only the actual I/O differs between Client and AsyncClient
- Request/Response objects work with both sync and async methods
- Clear, predictable API surface

**For jrpcx:** Apply the same pattern with BaseJSONRPCClient, JSONRPCClient, and AsyncJSONRPCClient.

---

### 2. Transport Abstraction (Testing Enabler) ⭐ CRITICAL FOR TESTING

```python
# Simple interface
class BaseTransport:
    def handle_request(request: Request) -> Response: ...

class AsyncBaseTransport:
    async def handle_async_request(request: Request) -> Response: ...
```

**Benefits:**
- Easy to test: MockTransport just returns mocked responses
- Easy to extend: WSGI/ASGI transports for testing without network
- Easy to customize: Multiple transports for different endpoints

**For jrpcx:** Create BaseJSONRPCTransport interface, implement HTTP transport, allow MockTransport for testing.

---

### 3. Configuration Management Pattern

**Problem:** How to distinguish between:
- "Not provided, use client default"
- "Explicitly set to None"

**Solution:** Sentinel value `USE_CLIENT_DEFAULT`:

```python
client = Client(timeout=5.0)

# This uses client's default timeout
response = client.get(url)

# This overrides with 10.0
response = client.get(url, timeout=10.0)

# This means "use client default" (avoids accidental override)
response = client.get(url, timeout=USE_CLIENT_DEFAULT)
```

**For jrpcx:** Use same pattern for timeout, headers, auth, etc.

---

### 4. Request/Response as First-Class Objects

Instead of just returning bytes, HTTPX models HTTP as objects:

```python
request = client.build_request("GET", url)
# Can inspect and modify before sending
request.headers["X-Custom"] = "value"
response = client.send(request)

# Response is rich with methods
response.status_code       # Status
response.content           # Full body
response.text              # Decoded text
response.json()            # Parsed JSON
response.headers           # Headers dict
response.history           # Redirect history
response.elapsed           # Timing info
response.raise_for_status() # Throw on 4xx/5xx
```

**For jrpcx:** Model JSON-RPC Request and Response objects with helpful methods.

---

### 5. Error Hierarchy with Context

Clear exception hierarchy preserves request/response context:

```python
try:
    response = client.get(url)
except httpx.HTTPError as exc:
    print(exc.request)        # The request that failed
    if hasattr(exc, 'response'):
        print(exc.response)    # The response received
```

Exception hierarchy:
- **RequestError**: Problem during request (timeout, network, etc.)
- **HTTPStatusError**: Server returned 4xx/5xx

**For jrpcx:** Create JSONRPCError with subclasses for different failure modes, always preserve context.

---

### 6. Type Safety Throughout

Full type annotations everywhere:

```python
def request(
    self,
    method: str,
    url: URL | str,
    *,
    params: QueryParamTypes | None = None,
    content: RequestContent | None = None,
    json: typing.Any | None = None,
    headers: HeaderTypes | None = None,
    timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
) -> Response:
```

**Type aliases for clarity:**
- `URLTypes = Union[URL, str]`
- `HeaderTypes = Union[Headers, Mapping[str, str], Sequence[Tuple[str, str]]]`
- `TimeoutTypes = Union[float, Tuple[float, float, float, float], Timeout]`

**For jrpcx:** Define clear type aliases, annotate all methods, enable mypy checking.

---

### 7. Event Hooks for Extensibility

Without tight coupling:

```python
def track_metrics(response):
    metrics.record(response.elapsed.total_seconds())

client = Client(
    event_hooks={
        "request": [log_request],
        "response": [log_response, track_metrics],
    }
)
```

**For jrpcx:** Add hooks for:
- `before_call`: Log method, inject request ID
- `after_response`: Log response, record metrics
- `on_error`: Log failures

---

### 8. Connection Pooling by Default

```python
# Bad: New connection each time
httpx.get(url1)
httpx.get(url2)

# Good: Connection reuse
with httpx.Client() as client:
    client.get(url1)  # Reuses connection
    client.get(url2)  # Reuses connection
```

**For jrpcx:** Same pattern - clients should be reused for performance.

---

### 9. Streaming Support

Two patterns:

```python
# Load into memory (default)
response = client.get(url)
print(response.content)

# Stream (for large responses)
with client.stream("GET", url) as response:
    for chunk in response.iter_bytes():
        process(chunk)
```

**For jrpcx:** Support streaming JSON-RPC responses for efficient bulk operations.

---

### 10. Testing Support Built-in

```python
# Mock responses
def handler(request):
    return Response(200, json={"result": "0x123"})

transport = MockTransport(handler)
client = Client(transport=transport)
response = client.get(url)  # Returns mocked response
```

**For jrpcx:** Same pattern enables easy testing without real RPC endpoints.

---

## Recommendations for jrpcx

### Core Architecture

```python
# Base class: shared logic
class BaseJSONRPCClient:
    def build_request(self, method, params) -> Request:
        return Request("POST", self.base_url, json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._next_id(),
        })
    
    def parse_response(self, response) -> Result:
        data = response.json()
        if "error" in data:
            raise JSONRPCError(data["error"])
        return data.get("result")

# Sync client
class JSONRPCClient(BaseJSONRPCClient):
    def call(self, method, params) -> Result:
        request = self.build_request(method, params)
        response = self._transport.handle_request(request)
        return self.parse_response(response)

# Async client
class AsyncJSONRPCClient(BaseJSONRPCClient):
    async def call(self, method, params) -> Result:
        request = self.build_request(method, params)
        response = await self._transport.handle_async_request(request)
        return self.parse_response(response)
```

### Transport Interface

```python
class BaseJSONRPCTransport:
    def handle_request(self, request: Request) -> Response:
        raise NotImplementedError()

class AsyncBaseJSONRPCTransport:
    async def handle_async_request(self, request: Request) -> Response:
        raise NotImplementedError()

class HTTPTransport(BaseJSONRPCTransport):
    def handle_request(self, request: Request) -> Response:
        # Use httpx for actual HTTP
        response = httpx.post(self.url, json=request.json())
        return Response(response.status_code, 
                       content=response.content, 
                       headers=response.headers)
```

### Type Safety

```python
from typing import Any, Dict, Union, Optional

JSONValue = Union[str, int, float, bool, None, Dict[str, Any], list]
JSONParams = Optional[Union[Dict[str, Any], list]]
MethodResult = Any

def call(
    self,
    method: str,
    params: JSONParams = None,
    timeout: Optional[float] = USE_CLIENT_DEFAULT,
) -> MethodResult:
    ...
```

### Error Hierarchy

```python
class JSONRPCError(Exception):
    def __init__(self, message: str, code: int = -32603):
        self.message = message
        self.code = code
        self.request: Optional[Request] = None
        self.response: Optional[Response] = None

class MethodNotFound(JSONRPCError):
    def __init__(self): super().__init__("Method not found", -32601)

class InvalidParams(JSONRPCError):
    def __init__(self): super().__init__("Invalid parameters", -32602)

class TransportError(JSONRPCError):
    pass
```

### Convenience API

```python
# Function-level API for simple use cases
def call(method: str, base_url: str, params: JSONParams = None) -> MethodResult:
    with JSONRPCClient(base_url) as client:
        return client.call(method, params)

# Client-based API for reuse
async with AsyncJSONRPCClient(base_url) as client:
    result1 = await client.call("eth_blockNumber")
    result2 = await client.call("eth_getBalance", ["0x..."])
```

---

## Project Structure Recommendation

```
jrpcx/
├── __init__.py              # Public API exports
├── _client.py               # Client, AsyncClient, BaseClient
├── _models.py               # Request, Response, JSONRPCError
├── _transports/
│   ├── __init__.py
│   ├── base.py             # BaseTransport, AsyncBaseTransport
│   ├── http.py             # HTTPTransport, AsyncHTTPTransport
│   └── mock.py             # MockTransport (for testing)
├── _types.py                # Type aliases
├── _config.py               # Configuration classes (Timeout, etc.)
└── _auth.py                 # Authentication schemes

tests/
├── test_client.py
├── test_async_client.py
├── test_transports.py
├── conftest.py             # pytest fixtures, mocks
```

---

## Success Metrics

After implementing jrpcx with these patterns:

1. ✅ **Single codebase, dual API**: `JSONRPCClient` and `AsyncJSONRPCClient` share >80% logic
2. ✅ **Testable without network**: MockTransport enables unit testing
3. ✅ **Type-safe**: mypy --strict passes
4. ✅ **Performant**: Connection pooling by default
5. ✅ **Extensible**: Event hooks, custom transports, custom auth
6. ✅ **Developer-friendly**: Clear API, good error messages, helpful docs

---

## Further Reading

Within the generated documents, focus on:

1. **HTTPX_ANALYSIS.md:**
   - Section 3: Sync/Async Duality Architecture (detailed)
   - Section 6: Transport Layer Architecture (critical for extensibility)
   - Section 7: Error Handling (comprehensive exception design)
   - Section 10: Testing Patterns (unit testing approach)

2. **HTTPX_QUICK_REFERENCE.md:**
   - Pattern #1: Sync/Async Duality
   - Pattern #2: Transport Abstraction
   - Pattern #3: Client Configuration
   - Pattern #7: Testing Patterns

---

## Conclusion

HTTPX demonstrates that building a dual sync/async library doesn't require code duplication. By using class inheritance (shared BaseClient) and strategic use of transports, you can maintain a single, coherent API surface while supporting both synchronous and asynchronous programming models.

The key insights for jrpcx:

1. **Separation of concerns**: BaseClient handles config/logic, Client/AsyncClient handle I/O
2. **Abstraction layers**: Transport abstraction enables testing and extensibility
3. **Type safety**: Comprehensive type hints prevent bugs and improve IDE support
4. **User ergonomics**: Simple for 80% of use cases (function API), powerful for 20% (client API)
5. **Testing**: MockTransport pattern makes testing trivial

These patterns have been battle-tested in production (httpx is widely used), so applying them to jrpcx should result in a robust, maintainable library.
