# HTTPX Design Patterns - Quick Reference

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       Public API                             │
│  httpx.get() httpx.post() httpx.Client() httpx.AsyncClient()│
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
    ┌──────────────┐           ┌─────────────────┐
    │   Client     │           │  AsyncClient    │
    │  (sync I/O)  │           │  (async I/O)    │
    └──────────────┘           └─────────────────┘
          │                             │
          └──────────────┬──────────────┘
                         ▼
            ┌────────────────────────┐
            │    BaseClient          │
            │  (shared config logic) │
            └────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Request  │  │ Response │  │ Headers  │
    │          │  │          │  │ Cookies  │
    └──────────┘  └──────────┘  └──────────┘
          │              │
          └──────────────┼──────────────┐
                         ▼              ▼
               ┌──────────────────┐  ┌─────────────┐
               │   Transport      │  │  Exceptions │
               │   (abstraction)  │  │  (hierarchy)│
               └──────────────────┘  └─────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   ┌────────────┐ ┌──────────┐ ┌──────────┐
   │HTTPTransport│ │MockTransport│ WSGITransport
   └────────────┘ └──────────┘ └──────────┘
```

---

## 1. Sync/Async Duality Pattern

### Structure
```
BaseClass (shared config & logic)
├── SyncClass (sync I/O)
│   └── def method() -> Result
└── AsyncClass (async I/O)
    └── async def method() -> Result
```

### Code Reuse Strategy
- **Shared**: Configuration, request building, response parsing
- **Different**: I/O operations (transport.handle_request vs transport.handle_async_request)
- **Dual Methods**: `def read()` and `async def aread()` on same object

### For jrpcx
```python
class BaseJSONRPCClient:
    def build_request(self, method, params) -> Request:
        # Build JSON-RPC request
        pass
    
    def parse_response(self, response) -> Result:
        # Parse JSON-RPC response
        pass

class JSONRPCClient(BaseJSONRPCClient):
    def call(self, method, params) -> Result:
        request = self.build_request(method, params)
        response = self._transport.handle_request(request)
        return self.parse_response(response)

class AsyncJSONRPCClient(BaseJSONRPCClient):
    async def call(self, method, params) -> Result:
        request = self.build_request(method, params)
        response = await self._transport.handle_async_request(request)
        return self.parse_response(response)
```

---

## 2. Transport Abstraction

### Interface Design
```python
class BaseTransport:
    def handle_request(self, request: Request) -> Response:
        raise NotImplementedError()
    
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self): pass

class AsyncBaseTransport:
    async def handle_async_request(self, request: Request) -> Response:
        raise NotImplementedError()
    
    async def __aenter__(self): return self
    async def __aexit__(self, *args): await self.aclose()
    async def aclose(self): pass
```

### Benefits
- Easy to mock for testing
- Support multiple transport types (HTTP, WebSocket, IPC, etc.)
- URL pattern routing for different endpoints

---

## 3. Client Configuration Pattern

### Using USE_CLIENT_DEFAULT Sentinel
```python
class Client:
    def __init__(self, timeout=5.0, auth=None):
        self.timeout = timeout
        self.auth = auth
    
    def request(self, url, timeout=USE_CLIENT_DEFAULT, auth=USE_CLIENT_DEFAULT):
        # Distinguish "not provided" vs "explicitly None"
        if isinstance(timeout, UseClientDefault):
            timeout = self.timeout
        if isinstance(auth, UseClientDefault):
            auth = self.auth
```

### Why NOT just use None?
- `None` means "explicitly disable this setting"
- `USE_CLIENT_DEFAULT` means "use the client's default"
- Prevents accidental override of defaults

### For jrpcx
```python
class JSONRPCClient:
    def __init__(self, base_url, timeout=30.0, headers=None):
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}
    
    def call(self, method, params, timeout=USE_CLIENT_DEFAULT, headers=USE_CLIENT_DEFAULT):
        # Merge with client defaults
        final_timeout = self.timeout if isinstance(timeout, UseClientDefault) else timeout
        final_headers = {**self.headers, **(headers or {})} if not isinstance(headers, UseClientDefault) else self.headers
```

---

## 4. Event Hooks Pattern

### Usage
```python
def log_request(request):
    print(f"→ {request.method} {request.url}")

def log_response(response):
    print(f"← {response.status_code}")

client = Client(
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    }
)
```

### For jrpcx
```python
class JSONRPCClient:
    def __init__(self, ..., event_hooks=None):
        self.event_hooks = {
            "before_request": [],
            "after_response": [],
            **(event_hooks or {})
        }
    
    def call(self, method, params):
        for hook in self.event_hooks["before_request"]:
            hook(method, params)
        
        response = self._send(method, params)
        
        for hook in self.event_hooks["after_response"]:
            hook(response)
        
        return response
