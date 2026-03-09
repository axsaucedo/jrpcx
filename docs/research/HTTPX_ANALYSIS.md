# HTTPX Architecture & Design Patterns Analysis

## Executive Summary

HTTPX is a modern HTTP client library for Python that balances ergonomics with power. It provides a unified, intuitive API for both synchronous and asynchronous HTTP operations with minimal code duplication. The codebase demonstrates excellent patterns for designing SDKs with rich feature sets while maintaining simplicity and type safety.

---

## 1. Project Overview

### What is HTTPX?

**HTTPX** is a fully-featured HTTP client library for Python 3.9+ that bridges the gap between the simplicity of `requests` and modern async/await patterns. It serves as a "next-generation HTTP client" with:

- Full requests-compatible API
- Native async/await support
- HTTP/1.1 and HTTP/2 support
- Integrated command-line client
- 100% test coverage
- Full type annotations

**Philosophy:**
- User-friendly and "requests-like" API for sync operations
- First-class async support without API fragmentation
- Type-safe with comprehensive type hints
- Explicit, intuitive parameter handling
- Connection pooling and performance by default

**Key Design Goals:**
1. **Familiarity**: API compatible with `requests` for ease of migration
2. **Async-first Design**: Async support built in from the ground up (not bolted on)
3. **Type Safety**: Comprehensive type hints throughout the library
4. **Strictness**: Timeouts enforced by default (unlike `requests`)
5. **Modularity**: Pluggable transports and customizable behavior
6. **Testing Support**: Built-in mocking and testing facilities

---

## 2. API Surface

### Public API Exports

HTTPX exposes a carefully curated public API through `__init__.py`. Key exported components:

```python
# Entry point functions (top-level API)
request, get, head, options, post, put, patch, delete, stream

# Main classes
Client, AsyncClient
Request, Response

# Data models
Headers, Cookies, QueryParams, URL

# Configuration
Auth, BasicAuth, DigestAuth, FunctionAuth, NetRCAuth
Timeout, Limits, Proxy

# Transports
BaseTransport, AsyncBaseTransport, HTTPTransport, AsyncHTTPTransport
MockTransport, WSGITransport, ASGITransport

# Exceptions (detailed in section 7)
HTTPError, RequestError, TransportError, HTTPStatusError, etc.

# Utilities
codes (HTTP status codes)
USE_CLIENT_DEFAULT (sentinel value)
```

### Usage Patterns

#### 1. Simple Function API (One-shot Requests)

```python
# For users who don't need connection reuse
response = httpx.get("https://example.com")
response = httpx.post("https://example.com/api", json={"key": "value"})
```

**Implementation Pattern**: Each function creates a client, sends one request, then closes it:

```python
def get(url, **kwargs):
    with Client(**config_kwargs) as client:
        return client.request("GET", url, **kwargs)
```

#### 2. Client Context Manager (Connection Pooling)

```python
# For reusing connections
with httpx.Client() as client:
    response = client.get("https://example.com")
    # Connection is pooled and reused
    other = client.get("https://example.com/api")
```

#### 3. Async API

```python
async with httpx.AsyncClient() as client:
    response = await client.get("https://example.com")
    results = await asyncio.gather(
        client.get("https://api1.com"),
        client.get("https://api2.com"),
    )
```

#### 4. Streaming API

```python
# Streaming response body
with httpx.stream("GET", "https://example.com") as response:
    for chunk in response.iter_bytes():
        process(chunk)

# Streaming request body
client.post(url, content=generator_of_bytes)
```

---

## 3. Sync/Async Duality Architecture

### Design Philosophy: Code Reuse Without Duplication

HTTPX achieves sync/async duality through **class hierarchy and method delegation** rather than duplicate code:

```
BaseClient (abstract base with shared logic)
├── Client (sync implementation)
└── AsyncClient (async implementation)

BaseTransport (abstract base)
├── HTTPTransport (sync I/O)

AsyncBaseTransport (abstract base)
├── AsyncHTTPTransport (async I/O)
```

### Shared Configuration in BaseClient

The `BaseClient` class handles all non-I/O logic:

