# jrpc2 Library Analysis - Complete Documentation

This directory contains comprehensive research and analysis of the **creachadair/jrpc2** Go library for JSON-RPC 2.0 implementation.

## Documents Included

### 1. **ANALYSIS_SUMMARY.txt** (Key Starting Point)
Quick overview with:
- Executive summary
- Key findings (7 main topics)
- Architecture patterns
- Strengths and limitations
- Best use cases
- Notable implementation details
- Quick verdict and rating

**Start here for**: 5-minute high-level overview

---

### 2. **JRPC2_RESEARCH_REPORT.md** (Comprehensive Reference)
In-depth analysis covering:

1. **Project Overview** - Design goals, package structure
2. **Client API** - Creating clients, calls, batch requests, notifications
3. **Channel/Transport Abstraction** - The most important design pattern
4. **Request/Response Types** - How messages are modeled
5. **Batch Operations** - Server-side batch processing semantics
6. **Error Handling** - Error types, codes, custom errors
7. **Handler Pattern** - Function adaptation and reflection
8. **Concurrency** - Client and server concurrency models
9. **Context Integration** - Timeout and cancellation support
10. **Code Organization** - Package structure and dependencies
11. **Type Safety** - How the library maintains safety without generics
12. **Strengths and Weaknesses** - Detailed pros and cons
13. **Real-World Usage Patterns** - Practical examples
14. **Comparison** - vs other JSON-RPC libraries
15. **Conclusion** - When to use jrpc2

**Length**: 1,080 lines of markdown
**Start here for**: Complete understanding of the library

---

### 3. **TECHNICAL_DEEP_DIVE.md** (Implementation Details)
Low-level implementation patterns:

1. **Channel Pattern** - Transport abstraction design
   - Interface design philosophy
   - Framing implementations (Line, Header, RawJSON, Direct)
   - Why it matters for architecture

2. **Client Concurrency** - Thread-safe request tracking
   - ID management and monotonic counters
   - Response synchronization with buffered channels
   - Context cancellation per request
   - Multiple waiters on single response

3. **Server Concurrency** - Request batching and ordering
   - Pipeline from read to deliver
   - Concurrency control with semaphores
   - The "notification barrier" (subtle but crucial)
   - Request ordering guarantees across batches

4. **Handler Adaptation** - Reflection at setup time
   - Type signature validation
   - Wrapper generation with pre-compilation
   - Array-to-struct translation (positional parameters)
   - Minimal reflection on hot path

5. **Error Code Conversion** - Context error mapping
   - ErrorCode function
   - ErrCoder interface
   - Context error conversions

6. **JSON Message Format** - Internal and wire representations
   - jmessage structure
   - Request, response, notification formats
   - Batch semantics

7. **Key Design Decisions** - Why certain choices were made
   - Buffered response channels
   - Multiple response waiters
   - Last-request inlining
   - Late-arrival handling

8. **Server Push** - Bidirectional RPC implementation
   - Client-side reception
   - Server-side invocation

9. **Performance Implications** - Lock contention, goroutines, memory
10. **Edge Cases** - Handling of error conditions

**Length**: ~1,500 lines of markdown with code examples
**Start here for**: Understanding implementation details and design rationale

---

## Quick Navigation

### By Topic

**Understanding the Architecture**:
→ ANALYSIS_SUMMARY.txt (10 min read)
→ JRPC2_RESEARCH_REPORT.md sections 1-3

**Using the Library**:
→ JRPC2_RESEARCH_REPORT.md sections 2, 4, 7, 13
→ Review examples in /tools/examples/

**Implementing Custom Features**:
→ TECHNICAL_DEEP_DIVE.md sections 1, 4, 7
→ Review handler/ package implementation

**Understanding Concurrency**:
→ TECHNICAL_DEEP_DIVE.md sections 2, 3
→ Review client.go and server.go with comments

**Transport Customization**:
→ TECHNICAL_DEEP_DIVE.md section 1
→ Review channel/ package

### By Audience

**Decision Makers** (Should I use jrpc2?):
→ ANALYSIS_SUMMARY.txt
→ JRPC2_RESEARCH_REPORT.md section 12 (Strengths/Weaknesses)
→ JRPC2_RESEARCH_REPORT.md section 14 (Comparison)

**Developers** (How do I use it?):
→ JRPC2_RESEARCH_REPORT.md sections 2, 4, 7, 13
→ /tools/examples/ directory
→ Official package documentation

**Architects** (How is it designed?):
→ ANALYSIS_SUMMARY.txt (Architecture section)
→ JRPC2_RESEARCH_REPORT.md sections 3, 8, 9
→ TECHNICAL_DEEP_DIVE.md all sections

**Contributors** (How does it work internally?):
→ TECHNICAL_DEEP_DIVE.md (entire document)
→ Source code: client.go, server.go, channel/
→ Tests: jrpc2_test.go, handler_test.go

