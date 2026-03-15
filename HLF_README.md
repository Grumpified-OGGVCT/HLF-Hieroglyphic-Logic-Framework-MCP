# HLF Language Framework Integration

This document describes the Hierarchical Language Framework (HLF) integration into Frankenstein MCP.

## Overview

HLF provides a spec-first, self-improving language framework with three profile tiers:

- **P0 (Cloud-only Core)**: Python + SQLite only, direct Ollama Cloud API
- **P1 (Cloud-assisted Workstation)**: P0 + LRU cache hot tier
- **P2 (Full Sovereign Lite)**: P1 + Redis + full host-function set

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HLF Language Framework                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Compiler   │  │  Infinite   │  │  Host Function          │ │
│  │  (hlfc.py)  │  │  RAG        │  │  Dispatcher             │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│         │                │                    │                │
│         ▼                ▼                    ▼                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Three-Tier Storage                      │  │
│  │  Hot: SQLite/LRU Cache  Warm: SQLite  Cold: Parquet      │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Ollama Cloud API (Model Gateway)            │  │
│  │  - gpt-oss:20b-cloud (default controller)                │  │
│  │  - Structured outputs                                    │  │
│  │  - Tool calling                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Set Environment

```bash
# P0 - Cloud-only Core (minimal)
set HLF_PROFILE=P0
set OLLAMA_API_KEY=your_ollama_key_here

# P1 - With LRU cache hot tier
set HLF_PROFILE=P1

# P2 - Full features (future)
set HLF_PROFILE=P2
```

### 2. Verify Installation

```bash
# Run test suite
python hlf/test_suite.py

# Or use npm
npm run hlf:test
```

### 3. Use CLI

```bash
# Switch profile
python hlf/hlf_cli.py --profile P1 --switch

# Validate setup
python hlf/hlf_cli.py --validate

# Run self-observation test
python hlf/hlf_cli.py --observe
```

## Key Components

### 1. Profile Manager (`hlf/__init__.py`)

Manages P0/P1/P2 configurations with automatic detection.

```python
from hlf import ProfileManager, switch_profile

# Auto-detect profile
profile = ProfileManager()

# Explicit profile
profile = ProfileManager("P1")

# Get configuration
print(profile.config.use_redis)  # False for P0
print(profile.config.hot_tier)   # "lru" for P1
```

### 2. SQLite Hot Store (`hlf/sqlite_hot_store.py`)

Replaces Redis for P0/P1 with SQLite WAL mode:

```python
from hlf.sqlite_hot_store import SQLiteHotStore, HybridHotStore

# P0: Pure SQLite
store = SQLiteHotStore()

# P1: LRU + SQLite hybrid
store = HybridHotStore()
```

### 3. Infinite RAG (`hlf/infinite_rag_hlf.py`)

Three-tier memory system:

```python
from hlf.infinite_rag_hlf import InfiniteRAGHLF, Fact

# Initialize
rag = InfiniteRAGHLF(profile="P0")

# Store compiler observation
rag.add_meta_intent({
    "source_hash": "abc123",
    "phase_timings": {"parse": 0.001},
    "gas_used": 100,
    "profile": "P0"
})

# Store knowledge
rag.add_fact(Fact(
    id="rule_1",
    content="HLF requires semicolons",
    source="spec"
))

# Query
intents = rag.get_recent_meta_intents(since=0, limit=10)
```

### 4. Model Gateway (`hlf/model_gateway.py`)

Direct Ollama Cloud API integration:

```python
from hlf.model_gateway import HLFModelGateway

gateway = HLFModelGateway(profile="P0")

# Structured output
result = gateway.generate_structured(
    prompt="Generate test data",
    schema={"type": "object", "properties": {"value": {"type": "integer"}}}
)

# Web search
results = gateway.web_search("HLF language framework")
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HLF_PROFILE` | Profile tier (P0/P1/P2) | Auto-detect |
| `HLF_OLLAMA_USE_CLOUD_DIRECT` | Use direct API | 1 (true) |
| `OLLAMA_API_KEY` | Ollama Cloud API key | None (required) |
| `OLLAMA_CONTROLLER_MODEL` | Default model | gpt-oss:20b-cloud |
| `HLF_RAG_DB_PATH` | RAG database path | ./data/hlf_rag.db |
| `HLF_HOT_TIER_CACHE_SIZE` | LRU cache size | 1000 |

