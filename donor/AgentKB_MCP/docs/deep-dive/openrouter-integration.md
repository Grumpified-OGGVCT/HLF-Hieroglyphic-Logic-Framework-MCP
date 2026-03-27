# OpenRouter Integration Deep Dive

**Status**: Implemented (Phase 2 enhancement)

This document captures EVERYTHING extracted from OpenRouter's documentation for integration into the Verified Developer KB Pro system.

---

## 1) What OpenRouter Provides

OpenRouter is a **unified API gateway** to 300+ AI models from multiple providers:

| Provider | Example Models |
|----------|---------------|
| OpenAI | GPT-4o, GPT-4 Turbo, o1 |
| Anthropic | Claude 3.5 Sonnet, Claude 3 Opus |
| Google | Gemini 1.5 Pro, Gemini 1.5 Flash |
| Meta | Llama 3.1 70B, Llama 3.3 70B |
| Mistral | Mistral Large, Mixtral |
| xAI | Grok |
| DeepSeek | DeepSeek R1, DeepSeek V3 |
| And 50+ more... | |

### Key Value Proposition

- **Single API Key**: One account, all models
- **Automatic Fallbacks**: If one provider is down, automatically routes to another
- **Cost Optimization**: Route to cheapest provider for a model
- **Throughput Optimization**: Route to fastest provider
- **OpenAI Compatible**: Drop-in replacement for OpenAI SDK

---

## 2) API Reference (Complete)

### Base URL
```
https://openrouter.ai/api/v1
```

### Authentication
```
Authorization: Bearer <OPENROUTER_API_KEY>
```

### Chat Completions Endpoint
```
POST /api/v1/chat/completions
```

### Request Schema (Full)

```python
{
    # Required
    "model": "anthropic/claude-3.5-sonnet",  # provider/model format
    "messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},  # For prefill
    ],
    
    # Standard LLM Parameters
    "temperature": 0.7,           # Range: [0, 2]
    "max_tokens": 4096,           # Range: [1, context_length)
    "top_p": 1.0,                 # Range: (0, 1]
    "top_k": 40,                  # Not available for OpenAI
    "frequency_penalty": 0.0,     # Range: [-2, 2]
    "presence_penalty": 0.0,      # Range: [-2, 2]
    "repetition_penalty": 1.0,    # Range: (0, 2]
    "stop": ["---"],              # Stop sequences
    "seed": 42,                   # For reproducibility
    
    # Streaming
    "stream": true,
    
    # Tool Calling
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        }
    ],
    "tool_choice": "auto",  # or "none" or {"type": "function", "function": {"name": "..."}}
    
    # Structured Output
    "response_format": {"type": "json_object"},
    
    # Provider Routing (OpenRouter-specific)
    "provider": {
        "order": ["anthropic", "openai"],  # Try in order
        "only": ["anthropic", "azure"],     # Restrict to these
        "ignore": ["deepinfra"],            # Skip these
        "allow_fallbacks": true,            # Default true
        "require_parameters": true,         # Only use providers supporting all params
        "data_collection": "deny",          # "allow" or "deny"
        "zdr": true,                        # Zero Data Retention
        "quantizations": ["fp8", "fp16"],   # Filter by quantization
        "sort": "throughput",               # "price", "throughput", "latency"
        "max_price": {
            "prompt": 1.0,      # Max $/M prompt tokens
            "completion": 2.0   # Max $/M completion tokens
        }
    },
    
    # Model Routing (multi-model)
    "models": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
    "route": "fallback",  # Use as fallback chain
    
    # Predicted output (latency optimization)
    "prediction": {
        "type": "content",
        "content": "The answer is..."
    }
}
```

### Response Schema