```python
class BaseClient:
    def __init__(
        self,
        auth=None,
        params=None,
        headers=None,
        cookies=None,
        timeout=DEFAULT_TIMEOUT_CONFIG,
        follow_redirects=False,
        max_redirects=DEFAULT_MAX_REDIRECTS,
        event_hooks=None,
        base_url="",
        trust_env=True,
        default_encoding="utf-8",
    ):
        self._auth = self._build_auth(auth)
        self._params = QueryParams(params)
        self.headers = Headers(headers)
        self._cookies = Cookies(cookies)
        self._timeout = Timeout(timeout)
        self.follow_redirects = follow_redirects
        self.max_redirects = max_redirects
        self._event_hooks = {...}
        self._trust_env = trust_env
        self._state = ClientState.UNOPENED
```

BaseClient provides:
- Configuration storage and merging
- Request building (`build_request()`)
- URL/header/cookie/param merging logic
- Redirect handling logic (protocol-independent)
- Authentication flow management (protocol-independent)
- Event hook management

### Client-specific and AsyncClient-specific Methods

Each subclass overrides I/O methods:

```python
class Client(BaseClient):
    def __init__(self, verify=True, cert=None, http1=True, http2=False, 
                 proxy=None, mounts=None, limits=DEFAULT_LIMITS, transport=None, **kwargs):
        super().__init__(**kwargs)
        self._transport = self._init_transport(...)  # Sync transport
        self._mounts = {URLPattern(key): transport for ...}  # Connection pool mounts

    def send(self, request, *, stream=False, auth=USE_CLIENT_DEFAULT) -> Response:
        # Protocol-independent logic
        # Delegating I/O to transport.handle_request()
        
    def _send_single_request(self, request: Request) -> Response:
        transport = self._transport_for_url(request.url)
        response = transport.handle_request(request)  # Sync I/O
        return response

class AsyncClient(BaseClient):
    def __init__(self, verify=True, cert=None, http1=True, http2=False, 
                 proxy=None, mounts=None, limits=DEFAULT_LIMITS, transport=None, **kwargs):
        super().__init__(**kwargs)
        self._transport = self._init_transport(...)  # Async transport
        self._mounts = {...}

    async def send(self, request, *, stream=False, auth=USE_CLIENT_DEFAULT) -> Response:
        # Protocol-independent logic (mostly identical to Client.send)
        # But awaits async methods
        
    async def _send_single_request(self, request: Request) -> Response:
        transport = self._transport_for_url(request.url)
        response = await transport.handle_async_request(request)  # Async I/O
        return response
```

### Key Pattern: Minimal Code Duplication

1. **Auth Flow**: Different implementations for sync vs async
   ```python
   class Auth:
       def auth_flow(self, request): ...  # Generic (generators)
       def sync_auth_flow(self, request): ...  # Sync wrapper
       def async_auth_flow(self, request): ...  # Async wrapper
   ```

2. **Request/Response**: Single unified model with both sync and async methods
   ```python
   class Request:
       def read(self) -> bytes: ...  # Sync
       async def aread(self) -> bytes: ...  # Async

   class Response:
       def iter_bytes(self) -> Iterator[bytes]: ...  # Sync
       async def aiter_bytes(self) -> AsyncIterator[bytes]: ...  # Async
   ```

3. **Byte Streams**: Separate sync and async base classes
   ```python
   class SyncByteStream:
       def __iter__(self) -> Iterator[bytes]: ...
       def close(self) -> None: ...

   class AsyncByteStream:
       async def __aiter__(self) -> AsyncIterator[bytes]: ...
       async def aclose(self) -> None: ...
   ```

### Async Detection Pattern

HTTPX uses a clever pattern where a single `Response` object can work with either sync or async streams:

```python
def iter_raw(self) -> Iterator[bytes]:
    if not isinstance(self.stream, SyncByteStream):
        raise RuntimeError("Attempted to call a sync iterator on an async stream.")
    # ... sync iteration

async def aiter_raw(self) -> AsyncIterator[bytes]:
    if not isinstance(self.stream, AsyncByteStream):
        raise RuntimeError("Attempted to call async iterator on a sync stream.")
    # ... async iteration
```

This ensures type safety and clear error messages if the wrong method is called.

---

## 4. Client Architecture

### BaseClient Initialization

