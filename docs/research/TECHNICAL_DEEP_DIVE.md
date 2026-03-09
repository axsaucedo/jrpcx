# Technical Deep Dive: jrpc2 Implementation Patterns

## 1. Channel Pattern: Transport Abstraction

### The Interface Design

```go
type Channel interface {
    Send([]byte) error
    Recv() ([]byte, error)
    Close() error
}
```

**Why This Design?**
- **Minimal API Surface**: 3 methods only, easy to implement
- **Message Semantics**: Records are opaque (no interpretation)
- **Framing Separation**: Framing is user-provided (pluggable)
- **Testing**: Can mock with channels directly

### Framing Implementations

#### Line Framing (Most Common)
```go
type split struct {
    split byte              // delimiter (default \n)
    wc io.WriteCloser
    buf *bufio.Reader
}

func (c split) Send(msg []byte) error {
    if bytes.IndexByte(msg, c.split) >= 0 {
        return errors.New("message contains split byte")
    }
    out := append(msg, c.split)
    _, err := c.wc.Write(out)
    return err
}

func (c split) Recv() ([]byte, error) {
    line, err := c.buf.ReadSlice(c.split)
    if n := len(line) - 1; n >= 0 {
        return line[:n], err
    }
    return nil, err
}
```

**Use Cases**:
- stdin/stdout communication
- telnet-style protocols
- Human-readable debugging
- Simple socket communication

#### Header Framing (LSP)
```go
Content-Type: application/json\r\n
Content-Length: 123\r\n
\r\n
<payload>
```

**Advantages**:
- Graceful recovery from malformed messages
- Content-type negotiation
- Compatible with HTTP semantics
- Used by Language Server Protocol

#### Direct Framing (Testing)
```go
func Direct() (client, server Channel) {
    c2s := make(chan []byte)
    s2c := make(chan []byte)
    client = direct{send: c2s, recv: s2c}
    server = direct{send: s2c, recv: c2s}
    return
}
```

**Perfect for**:
- Unit tests
- Same-process communication
- No framing overhead
- Direct buffer passing (be careful!)

### Why Channel Matters

Enables this pattern:

```go
// Works with ANY transport
func NewService(ch channel.Channel) (*Service, error) {
    cli := jrpc2.NewClient(ch, opts)
    // ...
}

// Usage:
NewService(channel.Line(conn, conn))        // TCP
NewService(channel.Header("app/json"))      // LSP
NewService(channel.RawJSON(r, w))           // Streaming JSON
NewService(channel.Direct())                // Testing
```

---

## 2. Concurrency Model: Client Side

### Request ID Management

```go
type Client struct {
    mu      sync.Mutex
    nextID  int64                      // monotonic counter
    pending map[string]*Response       // by string ID
}

func (c *Client) req(ctx context.Context, method string, params any) (*jmessage, error) {
    c.mu.Lock()
    defer c.mu.Unlock()
    
    id := json.RawMessage(strconv.FormatInt(c.nextID, 10))
    c.nextID++  // increment BEFORE use to avoid race
    
    return &jmessage{
        ID: id,
        M:  method,
        P:  bits,
    }, nil
}
```

**Why start at 1?**
- Avoids null equivalence with 0
- Makes debugging easier (1-indexed is human-readable)
- Prevents edge cases with JSON null handling

### Response Synchronization Pattern

```go
func newPending(ctx context.Context, id string) (context.Context, *Response) {
    pctx, cancel := context.WithCancel(ctx)
    return pctx, &Response{
        ch:     make(chan *jmessage, 1),  // BUFFERED!
        id:     id,
        cancel: cancel,
    }
}

// Called by send():
c.pending[p.id] = p
go c.waitComplete(pctx, p.id, p)  // launch context watcher

// Called by reader goroutine (in accept()):
c.pending[id] = p
p.ch <- rsp  // buffered, non-blocking write

// Called by waiter:
func (r *Response) wait() {
    raw, ok := <-r.ch
    if ok {  // first waiter
        r.err = raw.E
        r.result = raw.R
        close(r.ch)  // signal subsequent waiters
        r.cancel()
    }
    // Subsequent waiters read nil from closed ch
}
```

