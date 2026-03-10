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
└── ServerError
    ├── MethodNotFoundError
    ├── InvalidParamsError
    ├── InternalError
    └── ApplicationError
```

## API Reference

### Clients

| Class | Description |
|-------|-------------|
| `jrpcx.Client` | Synchronous JSON-RPC client (alias for `JSONRPCClient`) |
| `jrpcx.AsyncClient` | Asynchronous JSON-RPC client (alias for `AsyncJSONRPCClient`) |

### Transports

| Class | Description |
|-------|-------------|
| `HTTPTransport` | Sync HTTP transport (httpx) |
| `AsyncHTTPTransport` | Async HTTP transport (httpx) |
| `MockTransport` | Sync mock for testing |
| `AsyncMockTransport` | Async mock for testing |
| `BaseTransport` | Abstract base for custom transports |
| `AsyncBaseTransport` | Abstract base for async custom transports |

## License

MIT