```python
class BaseClient:
    def __init__(
        self,
        auth: AuthTypes | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
        follow_redirects: bool = False,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        event_hooks: Mapping[str, list[EventHook]] | None = None,
        base_url: URL | str = "",
        trust_env: bool = True,
        default_encoding: str | Callable[[bytes], str] = "utf-8",
    ) -> None:
```

**Constructor Parameters:**

| Parameter | Purpose | Default |
|-----------|---------|---------|
| `auth` | Default authentication for all requests | `None` |
| `params` | Default query parameters (merged with per-request) | `None` |
| `headers` | Default headers (merged with per-request) | Auto-generated (User-Agent, Accept-Encoding, Connection, etc.) |
| `cookies` | Default cookies (persisted across requests) | `None` |
| `timeout` | Request timeout configuration | `5.0` seconds |
| `follow_redirects` | Auto-follow HTTP redirects | `False` |
| `max_redirects` | Maximum redirects before error | `20` |
| `event_hooks` | Request/response lifecycle hooks | `{}` |
| `base_url` | Base URL for relative request URLs | `""` |
| `trust_env` | Use environment variables (proxies, certs) | `True` |
| `default_encoding` | Fallback text encoding | `"utf-8"` |

**Client-specific Parameters:**

```python
class Client(BaseClient):
    def __init__(
        self,
        verify: ssl.SSLContext | str | bool = True,
        cert: CertTypes | None = None,
        http1: bool = True,
        http2: bool = False,
        proxy: ProxyTypes | None = None,
        mounts: Mapping[str, BaseTransport | None] | None = None,
        limits: Limits = DEFAULT_LIMITS,
        transport: BaseTransport | None = None,
        **base_kwargs
    ):
```

### Connection Management

#### Transport Initialization

```python
class Client:
    def __init__(self, verify=True, cert=None, http1=True, http2=False, 
                 proxy=None, mounts=None, limits=DEFAULT_LIMITS, transport=None, **kwargs):
        self._transport = self._init_transport(
            verify=verify,
            cert=cert,
            trust_env=trust_env,
            http1=http1,
            http2=http2,
            limits=limits,
            transport=transport,  # Allow custom transport override
        )
        self._mounts: dict[URLPattern, BaseTransport | None] = {}
        # Add proxy mounts and custom mounts
```

#### Transport Mounts (URL Pattern Routing)

```python
# Route requests to specific transports based on URL pattern
self._mounts = {
    URLPattern("https://api.github.com/*"): github_transport,
    URLPattern("https://api.twitter.com/*"): twitter_transport,
    URLPattern("all://"): default_transport,  # Fallback
}

def _transport_for_url(self, url: URL) -> BaseTransport:
    """Returns the transport instance that should be used for a given URL."""
    for pattern, transport in self._mounts.items():
        if pattern.matches(url):
            return self._transport if transport is None else transport
    return self._transport
```

### Client State Management

```python
class ClientState(enum.Enum):
    UNOPENED = 1  # Not yet used or opened
    OPENED = 2    # In use or within context manager
    CLOSED = 3    # Closed or exited context
```

**Why State Matters:**
- Prevent use-after-close errors
- Ensure proper resource cleanup
- Provide clear error messages

### Context Manager Support

#### Synchronous Client

```python
class Client:
    def __enter__(self: T) -> T:
        if self._state != ClientState.UNOPENED:
            raise RuntimeError("Cannot open a client instance more than once.")
        self._state = ClientState.OPENED
        self._transport.__enter__()
        for transport in self._mounts.values():
            if transport is not None:
                transport.__enter__()
        return self

    def __exit__(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._state = ClientState.CLOSED
        self._transport.__exit__(exc_type, exc_value, traceback)
        for transport in self._mounts.values():
            if transport is not None:
                transport.__exit__(exc_type, exc_value, traceback)
```

#### Asynchronous Client

```python
class AsyncClient:
    async def __aenter__(self: U) -> U:
        if self._state != ClientState.UNOPENED:
            raise RuntimeError("Cannot open a client instance more than once.")
        self._state = ClientState.OPENED
        await self._transport.__aenter__()
        for transport in self._mounts.values():
            if transport is not None:
                await transport.__aenter__()
        return self

    async def __aexit__(self, exc_type=None, exc_value=None, traceback=None) -> None:
        self._state = ClientState.CLOSED
        await self._transport.__aexit__(exc_type, exc_value, traceback)
        for transport in self._mounts.values():
            if transport is not None:
                await transport.__aexit__(exc_type, exc_value, traceback)
```

