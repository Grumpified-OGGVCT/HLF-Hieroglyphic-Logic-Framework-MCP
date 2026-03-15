# HLF (High Leverage Framework) - Actionable Implementation Plan
## Extracted from Monolithic Research Document

---

## 🎯 CORE INSIGHT

**HLF's intelligence lives in its specs, grammar, and governance mechanisms—not in raw parameter count.**

The smallest local organism that can express full HLF intelligence requires:
- **Deterministic coordination** (spec-first grammar, ALIGN Ledger seals)
- **Structural compression** (glyph/ASCII surfaces reducing token footprint)
- **Governed tool use** (host-function tiers, intent capsules)
- **Swarm-aware self-improvement** (SIA agent, pro/con board)

**None of these require local GPU inference.**

---

## 📋 ACTIONABLE REFINEMENTS (Prioritized)

### ✅ REFINEMENT 1: SQLite WAL for Hot Tier (P0/P1)
**Status**: HIGH PRIORITY - Zero correctness loss

**Problem**: Redis hot tier (~1ms) vs SQLite WAL (~5ms) latency difference

**Solution**: Use SQLite WAL for P0/P1 hot tier with gas tolerance adjustment

**Implementation**:
```python
# File: hlf/infinite_rag.py - __init__() modification
if os.getenv("HLF_PROFILE") in ["P0", "P1"]:
    self.hot_store = SQLiteHotStore(self.db_path)  # Replace Redis
else:
    self.hot_store = RedisHotStore(redis_url)

# File: hlf/intent_capsule.py - adjust tolerance
GAS_TOLERANCE_MS = 50  # From 5ms (was: GAS_TOLERANCE_MS = 5)
```

**New Code Required**:
```python
# File: hlf/stores/sqlite_hot_store.py (NEW FILE)
import sqlite3
import json
import time

class SQLiteHotStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS hot_meta (
                key TEXT PRIMARY KEY,
                value BLOB,
                ts REAL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON hot_meta(ts)")

    def add_meta_intent(self, meta_intent: dict):
        key = f"meta:{meta_intent['source_hash']}:{meta_intent['timestamp']}"
        self.conn.execute(
            "INSERT OR REPLACE INTO hot_meta (key, value, ts) VALUES (?, ?, ?)",
            (key, json.dumps(meta_intent).encode(), time.time())
        )

    def get_recent_meta_intents(self, since: float, limit: int) -> list:
        rows = self.conn.execute(
            "SELECT value FROM hot_meta WHERE ts > ? ORDER BY ts DESC LIMIT ?",
            (since, limit)
        ).fetchall()
        return [json.loads(row[0].decode()) for row in rows]
```

**Verification Command**:
```bash
HLF_PROFILE=P0 uv run pytest tests/conformance/ -x
```

**Expected Result**: All 36 tests pass (or 28/28 for non-realtime tests)

---

### ✅ REFINEMENT 2: Direct Ollama Cloud API Default
**Status**: HIGH PRIORITY - Eliminates local daemon

**Problem**: Local Ollama daemon adds extra hop and failure point

**Solution**: Default to `https://ollama.com/api` direct API

**Implementation**:
```python
# File: agents/core/model_gateway.py - _get_ollama_base_url()
def _get_ollama_base_url(self):
    if os.getenv("HLF_OLLAMA_USE_CLOUD_DIRECT") == "1":
        return "https://ollama.com/api"  # Direct cloud API
    elif os.getenv("OLLAMA_HOST"):
        return os.getenv("OLLAMA_HOST")
    else:
        return "http://localhost:11434"  # Default local
```

**Environment Configuration**:
```bash
# .env file addition
HLF_OLLAMA_USE_CLOUD_DIRECT=1
OLLAMA_API_KEY=your_ollama_cloud_key_here
OLLAMA_BASE_URL=https://ollama.com/api
```

**Test Command**:
```bash
HLF_OLLAMA_USE_CLOUD_DIRECT=1 \
OLLAMA_API_KEY=your_key_here \
uv run python -m agents.core.model_gateway \
  --model "gpt-oss:20b-cloud" \
  --prompt "Say 'HLF cloud works' in 3 words"
```

---

### ✅ REFINEMENT 3: Minimal P0 Host-Function Set (5 Functions)
**Status**: HIGH PRIORITY - Strategic essentialism

**The 5 Essential Functions for P0**:
| Function | Purpose | Gas Cost |
|----------|---------|----------|
| `READ_FILE` | Read file contents | 2 |
| `WRITE_FILE` | Write file contents | 3 |
| `WEB_SEARCH` | Fetch web via Ollama Cloud | 5 |
| `STRUCTURED_OUTPUT` | JSON Schema validation | 4 |
| `SELF_OBSERVE` | SOC hook - meta-intent emission | 1 |