```python
{
    "id": "gen-xxxxxxxxxxxxxx",
    "object": "chat.completion",
    "created": 1704067200,
    "model": "anthropic/claude-3.5-sonnet",
    
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "The answer is...",
                "tool_calls": [...]  # If tool calling
            },
            "finish_reason": "stop",  # Normalized: stop, length, tool_calls, content_filter, error
            "native_finish_reason": "end_turn"  # Provider's raw reason
        }
    ],
    
    "usage": {
        "prompt_tokens": 100,      # Normalized (GPT-4o tokenizer)
        "completion_tokens": 50,
        "total_tokens": 150
    },
    
    "system_fingerprint": "fp_abc123"
}
```

### Generation Stats Endpoint (Exact Cost)

```
GET /api/v1/generation?id={generation_id}
```

Returns:
- Native token counts (model's actual tokenizer)
- Exact cost in credits
- Provider used
- Latency metrics

---

## 3) Model Shortcuts

| Shortcut | Effect |
|----------|--------|
| `model:nitro` | Sort by throughput (fastest) |
| `model:floor` | Sort by price (cheapest) |
| `model:free` | Use free tier only |

Example: `meta-llama/llama-3.1-70b-instruct:nitro`

---

## 4) Provider Routing Rules

### Default Behavior
1. Load balance across top providers, weighted by inverse-square of price
2. Deprioritize providers with outages in last 30 seconds
3. Fallback to other providers on failure

### Sorting Options

| Sort | Description |
|------|-------------|
| `price` | Always use cheapest provider |
| `throughput` | Always use fastest tokens/sec |
| `latency` | Always use lowest time-to-first-token |

### Privacy Controls

| Field | Values | Description |
|-------|--------|-------------|
| `data_collection` | `"allow"` / `"deny"` | Filter providers that may store/train on data |
| `zdr` | `true` / `false` | Zero Data Retention enforcement |

---

## 5) TypeScript SDK

### Installation
```bash
npm install @openrouter/sdk
```

### Basic Usage
```typescript
import { OpenRouter } from '@openrouter/sdk';

const openRouter = new OpenRouter({
    apiKey: process.env.OPENROUTER_API_KEY,
});

const completion = await openRouter.chat.send({
    model: 'anthropic/claude-3.5-sonnet',
    messages: [{ role: 'user', content: 'Hello' }],
    stream: false,
});
```

### callModel API (Advanced)

```typescript
const result = openRouter.callModel({
    model: 'openai/gpt-4o',
    input: 'What is the capital of France?',
});

// Multiple consumption patterns:
const text = await result.getText();
const response = await result.getResponse();  // Includes usage

// Streaming:
for await (const delta of result.getTextStream()) {
    process.stdout.write(delta);
}

// Reasoning stream (for reasoning models):
for await (const delta of result.getReasoningStream()) {
    console.log('Thinking:', delta);
}

// Tool calls:
const toolCalls = await result.getToolCalls();
for await (const toolCall of result.getToolCallsStream()) {
    console.log(`Tool: ${toolCall.name}`, toolCall.arguments);
}
```

---

## 6) Value for Our System

### Use Case 1: KB Model Alternatives

When Gemini is unavailable or expensive:

```python
# Primary: Gemini for KB queries
# Fallback: Claude or GPT-4 via OpenRouter
provider = {
    "models": ["google/gemini-pro", "anthropic/claude-3.5-sonnet"],
    "route": "fallback"
}
```

### Use Case 2: Research Agent Optimization

For research tasks, optimize for throughput:

```python
# Fast research with cost cap
provider = {
    "sort": "throughput",
    "max_price": {"prompt": 1.0, "completion": 2.0},
    "data_collection": "deny"  # Privacy
}
```

### Use Case 3: Privacy-First Research

When handling sensitive queries:

```python
provider = {
    "zdr": True,               # Zero data retention
    "data_collection": "deny", # No training on data
    "only": ["anthropic"]      # Trust only specific providers
}
```

### Use Case 4: Cost Attribution

Track per-query costs:

```python
# After completion, get exact cost
stats = await fetch(f"https://openrouter.ai/api/v1/generation?id={generation_id}")
cost = stats["cost"]
native_tokens = stats["native_tokens"]
```

---

## 7) Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Provider Abstraction                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐       ┌──────────────────┐               │
│  │                  │       │                  │               │
│  │  GeminiClient    │       │ OpenRouterClient │               │
│  │  (Primary)       │       │ (Fallback/Alt)   │               │
│  │                  │       │                  │               │
│  └────────┬─────────┘       └────────┬─────────┘               │
│           │                          │                          │
│           └──────────┬───────────────┘                          │
│                      │                                          │
│              ┌───────▼───────┐                                  │
│              │               │                                  │
│              │ LLMRouter     │                                  │
│              │ (Strategy)    │                                  │
│              │               │                                  │
│              └───────────────┘                                  │
│                                                                 │
│  Strategies:                                                    │
│  - PRIMARY_ONLY: Use Gemini only                               │
│  - FALLBACK: Try Gemini, fall back to OpenRouter               │
│  - COST_OPTIMIZED: Route based on cost                         │
│  - THROUGHPUT: Route to fastest                                │
│  - PRIVACY_FIRST: Use ZDR endpoints only                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8) Configuration