**Key Insight**: Buffered channel (size 1) prevents:
- Goroutine rendezvous (reader doesn't block)
- Deadlock on Close() (no pending writers to unblock)
- Data races (first reader updates response, then closes channel)

### Context Cancellation Per Request

```go
func (c *Client) waitComplete(pctx context.Context, id string, p *Response) {
    <-pctx.Done()  // wait for context to end
    
    c.mu.Lock()
    defer c.mu.Unlock()
    
    if _, ok := c.pending[id]; !ok {
        return  // already responded (too late)
    }
    
    delete(c.pending, id)
    
    // Convert context error to JSON-RPC error
    jerr := &Error{
        Code: ErrorCode(pctx.Err()),
        Message: pctx.Err().Error(),
    }
    
    p.ch <- &jmessage{ID: json.RawMessage(id), E: jerr}
    
    // Run cancellation hook (outside lock)
    if c.chook != nil {
        // OnCancel handler
    }
}
```

**Semantics**:
- Each request gets its own context (scoped lifetime)
- Cancellation is independent per request
- Hook allows custom cancellation (e.g., send cancel RPC)
- Gracefully handles "too late" cancellations

### Thread Safety

```go
// SAFE: Multiple goroutines calling simultaneously
go func() { cli.Call(ctx1, "foo", nil) }()
go func() { cli.Call(ctx2, "bar", nil) }()
go func() { cli.Batch(ctx3, specs) }()

// The lock protects:
// - nextID counter (monotonic increment)
// - pending map (response delivery)
// - ch and err fields (state)

// NOT protected by lock:
// - Individual Response objects
// - Response.wait() (uses buffered channel)
```

---

## 3. Concurrency Model: Server Side

### Batch Request Processing Pipeline

```
read(channel)
  └─> batch message received
      └─> enqueue batch
          └─> signal workers
              └─> nextRequest() dequeues batch
                  └─> dispatchLocked() validates & assigns
                      └─> checkAndAssignLocked()
                          ├─ duplicate ID detection
                          ├─ method assignment
                          └─ context setup
                      └─> waitForBarrier() (notification ordering)
                      └─> invoke handlers
                          ├─ sem.Acquire() (concurrency gating)
                          ├─ h(ctx, req)
                          └─ sem.Release()
                      └─> deliver() responses
```

### Concurrency Control

```go
type Server struct {
    sem *semaphore.Weighted  // default: runtime.NumCPU()
}

// In invoke():
func (s *Server) invoke(base context.Context, h Handler, req *Request) (...) {
    if err := s.sem.Acquire(ctx, 1); err != nil {
        return nil, err  // context cancelled
    }
    defer s.sem.Release(1)
    
    v, err := h(ctx, req)
    // ...
}
```

**Behavior**:
- Limits concurrent handler execution
- Semaphore is fair (FIFO-like)
- Respects request context deadlines
- Default: NumCPU (one slot per core)

### Notification Barrier

The most subtle concurrency mechanism:

```go
type Server struct {
    nbar sync.WaitGroup  // tracks pending notifications
}

// In dispatchLocked():
func (s *Server) dispatchLocked(next jmessages, ch sender) func() error {
    tasks := s.checkAndAssignLocked(next)
    todo, notes := tasks.numToDo()
    
    // KEY: Wait for prior notification batch to complete
    s.waitForBarrier(notes)
    
    return func() error {
        // ... invoke handlers ...
        if t.hreq.IsNotification() {
            s.nbar.Done()  // decrement when notification completes
        }
    }
}

// In waitForBarrier():
func (s *Server) waitForBarrier(n int) {
    s.mu.Unlock()  // avoid deadlock with handler calling back in
    defer s.mu.Lock()
    
    s.nbar.Wait()        // wait for prior batch notifications
    s.nbar.Add(n)        // register new notifications to await
}
```

**Why This Matters**:

JSON-RPC doesn't guarantee request order in responses:

```json
// Request batch:
[
  {"id":1, "method":"notify", "params":[]},
  {"id":2, "method":"call", "params":[]}
]

// If notification (id:1) completes AFTER call (id:2),
// the response order changes semantically.
// The notification barrier ensures notifications are processed
// before subsequent batches start.
```

**Sequence**:
1. Batch 1: calls [notification A, call B]
2. Wait for barrier (no prior notifications)
3. Execute A and B concurrently
4. Add 1 to barrier (A is pending notification)
5. Send responses [B]
6. Batch 2: calls [call C]
7. Wait for barrier (A must complete first)
8. A completes → nbar.Done()
9. Barrier satisfied, proceed with C

### Request Ordering Guarantees

```
Batch 1: [N1, R1] (N = notification, R = request with response)
Batch 2: [R2]
Batch 3: [N2, R3]

Timeline:
Time 0: Receive batch 1 -> N1, R1 queued
Time 1: Dispatch batch 1 -> N1 and R1 start concurrently
Time 2:  R1 completes -> response sent immediately
Time 3:  N1 completes -> (response not sent)
Time 4: Receive batch 2 -> R2 queued
Time 5: Dispatch batch 2 -> WAIT (N1 from batch 1 still pending!)
Time 6:  N1 completes -> nbar.Done()
Time 7: R2 starts executing
Time 8: R2 completes -> response sent
Time 9: Receive batch 3 -> N2, R3 queued
Time 10: Dispatch batch 3 -> (no barrier wait needed)
```

---

## 4. Handler Adaptation: Reflection at Setup Time

### Type Signature Validation

```go
func Check(fn any) (*FuncInfo, error) {
    info := &FuncInfo{Type: reflect.TypeOf(fn), fn: fn}
    
    // Validate function structure
    if np := info.Type.NumIn(); np == 0 || np > 2 {
        return nil, errors.New("wrong number of parameters")
    }
    if info.Type.In(0) != ctxType {
        return nil, errors.New("first param must be context.Context")
    }
    if info.Type.IsVariadic() {
        return nil, errors.New("variadic not supported")
    }
    
    // Extract parameter type if present
    if info.Type.NumIn() == 2 {
        info.Argument = info.Type.In(1)
    }
    
    // Validate return values
    no := info.Type.NumOut()
    if no < 1 || no > 2 {
        return nil, errors.New("wrong number of results")
    }
    if no == 2 && info.Type.Out(1) != errType {
        return nil, errors.New("second return must be error")
    }
    
    // Determine if returns error
    info.ReportsError = info.Type.Out(no-1) == errType
    if no == 2 || !info.ReportsError {
        info.Result = info.Type.Out(0)
    }
    
    return info, nil
}
```

### Wrapper Generation

```go
func (fi *FuncInfo) Wrap() jrpc2.Handler {
    // Pre-compile input unmarshaler
    var newInput func(ctx reflect.Value, req *jrpc2.Request) ([]reflect.Value, error)
    
    switch {
    case fi.Argument == nil:
        // No parameters expected
        newInput = func(ctx reflect.Value, req *jrpc2.Request) ([]reflect.Value, error) {
            if req.HasParams() {
                return nil, errNoParameters
            }
            return []reflect.Value{ctx}, nil
        }
    
    case fi.Argument == reqType:
        // Direct *Request access
        newInput = func(ctx reflect.Value, req *jrpc2.Request) ([]reflect.Value, error) {
            return []reflect.Value{ctx, reflect.ValueOf(req)}, nil
        }
    
    case fi.Argument.Kind() == reflect.Pointer:
        // Pointer parameter
        newInput = func(ctx reflect.Value, req *jrpc2.Request) ([]reflect.Value, error) {
            in := reflect.New(fi.Argument.Elem())
            if err := req.UnmarshalParams(wrapArg(in)); err != nil {
                return nil, err
            }
            return []reflect.Value{ctx, in}, nil
        }
    
    default:
        // Value parameter
        newInput = func(ctx reflect.Value, req *jrpc2.Request) ([]reflect.Value, error) {
            in := reflect.New(fi.Argument)
            if err := req.UnmarshalParams(wrapArg(in)); err != nil {
                return nil, err
            }
            return []reflect.Value{ctx, in.Elem()}, nil
        }
    }
    
    // Pre-compile output marshaler
    var decodeOut func([]reflect.Value) (any, error)
    
    if fi.Result == nil {
        // Only error result
        decodeOut = func(vals []reflect.Value) (any, error) {
            if err := vals[0].Interface().(error); err != nil {
                return nil, err
            }
            return nil, nil
        }
    } else if !fi.ReportsError {
        // Only value result
        decodeOut = func(vals []reflect.Value) (any, error) {
            return vals[0].Interface(), nil
        }
    } else {
        // Both value and error
        decodeOut = func(vals []reflect.Value) (any, error) {
            if err := vals[1].Interface().(error); err != nil {
                return nil, err
            }
            return vals[0].Interface(), nil
        }
    }
    
    // Capture function for invocation
    call := reflect.ValueOf(fi.fn).Call
    
    // Return wrapped handler (minimal reflection at runtime)
    return func(ctx context.Context, req *jrpc2.Request) (any, error) {
        args, ierr := newInput(reflect.ValueOf(ctx), req)
        if ierr != nil {
            return nil, ierr
        }
        return decodeOut(call(args))
    }
}
```

**Design Insight**:
- All reflection happens in `Wrap()` (called once at setup)
- Returned handler function uses pre-compiled helpers
- No reflection on hot path (each request invocation)
- Significant performance improvement vs dynamic wrapping

### Array-to-Struct Translation

```go
type arrayStub struct {
    v        any
    posNames []string
}

func (s *arrayStub) translate(data []byte) ([]byte, error) {
    if firstByte(data) != '[' {
        return data, nil  // not array, pass through
    }
    
    var arr []json.RawMessage
    if err := json.Unmarshal(data, &arr); err != nil {
        return nil, err
    }
    if len(arr) != len(s.posNames) {
        return nil, fmt.Errorf("got %d params, want %d", len(arr), len(s.posNames))
    }
    
    // Rewrite array [a, b, c] as {"x": a, "y": b, "z": c}
    obj := make(map[string]json.RawMessage, len(s.posNames))
    for i, name := range s.posNames {
        obj[name] = arr[i]
    }
    return json.Marshal(obj)
}

func (s *arrayStub) UnmarshalJSON(data []byte) error {
    actual, err := s.translate(data)
    if err != nil {
        return err
    }
    return json.Unmarshal(actual, s.v)
}
```

**Example**:
```go
type Params struct {
    X int `json:"x"`
    Y int `json:"y"`
}

// Call with [1, 2] -> {"x": 1, "y": 2} -> Unmarshal OK
// Call with {"x": 1, "y": 2} -> pass through OK
// Call with [1] -> error (wrong count)
```

---

## 5. Error Code Conversion

### Context Error Mapping

```go
func ErrorCode(err error) Code {
    if err == nil {
        return NoError
    }
    
    // Check if implements ErrCoder interface
    var c ErrCoder
    if errors.As(err, &c) {
        return c.ErrCode()
    }
    
    // Standard Go error conversions
    if errors.Is(err, context.Canceled) {
        return Cancelled  // -32097
    }
    if errors.Is(err, context.DeadlineExceeded) {
        return DeadlineExceeded  // -32096
    }
    
    // Default fallback
    return SystemError  // -32098
}
```

**Usage in Client**:
```go
// When context is cancelled during request:
if err := pctx.Err(); err != nil {
    jerr := &Error{
        Code: ErrorCode(err),      // converts to Cancelled
        Message: err.Error(),
    }
}
```

**Usage in Server**:
```go
// When handler returns custom error:
v, err := h(ctx, req)
if err != nil {
    return nil, err  // Error code inferred from ErrorCode(err)
}
```

---

## 6. JSON Message Format

### Internal Representation

```go
type jmessage struct {
    ID  json.RawMessage      // request ID (nil for notifications)
    M   string              // method name
    P   json.RawMessage     // parameters
    R   json.RawMessage     // result (response)
    E   *Error              // error (response)
    
    batch bool              // true if in batch
    err *Error              // parse error
}

// Flexible parsing:
// - Single request: {"jsonrpc":"2.0", "id":1, ...}
// - Batch: [{"jsonrpc":"2.0", "id":1, ...}, ...]
// - Notification: {"jsonrpc":"2.0", "method":"foo"} (no id)
```

### Wire Format Examples

**Request**:
```json
{"jsonrpc":"2.0", "id":1, "method":"Add", "params":[1,2,3]}
```

**Notification**:
```json
{"jsonrpc":"2.0", "method":"notify", "params":{}}
```

**Response (success)**:
```json
{"jsonrpc":"2.0", "id":1, "result":6}
```

**Response (error)**:
```json
{"jsonrpc":"2.0", "id":1, "error":{"code":-32602, "message":"Invalid params", "data":"..."}}
```

**Batch Request**:
```json
[
  {"jsonrpc":"2.0", "id":1, "method":"M1", "params":[]},
  {"jsonrpc":"2.0", "id":2, "method":"M2", "params":[]},
  {"jsonrpc":"2.0", "method":"notify", "params":[]}
]
```

**Batch Response** (notifications omitted):
```json
[
  {"jsonrpc":"2.0", "id":1, "result":"..."},
  {"jsonrpc":"2.0", "id":2, "result":"..."}
]
```

---

## 7. Key Design Decisions

### Why Buffered Response Channels?

```go
p.ch = make(chan *jmessage, 1)  // NOT chan *jmessage
```

**Reasons**:
1. **Non-blocking delivery**: Reader can deliver without waiting
2. **No rendezvous**: Goroutines don't block each other
3. **Supports multiple waiters**: First reader consumes, closes ch
4. **Clean semantics**: Closed channel signals "done"

### Why Multiple Response Waiters?

```go
func (r *Response) wait() {
    raw, ok := <-r.ch
    if ok {  // first successful read
        r.err = raw.E
        r.result = raw.R
        close(r.ch)
        r.cancel()
    }
    // Subsequent reads return nil from closed ch
}
```

**Use Case**:
```go
rsp, _ := cli.Call(ctx, "method", nil)

// Multiple goroutines can wait on same response
go func() { rsp.wait(); fmt.Println(rsp.Error()) }()
go func() { rsp.wait(); fmt.Println(rsp.Error()) }()
go func() { rsp.wait(); fmt.Println(rsp.Error()) }()

// All three will eventually see the same response
```

### Why Inline Last Request?

```go
// In dispatchLocked():
for _, t := range tasks {
    if todo == 1 {
        t.val, t.err = s.invoke(...)  // inline
        break
    }
    todo--
    wg.Go(func() { t.val, t.err = s.invoke(...) })
}
```

**Benefit**: Avoids goroutine creation for the last request, reducing context switch overhead on single-request batches.

### Why Check Contexts Again?

```go
// In waitComplete():
if _, ok := c.pending[id]; !ok {
    return  // already responded (too late)
}
```

**Reason**: Prevents double-delivery. If response arrived before context expired, the request is no longer pending, so we don't deliver an error.

---

## 8. Server Push Implementation

### Client-Side Reception

```go
func (c *Client) handleRequestLocked(msg *jmessage) {
    if msg.isNotification() {
        if c.snote != nil {
            c.snote(msg)  // async handler
        }
    } else if c.scall != nil {
        ctx := context.WithValue(c.cbctx, clientKey{}, c)
        c.done.Go(func() {
            bits := c.scall(ctx, msg)  // get response
            c.mu.Lock()
            if c.err != nil {
                // skip if closed
            } else {
                c.ch.Send(bits)  // send back to server
            }
            c.mu.Unlock()
        })
    }
}
```

### Server-Side Invocation

```go
func (s *Server) Callback(ctx context.Context, method string, params any) (*Response, error) {
    if !s.allowP {
        return nil, ErrPushUnsupported
    }
    
    rsp, err := s.pushReq(ctx, true /* want ID */, method, params)
    if err != nil {
        return nil, err
    }
    
    rsp.wait()  // wait for client response
    if err := rsp.Error(); err != nil {
        return nil, filterError(err)
    }
    return rsp, nil
}

func (s *Server) pushReq(ctx context.Context, wantID bool, method string, params any) (*Response, error) {
    s.mu.Lock()
    if s.ch == nil {
        return nil, ErrConnClosed
    }
    
    if wantID {
        id := strconv.FormatInt(s.callID, 10)
        s.callID++
        
        cbctx, cancel := context.WithCancel(ctx)
        rsp := &Response{
            ch: make(chan *jmessage, 1),
            id: id,
            cancel: cancel,
        }
        s.call[id] = rsp
        
        go s.waitCallback(cbctx, id, rsp)
        
        // Send request with ID
        msg := &jmessage{ID: json.RawMessage(id), M: method, P: params}
        s.ch.Send(msg.toJSON())
        
        return rsp, nil
    }
    
    // Notification (no ID)
    msg := &jmessage{M: method, P: params}
    return nil, s.ch.Send(msg.toJSON())
}
```

---

## 9. Practical Performance Implications

### Lock Contention

**Client Side**:
- Lock held briefly (just for ID allocation and pending map update)
- Reader and waiter don't block each other (buffered channel)
- Minimal contention in normal operation

**Server Side**:
- Lock held during queue manipulation
- Not held during handler execution (released before invoke)
- Semaphore gates concurrency, not lock

### Goroutine Overhead

**Client**: One reader goroutine + one waitComplete per pending request
**Server**: One reader + one serve loop + one per concurrent request (up to semaphore limit)

### Memory Usage

**Per Request (Client)**:
- Response struct: ~128 bytes
- Buffered channel (size 1): ~64 bytes
- Context: ~192 bytes
- Total: ~384 bytes per in-flight request

**Per Connection (Server)**:
- Server struct: ~1024 bytes
- Queues and maps: ~2KB
- Plus per-request: context (~192 bytes) + task (~256 bytes)

### Message Overhead

- Full marshaling/unmarshaling of JSON (no streaming)
- No connection multiplexing (one stream per connection)
- No compression (layer above could add)

---

## 10. Edge Cases and Robustness

### Duplicate Request IDs

```go
// Server detection:
dup := make(map[string]*task)
for _, req := range next {
    id := string(req.ID)
    if old := dup[id]; old != nil {
        old.err = errDuplicateID
        t.err = errDuplicateID
    } else {
        dup[id] = t
    }
}
```

**Behavior**: Both requests in batch fail with duplicate ID error.

### Empty Batch

```go
func (c *Client) send(ctx context.Context, reqs jmessages) ([]*Response, error) {
    if len(reqs) == 0 {
        return nil, errors.New("empty request batch")
    }
    // ...
}
```

**Spec says**: Server MUST reject with error object. Client prevents sending.

### Invalid JSON in Parameters

```go
func (c *Client) marshalParams(ctx context.Context, method string, params any) (json.RawMessage, error) {
    if params == nil {
        return nil, nil  // OK
    }
    pbits, err := json.Marshal(params)
    if err != nil {
        return nil, err  // fail early
    }
    if fb := firstByte(pbits); fb != '[' && fb != '{' && !isNull(pbits) {
        return nil, &Error{Code: InvalidRequest, Message: "invalid parameters"}
    }
    return pbits, nil
}
```

**Validation**: Parameters must be array or object (JSON-RPC requirement).

### Panic Recovery in Callbacks

```go
func (c *Client) handleCallback(cb Handler, msg *jmessage) {
    rsp := &jmessage{ID: msg.ID}
    v, err := panicToError(func() (any, error) {
        return cb(ctx, &Request{id: msg.ID, method: msg.M, params: msg.P})
    })
    if err != nil {
        rsp.E = &Error{...}
    } else {
        rsp.R = v
    }
    c.ch.Send(rsp.toJSON())
}
```

**Robustness**: Panics in client callback handlers are caught and converted to SystemError responses.