---

## Key Insights (TL;DR)

### The Channel Pattern
The most important design - allows transport independence. Any protocol can be implemented by creating a Channel that handles Send/Recv with framing. This is production-level abstraction.

### Concurrency Model
- **Client**: Thread-safe, multiple pending requests allowed
- **Server**: Requests in batch are concurrent up to semaphore limit
- **Ordering**: Non-batch requests maintain arrival order
- **Notifications**: Have ordering guarantee via "barrier"

### Handler Adaptation
Reflection happens at `handler.New()` time, not on each request. Pre-compiled wrappers handle parameter unmarshaling and return value marshaling with minimal runtime reflection.

### Response Synchronization
Buffered channel (size 1) enables:
- Non-blocking delivery by reader
- Multiple waiters on same response
- Clean "first reader wins" semantics
- No data races

### Error Handling
Standard JSON-RPC error codes plus custom codes. Context errors (Cancelled, DeadlineExceeded) automatically converted to error codes.

---

## File Structure

```
jrpc2/ (library root)
├── client.go           (449 lines) - Thread-safe client
├── server.go           (838 lines) - Concurrent request dispatch
├── base.go             (247 lines) - Request/Response/Assigner types
├── error.go            (73 lines)  - Error type
├── code.go             (110 lines) - Error codes
├── json.go             (333 lines) - JSON parsing
├── ctx.go              (46 lines)  - Context utilities
├── opts.go             (244 lines) - Configuration options
├── channel/            - Transport abstraction
│   ├── channel.go      - Interface and Direct() implementation
│   ├── split.go        - Line framing
│   ├── json.go         - RawJSON framing
│   └── hdr.go          - Header framing (LSP)
├── handler/            - Function adaptation
│   ├── handler.go      - Map, ServiceMap, New()
│   ├── positional.go   - Positional parameters
│   └── helpers.go      - Utilities
├── server/             - Convenience layer
│   └── local.go        - In-memory server/client for testing
├── jhttp/              - HTTP support
└── tools/examples/     - Real-world examples
    ├── adder/          - Simple stdin/stdout server
    ├── server/         - TCP server
    ├── client/         - TCP client
    └── http/           - HTTP transport
```

---

## Quick Reference

### Creating a Service

```go
// Handler registration
h := handler.New(func(ctx context.Context, x int) (int, error) {
    return x * 2, nil
})

assigner := handler.Map{"Double": h}
server := jrpc2.NewServer(assigner, nil)
server.Start(channel.Line(os.Stdin, os.Stdout))
server.Wait()
```

### Making a Call

```go
ch := channel.Line(conn, conn)
client := jrpc2.NewClient(ch, nil)

var result int
err := client.CallResult(ctx, "Double", 21, &result)
// result == 42
```

### Batch Calls

```go
rsps, err := client.Batch(ctx, []jrpc2.Spec{
    {Method: "Double", Params: 5},
    {Method: "Double", Params: 10},
})
```

### Custom Transport

```go
// Implement Channel interface
type MyChannel struct{}
func (c MyChannel) Send(b []byte) error { /* ... */ }
func (c MyChannel) Recv() ([]byte, error) { /* ... */ }
func (c MyChannel) Close() error { /* ... */ }

client := jrpc2.NewClient(MyChannel{}, nil)
```

---

## External Resources

- **Official Repository**: https://github.com/creachadair/jrpc2
- **JSON-RPC 2.0 Spec**: http://www.jsonrpc.org/specification
- **Language Server Protocol**: https://microsoft.github.io/language-server-protocol/
- **Go Playground Example**: https://go.dev/play/p/JWgZOVJh0nZ

---

## Analysis Methodology

This analysis was conducted through:

1. **Source Code Review**
   - Complete reading of core files (client.go, server.go, base.go)
   - Handler adaptation patterns (handler/handler.go)
   - Channel implementations (channel/*.go)
   - Test coverage examination (jrpc2_test.go)

2. **Architecture Analysis**
   - Data flow tracing
   - Concurrency pattern identification
   - Error handling path analysis
   - Interface design evaluation

3. **Pattern Recognition**
   - Concurrency primitives (channels, mutexes, semaphores)
   - Reflection usage (compile-time vs runtime)
   - Synchronization patterns
   - Context integration patterns

4. **Comparative Analysis**
   - vs gorilla/rpc
   - vs ethereum/go-ethereum
   - vs gRPC

---

## Notes

- Code is production-quality with extensive test coverage
- Minimal external dependencies (only 2 external packages)
- API is stable (semantic versioning)
- Well-suited for JSON-RPC use cases
- Channel pattern is excellent design for transport independence

---

**Last Updated**: March 2024
**Analyzed Library Version**: Latest from creachadair/jrpc2
**Total Analysis**: 3 comprehensive documents, ~3,700 lines of detailed analysis