### Profile Configurations

#### P0 (Cloud-only Core)
```python
use_redis: False
use_lru_cache: False
hot_tier: "sqlite"
host_function_set: "minimal"  # 5 functions
local_models: False
```

#### P1 (Cloud-assisted Workstation)
```python
use_redis: False
use_lru_cache: True
hot_tier: "lru"
host_function_set: "extended"  # 15 functions
local_models: False
```

#### P2 (Full Sovereign Lite)
```python
use_redis: True
use_lru_cache: True
hot_tier: "hybrid"
host_function_set: "full"
local_models: True  # Optional
```

## Testing

Run the full test suite:

```bash
python hlf/test_suite.py
```

Expected output:
```
test_basic_operations (__main__.TestLRUCache) ... ok
test_meta_intent_operations (__main__.TestSQLiteHotStore) ... ok
test_fact_lifecycle (__main__.TestInfiniteRAG) ... ok
test_full_workflow_p0 (__main__.TestIntegration) ... ok

----------------------------------------------------------------------
Ran 25+ tests in X.XXXs

OK
```

## Host Functions

### P0 Minimal Set (5 functions)

| Function | Purpose | Gas | Backend |
|----------|---------|-----|---------|
| `READ_FILE` | Read file contents | 2 | file_system |
| `WRITE_FILE` | Write file contents | 3 | file_system |
| `WEB_SEARCH` | Web search via Ollama | 5 | ollama_web_search |
| `STRUCTURED_OUTPUT` | JSON validation | 4 | json_schema |
| `SELF_OBSERVE` | Compiler observation | 1 | infinite_rag |

See `spec/effects/p0_host_functions.yaml` for full specification.

## Performance

### P0 Footprint
- **Memory**: ~50MB idle (Python + SQLite)
- **Startup**: <2 seconds
- **Hot tier latency**: ~5ms (SQLite WAL)
- **Inference latency**: 100-800ms (Ollama Cloud)

### P1 Footprint
- **Memory**: ~60MB idle (+10MB LRU cache)
- **Startup**: <2 seconds
- **Hot tier latency**: ~0.1ms (LRU cache)

## Integration with Frankenstein MCP

### Available Commands

```bash
# Initialize HLF
npm run hlf:init

# Verify setup
npm run hlf:verify

# Use CLI
npm run hlf:cli -- --help

# Run tests
npm run hlf:test

# Profile switching
npm run hlf:profile:p0
npm run hlf:profile:p1
npm run hlf:profile:p2
```

### API Endpoint

Health check at `/api/health` includes HLF status:

```json
{
  "status": "healthy",
  "services": {
    "hlf": {
      "status": "healthy",
      "profile": "P0",
      "features": ["compiler", "rag", "gateway"]
    }
  }
}
```

## Roadmap

### Phase 1: Core (P0) ✅
- [x] Profile manager
- [x] SQLite hot store
- [x] Infinite RAG
- [x] Model gateway (Ollama Cloud)
- [x] Test suite

### Phase 2: Enhanced (P1) ✅
- [x] LRU cache hot tier
- [x] Extended host functions
- [x] Self-observation

### Phase 3: Full (P2) 🚧
- [ ] Redis hot tier
- [ ] Full host-function set
- [ ] Local model support
- [ ] GUI integration

## References

- HLF Specification: `spec/effects/p0_host_functions.yaml`
- Implementation: `hlf/` directory
- Tests: `hlf/test_suite.py`
- CLI: `hlf/hlf_cli.py`
