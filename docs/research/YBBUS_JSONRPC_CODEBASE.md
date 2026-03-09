# Comprehensive Research Report: ybbus/jsonrpc Go Library

## Executive Summary

**ybbus/jsonrpc** is a lightweight, zero-dependency JSON-RPC 2.0 client library for Go that achieves a rare balance between simplicity and completeness. The entire implementation fits in a single 702-line file with no external runtime dependencies, yet provides full JSON-RPC 2.0 compliance including batch operations, intelligent parameter handling via reflection, and a clean interface-based API. Listed in the Awesome Go curated list, the library is a strong example of Go minimalism applied to protocol client design.

Key characteristics:
- **Single-file implementation**: 702 lines of production code, ~1,024 lines of tests
- **Zero runtime dependencies**: Uses only the Go standard library (testify for tests only)
- **Client-only**: No server component — focused purely on the calling side
- **HTTP transport**: Tightly coupled to HTTP via `net/http`, with an injectable `HTTPClient` interface
- **Reflection-based parameter magic**: Automatically determines correct JSON-RPC parameter format

---

## 1. Project Overview

### Purpose
The library provides a clean Go implementation of a JSON-RPC 2.0 client over HTTP, conforming strictly to the [JSON-RPC 2.0 specification](http://www.jsonrpc.org/specification). It is designed for applications that need to call JSON-RPC services — common in blockchain/cryptocurrency APIs, microservices, and legacy RPC systems.

### Design Philosophy
The library is built on **simplicity and convenience**:
- **Minimal footprint**: Single source file, single package
- **No external dependencies**: Uses only Go standard library
- **Ergonomic API**: Makes the common case trivial (variadic params, auto-wrapping)
- **Parameter flexibility**: Intelligent handling of various parameter types through reflection
- **Convention over configuration**: Smart defaults with minimal boilerplate

### Module Information

| Attribute | Value |
|-----------|-------|
| Module | `github.com/ybbus/jsonrpc/v3` |
| Go Version | 1.21+ |
| Latest Version | v3 (v1, v2 on separate branches) |
| License | MIT |
| Production Code | 702 lines (single file) |
| Test Code | 1,023 lines (single file) |
| Runtime Dependencies | None (stdlib only) |
| Test Dependencies | `github.com/stretchr/testify` |

### File Structure

```
ybbus-jsonrpc/
├── jsonrpc.go         # 702 lines — entire implementation
├── jsonrpc_test.go    # 1,023 lines — comprehensive test suite
├── go.mod
├── go.sum
├── README.md
└── LICENSE
```

---

## 2. Architecture and Code Organization

### Single-File Architecture

Despite living in a single file, the code has clear logical separation:

| Section | Lines (approx.) | Responsibility |
|---------|-----------------|----------------|
| Interface Definition | 19–116 | `RPCClient` interface with full documentation |
| Type Definitions | 118–272 | `RPCRequest`, `RPCResponse`, `RPCError`, `HTTPError`, `HTTPClient`, `RPCClientOpts` |
| Collection Types | 274–311 | `RPCResponses` (with `AsMap`, `GetByID`, `HasError`), `RPCRequests` |
| Factory Functions | 313–353 | `NewClient()`, `NewClientWithOpts()` |
| Client Implementation | 355–404 | `Call`, `CallRaw`, `CallFor`, `CallBatch`, `CallBatchRaw` |
| HTTP Transport | 406–547 | `newRequest()`, `doCall()`, `doBatchCall()` |
| Helper Functions | 549–702 | `Params()`, `GetInt()`, `GetFloat()`, `GetBool()`, `GetString()`, `GetObject()` |

### Key Architectural Decisions

1. **Interface-first design**: The public `RPCClient` interface is the primary API; the concrete `rpcClient` struct is unexported
2. **HTTP-coupled transport**: No transport abstraction layer — HTTP is baked in via `net/http`
3. **Reflection for ergonomics**: The `Params()` function uses `reflect` to auto-detect parameter shapes
4. **Decoder configuration**: Uses `json.Decoder` with `UseNumber()` and optional `DisallowUnknownFields()`
5. **No concurrency primitives**: The client is stateless per-request — no mutexes, no connection pooling beyond what `http.Client` provides

---

## 3. API Surface

### Factory Functions

```go
// Simple client creation with default settings
func NewClient(endpoint string) RPCClient

// Advanced client creation with configuration
func NewClientWithOpts(endpoint string, opts *RPCClientOpts) RPCClient
```

`NewClient` delegates to `NewClientWithOpts` with `nil` opts. The factory always returns the `RPCClient` interface, keeping the concrete type private.

### Core Client Interface

```go
type RPCClient interface {
    // Standard call with automatic parameter handling
    Call(ctx context.Context, method string, params ...interface{}) (*RPCResponse, error)

    // Raw call — no parameter transformation
    CallRaw(ctx context.Context, request *RPCRequest) (*RPCResponse, error)

    // Convenience: call + unmarshal result into out, unified error handling
    CallFor(ctx context.Context, out interface{}, method string, params ...interface{}) error

    // Batch call with automatic ID assignment (0, 1, 2, ...)
    CallBatch(ctx context.Context, requests RPCRequests) (RPCResponses, error)

    // Batch call with no ID/version transformation
    CallBatchRaw(ctx context.Context, requests RPCRequests) (RPCResponses, error)
}
```

### Request Builder Functions

```go
// Create a request with automatic parameter handling (uses Params() internally)
func NewRequest(method string, params ...interface{}) *RPCRequest

// Create a request with explicit ID
func NewRequestWithID(id int, method string, params ...interface{}) *RPCRequest

// Convert variadic params to correct JSON-RPC format (reflection-based)
func Params(params ...interface{}) interface{}
```

---

## 4. Request/Response Model

### RPCRequest

```go
type RPCRequest struct {
    Method  string      `json:"method"`
    Params  interface{} `json:"params,omitempty"`
    ID      int         `json:"id"`
    JSONRPC string      `json:"jsonrpc"`
}
```

**Key details:**
- `ID` is typed as `int` (not `interface{}`) — this limits ID flexibility vs. the JSON-RPC spec which allows strings
- `Params` uses `omitempty` — when nil, the `params` field is omitted entirely (spec-compliant for no-params calls)
- `JSONRPC` is always set to `"2.0"` by the library

### RPCResponse

```go
type RPCResponse struct {
    JSONRPC string      `json:"jsonrpc"`
    Result  interface{} `json:"result,omitempty"`
    Error   *RPCError   `json:"error,omitempty"`
    ID      int         `json:"id"`
}
```

**Response helper methods** provide type-safe extraction:

```go
func (r *RPCResponse) GetInt() (int64, error)       // via json.Number.Int64()
func (r *RPCResponse) GetFloat() (float64, error)    // via json.Number.Float64()
func (r *RPCResponse) GetBool() (bool, error)        // type assertion
func (r *RPCResponse) GetString() (string, error)    // type assertion
func (r *RPCResponse) GetObject(toType interface{}) error  // marshal→unmarshal round-trip
```

**Important behavioral notes:**
- `Result` can be `nil` even on success (valid per JSON-RPC spec)
- `GetObject` works via marshal→unmarshal: `json.Marshal(Result)` then `json.Unmarshal(js, toType)`. This means pre-populated structs are merged/enhanced rather than replaced.
- Numeric results arrive as `json.Number` (because `decoder.UseNumber()` is set), requiring `GetInt()`/`GetFloat()` for extraction
- If result is JSON `null` and you unmarshal to `&pointer`, the pointer becomes `nil`

### RPCError

```go
type RPCError struct {
    Code    int         `json:"code"`
    Message string      `json:"message"`
    Data    interface{} `json:"data,omitempty"`
}

func (e *RPCError) Error() string {
    return strconv.Itoa(e.Code) + ": " + e.Message
}
```

Implements the `error` interface. Follows the JSON-RPC 2.0 error object spec exactly. The `Data` field can hold arbitrary additional error information from the server.

---

## 5. Batch Operations

### Managed Batch: `CallBatch`

```go
func (client *rpcClient) CallBatch(ctx context.Context, requests RPCRequests) (RPCResponses, error)
```

**Automatic management:**
- Assigns sequential IDs: `requests[0].ID = 0`, `requests[1].ID = 1`, etc.
- Overwrites `JSONRPC` to `"2.0"` on all requests
- Returns error for empty request lists

**Usage pattern:**
```go
responses, err := client.CallBatch(ctx, RPCRequests{
    NewRequest("method1", arg1),
    NewRequest("method2", arg2),
    NewRequest("method3", arg3),
})
if err != nil {
    return err
}

// Responses may arrive unordered — use map lookup
resMap := responses.AsMap()
if resp, ok := resMap[0]; ok {
    result, _ := resp.GetInt()
}
```

### Raw Batch: `CallBatchRaw`

```go
func (client *rpcClient) CallBatchRaw(ctx context.Context, requests RPCRequests) (RPCResponses, error)
```

No ID or version transformation — user is fully responsible for request structure.

### Batch Response Helpers

```go
type RPCResponses []*RPCResponse

func (res RPCResponses) AsMap() map[int]*RPCResponse   // index by ID
func (res RPCResponses) GetByID(id int) *RPCResponse   // find by ID, nil if missing
func (res RPCResponses) HasError() bool                 // any response has Error != nil
```

**Key characteristics:**
- Responses may arrive in any order (per JSON-RPC spec)
- Responses may be incomplete (some requests may not get responses)
- All requests go in a single HTTP POST
- `AsMap()` creates `map[int]*RPCResponse` for O(1) lookup by ID

---

## 6. Error Handling

The library distinguishes three error categories with a clear hierarchy:

### 1. Network/HTTP Errors (`HTTPError`)

```go
type HTTPError struct {
    Code int    // HTTP status code (e.g., 500, 403)
    err  error  // Underlying error message (unexported)
}

func (e *HTTPError) Error() string { return e.err.Error() }
```

Returned as a Go `error` when:
- Network connection fails
- HTTP status code ≥ 400
- Response body cannot be parsed

**Detection via type assertion:**
```go
response, err := client.Call(ctx, "method")
if err != nil {
    if httpErr, ok := err.(*HTTPError); ok {
        log.Printf("HTTP error %d: %s", httpErr.Code, httpErr.Error())
    }
}
```

### 2. JSON-RPC Protocol Errors (`RPCError`)

Carried *inside* the `RPCResponse.Error` field (not as a Go error from `Call`):
```go
if response.Error != nil {
    log.Printf("RPC error %d: %s", response.Error.Code, response.Error.Message)
}
```

### 3. Response Parsing Errors

Returned when the response cannot be unmarshaled to the expected type (e.g., via `GetObject` or `GetInt`).

### Error Handling Patterns

**Pattern 1: `CallFor` (simplest — unified error)**
```go
var result MyType
err := client.CallFor(ctx, &result, "method", arg1, arg2)
if err != nil {
    // Network error, RPC error, or parse error — all unified
    return err
}
```

**Pattern 2: `Call` + manual checks (more control)**
```go
response, err := client.Call(ctx, "method", arg1)
if err != nil { return err }              // HTTP/network error
if response.Error != nil { return response.Error }  // RPC error
var result MyType
if err := response.GetObject(&result); err != nil { return err }  // parse error
```

**Pattern 3: Batch error checking**
```go
responses, err := client.CallBatch(ctx, requests)
if err != nil { return err }
if responses.HasError() {
    for _, resp := range responses {
        if resp.Error != nil {
            log.Printf("Request %d failed: %v", resp.ID, resp.Error)
        }
    }
}
```

### Dual-Return on HTTP Error with RPC Body

A notable design detail: when HTTP status ≥ 400 **and** the body contains a valid RPC response with an error, `doCall` returns **both** the `*RPCResponse` and an `*HTTPError`. This allows callers to inspect the RPC error details even when the HTTP layer signals failure.

```go
// From doCall() — lines 478-490
if httpResponse.StatusCode >= 400 {
    if rpcResponse.Error != nil {
        return rpcResponse, &HTTPError{
            Code: httpResponse.StatusCode,
            err:  fmt.Errorf("rpc call %v() on %v status code: %v. rpc response error: %v", ...),
        }
    }
    return rpcResponse, &HTTPError{Code: httpResponse.StatusCode, ...}
}
```

### Standard JSON-RPC 2.0 Error Codes

The library doesn't define or enforce these, but servers typically use:

| Code | Meaning |
|------|---------|
| -32700 | Parse error |
| -32600 | Invalid Request |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32603 | Internal error |
| -32000 to -32099 | Server error (reserved) |

---

## 7. Configuration Options (`RPCClientOpts`)

```go
type RPCClientOpts struct {
    HTTPClient         HTTPClient            // Custom HTTP client implementation
    CustomHeaders      map[string]string     // Custom headers (auth, API keys, etc.)
    AllowUnknownFields bool                  // Allow unknown fields in response JSON
    DefaultRequestID   int                   // Default ID for single requests (default: 0)
}
```

### Configuration Examples

**Basic authentication:**
```go
client := jsonrpc.NewClientWithOpts(endpoint, &jsonrpc.RPCClientOpts{
    CustomHeaders: map[string]string{
        "Authorization": "Basic " + base64.StdEncoding.EncodeToString(
            []byte("username:password")),
    },
})
```

**OAuth 2.0 with custom HTTP client:**
```go
config := clientcredentials.Config{
    ClientID: "id", ClientSecret: "secret", TokenURL: "https://auth.example.com/token",
}
client := jsonrpc.NewClientWithOpts(endpoint, &jsonrpc.RPCClientOpts{
    HTTPClient: config.Client(context.Background()),
})
```

**Timeout and TLS:**
```go
client := jsonrpc.NewClientWithOpts(endpoint, &jsonrpc.RPCClientOpts{
    HTTPClient: &http.Client{
        Timeout: 30 * time.Second,
        Transport: &http.Transport{
            TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12},
        },
    },
})
```

**Strict vs. lenient response parsing:**
```go
// Default: strict (unknown fields cause errors)
// Lenient: allows extra fields in response JSON
client := jsonrpc.NewClientWithOpts(endpoint, &jsonrpc.RPCClientOpts{
    AllowUnknownFields: true,
})
```

---

## 8. Transport/HTTP Customization

### HTTP Transport Details

The library is tightly coupled to HTTP via Go's `net/http`:
- **Method**: Always POST
- **Default headers**: `Content-Type: application/json`, `Accept: application/json`
- **Body**: JSON-marshaled `RPCRequest` (single) or `[]*RPCRequest` (batch)
- **Context**: Passed through via `http.NewRequestWithContext`

### HTTPClient Interface

```go
type HTTPClient interface {
    Do(req *http.Request) (*http.Response, error)
}
```

This is the sole extension point for transport customization. Since `*http.Client` satisfies this interface, it's a drop-in, but you can also inject:
- Retry-aware HTTP clients
- Clients with custom transports (proxy, TLS, Unix sockets)
- Logging/tracing wrappers
- OAuth2-managed clients (e.g., `golang.org/x/oauth2`)

### Header Handling

Custom headers are set after defaults, allowing override of `Content-Type` and `Accept`:

```go
// Special case: "Host" header sets request.Host, not Header map
for k, v := range client.customHeaders {
    if k == "Host" {
        request.Host = v
    } else {
        request.Header.Set(k, v)
    }
}
```

### Important: No Default Timeout

The default `http.Client{}` has **no timeout** — requests can block indefinitely. Production usage should always configure a timeout via `RPCClientOpts.HTTPClient` or use `context.WithTimeout`.

---

## 9. Parameter Handling (Reflection-Based Flexibility)

The `Params()` function is the heart of the library's ergonomic API. It uses reflection to automatically determine the correct JSON-RPC parameter format:

```go
func Params(params ...interface{}) interface{}
```

### Decision Logic

| Input | Behavior | JSON-RPC params |
|-------|----------|-----------------|
| No params | Returns `nil` → field omitted | *(omitted)* |
| Single struct/pointer-to-struct | Pass as-is (object) | `{"name":"Alex","age":35}` |
| Single array/slice | Pass as-is (array) | `[1, 2, 3]` |
| Single map | Pass as-is (object) | `{"key":"value"}` |
| Single primitive (`int`, `string`, `bool`) | Wrap in array | `[123]` |
| Multiple params of any type | Always wrap in array | `["Alex", 35, "Germany"]` |
| Single nil slice | Convert to `[]interface{}{}` | `[]` |
| Single nil map | Convert to `map[string]interface{}{}` | `{}` |
| Single nil value | Wrap in array as `[nil]` | `[null]` |

### Implementation Detail

The function traverses pointer chains via reflection to find the underlying type:

```go
// Traverse pointer chain to find base type
for typeOf = reflect.TypeOf(params[0]); typeOf != nil && typeOf.Kind() == reflect.Ptr; typeOf = typeOf.Elem() {
}

switch typeOf.Kind() {
case reflect.Struct:   finalParams = params[0]       // pass as object
case reflect.Array:    finalParams = params[0]       // pass as array
case reflect.Slice:    // check for nil → empty array, else pass as-is
case reflect.Map:      // check for nil → empty object, else pass as-is
default:               finalParams = params           // wrap in array
}
```

This enables the signature `Call(ctx, "method", arg1, arg2, ...)` to "just work" for all common parameter patterns without requiring callers to think about JSON-RPC parameter rules.

---

## 10. Testing Patterns

### Test Infrastructure

The test suite uses a shared `httptest.Server` with channel-based request capture:

```go
var requestChan = make(chan *RequestData, 1)
var responseBody = ""
var httpStatusCode = http.StatusOK

func TestMain(m *testing.M) {
    httpServer = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        data, _ := ioutil.ReadAll(r.Body)
        defer r.Body.Close()
        requestChan <- &RequestData{r, string(data)}
        w.WriteHeader(httpStatusCode)
        fmt.Fprintf(w, responseBody)
    }))
    defer httpServer.Close()
    os.Exit(m.Run())
}
```

This pattern allows tests to:
1. Set `responseBody` before each call to control server responses
2. Read from `requestChan` to inspect exact request JSON
3. Set `httpStatusCode` to simulate HTTP errors

### Test Coverage Areas (~1,023 lines)

| Category | Approx. Tests | What's Tested |
|----------|---------------|---------------|
| Parameter formatting | ~17 | All param combinations, edge cases (nil, empty, nested) |
| Response parsing | ~30+ | Null results, type conversions, struct merging |
| Batch operations | ~20+ | Format, ID mapping, error detection, raw batches |
| Configuration | ~4+ | Custom headers, unknown fields, default request ID |
| Error handling | Multiple | HTTP errors, RPC errors, parse errors, combined errors |
| Header verification | Multiple | Content-Type, Accept, custom headers, Host override |

### Testing Philosophy

- **Testify assertions** (`assert.New(t)`) for readable test code
- **Request verification**: Tests inspect the exact JSON sent to the server
- **Response simulation**: Tests set canned response bodies and verify client parsing
- **No mocks**: Uses real `httptest.Server` — integration-style unit tests
- **Channel synchronization**: Request capture via buffered channel ensures deterministic assertion

---

## 11. Strengths and Weaknesses

### Strengths ✅

| # | Strength | Detail |
|---|----------|--------|
| 1 | **Minimal complexity** | Single 702-line file, zero runtime dependencies, easy to audit |
| 2 | **Excellent API ergonomics** | Variadic params, intelligent wrapping, `CallFor` convenience method |
| 3 | **Full JSON-RPC 2.0 compliance** | Correct error handling, batch support, all parameter types |
| 4 | **Interface-first design** | `RPCClient` interface makes mocking trivial for consumer tests |
| 5 | **Context support** | Full `context.Context` integration for cancellation and deadlines |
| 6 | **Type-safe response helpers** | `GetInt()`, `GetString()`, `GetObject()` etc. |
| 7 | **Batch response helpers** | `AsMap()`, `GetByID()`, `HasError()` for ergonomic batch result handling |
| 8 | **Flexible HTTP customization** | `HTTPClient` interface accepts any `Do`-compatible client |
| 9 | **Production-proven** | Listed in Awesome Go, stable v3 API |
| 10 | **Comprehensive tests** | 1,023 lines covering parameter edge cases, errors, batches |

### Weaknesses ❌

| # | Weakness | Impact | Mitigation |
|---|----------|--------|------------|
| 1 | **No default timeout** | Requests can block indefinitely | Set timeout via `HTTPClient` or context |
| 2 | **`int`-only request IDs** | JSON-RPC spec allows string IDs | Low impact — most use cases use numeric IDs |
| 3 | **No middleware/hooks** | Can't intercept requests for logging/retry | Wrap with custom `HTTPClient` |
| 4 | **JSON Number handling** | Numeric results require `GetInt()`/`GetFloat()` conversion | By design (`UseNumber()` avoids float64 precision loss) |
| 5 | **No built-in retry** | No automatic retry or circuit breaker | Use custom `HTTPClient` with retry logic |
| 6 | **No request tracing** | No distributed tracing or correlation ID support | Add via custom `HTTPClient` wrapper |
| 7 | **HTTP-only transport** | No WebSocket, Unix socket, or stdio support | Out of scope for this library |
| 8 | **No notification support** | Can't send JSON-RPC notifications (requests without ID) | ID is always present (int, defaults to 0) |
| 9 | **`GetObject` marshal round-trip** | `json.Marshal` then `json.Unmarshal` is wasteful for large results | Acceptable for typical RPC payloads |
| 10 | **No server component** | Client-only library | Use alongside a server library if needed |

---

## 12. Key Design Patterns for jrpcx

### Pattern 1: Variadic Parameter Convenience

Instead of requiring explicit array/object construction:
```go
client.Call(ctx, "method", arg1, arg2, arg3)  // ✅ ergonomic
// vs
client.Call(ctx, "method", []interface{}{arg1, arg2, arg3})  // ❌ verbose
```

### Pattern 2: Reflection-Based Parameter Formatting

Automatically determines JSON-RPC `params` format (array vs. object) based on Go types. Removes cognitive burden from callers.

### Pattern 3: `CallFor` Convenience Method

Collapses three error checks (HTTP error, RPC error, parse error) into a single `error` return:
```go
var user User
err := client.CallFor(ctx, &user, "getUser", id)
```

### Pattern 4: Interface-First Public API

Exporting `RPCClient` interface while keeping `rpcClient` unexported enables:
- Easy mocking in consumer tests
- Swappable implementations
- Clear API contract

### Pattern 5: Typed Collection Helpers

`RPCResponses` as a named type with methods (`AsMap()`, `GetByID()`, `HasError()`) makes batch result handling ergonomic without separate utility functions.

### Pattern 6: Dual Error Return on HTTP+RPC Failure

When HTTP status ≥ 400 but the body contains a valid RPC error, both are returned. This preserves information that would be lost with a single error channel.

### Pattern 7: Configuration via Options Struct

Single `RPCClientOpts` struct with zero-value defaults means `NewClient(endpoint)` works with no configuration, while `NewClientWithOpts` enables full customization.

### Pattern 8: `HTTPClient` Interface for Transport Injection

The minimal `Do(req) (resp, error)` interface enables swapping the entire HTTP stack without changing client code.

---

## 13. Relevance to jrpcx

### What to Adopt ✅

1. **Variadic `Call` signature**: The `Call(ctx, method, params...)` pattern is genuinely ergonomic and should be a primary API in jrpcx. The intelligent parameter wrapping removes JSON-RPC spec knowledge from callers.

2. **`CallFor` convenience pattern**: A single-error-return method that combines call + unmarshal + error unification is valuable. Consider a generic version: `CallFor[T](ctx, method, params...) (T, error)`.

3. **Interface-first client design**: Exporting an interface (not a struct) as the primary client type makes mocking trivial. jrpcx should follow this pattern.

4. **Batch response helpers**: Named types with `AsMap()`, `GetByID()`, `HasError()` are simple and effective. jrpcx should provide similar ergonomics, potentially with generics.

5. **`HTTPClient` injection interface**: The `Do(req) (resp, error)` contract is the right level of abstraction for HTTP customization. jrpcx should use this or a similar pattern for transport flexibility.

6. **Nil slice/map → empty JSON**: Converting nil Go slices to `[]` and nil maps to `{}` for JSON-RPC compliance is a good defensive practice.

7. **Error type separation**: Distinguishing HTTP errors from RPC errors from parse errors gives callers fine-grained control. The `HTTPError` type with status code is worth adopting.

8. **`UseNumber()` on decoder**: Preserving numeric precision by using `json.Number` instead of `float64` is correct for a general-purpose RPC client. jrpcx should do the same.

### What to Improve On ✅

1. **Request ID flexibility**: jrpcx should support `interface{}` IDs (or at minimum `string | int`) per the JSON-RPC spec, not just `int`.

2. **Notification support**: JSON-RPC notifications (requests with no ID) are part of the spec. jrpcx should have a `Notify(ctx, method, params...)` method.

3. **Generic type parameters**: With Go 1.18+ generics, jrpcx can offer `CallFor[T]` instead of `CallFor(ctx, &out, ...)`, eliminating the need for pointer-to-pointer patterns.

4. **Transport abstraction**: Rather than coupling directly to HTTP, jrpcx should consider a transport interface that supports HTTP, WebSocket, and stdio — similar to jrpc2's channel pattern but simpler.

5. **Middleware/interceptor support**: The lack of request/response hooks is ybbus's most significant limitation for production use. jrpcx should provide a middleware chain for logging, tracing, retry, and metrics.

6. **Structured error context**: Error messages as formatted strings are hard to inspect programmatically. jrpcx should use structured errors with `errors.Is`/`errors.As` support and wrapped context.

7. **Default timeout**: jrpcx should ship with a sensible default timeout (e.g., 30s) rather than no timeout.

8. **`GetObject` efficiency**: The marshal→unmarshal round-trip in `GetObject` is wasteful. jrpcx should use `json.RawMessage` for the result field and unmarshal directly.

### What to Avoid ❌

1. **Single-file architecture**: While impressive for a small library, jrpcx's scope warrants proper package separation (client, transport, errors, batch).

2. **`interface{}` for params/result**: With Go generics available, avoid `interface{}` in public APIs where type parameters are feasible.

3. **Global package-level test state**: The test pattern using package-level `responseBody` and `httpStatusCode` variables creates test coupling. jrpcx should use per-test server instances.

4. **`int`-only IDs**: This violates the JSON-RPC spec and limits interoperability. Use `interface{}` or a dedicated `ID` type.

5. **No `DisallowUnknownFields` by default on responses**: ybbus defaults to strict, which breaks against servers that include non-standard fields. jrpcx should default to lenient and allow opting into strict mode.

---

## Quick Reference: Common Usage Patterns

### Simple Call
```go
client := jsonrpc.NewClient("http://api.example.com/rpc")

var result int
err := client.CallFor(ctx, &result, "add", 1, 2)
```

### Batch Call
```go
responses, err := client.CallBatch(ctx, RPCRequests{
    NewRequest("getUserById", 1),
    NewRequest("getUserById", 2),
})
resMap := responses.AsMap()
```

### Authenticated Client
```go
client := jsonrpc.NewClientWithOpts(endpoint, &jsonrpc.RPCClientOpts{
    HTTPClient: &http.Client{Timeout: 30 * time.Second},
    CustomHeaders: map[string]string{
        "Authorization": "Bearer " + token,
    },
})
```

### Error Handling
```go
response, err := client.Call(ctx, "transfer", from, to, amount)
if err != nil {
    if httpErr, ok := err.(*jsonrpc.HTTPError); ok {
        log.Printf("HTTP %d: %s", httpErr.Code, httpErr.Error())
    }
    return err
}
if response.Error != nil {
    return response.Error  // *RPCError implements error
}
txHash, _ := response.GetString()
```

---

**Report Generated**: July 2025
**Library Version**: v3
**Go Version**: 1.21+
**License**: MIT
**Source**: [github.com/ybbus/jsonrpc](https://github.com/ybbus/jsonrpc)