**Implementation**:
```yaml
# File: spec/effects/p0_host_functions.yaml (NEW FILE)
version: "0.5.0"
host_functions:
  - name: READ_FILE
    args: [{"name": "path", "type": "string"}]
    returns: "string"
    tier: ["forge", "sovereign"]
    gas: 2
    backend: "file_system"
    sensitive: false

  - name: WRITE_FILE
    args:
      - {"name": "path", "type": "string"}
      - {"name": "content", "type": "string"}
    returns: "string"
    tier: ["forge", "sovereign"]
    gas: 3
    backend: "file_system"
    sensitive: true

  - name: WEB_SEARCH
    args: [{"name": "query", "type": "string"}]
    returns: "string"
    tier: ["forge", "sovereign"]
    gas: 5
    backend: "ollama_web_search"
    sensitive: false

  - name: STRUCTURED_OUTPUT
    args:
      - {"name": "schema", "type": "object"}
      - {"name": "data", "type": "any"}
    returns: "boolean"
    tier: ["forge", "sovereign"]
    gas: 4
    backend: "json_schema_validator"
    sensitive: false

  - name: SELF_OBSERVE
    args: [{"name": "meta_intent", "type": "object"}]
    returns: "string"
    tier: ["forge", "sovereign"]
    gas: 1
    backend: "infinite_rag_hot_store"
    sensitive: false
```

---

### ✅ REFINEMENT 4: Default Controller Model
**Status**: MEDIUM PRIORITY - Model selection

**Selected Model**: `gpt-oss:20b-cloud`

**Why**:
- ⭐⭐⭐⭐ Reasoning strength (agentic workflows)
- ✅ Native tool calling
- ✅ Native structured outputs
- Low latency (~800ms)
- Cost: $0.0006/1K tokens

**Implementation**:
```python
# File: pyproject.toml or .env
OLLAMA_CONTROLLER_MODEL="gpt-oss:20b-cloud"
```

**Test Structured Output**:
```python
import requests, os, json

response = requests.post(
    'https://ollama.com/api/chat/completions',
    json={
        'model': 'gpt-oss:20b-cloud',
        'messages': [{'role': 'user', 'content': 'Return JSON: {"status":"ok","value":42}'}],
        'format': {'type': 'json_object'},
        'stream': False
    },
    headers={'Authorization': f'Bearer {os.getenv("OLLAMA_API_KEY")}'}
)
print(json.loads(response.json()['message']['content'])['value'])  # Should print 42
```

---

### ✅ REFINEMENT 5: LRU Cache Hot Tier Alternative
**Status**: MEDIUM PRIORITY - For <10ms operations

**Implementation**:
```python
# File: hlf/stores/lru_hot_store.py (NEW FILE)
from collections import OrderedDict

class LRUHotStore:
    def __init__(self, maxsize=1000):
        self.cache = OrderedDict()
        self.maxsize = maxsize

    def add_meta_intent(self, meta_intent: dict):
        key = f"meta:{meta_intent['source_hash']}:{meta_intent['timestamp']}"
        self.cache[key] = meta_intent
        self.cache.move_to_end(key)
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

    def get_recent_meta_intents(self, since: float, limit: int) -> list:
        results = []
        for key, value in reversed(self.cache.items()):
            if value.get('timestamp', 0) > since:
                results.append(value)
            if len(results) >= limit:
                break
        return results
```

**Hybrid Usage**:
```python
# In infinite_rag.py
if os.getenv("HLF_PROFILE") == "P0":
    self.hot_store = LRUHotStore(maxsize=1000)  # <0.1ms latency
elif os.getenv("HLF_PROFILE") == "P1":
    self.hot_store = SQLiteHotStore(self.db_path)  # ~5ms latency
else:
    self.hot_store = RedisHotStore(redis_url)  # <1ms latency
```

---

## 🔧 IMPLEMENTATION CHECKLIST

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `hlf/stores/sqlite_hot_store.py`
- [ ] Create `hlf/stores/lru_hot_store.py`
- [ ] Modify `hlf/infinite_rag.py` for profile-based store selection
- [ ] Update `hlf/intent_capsule.py` gas tolerance
- [ ] Create `spec/effects/p0_host_functions.yaml`
- [ ] Modify `agents/core/model_gateway.py` for direct cloud API

