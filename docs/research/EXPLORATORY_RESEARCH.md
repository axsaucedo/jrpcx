# Exploratory Research: jrpcx — A Modern Python JSON-RPC 2.0 Client

> **Document Type:** Foundational exploratory research
> **Project:** jrpcx — JSON-RPC 2.0 client library for Python
> **Date:** March 2025
> **Status:** Complete

---

## Table of Contents

1. [Research Objective](#1-research-objective)
2. [Research Methodology](#2-research-methodology)
3. [Candidate Libraries Evaluated](#3-candidate-libraries-evaluated)
4. [Selection Criteria & Rationale](#4-selection-criteria--rationale)
5. [JSON-RPC 2.0 Specification Summary](#5-json-rpc-20-specification-summary)
6. [Key Questions for Deep Research](#6-key-questions-for-deep-research)
7. [Next Steps](#7-next-steps)

---

## 1. Research Objective

### Problem Statement

The Python ecosystem lacks a JSON-RPC 2.0 client that feels as natural and well-designed as **httpx** does for HTTP. Existing solutions fall into two camps:

- **Minimal message builders** (e.g., `jsonrpcclient`) that handle serialization but leave transport entirely to the caller, requiring boilerplate for every request.
- **Full-featured frameworks** (e.g., `pjrpc`) that bundle client and server capabilities with extensive framework integrations, introducing complexity and dependencies that a client-only use case doesn't need.

Neither camp delivers the experience of writing `client.call("method", params)` with the same confidence, type safety, and flexibility that `httpx.get(url)` provides for HTTP.

### Goal

Build **jrpcx**: a simple, modern JSON-RPC 2.0 client for Python that is:

- **httpx-inspired** — familiar API patterns for Python developers, sync/async duality with minimal duplication
- **Transport-agnostic** — works over HTTP out of the box, with pluggable transports for WebSocket, TCP, IPC, or custom channels
- **Type-safe** — full type annotations, mypy strict compatibility, generics for typed responses
- **Batteries-included but lightweight** — sensible defaults, middleware support, batch operations, and error handling without framework-level complexity
- **Python 3.12+** — leveraging modern Python features without backward-compatibility baggage

### What This Document Covers

This is the **foundational research document** for jrpcx. It explains:

1. How we surveyed the JSON-RPC client landscape across three major ecosystems (Python, Go, JavaScript)
2. Which libraries were considered and why
3. Which six were selected for deep codebase analysis
4. What specific design questions each selection is intended to answer

The deep analyses themselves live in dedicated documents (see [RESEARCH_INDEX.md](./RESEARCH_INDEX.md)).

---

## 2. Research Methodology

### Approach

The research followed a structured three-phase process designed to maximize insight from the best existing implementations, regardless of language.

#### Phase 1: Broad Survey (Ecosystem Scan)

We surveyed JSON-RPC client implementations across three ecosystems:

| Ecosystem | Why Surveyed | Focus Areas |
|-----------|-------------|-------------|
| **Python** | Target ecosystem — must understand the competitive landscape, existing patterns, and gaps | API design, async support, typing, transport handling |
| **Go** | Known for excellent network library design, strong concurrency primitives, and clean abstractions | Transport abstraction, concurrency patterns, channel design |
| **JavaScript/Node.js** | Largest JSON-RPC ecosystem due to LSP, Ethereum, and WebSocket usage | Multi-transport support, middleware patterns, event systems |

Sources consulted:

- **GitHub search**: `json-rpc client` filtered by language, sorted by stars and recent activity
- **PyPI / npm / pkg.go.dev**: Package registry searches for `jsonrpc`, `json-rpc`, `rpc client`
- **Awesome lists**: `awesome-python`, `awesome-go`, `awesome-nodejs` curated RPC sections
- **Protocol-adjacent projects**: LSP implementations, Ethereum clients, and MCP (Model Context Protocol) clients that use JSON-RPC internally
- **Web research**: Blog posts, comparison articles, and community discussions on JSON-RPC library design

#### Phase 2: Candidate Screening (10+ Libraries)

Each candidate was evaluated on a quick-pass basis:

- **Repository health**: stars, recent commits, open issues, maintainer activity
- **Code size and scope**: lines of code, client-only vs. client+server, dependencies
- **API surface**: how users make RPC calls, batch support, error handling
- **Architecture**: transport abstraction, sync/async support, extensibility
- **Relevance to jrpcx**: does this library teach us something we can't learn from the others?

#### Phase 3: Deep Codebase Analysis (6 Libraries)

The six selected libraries received thorough source-code-level analysis. Each deep analysis included:

- Complete architectural breakdown (module structure, class hierarchy, data flow)
- API design evaluation (public interface, ergonomics, type safety)
- Transport abstraction study (how transports are defined, composed, and swapped)
- Error handling patterns (exception hierarchy, JSON-RPC error codes, edge cases)
- Testing strategies (unit vs. integration, mocking patterns, coverage approach)
- Design patterns extracted (with specific code references and applicability to jrpcx)

---

## 3. Candidate Libraries Evaluated

### 3.1 Selected for Deep Analysis

The following six libraries were chosen for comprehensive source-code analysis. Each was selected because it offers a **unique and complementary perspective** on a specific aspect of jrpcx's design.

---

#### ⭐ httpx (Python) — `encode/httpx`

| Attribute | Value |
|-----------|-------|
| **Repository** | [github.com/encode/httpx](https://github.com/encode/httpx) |
| **Language** | Python |
| **Scope** | HTTP client (not JSON-RPC) |
| **Codebase Size** | ~50,000+ lines |
| **Stars** | 13,000+ |
| **Key Feature** | Sync/async duality, transport abstraction, type safety |

**Why selected:** httpx is not a JSON-RPC library — it is the **design inspiration** for jrpcx. Its API philosophy, class hierarchy (`BaseClient` → `Client` / `AsyncClient`), transport abstraction (`BaseTransport` / `AsyncBaseTransport`), and configuration management (sentinel-based defaults, immutable config objects) define the target developer experience for jrpcx. Understanding how httpx achieves its clean API while supporting pluggable transports, middleware-like event hooks, and full type safety is essential.

**What it teaches jrpcx:**
- How to implement sync/async duality with minimal code duplication
- Transport abstraction that enables both real HTTP and mock/test transports
- Configuration merging patterns (client-level defaults + per-request overrides)
- Type annotation strategy for a large Python library under mypy strict mode
- How to design a "pit of success" API — correct usage is the easiest path

**Deep analysis:** [HTTPX_ANALYSIS.md](./HTTPX_ANALYSIS.md)

---

#### ⭐ jsonrpcclient (Python) — `explodinglabs/jsonrpcclient`

| Attribute | Value |
|-----------|-------|
| **Repository** | [github.com/explodinglabs/jsonrpcclient](https://github.com/explodinglabs/jsonrpcclient) |
| **Language** | Python |
| **Scope** | JSON-RPC message construction only |
| **Codebase Size** | ~260 lines |
| **Stars** | 600+ |
| **Key Feature** | Radical simplicity, transport-agnostic, functional API |

**Why selected:** jsonrpcclient represents the **minimal extreme** of JSON-RPC client design. At roughly 260 lines of code, it does exactly one thing: build and parse JSON-RPC 2.0 messages. It does not handle transport, connection management, or retries. This is a deliberate design choice — the library provides pure functions (`request()`, `parse()`) that the caller composes with whatever transport they prefer.

**What it teaches jrpcx:**
- The absolute minimum API surface for JSON-RPC message handling
- Functional design: stateless request/response builders with no side effects
- What happens when transport is fully externalized — both the freedom and the boilerplate cost
- Message ID generation strategies
- How far simplicity can go before users need more structure

**Design tension for jrpcx:** jsonrpcclient proves that message construction can be trivially simple. The question is whether jrpcx should absorb this simplicity at its core while layering transport, batching, and middleware on top — or whether a different architectural boundary makes more sense.

---

#### ⭐ pjrpc (Python) — `dapper91/pjrpc`

| Attribute | Value |
|-----------|-------|
| **Repository** | [github.com/dapper91/pjrpc](https://github.com/dapper91/pjrpc) |
| **Language** | Python |
| **Scope** | Full JSON-RPC client + server framework |
| **Codebase Size** | ~5,000+ lines (core) |
| **Stars** | 200+ |
| **Key Feature** | Backend abstraction, pydantic validation, OpenAPI generation |

**Why selected:** pjrpc is the most **full-featured Python JSON-RPC library** currently maintained. It supports multiple transport backends (aiohttp, flask, httpx, kombu, requests), pydantic-based parameter/result validation, middleware (called "interceptors"), batch operations, and even OpenAPI spec generation for JSON-RPC servers. It demonstrates what a "batteries-included" Python JSON-RPC library looks like.

**What it teaches jrpcx:**
- Backend abstraction pattern — how to support httpx, aiohttp, and requests as interchangeable transports
- Pydantic integration for request/response validation
- Middleware/interceptor architecture for cross-cutting concerns (logging, auth, retry)
- Batch operation API design
- Error handling with typed JSON-RPC exceptions
- What "too much scope" looks like — pjrpc bundles client + server + framework integrations, which increases complexity

**Design tension for jrpcx:** pjrpc validates that Python developers want type-safe, validated JSON-RPC with pluggable backends. But its combined client+server scope and framework integrations add complexity jrpcx aims to avoid. The challenge is extracting the client-side patterns (backend abstraction, validation, batching) while staying focused.

**Deep analysis:** [PJRPC_RESEARCH_REPORT.md](./PJRPC_RESEARCH_REPORT.md)

---

#### ⭐ ybbus/jsonrpc (Go) — `ybbus/jsonrpc`

| Attribute | Value |
|-----------|-------|
| **Repository** | [github.com/ybbus/jsonrpc](https://github.com/ybbus/jsonrpc) |
| **Language** | Go |
| **Scope** | JSON-RPC 2.0 client (HTTP transport) |
| **Codebase Size** | ~700 lines |
| **Stars** | 300+ |
| **Key Feature** | Zero dependencies, ergonomic API, focused scope |

**Why selected:** ybbus/jsonrpc is the **ergonomic benchmark** — a Go JSON-RPC client that achieves remarkable usability in roughly 700 lines with zero external dependencies. Its API is immediately intuitive: `client.Call("method", params)` returns a response you can unmarshal into any type. It handles HTTP transport, custom headers, basic auth, and TLS configuration without abstraction overhead.

**What it teaches jrpcx:**
- How to design a JSON-RPC client API that "just works" for the 90% use case
- Response handling ergonomics — `GetObject()`, `GetInt()`, typed accessors
- Configuration patterns for HTTP-specific concerns (headers, auth, timeouts) without over-abstracting
- Zero-dependency architecture — what can be achieved with standard library alone
- The cost of transport simplicity: HTTP-only means no WebSocket/TCP extensibility

**Design tension for jrpcx:** ybbus/jsonrpc proves that a focused, HTTP-only client can be incredibly simple and pleasant to use. jrpcx must decide whether to start with this simplicity (HTTP-first, add transports later) or build the transport abstraction from day one. The risk of the former is a painful refactor; the risk of the latter is premature abstraction.

---

#### ⭐ creachadair/jrpc2 (Go) — `creachadair/jrpc2`

| Attribute | Value |
|-----------|-------|
| **Repository** | [github.com/creachadair/jrpc2](https://github.com/creachadair/jrpc2) |
| **Language** | Go |
| **Scope** | Full JSON-RPC 2.0 client + server |
| **Codebase Size** | ~5,000+ lines |
| **Stars** | 100+ |
| **Key Feature** | Channel abstraction, concurrency, production-grade patterns |

**Why selected:** jrpc2 is the most **architecturally sophisticated** JSON-RPC implementation in this survey. Its `Channel` interface abstracts the bidirectional message stream completely — any byte stream (TCP, stdio, WebSocket, in-memory pipe) becomes a JSON-RPC transport by implementing `Send` and `Recv`. This is the pattern that enables LSP servers, MCP implementations, and other production systems to use JSON-RPC over arbitrary channels.

**What it teaches jrpcx:**
- Channel-based transport abstraction — the cleanest separation of "JSON-RPC protocol" from "how bytes move"
- Concurrency patterns for multiplexed requests over a single connection
- Request/response correlation with concurrent in-flight requests
- Context integration (Go's `context.Context`) for cancellation and deadlines — analogous to Python's async patterns
- Server push / bidirectional communication patterns
- How production-grade error handling works (error codes, data payloads, wrapped errors)

**Design tension for jrpcx:** jrpc2's channel abstraction is the gold standard, but it's designed for Go's goroutine model. Translating this to Python's async/await model requires careful thought — especially around concurrent request multiplexing and connection lifecycle management.

**Deep analysis:** [JRPC2_RESEARCH_REPORT.md](./JRPC2_RESEARCH_REPORT.md)

---

#### ⭐ jayson (JavaScript) — `tedeh/jayson`

| Attribute | Value |
|-----------|-------|
| **Repository** | [github.com/tedeh/jayson](https://github.com/tedeh/jayson) |
| **Language** | JavaScript (Node.js) |
| **Scope** | Full JSON-RPC 2.0 + 1.0 client + server |
| **Codebase Size** | ~3,000+ lines |
| **Stars** | 700+ |
| **Key Feature** | Multi-transport, middleware, relay, event system |

**Why selected:** jayson represents the **multi-transport, event-driven** approach to JSON-RPC. It supports HTTP, HTTPS, TCP, TLS, and WebSocket transports out of the box, with a middleware system for both client and server, a relay mechanism for proxying between transports, and Node.js EventEmitter integration. This is the most comprehensive transport story in the survey.

**What it teaches jrpcx:**
- Multi-transport architecture — how one library supports HTTP, TCP, and WebSocket with a unified API
- Middleware patterns for request/response interception (auth injection, logging, retry)
- Event system design for connection lifecycle events (connect, disconnect, error)
- Relay/proxy patterns — forwarding JSON-RPC between transports
- Dual protocol support (JSON-RPC 1.0 + 2.0) — how to handle protocol negotiation
- Batch request API design in an event-driven context

**Design tension for jrpcx:** jayson's callback + EventEmitter patterns are idiomatic JavaScript but don't translate directly to Python. The challenge is extracting the transport and middleware concepts while mapping them to Pythonic patterns (context managers, async generators, type-safe middleware chains).

**Deep analysis:** [JAYSON_RESEARCH_REPORT.md](./JAYSON_RESEARCH_REPORT.md)

---

### 3.2 Other Candidates Considered

The following libraries were evaluated during Phase 2 (candidate screening) but **not selected** for deep analysis. Each was excluded for a specific reason — either because its design insights were already covered by a selected library, or because it was too narrowly scoped, outdated, or domain-specific to inform jrpcx's design.

#### Python Ecosystem

| Library | Reason Not Selected |
|---------|-------------------|
| **python-jsonrpc** | Older library with declining maintenance. Its API patterns and architecture are superseded by pjrpc, which covers the same ground with modern Python features (async, type hints, pydantic). |
| **aiohttp-json-rpc** | Tightly coupled to the aiohttp framework. While functional for aiohttp-based projects, it doesn't demonstrate transport abstraction — the opposite of what jrpcx needs. pjrpc already shows aiohttp integration as one of many backends. |
| **jsonrpclib / jsonrpclib-pelix** | Originally a Python 2 library (jsonrpclib), later forked for Python 3 compatibility (pelix). The API design reflects pre-async Python patterns and lacks type annotations. jsonrpcclient provides a better example of minimal Python JSON-RPC design. |
| **json-rpc** (pavlov99) | A lightweight library that handles both client and server roles, but with a limited feature set and minimal transport abstraction. Its design space is already covered by the combination of jsonrpcclient (simplicity) and pjrpc (full features). |

#### Go Ecosystem

| Library | Reason Not Selected |
|---------|-------------------|
| **gorilla/rpc** | Part of the now-archived Gorilla web toolkit. Focused on HTTP handler-based server-side RPC with limited client capabilities. Its HTTP-centric, handler-registration approach is simpler than jrpc2 and doesn't offer additional architectural insights beyond what ybbus/jsonrpc provides. |
| **ethereum/go-ethereum** (JSON-RPC client) | Go-Ethereum's JSON-RPC client is production-hardened but heavily specialized for Ethereum's API patterns (subscription management, block-specific retry logic, hex encoding conventions). The domain-specific concerns obscure the general JSON-RPC design patterns that jrpcx needs. jrpc2 provides cleaner general-purpose abstractions. |
| **net/rpc** (Go stdlib) | Go's standard library RPC package uses a custom binary protocol (gob encoding) rather than JSON-RPC 2.0. While its client design is influential in the Go ecosystem, the protocol differences make it less directly applicable than ybbus/jsonrpc and jrpc2. |

#### JavaScript / Node.js Ecosystem

| Library | Reason Not Selected |
|---------|-------------------|
| **json-rpc-2.0** (npm) | A simpler, TypeScript-native alternative to jayson. While cleaner in some respects, jayson was preferred for deep analysis because it demonstrates more transport patterns, middleware capabilities, and real-world complexity. json-rpc-2.0's TypeScript patterns are worth noting but don't add enough unique insight beyond jayson. |
| **vscode-jsonrpc** | Microsoft's JSON-RPC implementation used in VS Code's LSP client. Highly specialized for the Language Server Protocol lifecycle and deeply coupled to VS Code's extension model. The general JSON-RPC patterns are better studied through jrpc2 (which is also used in LSP contexts but with cleaner abstraction boundaries). |
| **grpc-web / connect-es** | While gRPC and Connect use similar client patterns, they implement a different protocol (Protocol Buffers over HTTP/2) and their design choices are driven by different constraints than JSON-RPC 2.0. |

---

## 4. Selection Criteria & Rationale

### Design Matrix

Each selected library was chosen to inform a specific aspect of jrpcx's architecture. The selection was intentionally **cross-language** and **complementary** — no two libraries were selected for the same primary reason.

| Library | Primary Design Insight | Secondary Insights |
|---------|----------------------|-------------------|
| **httpx** | API design philosophy, sync/async duality | Transport abstraction, type safety, config management |
| **jsonrpcclient** | Minimal message construction | Transport-agnostic design, functional architecture |
| **pjrpc** | Full-featured Python JSON-RPC patterns | Backend abstraction, validation, middleware |
| **ybbus/jsonrpc** | Ergonomic client API design | Zero-dependency architecture, HTTP-focused simplicity |
| **jrpc2** | Channel-based transport abstraction | Concurrency, production-grade error handling |
| **jayson** | Multi-transport + middleware architecture | Event system, relay patterns, protocol flexibility |

### Coverage Analysis

The six selected libraries collectively cover every major architectural concern for jrpcx:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    jrpcx Design Space Coverage                      │
├─────────────────────┬───────────────────────────────────────────────┤
│ Concern             │ Primary Source        │ Supporting Sources    │
├─────────────────────┼───────────────────────┼───────────────────────┤
│ API Design          │ httpx                 │ ybbus/jsonrpc         │
│ Sync/Async Duality  │ httpx                 │ pjrpc                 │
│ Transport Abstract. │ jrpc2                 │ httpx, jayson          │
│ Message Building    │ jsonrpcclient         │ ybbus/jsonrpc         │
│ Batch Operations    │ pjrpc                 │ jayson, jsonrpcclient │
│ Middleware          │ jayson                │ pjrpc (interceptors)  │
│ Error Handling      │ jrpc2                 │ pjrpc, httpx          │
│ Type Safety         │ httpx                 │ pjrpc (pydantic)      │
│ Multi-Transport     │ jayson                │ jrpc2 (channels)      │
│ Configuration       │ httpx                 │ ybbus/jsonrpc         │
│ Testing Patterns    │ httpx                 │ jrpc2                 │
│ Concurrency         │ jrpc2                 │ httpx (async pools)   │
└─────────────────────┴───────────────────────┴───────────────────────┘
```

### Why Cross-Language Research?

JSON-RPC 2.0 is a language-agnostic protocol, and the best implementations are not all in Python. Restricting research to Python alone would miss:

- **Go's channel abstraction** (jrpc2) — the cleanest transport separation in any JSON-RPC library
- **Go's ergonomic simplicity** (ybbus/jsonrpc) — proof that a great client API needs very little code
- **JavaScript's multi-transport patterns** (jayson) — the most comprehensive transport story, born from Node.js's event-driven architecture and the ecosystem's heavy JSON-RPC usage (LSP, Ethereum, WebSocket APIs)

The goal is not to port these libraries to Python but to **extract their best design decisions** and translate them into Pythonic patterns.

---

## 5. JSON-RPC 2.0 Specification Summary

Any JSON-RPC 2.0 client must correctly implement the protocol as defined in the [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification). This section summarizes the protocol features that jrpcx must support.

### Core Protocol

JSON-RPC 2.0 is a stateless, lightweight remote procedure call protocol using JSON as the data format. It is transport-agnostic — the specification defines only the message format, not how messages are delivered.

### Request Object

A JSON-RPC request is a JSON object with the following members:

| Member | Required | Description |
|--------|----------|-------------|
| `jsonrpc` | Yes | Must be exactly `"2.0"` |
| `method` | Yes | String name of the method to invoke |
| `params` | No | Structured value (array or object) holding the parameter values |
| `id` | Yes* | Unique identifier (string, number, or null). *Omitted for notifications. |

```json
{
    "jsonrpc": "2.0",
    "method": "subtract",
    "params": {"minuend": 42, "subtrahend": 23},
    "id": 1
}
```

### Response Object

A JSON-RPC response is a JSON object with either a `result` or an `error` member (never both):

| Member | Required | Description |
|--------|----------|-------------|
| `jsonrpc` | Yes | Must be exactly `"2.0"` |
| `result` | On success | The return value of the invoked method |
| `error` | On failure | Error object with `code`, `message`, and optional `data` |
| `id` | Yes | Must match the request `id` (or `null` if request `id` couldn't be detected) |

### Error Object

| Member | Required | Description |
|--------|----------|-------------|
| `code` | Yes | Integer error code |
| `message` | Yes | Short human-readable description |
| `data` | No | Additional error information (any type) |

**Reserved error codes:**

| Code | Meaning |
|------|---------|
| `-32700` | Parse error — invalid JSON |
| `-32600` | Invalid request — not a valid JSON-RPC request |
| `-32601` | Method not found |
| `-32602` | Invalid params |
| `-32603` | Internal error |
| `-32000` to `-32099` | Server error (implementation-defined) |

### Notifications

A notification is a request without an `id` member. The server MUST NOT reply to notifications. Clients use notifications for fire-and-forget operations.

```json
{
    "jsonrpc": "2.0",
    "method": "update",
    "params": [1, 2, 3, 4, 5]
}
```

### Batch Requests

Multiple requests can be sent as a JSON array. The server processes them (potentially in parallel) and returns a JSON array of responses. Key rules:

- The response array may be in any order (clients must correlate by `id`)
- Notifications in a batch produce no corresponding response
- An empty batch `[]` is an invalid request
- A batch of only notifications returns nothing (no response at all)

```json
[
    {"jsonrpc": "2.0", "method": "sum", "params": [1, 2], "id": "1"},
    {"jsonrpc": "2.0", "method": "notify", "params": [7]},
    {"jsonrpc": "2.0", "method": "getData", "id": "2"}
]
```

### Implementation Requirements for jrpcx

Based on the specification, jrpcx must handle:

1. **Request construction** — proper `jsonrpc`, `method`, `params`, and `id` fields
2. **ID generation and correlation** — unique IDs per request, matching responses by ID
3. **Notification support** — requests without `id`, no response expected
4. **Batch operations** — sending arrays of requests, correlating array of responses
5. **Error parsing** — structured error objects with code, message, and data
6. **Params flexibility** — support both positional (array) and named (object) parameters
7. **Transport independence** — the spec says nothing about transport; jrpcx should reflect this

---

## 6. Key Questions for Deep Research

Each deep codebase analysis was guided by specific architectural questions. These questions reflect the design decisions jrpcx must make, organized by the library best positioned to answer them.

### httpx — API Design & Architecture

| # | Question | Why It Matters |
|---|----------|---------------|
| 1 | How does httpx implement sync/async duality with minimal code duplication? | jrpcx needs both `Client` and `AsyncClient` without maintaining two parallel codebases |
| 2 | How does the `BaseTransport` / `AsyncBaseTransport` abstraction work? | Defines how jrpcx will abstract JSON-RPC transports (HTTP, WebSocket, TCP) |
| 3 | How does httpx merge client-level defaults with per-request parameters? | jrpcx needs the same pattern: default timeout/headers on the client, overridable per-call |
| 4 | What sentinel pattern does httpx use for "not provided" vs `None`? | Critical for configuration merging — `timeout=None` (disable) vs not passing timeout (use default) |
| 5 | How does httpx structure its type annotations for mypy strict mode? | Sets the bar for jrpcx's type safety approach |
| 6 | How does httpx handle connection lifecycle and resource cleanup? | Context manager patterns, `__enter__`/`__aenter__`, connection pooling |

### jsonrpcclient — Minimal Design

| # | Question | Why It Matters |
|---|----------|---------------|
| 1 | What is the absolute minimum code needed for JSON-RPC message construction? | Defines the irreducible core of jrpcx's message layer |
| 2 | How does a purely functional JSON-RPC API look? | Alternative to class-based design — trade-offs in statefulness |
| 3 | How does jsonrpcclient handle message ID generation? | ID uniqueness strategies (UUID, incrementing integer, caller-provided) |
| 4 | What does the transport boundary look like when fully externalized? | Informs where jrpcx should draw the line between protocol and transport |

### pjrpc — Python JSON-RPC Patterns

| # | Question | Why It Matters |
|---|----------|---------------|
| 1 | How does pjrpc abstract multiple transport backends (httpx, aiohttp, requests)? | Directly applicable — jrpcx needs the same backend pluggability |
| 2 | How does pydantic validation integrate with JSON-RPC request/response? | Type-safe parameter and result validation is a key jrpcx feature |
| 3 | What does pjrpc's interceptor (middleware) architecture look like? | Middleware for auth, logging, retry — essential for production use |
| 4 | How does pjrpc handle batch operations in its API? | Batch API ergonomics — builder pattern vs. context manager vs. explicit list |
| 5 | What is pjrpc's error hierarchy and how does it map JSON-RPC error codes? | Exception class design for jrpcx |

### ybbus/jsonrpc — Ergonomic Simplicity

| # | Question | Why It Matters |
|---|----------|---------------|
| 1 | How does ybbus/jsonrpc achieve great ergonomics in ~700 lines? | Proves that jrpcx's core can be small — complexity should be opt-in |
| 2 | What do typed response accessors (`GetObject`, `GetInt`) look like? | Response handling UX — how users extract typed data from RPC results |
| 3 | How does a zero-dependency JSON-RPC client handle configuration? | When stdlib is enough — and when it isn't |
| 4 | What are the limitations of an HTTP-only transport approach? | Helps jrpcx decide whether to build transport abstraction from day one |

### jrpc2 — Transport & Concurrency

| # | Question | Why It Matters |
|---|----------|---------------|
| 1 | How does the `Channel` interface abstract bidirectional message streams? | The gold standard for transport abstraction — jrpcx's `Transport` protocol should learn from this |
| 2 | How does jrpc2 handle concurrent in-flight requests over a single connection? | Multiplexing is essential for async clients — request ID correlation, response routing |
| 3 | How does jrpc2 integrate Go's `context.Context` for cancellation and deadlines? | Analogous to Python's `asyncio` cancellation — how timeouts propagate through RPC calls |
| 4 | What does production-grade JSON-RPC error handling look like? | Error codes, data payloads, error wrapping, sentinel errors |
| 5 | How does jrpc2 support server push and bidirectional communication? | Future jrpcx feature — WebSocket-based bidirectional JSON-RPC |

### jayson — Multi-Transport & Middleware

| # | Question | Why It Matters |
|---|----------|---------------|
| 1 | How does jayson support HTTP, TCP, and WebSocket with a unified client API? | Multi-transport architecture patterns — how the API stays consistent across transports |
| 2 | What does jayson's middleware system look like for request/response interception? | Middleware chain design — ordering, error handling, async middleware |
| 3 | How does jayson handle connection lifecycle events? | Event system for connect/disconnect/error — how jrpcx should surface transport events |
| 4 | How does jayson's relay/proxy mechanism work? | Forwarding between transports — interesting for gateway/proxy use cases |
| 5 | How does jayson handle JSON-RPC 1.0 + 2.0 protocol negotiation? | Protocol versioning — jrpcx is 2.0-only but should understand the trade-off |

---

## 7. Next Steps

This exploratory research document establishes the **foundation and rationale** for jrpcx's design research. The next phase involves:

1. **Deep codebase analyses** — detailed technical breakdowns of each selected library (see individual reports)
2. **Pattern synthesis** — extracting the best patterns from all six libraries into a unified design vision
3. **Architecture proposal** — translating research findings into jrpcx's module structure, class hierarchy, and API surface
4. **Prototype implementation** — building a minimal working client to validate the architectural decisions

For the complete set of research documents, see [RESEARCH_INDEX.md](./RESEARCH_INDEX.md).

---

*This document is part of the jrpcx research corpus. For navigation across all research documents, see the [Research Index](./RESEARCH_INDEX.md).*
