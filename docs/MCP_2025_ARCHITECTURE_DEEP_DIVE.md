# MCP 2025-11-25 Transport Architecture Overview

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Client Request                               │
│  (HTTP POST /messages/ or /sse with headers)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Starlette FastAPI App                          │
│                    (underlying FastMCP)                             │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                     ┌───────▼───────┐
                     │   Middleware  │
                     │  Stack Order  │
                     └───────┬───────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   [Request]          [Extract Headers]      [Standard]
   Logging            & Session ID            Middleware
                          │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   [Phase 2]          [Phase 3]            [Core]
   Validate           Create/Track         Route
   Protocol           Session ID           Dispatch
   Version                │
        │                 │
        ▼                 ▼
   Unsupported? ─→ Invalid Session? ─→ Call Next
  Return 400        [Optional]
        │                 │
        └─────────┬───────┘
                  │
                  ▼
     ┌────────────────────────────┐
     │   Route Handler Execution  │
     │  /messages/                │
     │  /protocol/info            │
     │  /protocol/sessions        │
     └────────────┬───────────────┘
                  │
                  ▼
     ┌────────────────────────────┐
     │    Inject Response Headers │
     │  MCP-Protocol-Version: xxx │
     │  MCP-Session-Id: xxxxx     │
     └────────────┬───────────────┘
                  │
                  ▼
     ┌────────────────────────────┐
     │    Return HTTP Response    │
     │    200 OK / 400 / etc.     │
     └────────────────────────────┘
```

## Module Organization

### `hlf_mcp/mcp_protocol_v2025.py`
Core protocol compliance implementation:

```
MCPSession
├── session_id: str (UUID)
├── created_at: str (ISO timestamp)
├── last_activity_at: str (ISO timestamp)
├── message_count: int
├── initialize_called: bool
└── Methods:
    ├── record_message()
    ├── record_initialize()
    └── to_dict() → Dict for JSON response

MCPSessionStore
├── _sessions: Dict[session_id, MCPSession]
├── _session_by_request_id: Dict[request_id, session_id]
└── Methods:
    ├── create_session() → MCPSession
    ├── get_session(id) → MCPSession | None
    ├── record_message(id) → bool
    ├── record_initialize(id) → bool
    └── list_sessions() → List[Dict]

Validation Functions
├── validate_protocol_version(header) → (bool, str | None)
└── build_mcp_response_headers(session_id, version) → Dict[str, str]

Constants
├── SUPPORTED_PROTOCOL_VERSIONS = {"2025-11-25", "2024-11-05"}
└── CANONICAL_PROTOCOL_VERSION = "2025-11-25"
```

### `hlf_mcp/server.py` Integration Points

```
Imports from mcp_protocol_v2025:
├── MCPSessionStore
├── get_session_store()
├── validate_protocol_version()
├── build_mcp_response_headers()
├── make_mcp_protocol_middleware()
└── log_session_info()

Custom Routes Added:
├── @mcp.custom_route("/health", ...)
│   └── Existing endpoint (unchanged)
├── @mcp.custom_route("/protocol/info", ...)
│   └── New: Protocol capability status
├── @mcp.custom_route("/protocol/sessions", ...)
│   └── New: List all sessions
└── @mcp.custom_route("/protocol/sessions/{session_id}", ...)
    └── New: Get session details

Middleware Setup:
└── _setup_protocol_compliance_middleware()
    └── Registers MCPProtocolMiddleware with FastMCP app
        ├── Phase 2: validate_protocol_version()
        └── Phase 3: session tracking & injection

Main Entry Point:
└── main()
    ├── Logs "MCP 2025-11-25 Protocol Compliance enabled"
    ├── Calls _setup_protocol_compliance_middleware() for HTTP transports
    └── Logs server bind address with compliance confirmation
```

## Request Flow Example: Initialize with Session

### Phase 2 & 3 Combined Flow

```
1. Client sends:
   POST /messages/
   Headers:
     MCP-Protocol-Version: 2025-11-25
     Content-Type: application/json
   Body:
     {"jsonrpc":"2.0","method":"initialize","params":{},"id":1}

2. MCPProtocolMiddleware intercepts request:
   a) Extract headers:
      - protocol_version = "2025-11-25"
      - session_id = None (first request)

   b) Phase 2 Validation:
      - validate_protocol_version("2025-11-25")
      - Result: (True, None)  ✓ Allowed

   c) Phase 3 Session:
      - session_id is None, so create new session
      - store.create_session() → MCPSession
      - Record initialize event: store.record_initialize(new_session_id)

3. Route handler executes:
   - Parse JSON-RPC message
   - Call hlf_compile or other tools
   - Return result

4. Response Headers Injection:
   - response.headers["MCP-Session-Id"] = new_session_id
   - response.headers["MCP-Protocol-Version"] = "2025-11-25"

5. Return to client:
   HTTP/1.1 200 OK
   Headers:
     MCP-Session-Id: 550e8400-e29b-41d4-a716-446655440000
     MCP-Protocol-Version: 2025-11-25
     Content-Type: application/json
   Body:
     {"jsonrpc":"2.0","result":{...},"id":1}

6. Client extracts session ID:
   session_id = "550e8400-e29b-41d4-a716-446655440000"
   store in local context
```

### Subsequent Request (Session Reuse)

```
1. Client sends:
   POST /messages/
   Headers:
     MCP-Protocol-Version: 2025-11-25
     MCP-Session-Id: 550e8400-e29b-41d4-a716-446655440000  ← From previous response
     Content-Type: application/json
   Body:
     {"jsonrpc":"2.0","method":"tools/list","params":{},"id":2}

