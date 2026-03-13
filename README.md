# jrpcx

A modern Python JSON-RPC 2.0 client inspired by [httpx](https://www.python-httpx.org/).

## Installation

```bash
pip install jrpcx
```

## Quick Start

```python
import jrpcx

# Proxy-first API — call methods directly as attributes
with jrpcx.Client("https://rpc.example.com") as client:
    result = client.eth_blockNumber()
    balance = client.eth_getBalance("0x...", "latest")
```

## Features

- **Proxy-first API**: Call RPC methods as Python attributes — `client.method()`
- **Sync & Async**: Full `JSONRPCClient` and `AsyncJSONRPCClient`
- **Type-safe**: Strict `mypy` compliance, `py.typed` marker
- **httpx-powered**: Built on [httpx](https://www.python-httpx.org/) for HTTP transport
- **Pluggable transports**: Custom transports for WebSocket, IPC, etc.
- **Event hooks**: Observe requests, responses, and errors
- **Notifications**: Fire-and-forget calls via `client.notify.method()`
- **Batch requests**: Group multiple calls in a single round-trip
- **Middleware**: Composable request/response pipeline
- **Retry middleware**: Built-in retry with exponential backoff
- **Logging helpers**: One-liner request/response logging hooks
- **Typed errors**: Auto-register custom `ServerError` subclasses by code
- **Custom serialization**: `json_encoder` for Decimal, datetime, etc.
- **Typed responses**: Deserialize results into dataclasses / Pydantic models
- **MockTransport**: Test your code without a server

## Usage

### Proxy API (Default)

```python
import jrpcx

with jrpcx.Client("https://rpc.example.com") as client:
    # Positional params → JSON array
    result = client.add(1, 2)

    # Keyword params → JSON object
    greeting = client.greet(name="World")

    # Nested namespaces
    methods = client.system.listMethods()
```

### Explicit `.call()` for Reserved Names

```python
# "close" is a reserved name (it closes the client)
result = client.call("close", {"reason": "done"})
```

### Async

```python
import jrpcx

async with jrpcx.AsyncClient("https://rpc.example.com") as client:
    result = await client.eth_blockNumber()
    balance = await client.eth_getBalance("0x...", "latest")
```

### Without Context Manager

```python
import jrpcx

client = jrpcx.Client("https://rpc.example.com")
result = client.add(1, 2)
client.close()
```

### Configuration

```python
import jrpcx

client = jrpcx.Client(
    "https://rpc.example.com",
    headers={"Authorization": "Bearer token"},
    auth=("user", "pass"),
    timeout=30.0,
)
```

### Error Handling

```python
import jrpcx

with jrpcx.Client("https://rpc.example.com") as client:
    try:
        client.nonexistent_method()
    except jrpcx.MethodNotFoundError as e:
        print(f"Method not found: {e}")
    except jrpcx.TimeoutError:
        print("Request timed out")
    except jrpcx.TransportError as e:
        print(f"Transport error: {e}")
    except jrpcx.JSONRPCError as e:
        print(f"JSON-RPC error: {e}")
```

### Event Hooks

```python
import jrpcx

def log_request(method, params):
    print(f"→ {method}({params})")

def log_response(response):
    print(f"← {response.result}")

client = jrpcx.Client(
    "https://rpc.example.com",
    event_hooks={
        "request": [log_request],
        "response": [log_response],
    },
)
```

### Notifications

Send fire-and-forget calls (no response, no `id` in the JSON-RPC request):

```python
import jrpcx

with jrpcx.Client("https://rpc.example.com") as client:
    client.notify.log_event("user_login", user_id=42)

    # Nested namespaces work
    client.notify.system.shutdown()
```

Async:

```python
async with jrpcx.AsyncClient("https://rpc.example.com") as client:
    await client.notify.log_event("user_login", user_id=42)
```

### Batch Requests

Group multiple calls into a single round-trip:

```python
import jrpcx

with jrpcx.Client("https://rpc.example.com") as client:
    with client.batch() as batch:
        batch.add(1, 2)
        batch.subtract(10, 5)
        batch.notify.log("batch started")  # notification inside batch

    # Access results after the batch context exits
    print(batch.results.values())        # [3, 5]
    print(batch.results.successes)       # list of successful Response objects
    print(batch.results.errors)          # list of error Response objects
    print(batch.results.by_id("1"))      # lookup by request id
```

Async:

```python
async with jrpcx.AsyncClient("https://rpc.example.com") as client:
    async with client.batch() as batch:
        batch.add(1, 2)
        batch.subtract(10, 5)

    print(batch.results.values())
```

### Middleware

Add composable middleware to the client. Each middleware receives the outgoing request and a `call_next` callable:

```python
import jrpcx

def timing_middleware(request, call_next):
    import time
    start = time.monotonic()
    response = call_next(request)
    elapsed = time.monotonic() - start
    print(f"{request.method} took {elapsed:.3f}s")
    return response

client = jrpcx.Client(
    "https://rpc.example.com",
    middleware=[timing_middleware],
)
```

Chain multiple middleware — they execute in the order provided:

```python
client = jrpcx.Client(
    "https://rpc.example.com",
    middleware=[auth_middleware, timing_middleware, cache_middleware],
)
```

### Retry Middleware

Built-in retry middleware with configurable backoff:

```python
from jrpcx.middleware import retry, ExponentialBackoff

client = jrpcx.Client(
    "https://rpc.example.com",
    middleware=[
        retry(
            max_retries=3,
            backoff=ExponentialBackoff(base=0.5, max_delay=10.0),
            retry_codes=[-32000, -32603],  # server error codes to retry
        ),
    ],
)
```

For async clients use `async_retry`:

```python
from jrpcx.middleware import async_retry, ExponentialBackoff

client = jrpcx.AsyncClient(
    "https://rpc.example.com",
    middleware=[
        async_retry(max_retries=3, backoff=ExponentialBackoff()),
    ],
)
```

### Logging Helpers

One-liner request/response logging via event hooks:

```python
import logging
import jrpcx

logger = logging.getLogger("jrpcx")

client = jrpcx.Client(
    "https://rpc.example.com",
    event_hooks={
        "request": [jrpcx.log_request(logger)],
        "response": [jrpcx.log_response(logger)],
    },
)
```

### Typed Error Deserialization

Subclass `jrpcx.ServerError` with a `CODE` class attribute to auto-register custom error types. When the server returns that code, jrpcx raises your subclass:

```python
import jrpcx

class InsufficientFunds(jrpcx.ServerError):
    CODE = -32001

try:
    client.withdraw(amount=9999)
except InsufficientFunds as e:
    print(e.data)  # server-provided detail
```

### Custom Serialization

Pass a custom `json_encoder` for types that `json.dumps` doesn't handle natively:

```python
import decimal
import jrpcx

def decimal_encoder(obj):
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

client = jrpcx.Client(
    "https://rpc.example.com",
    json_encoder=decimal_encoder,
)
client.transfer(amount=decimal.Decimal("1.005"))
```

### Typed Response Deserialization

Pass `result_type` to `.call()` to deserialize the result into a dataclass or Pydantic model:

```python
from dataclasses import dataclass
import jrpcx

@dataclass
class Block:
    number: int
    hash: str

with jrpcx.Client("https://rpc.example.com") as client:
    block = client.call("eth_getBlockByNumber", ["latest", False], result_type=Block)
    print(block.number)  # int, not dict
```

### Testing with MockTransport

```python
import jrpcx

def handler(request):
    if request.method == "add":
        a, b = request.params
        return jrpcx.Response(id=request.id, result=a + b)
    return jrpcx.Response(
        id=request.id,
        error=jrpcx.ErrorData(code=-32601, message="Not found"),
    )

transport = jrpcx.MockTransport(handler)
client = jrpcx.Client("http://test", transport=transport)
assert client.add(1, 2) == 3
```

### Custom Transport

```python
import jrpcx

class MyTransport(jrpcx.BaseTransport):
    def handle_request(self, request: bytes) -> bytes:
        # Send request bytes, return response bytes
        ...

client = jrpcx.Client("custom://endpoint", transport=MyTransport())
```

## Exception Hierarchy

```
JSONRPCError
├── TransportError
│   ├── TimeoutError
│   ├── ConnectionError
│   └── HTTPStatusError
├── ProtocolError
│   ├── ParseError
│   ├── InvalidRequestError
│   └── InvalidResponseError
└── ServerError                  ← subclass with CODE to auto-register
    ├── MethodNotFoundError
    ├── InvalidParamsError
    ├── InternalError
    ├── ApplicationError
    └── <your subclass>          (auto-registered by CODE)
```

## API Reference

### Clients

| Class | Description |
|-------|-------------|
| `jrpcx.Client` | Synchronous JSON-RPC client (alias for `JSONRPCClient`) |
| `jrpcx.AsyncClient` | Asynchronous JSON-RPC client (alias for `AsyncJSONRPCClient`) |
| `jrpcx.BatchContext` | Context manager returned by `client.batch()` |
| `jrpcx.BatchResults` | Results container with `.successes`, `.errors`, `.by_id()`, `.values()` |

### Transports

| Class | Description |
|-------|-------------|
| `HTTPTransport` | Sync HTTP transport (httpx) |
| `AsyncHTTPTransport` | Async HTTP transport (httpx) |
| `MockTransport` | Sync mock for testing |
| `AsyncMockTransport` | Async mock for testing |
| `BaseTransport` | Abstract base for custom transports |
| `AsyncBaseTransport` | Abstract base for async custom transports |

### Middleware

| Symbol | Description |
|--------|-------------|
| `jrpcx.middleware.retry` | Sync retry middleware factory |
| `jrpcx.middleware.async_retry` | Async retry middleware factory |
| `jrpcx.middleware.ExponentialBackoff` | Exponential backoff strategy |

### Helpers

| Symbol | Description |
|--------|-------------|
| `jrpcx.log_request(logger)` | Returns an event hook that logs outgoing requests |
| `jrpcx.log_response(logger)` | Returns an event hook that logs incoming responses |

## License

MIT