### Request/Response Method Chain

```python
class Client(BaseClient):
    # Primary request methods
    
    def request(self, method, url, *, params=None, content=None, 
                data=None, files=None, json=None, headers=None, 
                cookies=None, auth=USE_CLIENT_DEFAULT, 
                follow_redirects=USE_CLIENT_DEFAULT, 
                timeout=USE_CLIENT_DEFAULT, 
                extensions=None) -> Response:
        """Build and send a request."""
        request = self.build_request(...)
        return self.send(request, auth=auth, follow_redirects=follow_redirects)
    
    def send(self, request: Request, *, stream=False, 
             auth=USE_CLIENT_DEFAULT, 
             follow_redirects=USE_CLIENT_DEFAULT) -> Response:
        """Send a prepared request."""
        # Handle auth flow
        auth = self._build_request_auth(request, auth)
        # Handle redirects
        response = self._send_handling_auth(request, auth, follow_redirects, history=[])
        if not stream:
            response.read()  # Load body into memory
        return response
    
    def _send_single_request(self, request: Request) -> Response:
        """Send a single request without redirect handling."""
        transport = self._transport_for_url(request.url)
        response = transport.handle_request(request)
        # Bind timing info
        response.stream = BoundSyncStream(response.stream, response, start)
        # Extract cookies
        self.cookies.extract_cookies(response)
        return response
    
    def stream(self, method, url, **kwargs) -> Iterator[Response]:
        """Context manager for streaming responses."""
        request = self.build_request(...)
        response = self.send(request, stream=True)
        try:
            yield response
        finally:
            response.close()
    
    # Convenience methods
    def get(self, url, **kwargs) -> Response:
        return self.request("GET", url, **kwargs)
    
    def post(self, url, **kwargs) -> Response:
        return self.request("POST", url, **kwargs)
    
    # ... put, patch, delete, head, options
```

---

## 5. Request/Response Model

### Request Object

```python
class Request:
    def __init__(
        self,
        method: str,
        url: URL | str,
        *,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: typing.Any | None = None,
        stream: SyncByteStream | AsyncByteStream | None = None,
        extensions: RequestExtensions | None = None,
    ) -> None:
        self.method = method.upper()
        self.url = URL(url, params=params)
        self.headers = Headers(headers)
        self.extensions = extensions or {}
        # Stream handling and auto-headers
```

**Key Features:**

1. **Content Encoding**: Automatically encodes content based on parameters:
   ```python
   # Choose encoding based on what's provided
   if content is not None:
       # Raw bytes content
   elif json is not None:
       # JSON-encode the object
       headers, stream = encode_request(json=json)
   elif data is not None:
       # Form-encode (application/x-www-form-urlencoded)
       headers, stream = encode_request(data=data)
   elif files is not None:
       # Multipart file upload
       headers, stream = encode_request(files=files)
   else:
       # Empty body
   ```

2. **Lazy Body Loading**:
   ```python
   @property
   def content(self) -> bytes:
       if not hasattr(self, "_content"):
           raise RequestNotRead()
       return self._content
   
   def read(self) -> bytes:
       """Eagerly read body into memory."""
       if not hasattr(self, "_content"):
           self._content = b"".join(self.stream)
           # Replace stream with replayable ByteStream
           self.stream = ByteStream(self._content)
       return self._content
   ```

3. **Dual sync/async support**:
   ```python
   def read(self) -> bytes: ...
   async def aread(self) -> bytes: ...
   ```

### Response Object

```python
class Response:
    def __init__(
        self,
        status_code: int,
        *,
        headers: HeaderTypes | None = None,
        content: ResponseContent | None = None,
        text: str | None = None,
        html: str | None = None,
        json: typing.Any = None,
        stream: SyncByteStream | AsyncByteStream | None = None,
        request: Request | None = None,
        extensions: ResponseExtensions | None = None,
        history: list[Response] | None = None,
        default_encoding: str = "utf-8",
    ) -> None:
        self.status_code = status_code
        self.headers = Headers(headers)
        self._request = request
        self.next_request = None  # Set when follow_redirects=False
        self.extensions = extensions or {}
        self.history = history or []
        self.is_closed = False
        self.is_stream_consumed = False
```