### Environment Variables

```env
# Primary provider (Gemini)
GOOGLE_API_KEY=your-gemini-key

# Secondary provider (OpenRouter)
OPENROUTER_API_KEY=your-openrouter-key

# Routing strategy
LLM_ROUTING_STRATEGY=fallback  # primary_only, fallback, cost_optimized, throughput, privacy_first

# OpenRouter preferences
OPENROUTER_DEFAULT_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_SORT=price  # price, throughput, latency
OPENROUTER_DATA_COLLECTION=deny  # allow, deny
OPENROUTER_ZDR=true  # true, false

# Cost controls
OPENROUTER_MAX_PRICE_PROMPT=1.0
OPENROUTER_MAX_PRICE_COMPLETION=2.0
```

---

## 9) Models Recommended for KB Tasks

### For KB Queries (High Accuracy)
| Model | Strengths |
|-------|-----------|
| `anthropic/claude-3.5-sonnet` | Best reasoning, lowest hallucination |
| `google/gemini-1.5-pro` | Long context, multimodal |
| `openai/gpt-4o` | Balanced, fast |

### For Research (Speed + Cost)
| Model | Strengths |
|-------|-----------|
| `anthropic/claude-3.5-sonnet:nitro` | Fast Claude |
| `meta-llama/llama-3.1-70b-instruct:nitro` | Fast open-source |
| `mistralai/mistral-large` | Cost-effective |

### For Embeddings
| Model | Notes |
|-------|-------|
| Use Gemini `text-embedding-004` | Primary |
| OpenRouter doesn't expose embeddings directly | Must use provider API |

---

## 10) Cost Comparison

| Model | Input $/M | Output $/M |
|-------|-----------|------------|
| `google/gemini-1.5-flash` | $0.075 | $0.30 |
| `google/gemini-1.5-pro` | $1.25 | $5.00 |
| `anthropic/claude-3.5-sonnet` | $3.00 | $15.00 |
| `openai/gpt-4o` | $2.50 | $10.00 |
| `meta-llama/llama-3.1-70b:nitro` | $0.52 | $0.75 |

---

## 11) Headers for Attribution

```python
headers = {
    "Authorization": f"Bearer {api_key}",
    "HTTP-Referer": "https://your-app.com",  # For OpenRouter rankings
    "X-Title": "Verified Developer KB Pro",   # App name
}
```

---

## Summary of Extracted Value

1. **300+ models** via single API
2. **Automatic fallbacks** for reliability
3. **Cost optimization** via routing
4. **Privacy controls** (ZDR, data collection)
5. **Exact cost tracking** via generation stats
6. **Quantization filtering** for performance
7. **Provider preferences** for compliance
8. **OpenAI compatibility** for easy integration
9. **Streaming support** for real-time responses
10. **Tool calling** for agentic workflows

