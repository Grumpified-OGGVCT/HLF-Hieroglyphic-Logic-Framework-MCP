# Architecture Overview

## System Design

The AgentsKB MCP Server is a production-ready Model Context Protocol server that provides access to the AgentsKB knowledge base API. It follows best practices for TypeScript, error handling, and MCP protocol implementation.

## Components

### 1. MCP Server (`src/index.ts`)
- Implements the Model Context Protocol using `@modelcontextprotocol/sdk`
- Uses stdio transport for communication with MCP clients (e.g., Claude Desktop)
- Registers three tools: `ask_question`, `search_questions`, `get_stats`
- Handles tool execution with proper error handling and logging

### 2. API Client (`src/api-client.ts`)
- Encapsulates all HTTP communication with AgentsKB REST API
- Handles authentication, request formatting, and response parsing
- Implements comprehensive error handling for network and API errors
- Supports all AgentsKB API endpoints:
  - `POST /ask` - Ask a question
  - `POST /ask-batch` - Batch questions
  - `GET /search` - Search Q&A database
  - `GET /stats` - Get statistics
  - `GET /health` - Health check

### 3. Configuration (`src/config.ts`)
- Manages environment variables using `dotenv`
- Validates configuration with Zod schemas
- Provides typed configuration object
- Handles missing or invalid configuration gracefully

### 4. Logger (`src/logger.ts`)
- Structured logging utility
- Supports DEBUG, INFO, WARN, ERROR levels
- Writes to stderr (standard for MCP servers)
- Includes timestamps and contextual data

### 5. Types (`src/types.ts`)
- Complete TypeScript type definitions for all API responses
- Ensures type safety throughout the application
- Documents API contract

## Data Flow

```
Claude Desktop (MCP Client)
    ↓
Stdio Transport (JSON-RPC 2.0)
    ↓
MCP Server (src/index.ts)
    ↓
Tool Handler (ask_question/search_questions/get_stats)
    ↓
API Client (src/api-client.ts)
    ↓
AgentsKB REST API (HTTPS)
    ↓
Response Processing
    ↓
MCP Response (JSON-RPC 2.0)
    ↓
Claude Desktop
```

## Error Handling Strategy

1. **Configuration Errors**: Fail fast at startup with clear error messages
2. **API Errors**: Catch and format AgentsKB API errors with proper context
3. **Network Errors**: Handle timeouts and connection failures gracefully
4. **Validation Errors**: Use Zod schemas to validate inputs before API calls
5. **Tool Execution Errors**: Wrap errors in user-friendly messages

## Security Considerations

- ✅ API keys stored in environment variables (never in code)
- ✅ `.env` file excluded from version control
- ✅ HTTPS-only API communication
- ✅ Input validation prevents injection attacks
- ✅ Error messages don't expose sensitive information
- ✅ Secure logging (no API keys in logs)

## Performance Optimizations

- Uses native `fetch` API (Node.js 20+)
- Efficient JSON parsing
- Minimal dependencies
- No unnecessary abstractions
- Direct stdio communication (no HTTP overhead)

## Testing Strategy

While this implementation doesn't include automated tests, the architecture supports:
- Unit testing of API client (mock fetch)
- Integration testing with MCP protocol
- End-to-end testing with Claude Desktop

## Deployment

The server is designed to run:
- **Development**: `npm run dev` (tsx with hot reload)
- **Production**: `npm start` (tsx, no compilation needed)
- **MCP Integration**: Via Claude Desktop configuration

## Dependencies

### Production
- `@modelcontextprotocol/sdk` - Official MCP SDK
- `dotenv` - Environment variable management
- `zod` - Schema validation

### Development
- `typescript` - Type checking
- `tsx` - TypeScript execution
- `eslint` - Code linting
- `prettier` - Code formatting

## Future Enhancements

Potential improvements:
- Caching layer for frequently asked questions
- Batch request optimization
- Metrics and observability
- Health check endpoint
- Rate limiting
- Retry logic with exponential backoff