**Content Access Methods:**

```python
# Convenience properties (require content to be read)
@property
def content(self) -> bytes:
    if not hasattr(self, "_content"):
        raise ResponseNotRead()
    return self._content

@property
def text(self) -> str:
    # Automatically decoded using detected charset
    
@property
def json(self) -> Any:
    # Parsed JSON

# Streaming iterators
def iter_bytes(self, chunk_size=None) -> Iterator[bytes]:
    """Iterate decoded bytes with decompression."""
    
def iter_text(self, chunk_size=None) -> Iterator[str]:
    """Iterate decoded text lines."""
    
def iter_lines(self) -> Iterator[str]:
    """Iterate response as lines."""
    
def iter_raw(self, chunk_size=None) -> Iterator[bytes]:
    """Iterate raw bytes (no decompression)."""

# Async variants
async def aread(self) -> bytes: ...
async def aiter_bytes(self, chunk_size=None) -> AsyncIterator[bytes]: ...
async def aiter_text(self, chunk_size=None) -> AsyncIterator[str]: ...
async def aiter_lines(self) -> AsyncIterator[str]: ...
async def aiter_raw(self, chunk_size=None) -> AsyncIterator[bytes]: ...

# Lifecycle
def read(self) -> bytes:
    """Read all content into memory."""
    
def close(self) -> None:
    """Release connection and stream resources."""
```

**Response Analysis Methods:**

```python
@property
def status_code(self) -> int:
    """HTTP status code (200, 404, 500, etc.)"""

@property
def reason_phrase(self) -> str:
    """HTTP reason phrase (OK, Not Found, Server Error, etc.)"""

@property
def http_version(self) -> str:
    """HTTP version (HTTP/1.1, HTTP/2)"""

@property
def url(self) -> URL:
    """The request URL"""

@property
def is_success(self) -> bool:
    """Check if status code is 2xx"""

@property
def is_redirect(self) -> bool:
    """Check if status code is 3xx"""

@property
def has_redirect_location(self) -> bool:
    """Check if Location header is present"""

@property
def elapsed(self) -> timedelta:
    """Time taken for complete request/response cycle"""

@property
def cookies(self) -> Cookies:
    """Parsed Set-Cookie headers"""

@property
def links(self) -> dict:
    """Parsed Link headers"""

def raise_for_status(self) -> Response:
    """Raise HTTPStatusError for 4xx/5xx status codes"""

def num_bytes_downloaded(self) -> int:
    """Total bytes received from network"""
```

**Redirect History:**

```python
response = client.get("https://example.com", follow_redirects=True)
response.history  # List of intermediate Response objects
response.history[0].status_code  # 301
response.history[1].status_code  # 302
response.status_code  # 200 (final)
```

---

## 6. Transport Layer Architecture

### Transport Abstraction

The transport layer is where actual network I/O happens. It's abstracted behind a simple interface:

```python
class BaseTransport:
    """Synchronous transport base class."""
    
    def handle_request(self, request: Request) -> Response:
        """
        Send a single HTTP request and return a response.
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError()
    
    def close(self) -> None:
        """Release network resources."""
        pass
    
    def __enter__(self) -> BaseTransport:
        return self
    
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


class AsyncBaseTransport:
    """Asynchronous transport base class."""
    
    async def handle_async_request(self, request: Request) -> Response:
        """
        Send a single HTTP request and return a response (async).
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError()
    
    async def aclose(self) -> None:
        """Release network resources (async)."""
        pass
    
    async def __aenter__(self) -> AsyncBaseTransport:
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.aclose()
```

### Default Implementation (HTTPTransport)

The default `HTTPTransport` handles HTTP/1.1 and HTTP/2:

```python
class HTTPTransport(BaseTransport):
    def __init__(
        self,
        verify: ssl.SSLContext | str | bool = True,
        cert: CertTypes | None = None,
        trust_env: bool = True,
        http1: bool = True,
        http2: bool = False,
        limits: Limits = DEFAULT_LIMITS,
        proxy: Proxy | None = None,
    ):
        # Initialize underlying HTTP connection pool via httpcore
        # httpcore is the low-level networking library used by httpx
        
    def handle_request(self, request: Request) -> Response:
        """Send request and return response."""
        # Delegate to httpcore connection pool
        # Handle HTTP protocol details
```