```

---

## 5. Exception Hierarchy

### HTTPX Example
```
HTTPError
├── RequestError
│   ├── TransportError
│   │   ├── TimeoutException
│   │   ├── NetworkError
│   │   └── ProtocolError
│   ├── DecodingError
│   └── TooManyRedirects
└── HTTPStatusError
```

### For jrpcx
```
JSONRPCError
├── TransportError (network/connection issues)
├── ParseError (invalid JSON-RPC response)
├── MethodError (method not found, -32601)
├── InvalidParams (invalid params, -32602)
├── InternalError (server error, -32603)
└── ServerError (application-specific, -32000 to -32099)
```

**Key: Preserve context (request, response)**

---

## 6. Type Safety Pattern

### Type Aliases
```python
URLTypes = Union[URL, str]
HeaderTypes = Union[Headers, Mapping[str, str], Sequence[Tuple[str, str]]]
TimeoutTypes = Union[float, Tuple[float, float, float, float], Timeout]
AuthTypes = Union[Tuple[str, str], Callable[[Request], Request], Auth]
```

### Benefits
- IDE autocomplete
- Type checker support (mypy, pyright)
- Clear parameter documentation

---

## 7. Testing Patterns

### MockTransport
```python
def handler(request: Request) -> Response:
    if "users" in request.url.path:
        return httpx.Response(200, json={"users": []})
    return httpx.Response(404)

transport = httpx.MockTransport(handler)
client = httpx.Client(transport=transport)
response = client.get("https://api.example.com/users")
```

### For jrpcx
```python
def handler(request: Request) -> Response:
    data = request.json()
    if data["method"] == "eth_getBalance":
        return Response(200, json={
            "jsonrpc": "2.0",
            "id": data["id"],
            "result": "0x123456"
        })

transport = MockTransport(handler)
client = JSONRPCClient(transport=transport, base_url="http://localhost:8545")
```

---

## 8. Request Building & Merging

### Pattern
```python
# Client has defaults
client = Client(
    headers={"Authorization": "Bearer token"},
    params={"api_version": "v1"},
)

# Per-request overrides/additions
response = client.get(
    "/users",
    headers={"X-Custom": "value"},  # Merged
    params={"filter": "active"},    # Merged
)

# Final headers: Authorization + X-Custom
# Final params: api_version + filter
```

### Implementation
```python
def _merge_headers(self, headers):
    merged = dict(self.headers)
    if headers:
        merged.update(headers)
    return merged

def _merge_params(self, params):
    merged = dict(self.params)
    if params:
        merged.update(params)
    return merged
```

---

## 9. Streaming API

### Pattern
```python
# Context manager ensures cleanup
with httpx.stream("GET", url) as response:
    for chunk in response.iter_bytes():
        process(chunk)

# Async variant
async with asyncio.to_thread(httpx.stream, "GET", url) as response:
    async for chunk in response.aiter_bytes():
        process(chunk)
```

### For jrpcx
```python
with client.stream("eth_getLogs", params={...}) as response:
    for log in response.iter_lines():
        process_log(json.loads(log))
```

---

## 10. Connection Pooling & Reuse

### Pattern
```python
# Bad: New connection for each request
response1 = httpx.get(url1)
response2 = httpx.get(url2)

# Good: Reuse connection
with httpx.Client() as client:
    response1 = client.get(url1)
    response2 = client.get(url2)
    # Same connection pool used
```

### For jrpcx
```python
# Bad
for i in range(1000):
    result = jrpcx.call("eth_blockNumber", base_url)

# Good
async with jrpcx.AsyncClient(base_url) as client:
    tasks = [client.call("eth_blockNumber") for i in range(1000)]
    results = await asyncio.gather(*tasks)
    # All requests use pooled connections
```

---

## Key Takeaways

1. **Separate Concerns**: BaseClass (config) vs Client (I/O)
2. **Minimal Duplication**: Share business logic, only differ on I/O
3. **Transport Abstraction**: Easy to test and extend
4. **Type Safety**: Full annotations throughout
5. **Sentinel Values**: USE_CLIENT_DEFAULT for distinguishing intent
6. **Error Context**: Preserve request/response in exceptions
7. **Event Hooks**: Extensibility without tight coupling
8. **Testing First**: MockTransport baked in
9. **Connection Reuse**: Context managers for resource management
10. **Convenience API**: Simple functions + powerful client class

