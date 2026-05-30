# HLF MCP — Docker Guide

> Claim lane: **current-true** — the images and commands below work with the packaged server.

## Quick Start

```bash
# Pull and run the HTTP server
docker pull ghcr.io/grumpified-oggvct/hlf-mcp:latest
docker run --rm -p 8000:8000 ghcr.io/grumpified-oggvct/hlf-mcp:latest

# Verify it is alive
curl http://localhost:8000/health
# → {"status":"ok","transport":"streamable-http"}
```

Or build locally:

```bash
docker build -t hlf-mcp:latest .
docker run --rm -p 8000:8000 hlf-mcp:latest
```

## Images

| Registry | Image | Status |
|---|---|---|
| Docker Hub | `grumpified/hlf-mcp:latest` · `:0.5.0` | ✅ Published |
| GitHub Container Registry | `ghcr.io/grumpified-oggvct/hlf-mcp:latest` · `:0.5.0` | ✅ Published |

## Transport Modes

The server supports three transports, selected via the `HLF_TRANSPORT` environment variable.

### Streamable HTTP (default)

Modern MCP transport. Single endpoint with optional SSE streaming.

```bash
docker run --rm -p 8000:8000 hlf-mcp:latest
# Endpoint: http://localhost:8000/mcp
```

**Env vars:** `HLF_TRANSPORT=streamable-http`, `HLF_PORT=8000` (default)

### SSE (legacy HTTP)

Deprecated HTTP+SSE compatibility mode. Prefer streamable-http.

```bash
docker run --rm -e HLF_TRANSPORT=sse -p 8000:8000 hlf-mcp:latest
# SSE endpoint:    GET  http://localhost:8000/sse
# Messages endpoint: POST http://localhost:8000/messages/
```

### stdio

Native MCP transport for desktop clients (Claude Desktop, VS Code, etc.).

```bash
docker run --rm -i -e HLF_TRANSPORT=stdio hlf-mcp:latest
```

## Environment Variables

| Variable | Values | Default | Description |
|---|---|---|---|
| `HLF_TRANSPORT` | `streamable-http`, `sse`, `http`, `stdio` | `streamable-http` | MCP transport protocol |
| `HLF_HOST` | IP address | `0.0.0.0` | Listen address (HTTP transports) |
| `HLF_PORT` | 1–65535 | `8000` | Listen port (HTTP transports) |
| `HLF_STRICT` | `0`, `1` | `1` | Fail-closed on governance violations |
| `HLF_HOT_TIER` | `none`, `valkey` | `none` | Hot cache backend |
| `HLF_MEMORY_DB` | file path | `db/hlf_memory.db` | SQLite memory database path |
| `VALKEY_URL` | Redis URL | `redis://valkey:6379` | Valkey connection string |

## Docker Compose

### Basic (HTTP only)

```bash
docker compose up
```

### With Valkey hot cache

```bash
docker compose --profile hot up
```

### With full tier (Valkey + beartype enforcement)

```bash
docker compose --profile full up
```

Customize via `.env`:

```ini
HLF_PORT=9000
HLF_TRANSPORT=sse
HLF_MEMORY_DB=/app/db/hlf_memory.db
```

## MCP Client Configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hlf-mcp": {
      "type": "streamableHttp",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

For stdio via Docker:

```json
{
  "mcpServers": {
    "hlf-mcp": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-e", "HLF_TRANSPORT=stdio", "ghcr.io/grumpified-oggvct/hlf-mcp:latest"]
    }
  }
}
```

### VS Code (`.mcp.json`)

```json
{
  "servers": {
    "hlf-mcp": {
      "type": "streamableHttp",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Health Check

The image includes a built-in health check that calls `/health` every 30 seconds.

```bash
# Manual check
curl http://localhost:8000/health

# Docker health status
docker inspect --format='{{.State.Health.Status}}' hlf-mcp
# → healthy
```

## Persistence

Mount volumes for persistent memory and data:

```bash
docker run --rm -p 8000:8000 \
  -v hlf-db:/app/db \
  -v hlf-data:/app/data \
  hlf-mcp:latest
```

## Security

- Runs as non-root user `hlf` (UID/GID 1000 equivalent)
- HTTP transports bind `0.0.0.0` inside the container — use `-p 127.0.0.1:8000:8000` to restrict to localhost
- For remote access, front with a reverse proxy (Caddy, nginx) with TLS and authentication
- Governance enforcement (`HLF_STRICT=1`) fails closed on policy violations

## Building From Source

```bash
git clone https://github.com/Grumpified-OGGVCT/SwarmGlass-MCP.git
cd SwarmGlass-MCP
docker build -t hlf-mcp:latest .
```

## Related Docs

- [HLF_MCP_TRANSPORT_GUIDE.md](HLF_MCP_TRANSPORT_GUIDE.md) — non-Python client integration
- [BUILD_GUIDE.md](../BUILD_GUIDE.md) — full build and automation guide
- [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md) — single source of truth for current state