### Transport Mounting

Clients can use multiple transports for different URL patterns:

```python
# Example: Use different transports for different APIs
client = httpx.Client(
    mounts={
        "https://github.com/": github_transport,
        "https://twitter.com/": twitter_transport,
        # Default transport used for unmatched patterns
    }
)
```

### Alternative Transports

#### MockTransport (Testing)

```python
def handler(request: Request) -> Response:
    return httpx.Response(200, json={"status": "ok"})

transport = MockTransport(handler)
client = Client(transport=transport)
response = client.get("https://example.com")  # Returns mocked response
```

#### WSGITransport (WSGI Application Testing)

```python
# Test a Django/Flask app without network
app = create_app()
transport = WSGITransport(app)
client = Client(transport=transport)
response = client.get("/api/users")  # Calls app directly
```

#### ASGITransport (ASGI Application Testing)

```python
# Test a Starlette/FastAPI app without network
app = create_async_app()
transport = ASGITransport(app)
async_client = AsyncClient(transport=transport)
response = await async_client.get("/api/users")  # Calls app directly
```

---

## 7. Error Handling

### Exception Hierarchy

HTTPX uses a well-designed exception hierarchy for different error scenarios:

```
HTTPError (base for all HTTP errors)
├── RequestError (problems during request sending)
│   ├── TransportError (network/protocol level)
│   │   ├── TimeoutException
│   │   │   ├── ConnectTimeout
│   │   │   ├── ReadTimeout
│   │   │   ├── WriteTimeout
│   │   │   └── PoolTimeout
│   │   ├── NetworkError
│   │   │   ├── ConnectError
│   │   │   ├── ReadError
│   │   │   ├── WriteError
│   │   │   └── CloseError
│   │   ├── ProtocolError
│   │   │   ├── LocalProtocolError
│   │   │   └── RemoteProtocolError
│   │   ├── ProxyError
│   │   └── UnsupportedProtocol
│   ├── DecodingError (response body decode failure)
│   └── TooManyRedirects
└── HTTPStatusError (4xx/5xx responses)

StreamError (programming errors accessing streams)
├── StreamConsumed
├── StreamClosed
├── ResponseNotRead
└── RequestNotRead

InvalidURL
CookieConflict
```

### Exception Features

```python
class HTTPError(Exception):
    """Base class for RequestError and HTTPStatusError."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self._request: Request | None = None
    
    @property
    def request(self) -> Request:
        """Access the associated request."""
        if self._request is None:
            raise RuntimeError("The .request property has not been set.")
        return self._request


class HTTPStatusError(HTTPError):
    """Raised by response.raise_for_status()."""
    
    def __init__(self, message: str, *, request: Request, response: Response) -> None:
        super().__init__(message)
        self.request = request
        self.response = response
```

### Usage Pattern

```python
try:
    response = httpx.get("https://example.com")
    response.raise_for_status()
except httpx.HTTPError as exc:
    print(f"HTTP Exception for {exc.request.url}")
    print(f"Response: {exc.response.status_code}")
```

### Request Context Manager

A utility for automatically associating exceptions with their request:

```python
@contextlib.contextmanager
def request_context(request: Request | None = None) -> Iterator[None]:
    """Attach request context to RequestError exceptions."""
    try:
        yield
    except RequestError as exc:
        if request is not None:
            exc.request = request
        raise exc
```

---

## 8. Middleware/Hooks System

### Event Hooks

HTTPX provides lifecycle hooks for request/response processing:

```python
client = httpx.Client(
    event_hooks={
        "request": [log_request, validate_request],
        "response": [log_response, update_metrics],
    }
)

def log_request(request: Request) -> None:
    print(f"Sending: {request.method} {request.url}")

def log_response(response: Response) -> None:
    print(f"Received: {response.status_code}")
```

**Hook Points:**

1. **"request" hooks**: Called before each request is sent
   ```python
   def hook(request: Request) -> None:
       # Modify request if needed
       request.headers["X-Custom"] = "value"
   ```

