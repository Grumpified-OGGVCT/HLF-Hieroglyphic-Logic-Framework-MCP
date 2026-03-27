# How AgentsKB MCP Server Works - Your Goal Achieved! 🎯

## Your Goal (Perfectly Understood!)

You want to **level the playing field** for smaller/weaker coding models by giving them access to a curated knowledge base of 26,841+ expert Q&As. This way:
- A 20B parameter model + AgentsKB = Performance closer to a 70B+ model
- Models weak in coding can pull expert answers on-demand
- Local/low-parameter models can compete with cloud giants

**This is EXACTLY what this MCP server does!** ✅

## How It Works

### The Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Your AI Model (e.g., 20B local model, Qwen, etc.)      │
│  "I need to know how to use PostgreSQL indexes..."      │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Calls MCP Tool: ask_question()
                 ▼
┌─────────────────────────────────────────────────────────┐
│  MCP Server (this code - runs as a process)            │
│  - Receives tool call from model                        │
│  - Validates the question                               │
│  - Makes HTTP request to AgentsKB API                   │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ HTTP Request
                 ▼
┌─────────────────────────────────────────────────────────┐
│  AgentsKB API (Cloud Service)                          │
│  - Searches 26,841 Q&As using vector search            │
│  - Returns best match with 99% confidence              │
│  - Includes sources and domain info                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ JSON Response
                 ▼
┌─────────────────────────────────────────────────────────┐
│  MCP Server                                              │
│  - Formats response for MCP protocol                    │
│  - Returns to AI model                                  │
└────────────────┬────────────────────────────────────────┘
                 │
                 │ Structured Answer
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Your AI Model                                           │
│  "Based on AgentsKB: PostgreSQL indexes are created..." │
│  Now has expert-level knowledge! 🎉                     │
└─────────────────────────────────────────────────────────┘
```

## What the Server Actually Does

### 1. **It IS a Server Process**
- Runs as a Node.js process (via `tsx`)
- Communicates via stdio (standard input/output)
- Listens for MCP protocol messages
- Handles tool calls from AI models

### 2. **Exposes Three Tools**

When your AI model needs coding knowledge, it can call:

#### `ask_question`
```javascript
// Model calls this when it needs an answer
{
  "question": "How do I optimize PostgreSQL queries?",
  "domain": "postgresql",
  "tier": "GOLD"
}

// Returns:
{
  "answer": {
    "text": "PostgreSQL query optimization involves...",
    "confidence": 0.99,
    "sources": ["https://postgresql.org/docs/..."]
  }
}
```

#### `search_questions`
```javascript
// Model searches for related Q&As
{
  "query": "database indexing strategies",
  "limit": 5
}

// Returns multiple relevant Q&As ranked by similarity
```

#### `get_stats`
```javascript
// Model can check what's available
// Returns: 26,841 Q&As across 47+ domains, 99% confidence
```

### 3. **Connects to AgentsKB API**

The server makes HTTP requests to:
```
https://agentskb-api.agentskb.com/api/free/ask
```

This is the **actual knowledge base** - 26,841 curated Q&As stored in a vector database (Qdrant) with semantic search.

## Your Use Case: Smaller Models + Knowledge Base

### Scenario: 20B Parameter Model

**Without AgentsKB:**
```
User: "How do I implement a PostgreSQL connection pool?"
Model: "A connection pool is... [generic answer, may be incomplete]"
```

**With AgentsKB MCP Server:**
```
User: "How do I implement a PostgreSQL connection pool?"
Model: [Calls ask_question tool]
       → Gets expert answer from 26,841 Q&As
       → "Based on AgentsKB: PostgreSQL connection pooling involves
          using pgBouncer or built-in pooling. Key considerations:
          1. max_connections setting...
          2. Pool sizing formula: (core_count * 2) + effective_spindle_count...
          [Expert-level, sourced answer with 99% confidence]"
```

### The Power

1. **On-Demand Expertise**: Model doesn't need to "know" everything - it can look it up
2. **99% Accuracy**: Pre-researched answers vs. model's training data
3. **Fast**: <1 second response vs. 10-15s web search
4. **Cheap**: ~500 tokens vs. 10-15K tokens for web search
5. **Domain-Specific**: 47+ technical domains covered

## Real Example Flow

### Step 1: Model Needs Knowledge
```
Model: "User asked about FastAPI async endpoints. 
        I should check AgentsKB for best practices."
```

### Step 2: Model Calls Tool
```json
{
  "tool": "ask_question",
  "arguments": {
    "question": "How do I create async endpoints in FastAPI?",
    "domain": "python",
    "tier": "GOLD"
  }
}
```

### Step 3: Server Processes
- Validates input
- Makes HTTP request to AgentsKB API
- Waits for response (<1s)

### Step 4: Server Returns Answer
```json
{
  "answer": {
    "text": "FastAPI supports async endpoints natively. 
             Use async def for route handlers...",
    "confidence": 0.98,
    "sources": ["https://fastapi.tiangolo.com/async/"]
  }
}
```

### Step 5: Model Uses Answer
```
Model: "Based on AgentsKB's expert knowledge:
        FastAPI supports async endpoints natively. 
        Use async def for route handlers..."
```

## Why This Works for Your Goal

### ✅ Levels the Playing Field

**Small Model (20B) without AgentsKB:**
- Limited coding knowledge in training data
- May give incomplete/incorrect answers
- Relies on what it "remembers"

**Small Model (20B) with AgentsKB:**
- Can access 26,841 expert Q&As on-demand
- Gets 99% confidence answers
- Performance approaches larger models
- **Cost**: Still runs locally, just adds API calls

### ✅ Works with Any Model

- **Local models** (Ollama, LM Studio, etc.)
- **Cloud models** (OpenAI, Anthropic, etc.)
- **Small models** (7B, 13B, 20B)
- **Specialized models** (coding-focused but weak in other areas)

### ✅ Efficient

- **Fast**: <1s per query
- **Cheap**: ~500 tokens per answer
- **Batch**: Can ask 100 questions in one call
- **Cached**: AgentsKB API handles caching

## The Files

### What You Have

1. **`src/index.ts`** - The MCP server (exposes tools)
2. **`src/api-client.ts`** - HTTP client to AgentsKB API
3. **`src/config.ts`** - Configuration (API key, etc.)
4. **`.env`** - Your API key

### What Runs

- **MCP Server Process**: `tsx src/index.ts` (runs when Cursor/IDE needs it)
- **AgentsKB API**: Cloud service (the actual knowledge base)

### What the Model Sees

When configured, your AI model sees these tools:
- `ask_question` - Get expert answers
- `search_questions` - Search the knowledge base
- `get_stats` - Check what's available

## Summary

**Yes, this IS a server!** It's an MCP server that:
1. ✅ Runs as a process (automatically started by your IDE)
2. ✅ Exposes tools that AI models can call
3. ✅ Connects to AgentsKB API (the knowledge base)
4. ✅ Returns expert answers to models
5. ✅ **Achieves your goal**: Levels the playing field for smaller models

**Your 20B model + AgentsKB = Expert-level coding knowledge on-demand!** 🚀

The server doesn't "load files" - it's a **bridge** between your AI model and the AgentsKB knowledge base API. The knowledge base lives in the cloud (26,841 Q&As), and your server fetches answers on-demand when the model needs them.

