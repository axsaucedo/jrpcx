# Comprehensive Research Report: creachadair/jrpc2 Go Library

## Executive Summary

The **jrpc2** library is a fully-featured, production-ready implementation of the JSON-RPC 2.0 protocol in Go. It provides both client and server components with a strong emphasis on:
- **Clean abstractions** through the channel pattern for transport independence
- **Type-safe parameter handling** via reflection-based handler adaptation
- **Concurrent request processing** with configurable concurrency limits
- **Context integration** for cancellation and deadline support
- **Non-standard extensions** like server push capabilities (LSP-compatible)

---

## 1. Project Overview

### Library Purpose
The jrpc2 library implements the [JSON-RPC 2.0 specification](http://www.jsonrpc.org/specification) as a complete client-server framework for Go applications. It enables RPC communication between processes using JSON as the wire format.

### Key Design Goals
1. **Protocol Compliance**: Strict adherence to JSON-RPC 2.0 specification
2. **Transport Independence**: Abstract the underlying transport mechanism via channels
3. **Ease of Use**: Minimal boilerplate for common use cases
4. **Type Safety**: Leverage Go's reflection to adapt functions into handlers with validation
5. **Concurrency**: Safe concurrent operation with controlled parallelism
6. **Extensibility**: Support for custom transports, error codes, and server push

### Package Structure
```
jrpc2/
├── jrpc2/          (main package - client, server, request/response, errors)
├── channel/        (transport abstraction - framing implementations)
├── handler/        (function adaptation and handler registration)
├── server/         (convenience utilities - Local in-memory server/client pair)
└── jhttp/          (HTTP-based transport - bridge for HTTP requests)
```

---

## 2. Client API

### Creating a Client
```go
ch := channel.Line(conn, conn)  // any Channel implementation
cli := jrpc2.NewClient(ch, nil) // nil for default options
```

**Client Structure** (client.go, lines 18-35):
```go
type Client struct {
    done *sync.WaitGroup           // tracks reader goroutine
    pending map[string]*Response   // requests awaiting replies, keyed by ID
    nextID int64                   // monotonic request ID counter
    cbctx context.Context          // terminates when client closes
    ch channel.Channel             // underlying transport
    err error                      // final error status
}
```

### Single Request Call
```go
rsp, err := cli.Call(ctx, "Math.Add", []int{1, 3, 5, 7})
if e, ok := err.(*jrpc2.Error); ok {
    log.Fatalf("Server error: %v", e)
}
var result int
rsp.UnmarshalResult(&result)
```

**Implementation Details**:
- `Call()` creates a single request, sends it, and waits for the response
- ID is auto-incremented (starting at 1 to avoid null equivalence issues)
- Parameters are validated to be JSON arrays or objects
- Context timeouts are supported and converted to jrpc2 error codes

### Batch Requests
```go
rsps, err := cli.Batch(ctx, []jrpc2.Spec{
    {Method: "Math.Add", Params: []int{1, 2, 3}},
    {Method: "Math.Mul", Params: []int{4, 5, 6}},
    {Method: "Math.Max", Params: []int{-1, 5, 3}},
})
// Responses returned in same order, omitting notifications
```

**Features**:
- Multiple requests sent in a single batch
- Concurrent processing on server side
- Responses maintain order of non-notification requests
- Batch errors are separate from individual response errors

### Notifications
```go
err := cli.Notify(ctx, "Alert", handler.Obj{
    "message": "A fire is burning!",
})
```

**Semantics**:
- One-way request with no expected response
- Complete once sent (no waiting for server processing)
- Can be part of batch requests
- Useful for asynchronous updates

### Convenient Result Unpacking
```go
var sum int
err := cli.CallResult(ctx, "Math.Add", []int{1,2,3}, &sum)
```

### Concurrent Request Handling
The client is **thread-safe for concurrent use**:
- Multiple goroutines can call `Call()`, `Batch()`, or `Notify()` simultaneously
- WaitGroup-based reader goroutine processes responses from server
- Pending responses stored in map with ID-based lookup
- Buffered channels prevent rendezvous between reader and callers

---

## 3. Channel/Transport Abstraction

### Channel Interface Design (channel/channel.go)
```go
type Channel interface {
    Send([]byte) error              // send one complete record
    Recv() ([]byte, error)          // receive one complete record
    Close() error                   // close the channel
}

type Framing func(io.Reader, io.WriteCloser) Channel
```

**Design Philosophy**:
- Minimal interface (3 methods only)
- Records are opaque byte sequences (no interpretation)
- Framing is responsible for message delimitation
- One sender and one receiver may use channel concurrently (but not otherwise thread-safe)

### Built-in Framing Implementations

#### 1. Line Framing (channel/split.go)
```go
ch := channel.Line(r, wc)  // messages terminated by \n
```
- Messages delimited by newline character (LF)
- Constraint: messages cannot contain \n internally
- Simple, human-readable for debugging
- Good for line-based protocols (stdin/stdout, netcat)

#### 2. Raw JSON Framing (channel/json.go)
```go
ch := channel.RawJSON(r, wc)
```
- Each message is a complete JSON value
- Decoder automatically handles JSON structure
- No out-of-band framing
- Cannot recover from invalid JSON

#### 3. Header Framing (channel/hdr.go)
```go
ch := channel.Header("application/json")  // HTTP-style headers
```

Format:
```
Content-Type: application/json\r\n
Content-Length: 123\r\n
\r\n
<payload>
```
- Inspired by HTTP message framing
- Supports Content-Type validation
- Graceful recovery from malformed messages
- Used by Language Server Protocol (LSP)

#### 4. Direct In-Memory Channel (channel/channel.go)
```go
client, server := channel.Direct()
```
- Two-way buffered channels
- No framing, direct message passing
- Useful for testing, same-process communication
- Zero-copy if caller manages buffers

### Transport Independence Pattern

This is a **key architectural strength**:

```go
// HTTP transport
httpCh := jhttp.Channel(httpConn)

// TCP socket
tcpCh := channel.Line(conn, conn)

// WebSocket (via LSP header)
wsCh := channel.Header("application/vnd.gpt+json")

// Both client and server use identical interface:
cli := jrpc2.NewClient(ch, opts)
srv := jrpc2.NewServer(assigner, opts).Start(ch)
```

**Benefits**:
- Swap transports without changing application logic
- Easy to test with in-memory channels
- Support multiple protocols simultaneously
- Custom framings can be added for specialized transports

---

## 4. Request/Response Types

### Request Structure (base.go)
```go
type Request struct {
    id     json.RawMessage  // nil for notifications
    method string           // method name
    params json.RawMessage  // encoded parameters
}

// Methods
func (r *Request) IsNotification() bool
func (r *Request) ID() string
func (r *Request) Method() string
func (r *Request) HasParams() bool
func (r *Request) UnmarshalParams(v any) error
```

**Parameter Unmarshaling Features**:
- Automatically ignores unknown fields in objects
- Supports `StrictFields` wrapper for strict validation
- Handles positional array parameters via struct field mapping
- Returns `InvalidParams` error on decode failure
- Supports `json.RawMessage` for passthrough

### Response Structure (base.go)
```go
type Response struct {
    id     string
    err    *Error
    result json.RawMessage
    ch     chan *jmessage  // for synchronization
    cancel func()          // context cancellation
}

// Methods
func (r *Response) ID() string
func (r *Response) Error() *Error
func (r *Response) UnmarshalResult(v any) error
func (r *Response) SetID(s string)  // for proxies
```

**Synchronization Details**:
- Channel-based waiting (first reader updates response, closes channel)
- Multiple waiters supported (safe for concurrent access)
- Context cancellation handled automatically
- Result only valid after `wait()` completes

### JSON Wire Format (RFC 7159)

Request:
```json
{"jsonrpc":"2.0", "id":1, "method":"Add", "params":[1,2,3]}
```

Response:
```json
{"jsonrpc":"2.0", "id":1, "result":6}
```

Error Response:
```json
{"jsonrpc":"2.0", "id":1, "error":{"code":-32602, "message":"Invalid params"}}
```

---

## 5. Batch Operations

### Batch Request Semantics
```go
specs := []jrpc2.Spec{
    {Method: "M1", Params: p1},          // normal call
    {Method: "M2", Params: p2, Notify: true},  // notification
    {Method: "M3", Params: p3},          // normal call
}
rsps, err := cli.Batch(ctx, specs)
// rsps contains 2 responses (M1, M3) - M2 omitted per spec
```

**Server-Side Processing** (server.go):
1. Receive entire batch as array
2. Validate each request (duplicate IDs, method names)
3. **Partition into concurrent and sequential**:
   - Requests in same batch can be concurrent
   - Requests from different batches maintain order
   - Non-concurrent requests processed in order
4. Assign handlers and set up contexts
5. Invoke handlers with concurrency limit
6. Collect responses and send back

**Notification Barrier** (server.go, lines 220-225):
```go
type Server struct {
    nbar sync.WaitGroup  // notification barrier
}

func (s *Server) waitForBarrier(n int) {
    s.nbar.Unlock()
    defer s.nbar.Lock()
    s.nbar.Wait()        // wait for pending notifications
    s.nbar.Add(n)        // register new notifications
}
```

**Semantics**:
- Ensures notifications within batch complete before subsequent calls
- Prevents reordering violations across batch boundaries
- Crucial for LSP and other strict ordering requirements

---

## 6. Error Handling

### Error Type Hierarchy

```go
// jrpc2.Error - JSON-RPC error object (RFC 7159)
type Error struct {
    Code    Code            // machine-readable error code (-32768 to 32000)
    Message string          // human-readable description
    Data    json.RawMessage // optional error-specific data
}

// ErrCoder interface for converting Go errors to error codes
type ErrCoder interface {
    ErrCode() Code
}
```

### Standard Error Codes (code.go)
```go
const (
    ParseError     Code = -32700  // Invalid JSON
    InvalidRequest Code = -32600  // Request structure invalid
    MethodNotFound Code = -32601  // Method doesn't exist
    InvalidParams  Code = -32602  // Parameters don't match
    InternalError  Code = -32603  // Server internal error
    
    // jrpc2-specific codes
    NoError          Code = -32099
    SystemError      Code = -32098
    Cancelled        Code = -32097  // context.Canceled
    DeadlineExceeded Code = -32096  // context.DeadlineExceeded
)
```

### Error Code Detection
```go
func ErrorCode(err error) Code {
    if err == nil { return NoError }
    if err implements ErrCoder { return err.ErrCode() }
    if errors.Is(err, context.Canceled) { return Cancelled }
    if errors.Is(err, context.DeadlineExceeded) { return DeadlineExceeded }
    return SystemError
}
```

### Handler Error Returns
```go
func handleRequest(ctx context.Context, req *jrpc2.Request) (any, error) {
    // Option 1: Return jrpc2.Error directly
    if badParams {
        return nil, jrpc2.Errorf(jrpc2.InvalidParams, "expected array")
    }
    
    // Option 2: Return custom error implementing ErrCoder
    if notFound {
        return nil, customErr{code: -32999}  // custom app code
    }
    
    // Option 3: Return standard Go error (converted to SystemError)
    if dbError {
        return nil, fmt.Errorf("database connection lost")
    }
    
    return result, nil
}
```

### Error Data Attachment
```go
err := jrpc2.Errorf(jrpc2.InvalidParams, "wrong type")
err = err.WithData(map[string]any{
    "expected": "array",
    "got":      "object",
})
// JSON: {"code":-32602, "message":"wrong type", "data":{...}}
```

---

## 7. Handler Pattern

### Handler Signature (base.go)
```go
type Handler = func(context.Context, *Request) (any, error)
```

### Reflection-Based Adaptation (handler/handler.go)

The library uses **heavy reflection during setup, minimal reflection at call time**:

```go
// Flexible signatures supported:
func(ctx context.Context) error
func(ctx context.Context) Y
func(ctx context.Context) (Y, error)
func(ctx context.Context, X) error
func(ctx context.Context, X) Y
func(ctx context.Context, X) (Y, error)
func(ctx context.Context, *jrpc2.Request) error
func(ctx context.Context, *jrpc2.Request) (any, error)

// Usage
h := handler.New(myFunc)  // panics on invalid signature
```

### Handler Registration (handler/handler.go)

**Map-based dispatch**:
```go
assigner := handler.Map{
    "Add": handler.New(func(ctx context.Context, vals []int) int {
        sum := 0
        for _, v := range vals { sum += v }
        return sum
    }),
    "Mul": handler.New(func(ctx context.Context, x, y int) int {
        return x * y
    }),
}
```

**Service hierarchy**:
```go
assigner := handler.ServiceMap{
    "Math": handler.Map{
        "Add": handler.New(Add),
        "Mul": handler.New(Mul),
    },
    "String": handler.Map{
        "Upper": handler.New(Upper),
    },
}
// Calls: "Math.Add", "String.Upper"
```

### Parameter Handling

**Array-to-Struct Translation** (handler/handler.go):
```go
type Params struct {
    X int    `json:"x"`
    Y int    `json:"y"`
}

func Add(ctx context.Context, p Params) int { return p.X + p.Y }

// Supports both:
// {"x": 5, "y": 3}  - object
// [5, 3]            - array (mapped to X, Y in order)
```

**Positional Parameters**:
```go
h := handler.NewPos(MyFunc, "first", "second", "third")
```

**Strict Field Checking**:
```go
fi := handler.Check(MyFunc)
fi.SetStrict(true)  // reject unknown fields
h := fi.Wrap()
```

### Handler Wrapper Implementation (handler/handler.go, lines 135-240)

The `Wrap()` method generates optimized wrappers:

1. **Pre-compilation of helper functions**:
   - `newInput`: Unmarshals JSON to Go types
   - `decodeOut`: Marshals Go results back to JSON
   - Validation happens at wrap-time, not call-time

2. **Three input cases**:
   - No parameters: validates no params sent
   - `*Request` type: passes request directly
   - Struct/value type: unmarshals JSON into typed param

3. **Return value handling**:
   - No result, error only
   - Result only, no error
   - Result and error both

### Accessing Request Context

Within a handler:
```go
func MyHandler(ctx context.Context, req *jrpc2.Request) (any, error) {
    // Option 1: Direct parameter (for native handlers)
    method := req.Method()
    
    // Option 2: Via context (for wrapped handlers)
    req = jrpc2.InboundRequest(ctx)
    
    // Option 3: Access server
    srv := jrpc2.ServerFromContext(ctx)
}
```

---

## 8. Concurrency Model

### Client Concurrency (client.go)

**Thread-Safe Design**:
```go
c.mu sync.Mutex                    // protects shared state
c.pending map[string]*Response     // keyed by request ID
c.nextID int64                     // atomic increment
c.done *sync.WaitGroup             // reader goroutine tracking

// Call flow:
// 1. Call() creates request outside lock
// 2. Acquires lock, sends message
// 3. Registers Response in pending map
// 4. Launches waitComplete goroutine for context cancellation
// 5. Releases lock
// 6. Caller waits on Response.ch (buffered, 1)
// 7. Reader goroutine processes responses, delivers via ch
```

**Response Wait Synchronization** (base.go, lines 173-196):
```go
func (r *Response) wait() {
    raw, ok := <-r.ch
    if ok {  // first waiter
        r.err = raw.E
        r.result = raw.R
        close(r.ch)        // signal other waiters
        r.cancel()
    }
    // Subsequent waiters read nil from closed ch
}
```

**Features**:
- Multiple concurrent waiters on same response supported
- First successful reader updates response and closes channel
- No data race due to strict ordering
- Context cancellation tracked per request

### Server Concurrency (server.go)

**Concurrency Limits**:
```go
type Server struct {
    sem *semaphore.Weighted  // bounded concurrency
}

// Default: runtime.NumCPU() (configurable)
opts := &jrpc2.ServerOptions{Concurrency: 16}
```

**Request Processing Pipeline** (server.go, lines 154-212):
```
serve()
  └─ nextRequest() [blocking queue]
      └─ dispatchLocked(batch) [with semaphore]
          ├─ checkAndAssignLocked() [assign handlers]
          ├─ waitForBarrier() [notification ordering]
          └─ invoke handlers
              ├─ sem.Acquire()    [concurrency gating]
              ├─ h(ctx, req)      [handler execution]
              └─ sem.Release()
```

**Request Batch Ordering** (server.go, lines 236-273):
```go
func (s *Server) dispatchLocked(next jmessages, ch sender) func() error {
    tasks := s.checkAndAssignLocked(next)
    todo, notes := tasks.numToDo()
    s.waitForBarrier(notes)  // wait for prior notifications
    
    return func() error {
        var wg sync.WaitGroup
        for _, t := range tasks {
            if todo == 1 {
                t.val, t.err = s.invoke(...)  // last: inline
                break
            }
            todo--
            wg.Go(func() { t.val, t.err = s.invoke(...) })
        }
        wg.Wait()
        return s.deliver(tasks.responses(...), ch, ...)
    }
}
```

**Key Properties**:
- Concurrent requests within a batch execute in parallel
- Non-concurrent requests from different batches maintain order
- Last request in batch executes inline (avoids goroutine overhead)
- Notification barrier ensures strict ordering across batches

### Server Push (Bidirectional RPC)

Servers can push calls/notifications to clients:
```go
func MyHandler(ctx context.Context, req *jrpc2.Request) (any, error) {
    srv := jrpc2.ServerFromContext(ctx)
    
    // Send notification (one-way)
    srv.Notify(ctx, "ClientUpdate", status)
    
    // Send call and wait for response (requires client support)
    if rsp, err := srv.Callback(ctx, "ClientMethod", params); err == nil {
        // Process response
    }
}
```

**Configuration**:
```go
opts := &jrpc2.ServerOptions{AllowPush: true}
```

---

## 9. Context Integration

### Context Propagation

**Server Handler Context** (server.go, lines 358-367):
```go
func (s *Server) setContext(t *task, id string) {
    t.ctx = context.WithValue(s.newctx(), inboundRequestKey{}, t.hreq)
    
    if id != "" {  // non-notification
        ctx, cancel := context.WithCancel(t.ctx)
        s.used[id] = cancel
        t.ctx = ctx
    }
}
```

**Context Values Available**:
- `jrpc2.InboundRequest(ctx)` - get Request
- `jrpc2.ServerFromContext(ctx)` - get Server
- `jrpc2.ClientFromContext(ctx)` - get Client (in callback handlers)

### Timeout and Cancellation (client.go, lines 245-282)

**Client Context Handling**:
```go
func (c *Client) waitComplete(pctx context.Context, id string, p *Response) {
    <-pctx.Done()  // wait for context to end
    
    c.mu.Lock()
    if _, ok := c.pending[id]; !ok {
        return  // already responded
    }
    delete(c.pending, id)
    
    // Convert context error to JSON-RPC error code
    var jerr *Error
    if pctx.Err() != nil {
        jerr = &Error{Code: ErrorCode(pctx.Err()), Message: pctx.Err().Error()}
    }
    p.ch <- &jmessage{ID: json.RawMessage(id), E: jerr}
    
    if c.chook != nil {
        // Invoke OnCancel hook
    }
}
```

**Features**:
- Context cancellation converts to `Cancelled` error code (-32097)
- Deadline exceeded converts to `DeadlineExceeded` code (-32096)
- OnCancel hook supports custom cancellation handling (e.g., send cancel RPC)
- Per-request timeout support

### Built-in Context Options (opts.go, lines 42-44)

```go
type ServerOptions struct {
    NewContext func() context.Context  // custom base context factory
}

// Example: add default 30-second timeout
opts := &jrpc2.ServerOptions{
    NewContext: func() context.Context {
        ctx, _ := context.WithTimeout(context.Background(), 30*time.Second)
        return ctx
    },
}
```

---

## 10. Code Organization

### Package Hierarchy

```
jrpc2/
├── client.go          (449 lines)  - Client implementation
├── server.go          (838 lines)  - Server implementation  
├── base.go            (247 lines)  - Request/Response types, Assigner/Handler interfaces
├── error.go           (73 lines)   - Error type and codes
├── code.go            (110 lines)  - Error code definitions and conversion
├── json.go            (333 lines)  - JSON parsing and message serialization
├── opts.go            (244 lines)  - Configuration options
├── ctx.go             (46 lines)   - Context utilities
├── doc.go             (266 lines)  - Package documentation
│
├── channel/
│   ├── channel.go     - Channel interface and Direct() implementation
│   ├── split.go       - Line/Split framing
│   ├── json.go        - RawJSON framing
│   ├── hdr.go         - Header/StrictHeader framing (HTTP-style)
│   └── bench_test.go  - Performance tests
│
├── handler/
│   ├── handler.go     (403 lines) - Function adaptation, Map/ServiceMap
│   ├── positional.go  - Positional parameter support
│   ├── helpers.go     - Utility functions
│   └── example_test.go - Usage examples
│
├── server/
│   ├── local.go       - In-memory server/client pair for testing
│   └── loop.go        - Connection loop for multiple clients
│
└── jhttp/
    ├── channel.go     - HTTP-based channel
    ├── getter.go      - HTTP GET request support
    └── bridge.go      - Client/server bridge for HTTP
```

### Dependencies
- Standard library only: `context`, `encoding/json`, `sync`, `time`, `io`, `net`
- External: `golang.org/x/sync/semaphore` (bounded concurrency)
- External: `github.com/creachadair/mds/queue` (work queue)

### Key Type Relationships

```
Assigner interface
  ├─ (ctx, method) -> Handler
  └─ Optional: Namer interface
      └─ Names() -> []string

Handler type (function)
  └─ (context.Context, *Request) -> (any, error)

Channel interface
  ├─ Send([]byte) error
  ├─ Recv() ([]byte, error)
  └─ Close() error
  └─ Created by Framing function

Server
  ├─ uses Assigner to lookup handlers
  ├─ uses Channel for I/O
  ├─ batches work in queues
  └─ uses semaphore for concurrency control

Client
  ├─ uses Channel for I/O
  ├─ tracks pending Responses by ID
  └─ uses context for timeout/cancellation
```

---

## 11. Type Safety & Go Generics

### No Generics Used
This library predates Go 1.18 generics and doesn't use them. Instead, it relies on:

1. **Interface{}** for return values and parameters
   ```go
   type Handler = func(context.Context, *Request) (any, error)
   ```

2. **Type Assertions** for unmarshaling
   ```go
   var result MyType
   err := rsp.UnmarshalResult(&result)
   ```

3. **Reflection** at wrapper generation time (not runtime)
   ```go
   fi, _ := handler.Check(myFunc)
   h := fi.Wrap()  // reflection during setup
   ```

### Type Safety Mechanisms

**Compile-Time**:
- Handler signature validation via `handler.Check()`
- Request parameter types validated via `UnmarshalParams()`
- Response result types validated via `UnmarshalResult()`

**Runtime**:
- JSON unmarshaling validates types
- Channel framing validates message format
- Error codes validate ranges (-32768 to 32000)

**Static Assertions** (internal_test.go):
```go
var (
    _ jrpc2.ErrCoder = (*jrpc2.Error)(nil)
)
```

---

## 12. Strengths and Weaknesses

### Strengths ✓

1. **Transport Independence**
   - Channel abstraction cleanly separates protocol from transport
   - Easy to add custom framings (WebSocket, HTTP/2, etc.)
   - Excellent for testing with in-memory channels

2. **Full JSON-RPC 2.0 Compliance**
   - Handles all edge cases (empty batches, duplicate IDs, notifications)
   - Proper error codes and error data support
   - Batch request semantics respected

3. **Concurrent Operation**
   - Thread-safe client for multiple concurrent requests
   - Configurable server concurrency with semaphore
   - Proper request ordering across batches

4. **Flexible Handler Definition**
   - Minimal boilerplate via handler.New()
   - Supports multiple signatures
   - Automatic JSON parameter handling with struct field mapping
   - Positional parameter support

5. **Context Integration**
   - Per-request timeouts via context
   - Cancellation propagation
   - Hooks for custom cancellation handling
   - Proper cleanup on shutdown

6. **Error Handling**
   - Standard error codes plus custom app codes
   - Error data attachment
   - ErrCoder interface for custom error types
   - Automatic context error conversion

7. **Server Push (Bidirectional)**
   - Non-standard but useful extension
   - LSP-compatible
   - Configurable per-server

8. **Production Quality**
   - Extensive test coverage (1330 line test file)
   - Panic recovery in callback handlers
   - Metrics/telemetry support via expvar
   - Stable API (semantic versioning)

9. **Minimal Dependencies**
   - Mostly standard library
   - Only 2 external dependencies
   - Fast to import and compile

### Weaknesses/Limitations ✗

1. **No Streaming Support**
   - Request/response are message-based, not streaming
   - Large payloads require marshaling entire message into memory
   - No support for Server-Sent Events or streaming requests

2. **No Middleware/Interceptors**
   - No hook points for logging, auth, or metrics at protocol level
   - Must wrap handlers or use custom Assigner implementation
   - No request/response modification without reflection

3. **Limited HTTP Support**
   - `jhttp` package is thin, mostly for simple request/response
   - No built-in HTTP header handling (Content-Type, Authorization)
   - No cookie/session support

4. **No Built-in TLS**
   - Relies on net.Dial which can be wrapped with TLS
   - No convenience helpers (compared to gRPC)
   - User responsible for certificate handling

5. **Channel API is One-Way Per Call**
   - Must use separate channels for bidirectional communication
   - Server push requires client support (non-standard)
   - Harder to implement request-response patterns in custom framings

6. **Reflection Overhead on Handler Registration**
   - While optimized (pre-compilation), still has startup cost
   - Not suitable for dynamic handler registration in hot paths
   - Direct Handler implementation if performance critical

7. **No Built-in Service Discovery**
   - Must hardcode server addresses
   - No registry or load balancing
   - No automatic failover

8. **Limited Debugging Support**
   - Logger hook is basic (Printf style)
   - No structured logging
   - No request/response tracing by default

9. **Error Messages Could Be More Detailed**
   - Some validation errors lack context
   - Stack traces not included in error data
   - Difficult to debug handler failures

10. **Documentation**
    - Package docs are excellent but examples are limited
    - No guide for common patterns (auth, metrics, logging)
    - Real-world deployment patterns not documented

### Performance Characteristics

**Strengths**:
- Pre-compiled handlers minimize reflection overhead
- Buffered channels prevent context switch overhead
- Inline execution of last request in batch
- No goroutine per request unless concurrent

**Limitations**:
- Full message marshaling/unmarshaling (no streaming)
- Channel.Send() is blocking (no async send buffer)
- No connection pooling
- Semaphore-based concurrency control (not as fine-grained as work stealing)

---

## 13. Real-World Usage Patterns

### Simple Request-Response
```go
// Server
assigner := handler.Map{
    "ping": handler.New(func(ctx context.Context) string {
        return "pong"
    }),
}
srv := jrpc2.NewServer(assigner, nil)
srv.Start(channel.Line(os.Stdin, os.Stdout))
srv.Wait()

// Client
ch := channel.Line(conn, conn)
cli := jrpc2.NewClient(ch, nil)
rsp, _ := cli.Call(context.Background(), "ping", nil)
var result string
rsp.UnmarshalResult(&result)  // "pong"
```

### Service Hierarchy
```go
assigner := handler.ServiceMap{
    "Math": handler.Map{
        "Add": handler.New(Add),
        "Mul": handler.New(Mul),
    },
    "String": handler.Map{
        "Upper": handler.New(Upper),
        "Lower": handler.New(Lower),
    },
}
srv := jrpc2.NewServer(assigner, nil).Start(ch)
```

### Batch Operations
```go
specs := []jrpc2.Spec{
    {Method: "Math.Add", Params: []int{1,2,3}},
    {Method: "Math.Mul", Params: []int{4,5}},
}
rsps, _ := cli.Batch(ctx, specs)
for i, rsp := range rsps {
    var result int
    rsp.UnmarshalResult(&result)
    log.Printf("Result %d: %d", i, result)
}
```

### With Timeouts
```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
rsp, err := cli.Call(ctx, "slow_method", nil)
if errors.Is(err, context.DeadlineExceeded) {
    log.Println("Timeout!")
}
```

### Server Push (LSP-style)
```go
func HandleRequest(ctx context.Context, req *jrpc2.Request) (any, error) {
    srv := jrpc2.ServerFromContext(ctx)
    
    // Send status update to client
    srv.Notify(ctx, "$/setStatus", map[string]string{
        "status": "busy",
    })
    
    // Do work...
    
    // Check if client wants to cancel
    if ctx.Err() != nil {
        return nil, ctx.Err()
    }
    
    return result, nil
}

opts := &jrpc2.ServerOptions{AllowPush: true}
srv := jrpc2.NewServer(assigner, opts).Start(ch)
```

---

## 14. Comparison to Similar Projects

| Feature | jrpc2 | gorilla/rpc | ethereum/go-ethereum | coreos/etcd |
|---------|-------|-------------|----------------------|------------|
| JSON-RPC 2.0 | ✓ Full | ✗ Custom | ✓ Partial | ✗ Custom |
| Transport Abstraction | ✓ Excellent | ✗ HTTP only | ✗ HTTP only | ✗ gRPC |
| Bidirectional | ✓ (non-std) | ✗ | ✗ | ✓ gRPC |
| Handler Adaptation | ✓ Auto | ✓ Manual | ✗ | ✗ |
| Batch Requests | ✓ | ✗ | ✓ | ✗ |
| Error Codes | ✓ Standard | ✓ Custom | ✓ Custom | ✗ |
| Context Support | ✓ Full | ✓ Basic | ✗ | ✓ Full |
| Dependencies | ✓ Minimal | ✓ Minimal | ✓ Minimal | ✗ Many |

---

## 15. Conclusion

The **creachadair/jrpc2** library is a **well-engineered, production-ready implementation** of JSON-RPC 2.0 that prioritizes:

1. **Clean abstractions** (transport-independent channels)
2. **Ease of use** (reflection-based handler adaptation)
3. **Correctness** (full spec compliance, extensive tests)
4. **Concurrency** (safe for concurrent use, configurable parallelism)
5. **Minimal overhead** (few external dependencies, efficient message handling)

It's an excellent choice for:
- Building microservices that need JSON-RPC
- Implementing LSP language servers
- Creating lightweight RPC frameworks
- Testing distributed systems
- Learning JSON-RPC implementation patterns

It's less suitable for:
- Streaming or file transfer workloads
- Systems requiring built-in authentication
- High-throughput, low-latency scenarios
- Applications needing HTTP-specific features

The codebase is clean, well-documented, and maintainable, making it an ideal reference implementation for the JSON-RPC 2.0 protocol.