2. **"response" hooks**: Called after each response is received
   ```python
   def hook(response: Response) -> None:
       # Access response data
       print(f"Status: {response.status_code}")
   ```

### Authentication System

HTTPX provides a flexible authentication framework:

```python
class Auth:
    """Base authentication class."""
    
    def auth_flow(
        self, request: Request
    ) -> Generator[Request, Response, None]:
        """
        Authentication flow generator.
        
        yield request  -> client sends it
        response = yield  -> receive response
        yield new_request  -> for multi-step auth (OAuth, etc.)
        """
        yield request
    
    def sync_auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        """Synchronous authentication flow."""
        # Default: delegates to auth_flow
        
    async def async_auth_flow(
        self, request: Request
    ) -> AsyncGenerator[Request, Response]:
        """Asynchronous authentication flow."""
        # Default: async wrapper around auth_flow
```

**Built-in Authentication Implementations:**

```python
# Basic Auth
auth = httpx.BasicAuth(username="user", password="pass")
response = client.get(url, auth=auth)

# Digest Auth
auth = httpx.DigestAuth(username="user", password="pass")

# Function-based Auth
def auth_flow(request):
    request.headers["Authorization"] = f"Bearer {get_token()}"
    yield request

auth = httpx.FunctionAuth(auth_flow)

# .netrc file-based Auth
auth = httpx.NetRCAuth()
```

**Multi-step Authentication Example (OAuth-like):**

```python
class OAuth2Auth(Auth):
    requires_response_body = True  # Need to read response body
    
    def auth_flow(self, request):
        # Step 1: Send initial request
        response = yield request
        
        if response.status_code == 401:
            # Step 2: Get new token
            token = self.refresh_token(response)
            
            # Step 3: Retry with new token
            request.headers["Authorization"] = f"Bearer {token}"
            response = yield request
        
        return response
```

### Redirect Handling

HTTPX handles HTTP redirects automatically:

```python
# Follow all redirects
response = client.get(url, follow_redirects=True)
print(response.status_code)  # 200 (final)
print(response.history)  # [Response(301), Response(302)]

# Don't follow redirects (default)
response = client.get(url, follow_redirects=False)
print(response.status_code)  # 301 or 302
print(response.next_request)  # The next request to follow manually
```

---

## 9. Type Safety

### Comprehensive Type Annotations

HTTPX uses type hints throughout for IDE support and type checking:

```python
from typing import Union, Optional, Mapping, Sequence, Callable
from typing_extensions import TypeAlias

# Type aliases for common parameter types
URLTypes: TypeAlias = Union["URL", str]

PrimitiveData = Optional[Union[str, int, float, bool]]

QueryParamTypes = Union[
    "QueryParams",
    Mapping[str, Union[PrimitiveData, Sequence[PrimitiveData]]],
    List[Tuple[str, PrimitiveData]],
    str,
    bytes,
]

HeaderTypes = Union[
    "Headers",
    Mapping[str, str],
    Sequence[Tuple[str, str]],
]

CookieTypes = Union["Cookies", CookieJar, Dict[str, str], List[Tuple[str, str]]]

TimeoutTypes = Union[
    Optional[float],
    Tuple[Optional[float], Optional[float], Optional[float], Optional[float]],
    "Timeout",
]

AuthTypes = Union[
    Tuple[Union[str, bytes], Union[str, bytes]],
    Callable[["Request"], "Request"],
    "Auth",
]

FileTypes = Union[
    # file (or bytes)
    FileContent,
    # (filename, file (or bytes))
    Tuple[Optional[str], FileContent],
    # (filename, file, content_type)
    Tuple[Optional[str], FileContent, Optional[str]],
    # (filename, file, content_type, headers)
    Tuple[Optional[str], FileContent, Optional[str], Mapping[str, str]],
]
```

### Type-safe Method Signatures

```python
def request(
    self,
    method: str,
    url: URL | str,
    *,
    params: QueryParamTypes | None = None,
    content: RequestContent | None = None,
    data: RequestData | None = None,
    files: RequestFiles | None = None,
    json: typing.Any | None = None,
    headers: HeaderTypes | None = None,
    cookies: CookieTypes | None = None,
    auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
    follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
    timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
    extensions: RequestExtensions | None = None,
) -> Response:
    ...
```