2. MCPProtocolMiddleware intercepts:
   a) Extract headers:
      - protocol_version = "2025-11-25"
      - session_id = "550e8400-e29b-41d4-a716-446655440000"

   b) Phase 2 Validation:
      - validate_protocol_version("2025-11-25")
      - Result: (True, None)  ✓ Allowed

   c) Phase 3 Session:
      - session_id is present
      - store.record_message(session_id)
      - session.message_count += 1
      - session.last_activity_at = now()

3. Route handler executes:
   - tools/list request processed
   - Return tool schemas

4. Response Headers Injection:
   - response.headers["MCP-Session-Id"] = session_id  (same)
   - response.headers["MCP-Protocol-Version"] = "2025-11-25"

5. Return to client:
   HTTP/1.1 200 OK
   Headers:
     MCP-Session-Id: 550e8400-e29b-41d4-a716-446655440000  ← Same ID
     MCP-Protocol-Version: 2025-11-25
     Content-Type: application/json
   Body:
     {"jsonrpc":"2.0","result":{"tools":[...]},"id":2}
```

## Error Handling: Phase 2 Unsupported Version

```
1. Client sends:
   POST /messages/
   Headers:
     MCP-Protocol-Version: 1999-01-01  ← Unsupported
     Content-Type: application/json
   Body:
     {...}

2. MCPProtocolMiddleware intercepts:
   a) Extract headers:
      - protocol_version = "1999-01-01"
      - session_id = None

   b) Phase 2 Validation:
      - validate_protocol_version("1999-01-01")
      - Result: (False, "Unsupported MCP-Protocol-Version: 1999-01-01. Supported: 2024-11-05, 2025-11-25")
      - Log warning: "Protocol version validation failed for /messages/: ..."

   c) Return error response immediately:
      (route handler NOT called)

3. Return to client:
   HTTP/1.1 400 Bad Request
   Content-Type: application/json
   Body:
     {
       "status": "error",
       "error": "Unsupported MCP-Protocol-Version: 1999-01-01. Supported: 2024-11-05, 2025-11-25",
       "supported_versions": ["2025-11-25", "2024-11-05"]
     }
```

## Diagnostic Endpoints

### `GET /protocol/info`
Real-time protocol capability status.

```
Request:
  GET /protocol/info

Response:
  HTTP/1.1 200 OK
  {
    "status": "ok",
    "canonical_protocol_version": "2025-11-25",
    "supported_versions": ["2025-11-25", "2024-11-05"],
    "phase_2_enabled": true,
    "phase_3_enabled": true,
    "features": {
      "phase_2_header_validation": "MCP-Protocol-Version header validation with 400 on unsupported",
      "phase_3_session_management": "MCP-Session-Id header generation and tracking"
    },
    "content_types_accepted": ["application/json"],
    "transport": "sse"  (or "streamable-http", "stdio")
  }
```

### `GET /protocol/sessions`
List all active sessions.

```
Request:
  GET /protocol/sessions

Response:
  HTTP/1.1 200 OK
  {
    "status": "ok",
    "active_sessions": 2,
    "sessions": [
      {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "created_at": "2026-03-27T10:15:32.125000",
        "last_activity_at": "2026-03-27T10:15:35.642000",
        "message_count": 5,
        "initialize_called": true
      },
      {
        "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "created_at": "2026-03-27T10:16:00.000000",
        "last_activity_at": "2026-03-27T10:16:01.000000",
        "message_count": 1,
        "initialize_called": true
      }
    ]
  }
```

### `GET /protocol/sessions/{session_id}`
Get details for a specific session.

```
Request:
  GET /protocol/sessions/550e8400-e29b-41d4-a716-446655440000

Response:
  HTTP/1.1 200 OK
  {
    "status": "ok",
    "session": {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-03-27T10:15:32.125000",
      "last_activity_at": "2026-03-27T10:15:35.642000",
      "message_count": 5,
      "initialize_called": true
    }
  }

Not Found Response:
  HTTP/1.1 404 Not Found
  {
    "status": "error",
    "error": "Session '550e8400-dead-0000-0000-000000000000' not found"
  }
```

## Configuration & Environment

### Transport Modes
- `HLF_TRANSPORT=stdio` — No HTTP, no middleware needed
- `HLF_TRANSPORT=sse` — HTTP + SSE, middleware enabled
- `HLF_TRANSPORT=streamable-http` — Streamable HTTP, middleware enabled

### Optional Strict Mode
```bash
HLF_REQUIRE_SESSION=true python -m hlf.server
```
Forces all requests to include valid `MCP-Session-Id` header (403 Forbidden if missing).

## Performance Considerations

### Session Storage
- In-memory dict (no persistence across restarts)
- UUID key for O(1) session lookup
- Suitable for single-process deployments
- For distributed deployments: upgrade to Redis-backed session store

### Memory Usage (estimate)
- Each session: ~300 bytes overhead
- 1000 concurrent sessions: ~300 KB
- No automatic session cleanup (sessions live until server restart)

### Latency Impact
- Phase 2 validation: <1 ms (string comparison)
- Phase 3 recording: <1 ms (dict update + uuid generation on first request)
- Negligible impact on throughput

## Security Considerations

### Phase 2 (Header Validation)
✓ Validates version format to prevent injection attacks
✓ Returns clear error messages without exposing internals

### Phase 3 (Session Management)
✓ Uses standard UUIDs (cryptographically random)
✓ Session IDs are opaque strings (no sensitive data encoded)
✓ Optional: Implement session expiration if needed
⚠ Sessions persist in memory (restart clears all)

### Future Hardening
- [ ] Session expiration (TTL)
- [ ] Session encryption for inter-process IPC
- [ ] HMAC-signed session IDs
- [ ] Rate limiting per session
- [ ] Session binding to client IP (optional)