### Phase 2: Integration & Testing (Week 2)
- [ ] Add environment variable configuration
- [ ] Create profile detection utility
- [ ] Update conformance suite tags
- [ ] Test P0 profile (Python + SQLite only)
- [ ] Test P1 profile (Python + SQLite + LRU)
- [ ] Test P2 profile (Full stack)

### Phase 3: Documentation (Week 3)
- [ ] Update SETUP_GUIDE.md with HLF profiles
- [ ] Create P0 quickstart documentation
- [ ] Document host function specifications
- [ ] Create migration guide from P0→P1→P2

---

## 📊 P0/P1/P2 Profile Matrix

| Feature | P0 (Cloud-only Core) | P1 (Cloud Workstation) | P2 (Full Sovereign) |
|---------|----------------------|------------------------|---------------------|
| **Local Footprint** | Python + SQLite | Python + SQLite + LRU | Python + SQLite + Redis |
| **Inference** | Direct Ollama Cloud | Direct Ollama Cloud | Ollama Cloud + Local |
| **Hot Tier** | LRU Cache (<0.1ms) | SQLite WAL (~5ms) | Redis (<1ms) |
| **Host Functions** | 5 essential | 8 extended | 23+ full set |
| **Agents** | None | Selective | Full swarm |
| **Docker** | ❌ No | ❌ No | ✅ Optional |
| **RAM (idle)** | ~50MB | ~60MB | ~200MB |

---

## 🧪 VERIFICATION COMMANDS

### Test P0 Cloud-only Core
```bash
# 1. Setup P0 environment
uv sync --no-extras
export HLF_PROFILE=P0
export HLF_OLLAMA_USE_CLOUD_DIRECT=1
export OLLAMA_API_KEY="your_key_here"

# 2. Run conformance suite (non-realtime tests)
uv run pytest tests/conformance/ -m "not realtime_safety_required" -v
# EXPECTED: 28/28 tests pass

# 3. Test self-observation
uv run hlf.hlfc examples/hello_world.hlf
uv run python -c "
from hlf.infinite_rag import InfiniteRAG
rag = InfiniteRAG()
print('Meta-intents:', len(rag.hot_store.cache if hasattr(rag.hot_store, 'cache') else []))
"
```

### Test Host Functions
```bash
# Test all 5 P0 host functions
uv run python -m agents.core.host_function_dispatcher \
  --function READ_FILE --args '{"path":"/etc/hostname"}' \
  --function WEB_SEARCH --args '{"query":"HLF language"}'
```

---

## 🎯 SUCCESS CRITERIA

✅ **P0 is viable when**:
- 28/28 non-realtime conformance tests pass
- Self-observation hook captures compiler meta-intents
- Host functions work via Ollama Cloud
- Zero local GPU dependencies
- <50MB RAM idle footprint

✅ **P1 is viable when**:
- All P0 criteria met
- SQLite WAL hot tier <10ms latency
- LRU cache for sub-millisecond ops
- Optional local Ollama daemon works

✅ **P2 is viable when**:
- All P1 criteria met
- Full 23+ host function set
- Redis hot tier <1ms latency
- Full agent swarm operational

---

## 📦 NEW DEPENDENCIES TO ADD

### Python Dependencies (add to requirements-upgraded.txt)
```
# For LRU cache hot tier
cachetools>=5.5.0

# For JSON Schema validation (STRUCTURED_OUTPUT host function)
jsonschema>=4.23.0

# For Ollama Cloud direct API
httpx>=0.28.0

# For SQLite WAL optimization
apsw>=3.46.0  # Alternative SQLite wrapper with better WAL support
```

### Node.js Dependencies (add to package.json if needed)
```json
{
  "dependencies": {
    "@ollama/sdk": "^0.1.0"
  }
}
```

---

## 🚀 IMMEDIATE NEXT STEPS

1. **Create the store implementations** (SQLiteHotStore, LRUHotStore)
2. **Modify model_gateway.py** for direct cloud API
3. **Update environment configuration** with new variables
4. **Test P0 profile** with conformance suite
5. **Verify self-observation** captures meta-intents

**Estimated time**: 2-3 days for full implementation

---

## 💡 KEY TAKEAWAY

**HLF's smallest viable organism (P0)**:
- Python runtime
- SQLite database
- Direct Ollama Cloud API
- 5 essential host functions
- LRU cache hot tier
- Zero Docker/Redis/GPU dependencies

**This is not reductionism**—it's strategic essentialism that preserves HLF's core value (spec-first governance, self-improvement, deterministic coordination) while eliminating all non-essential local compute.

The "soul" of HLF lives in its specs and governance—not in its dependencies.