### Type Guard Pattern (USE_CLIENT_DEFAULT)

To distinguish between "not provided" and "explicitly None":

```python
class UseClientDefault:
    """Sentinel value for unset parameters."""
    pass

USE_CLIENT_DEFAULT = UseClientDefault()

# In client.send():
auth = self._build_request_auth(request, auth)

def _build_request_auth(self, request: Request, auth: AuthTypes | UseClientDefault | None):
    if isinstance(auth, UseClientDefault):
        auth = self.auth  # Use client default
    else:
        auth = self._build_auth(auth)
```

This prevents accidental overwriting of defaults with `None`.

---

## 10. Testing Patterns

### MockTransport for Unit Testing

```python
def test_api_call():
    def handler(request: Request) -> Response:
        return httpx.Response(
            200,
            json={"users": ["alice", "bob"]},
        )
    
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    
    response = client.get("https://api.example.com/users")
    assert response.status_code == 200
    assert response.json() == {"users": ["alice", "bob"]}
```

### Conditional Request Handling

```python
def handler(request: Request) -> Response:
    if request.method == "GET" and "users" in request.url.path:
        return httpx.Response(200, json={"users": []})
    elif request.method == "POST" and "users" in request.url.path:
        data = request.json()
        return httpx.Response(201, json={"id": 1, **data})
    else:
        return httpx.Response(404)

transport = httpx.MockTransport(handler)
client = httpx.Client(transport=transport)
```

### WSGI/ASGI Testing

```python
# Direct testing of Django/Flask/Starlette apps
from django.test import Client as DjangoClient
from myapp import django_app

transport = httpx.WSGITransport(app=django_app)
client = httpx.Client(transport=transport)

response = client.get("/api/users")
assert response.status_code == 200
```

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_client():
    async def handler(request: Request) -> Response:
        await asyncio.sleep(0.1)  # Simulate I/O
        return httpx.Response(200, json={"status": "ok"})
    
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://example.com")
        assert response.json() == {"status": "ok"}
```

---

## Design Patterns Summary for JSON-RPC Client

### Applicable Patterns for jrpcx

Based on the HTTPX analysis, here are the key patterns most relevant for a JSON-RPC client:

#### 1. **Sync/Async Duality Pattern**
- Create a `BaseJSONRPCClient` with shared logic
- Subclass into `JSONRPCClient` (sync) and `AsyncJSONRPCClient`
- Share request building and response parsing logic
- Only differ in transport I/O methods

#### 2. **Transport Layer Abstraction**
- Define `BaseJSONRPCTransport` interface
- Implement default HTTP transport
- Allow custom transports (HTTP/2, WebSocket, IPC, etc.)
- Support mocking via `MockTransport`

#### 3. **Client Configuration Pattern**
- Base configuration in `__init__`: timeout, auth, headers
- Per-request overrides via `USE_CLIENT_DEFAULT` sentinel
- Merging strategy for headers/params
- Context manager for connection management

#### 4. **Middleware/Hooks**
- Request hooks (logging, request ID injection)
- Response hooks (logging, metric collection)
- Auth flow system (API key, OAuth, custom schemes)

#### 5. **Error Hierarchy**
- Base `JSONRPCError` exception
- Specific subclasses: `TransportError`, `ParseError`, `MethodError`, `InvalidParams`
- Preserve request/response context

#### 6. **Type Safety**
- Define type aliases for common inputs
- Full type hints on all methods
- Sentinel values for "unset" states

#### 7. **Convenience API**
- Simple function-level API: `jrpcx.call(method, url, params, ...)`
- Client-based API for connection reuse
- Streaming support for large responses

---

## Conclusion

HTTPX demonstrates excellent library design through:

1. **User-Centric API**: Simple for common use cases, powerful for advanced scenarios
2. **Type Safety**: Comprehensive type hints throughout
3. **Code Reuse**: Shared logic between sync/async with minimal duplication
4. **Abstraction Layers**: Clean transport abstraction enabling testing and customization
5. **Error Design**: Clear exception hierarchy with contextual information
6. **Extensibility**: Hooks, auth flows, custom transports
7. **Testing First**: Built-in support for mocking and testing

These patterns provide a strong foundation for designing the jrpcx JSON-RPC client library with similar ergonomics and power.
