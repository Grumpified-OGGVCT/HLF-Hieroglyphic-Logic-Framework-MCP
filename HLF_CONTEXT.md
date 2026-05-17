# HLF Context — Agent Injection Prefix

> Load this before any agent touches HLF code, writes HLF, or modifies HLF infrastructure. Prevents blind-coding regressions.

---

## 1. What HLF Is

HLF (Hieroglyphic Logic Framework) is a **governed language and coordination substrate** for turning natural-language intent into auditable, cryptographically-evidenced machine action.

It is NOT:
- A pretty syntax wrapper around tool calls
- A config format
- A prompt template system

It IS:
- A real compiler with 5-pass pipeline (NFKC norm → LALR(1) parse → SET env → $VAR expansion → ALIGN ledger validate)
- A bytecode VM with gas metering
- A knowledge substrate (HKS) with Merkle-chained memory, cosine dedup, and compounding recall
- A governance spine (ALIGN ledger, intent capsules at hearth/forge/sovereign tiers)
- An MCP server (FastMCP, stdio/SSE/streamable-http transports)

The README explicitly says: **"the MCP server is the right front door, the right current product lane, and the right bootstrap surface for HLF now, while the larger HLF vision remains bigger than MCP in semantics, governance, memory, coordination, trust, and execution."**

---

## 2. Architecture (How Things Fit Together)

```
Agent Intent (NLP)
    │
    ▼
Translator (language_to_hlf / LLM bridge)
    │
    ▼
Compiler (5-pass → AST)
    │
    ├──▶ Bytecode VM (gas-metered execution)
    ├──▶ HKS Memory (store exemplar → query recall → compound)
    ├──▶ Governance (ALIGN ledger, capsule admission)
    └──▶ Audit (evidence traces, operator review)
```

**HKS Compounding Loop** (the core hypothesis):
1. Intent arrives → query HKS for similar past translations (few-shot recall)
2. LLM bridge translates intent → HLF (with few-shot examples)
3. Compiler validates output
4. Successful translation stored as validated exemplar in HKS
5. Next intent gets better few-shot → quality compounds

**Key subsystems:**
| Subsystem | File | Purpose |
|-----------|------|---------|
| Grammar | `hlf_mcp/hlf/grammar.py` | LALR(1) grammar, glyph defs, tags, ASCII aliases |
| Compiler | `hlf_mcp/hlf/compiler.py` | 5-pass compile pipeline |
| Translator | `hlf_mcp/hlf/translator.py` | NLP↔HLF (keyword heuristic fallback) |
| LLM Bridge | `hlf_mcp/hlf/hlf_llm_bridge.py` | Ollama API → HLF generation |
| HKS Memory | `hlf_mcp/rag/memory.py` | Store/exemplar/query/recall |
| MCP Server | `hlf_mcp/server.py` | FastMCP tool surface |
| Translation MCP | `hlf_mcp/server_translation.py` | MCP-facing translation tools + system prompt |
| Benchmark | `hlf_mcp/hlf/benchmark.py` | Benchmark data and runners |
| Compounding BM | `compounding_benchmark.py` | 3-cycle HKS compounding test |

---

## 3. Grammar — CRITICAL (Most Agents Get This Wrong)

**Source of truth**: `hlf_mcp/hlf/grammar.py` line 38-221 (Lark LALR(1) grammar).

### Two Valid HLF Forms

**Form 1: Flat Glyph Statements** (no MODULE/GOAL keywords)
```
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
Ω
```
- Each line is a `glyph_stmt`: `GLYPH tag? arg_list?`
- Glyph: one of `Δ Ж ⨝ ⌘ ∇ ⩕ ⊎ ⌂ Σ`
- Tag: `[TAG_NAME]` — UPPERCASE, underscores, digits. **NO HYPHENS.**
- Args: `key="value"` (kv_arg) or positional (pos_arg)
- Continuation lines indented with 2 spaces under parent glyph
- Ω (Omega) on its own line terminates the program
- **DO NOT use `MODULE`, `GOAL`, or `FUNCTION` as keywords** — these are only valid with `{ }` blocks

**Form 2: Block Form** (MODULE/FUNCTION/INTENT with curly braces)
```
[HLF-v3]
MODULE main {
  Δ [INTENT] goal="hello_world"
    Ж [ASSERT] status="ok"
}
Ω
```
- `module_block_stmt: KW_MODULE IDENT arg_list? block`
- `func_block_stmt: KW_FUNCTION IDENT param_list? block`
- `intent_stmt: KW_INTENT IDENT arg_list? block`
- block = `LBRACE statement* RBRACE`
- **MODULE/FUNCTION/INTENT MUST be followed by `{ }`** — no exceptions

### Glyph → Semantic Mapping
| Glyph | Name | Role | ASCII Alias |
|-------|------|------|-------------|
| Δ | DELTA | analyze / primary action | ANALYZE |
| Ж | ZHE | enforce / constrain / assert | ENFORCE, CONSTRAIN |
| ⨝ | JOIN | consensus / join / vote | JOIN, CONSENSUS, VOTE |
| ⌘ | COMMAND | command / delegate / route | CMD, COMMAND |
| ∇ | NABLA | source / parameter / data flow | SOURCE |
| ⩕ | BOWTIE | priority / weight / rank | PRIORITY |
| ⊎ | UNION | branch / condition / fork | BRANCH, UNION |
| ⌂ | HOUSE | memory anchor / recall provenance | MEMORY_ANCHOR |
| Σ | SIGMA | summary / aggregate / capsule surface | SUMMARY, SUMMARIZE, AGGREGATE |

### Tag Name Rules (TAG_NAME)
- Regex: `/[A-Z][A-Z0-9_]*/`
- MUST start with uppercase letter
- Underscores and digits OK
- **HYPHENS FORBIDDEN** — `AUDIT-TRAIL` becomes `TAG_NAME` + `MINUS` + `IDENT`, which fails parse
- Valid: `INTENT`, `ASSERT`, `ACTION`, `CONSTRAINT`, `DEPLOY`, `EXTRACT`, `VALIDATE`, `AUDIT_TRAIL`

### Keywords (21 total)
`ASSIGN`, `SET`, `IF`, `ELIF`, `ELSE`, `FOR`, `IN`, `PARALLEL`, `MODULE`, `FUNCTION`, `INTENT`, `TOOL`, `CALL`, `RESULT`, `RETURN`, `LOG`, `IMPORT`, `MEMORY`, `RECALL`, `SPEC_DEFINE`, `SPEC_GATE`, `SPEC_UPDATE`, `SPEC_SEAL`, `AND`, `OR`, `NOT`

### Canonical Tags
`INTENT`, `CAPSULE`, `THOUGHT`, `OBSERVATION`, `PLAN`, `CONSTRAINT`, `ASSERT`, `EXPECT`, `ACTION`, `DELEGATE`, `ROUTE`, `SOURCE`, `PARAM`, `PRIORITY`, `VOTE`, `RESULT`, `SET`, `MODULE`, `IMPORT`, `FUNCTION`, `CODE`, `DATA`, `MEMORY`, `RECALL`, `PROVENANCE`, `GOVERNANCE`, `RELATE`, `GATE`, `DEFINE`, `CALL`, `WHILE`, `TRY`, `CATCH`, `RETURN`, `MIGRATION`, `MIGRATION_SPEC`, `ALIGN`, `SPEC`, `SPEC_DEFINE`, `SPEC_GATE`, `SPEC_UPDATE`, `SPEC_SEAL`

---

## 4. Valid Examples (Copy These Patterns)

### Simple Intent (from `test_compiler.py`)
```hlf
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
Ω
```

### Security Audit (from `test_compiler.py`)
```hlf
[HLF-v3]
Δ analyze /security/seccomp.json
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] vulnerability_shorthand
  ⨝ [VOTE] consensus="strict"
Ω
```

### Delegation (from `test_compiler.py`)
```hlf
[HLF-v3]
⌘ [DELEGATE] agent="scribe" goal="fractal_summarize"
  ∇ [SOURCE] /data/raw_logs/matrix_sync_2026.txt
  ⩕ [PRIORITY] level="high"
  Ж [ASSERT] vram_limit="8GB"
Ω
```

### Multi-Step Pipeline (LLM-translated pattern)
```hlf
[HLF-v3]
⌘ [GOAL] objective="deploy platform update"
Δ [MIGRATE] target="database"
Δ [DEPLOY] target="API gateway"
Δ [DEPLOY] target="worker services"
Δ [SMOKE] test="smoke tests"
Ж [ASSERT] condition="all tests pass"
Σ [RESULT] output="deployment complete"
Ω
```

### With SET Variable (from `test_compiler.py`)
```hlf
[HLF-v3]
SET model_name = "llama3.2"
Δ [INTENT] model="llama3.2"
Ω
```

### With Spec Lifecycle (from `test_compiler.py`)
```hlf
[HLF-v3]
SPEC_DEFINE [MIGRATION] version="1.0" idempotent=true
Δ [INTENT] goal="migrate"
SPEC_GATE [MIGRATION] rollback_on_fail=true
Ω
```

### Module Block Form (from gallery)
```hlf
[HLF-v3]
MODULE main {
  Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
}
Ω
```

---

## 5. Common Anti-Patterns (DO NOT DO)

### ❌ MODULE without braces
```hlf
# WRONG — parser sees MODULE, expects {, gets Δ → "Expected LBRACE"
[HLF-v3]
MODULE main
Δ action="deploy"
Ω
```
**Fix**: Either remove `MODULE main` (use flat glyph form) OR add `{ }` block.

### ❌ GOAL as keyword
```hlf
# WRONG — GOAL is not a keyword, parser sees IDENT then glyph
[HLF-v3]
GOAL Deploy
Δ action="deploy"
Ω
```
**Fix**: Use `⌘ [GOAL] objective="Deploy"` instead.

### ❌ Hyphens in tags
```hlf
# WRONG — [AUDIT-TRAIL] becomes TAG_NAME + MINUS + IDENT
Δ [AUDIT-TRAIL] check="compliance"
```
**Fix**: Use `[AUDIT_TRAIL]` with underscore.

### ❌ Wrapping everything in one INTENT glyph
```hlf
# WRONG — collapses all semantic detail into one blob
[HLF-v3]
Δ [INTENT] goal="deploy platform: 1) migrate DB 2) deploy API 3) deploy workers 4) smoke test 5) switch traffic"
Ω
```
**Fix**: Decompose into one glyph per step.

### ❌ Omitting Ω terminator
```hlf
# WRONG — parser expects Ω at end
[HLF-v3]
Δ [INTENT] goal="test"
```
**Fix**: Always end with `Ω` on its own line.

### ❌ Storing uncompilable exemplars in HKS
```python
# WRONG — garbage in, garbage out compounding
memory.store_exemplar(exemplar)  # without compile check
```
**Fix**: Only store after `compiler.compile(hlf_source)` succeeds.

### ❌ Using kimi-k2.6:cloud for HLF generation
```python
# WRONG — kimi-k2.6 returns empty responses via Ollama /api/generate
bridge = HLFLLMBridge(model="kimi-k2.6:cloud")
```
**Fix**: Use `deepseek-v4-pro:cloud` or local models. The default model in `hlf_llm_bridge.py` is `kimi-k2.6:cloud` — override it.

---

## 6. HKS (Hieroglyphic Knowledge Substrate)

HKS is the memory system that enables compounding improvement.

**Store path:**
```python
from hlf_mcp.rag.memory import HKSValidatedExemplar, HKSProvenance, HKSTestEvidence

exemplar = HKSValidatedExemplar(
    problem="original NLP intent",
    validated_solution="compiled HLF output",
    domain="devops",  # must be valid domain
    solution_kind="translation",
    provenance=HKSProvenance(source_type="benchmark", source="...", collector="...", collected_at="..."),
    tests=[HKSTestEvidence(name="compile_check", passed=True, exit_code=0, counts={"passed": 1})],
    tags=["intent_id", "cycle_1"],
    evaluation={"authority": "local_hks", "groundedness": 1.0, ...},
)
memory.store_exemplar(exemplar)
```

**Recall path:**
```python
recall = memory.query(intent_text[:300], entry_kind="hks_exemplar", domain="devops")
memory_hits = recall.get("results", [])
# hits have .get("content"), .get("similarity"), .get("confidence")
```

**Valid domains**: `ai-engineering`, `backend`, `data-engineering`, `devops`, `frontend`, `general-coding`, `hlf-specific`, `infrastructure`, `security` — unknown domains accepted but flagged.

**Storage backend**: SQLite WAL `fact_store` + Merkle Chain Writer + cosine dedup at 0.98 threshold.

---

## 7. LLM Bridge Details

**File**: `hlf_mcp/hlf/hlf_llm_bridge.py`

**API**: `bridge.send(prompt, *, role, system, model, session) → LLMCallResult`

**LLMCallResult fields**: `hlf_output`, `raw_response`, `model_used`, `prompt_tokens`, `completion_tokens`, `latency_s`, `compile_success`, `compile_error`, `extracted`

**HLF extraction** (`_extract_hlf()`): tries (1) code block with `[HLF-v3]` marker → (2) any code block → (3) inline `[HLF-v3]...Ω` → (4) fallback marker.

**Ollama**: `OLLAMA_HOST=http://localhost:11434` (connect URL, not bind address). Embedding models: `nomic-embed-text-v2-moe` (768-dim), `qwen3-embedding:0.6b`, `qwen3-embedding:4b`. Uses `"prompt"` key for embeddings (not `"input"`).

**Recommended models for HLF**: `deepseek-v4-pro:cloud` (works, ~9s latency) or local `qwen3.5:9b` / `deepcoder:latest`. Avoid `kimi-k2.6:cloud` (empty responses).

---

## 8. Translator Pipeline

**File**: `hlf_mcp/hlf/translator.py`

`language_to_hlf(text, language="en")` → HLF source string (keyword heuristic fallback)
`translation_diagnostics(hlf_source)` → diagnostic metrics

The translator is a keyword-matching heuristic. For real semantic translation, use the LLM bridge path via `translate_intent()` in `compounding_benchmark.py` or the `_build_hlf_translator_system_prompt()` in `server_translation.py`.

---

## 9. System Prompts (When Writing LLM Prompts for HLF)

All three locations must teach the same correct grammar:

1. **`hlf_llm_bridge.py::_hlf_system_prompt()`** — base system prompt
2. **`server_translation.py::_build_hlf_translator_system_prompt()`** — MCP tool prompt
3. **`compounding_benchmark.py::translate_intent()`** — benchmark prompt

**Required prompt elements:**
- Start with `[HLF-v3]`, end with `Ω` on its own line
- Use glyphs (Δ Ж ⨝ ⌘ ∇ ⩕ ⊎ ⌂ Σ) with `[TAG]` and `key="value"` args
- Tags: UPPERCASE, underscores, NO hyphens
- DO NOT use MODULE, FUNCTION, GOAL as keywords (unless with `{ }` blocks)
- Decompose into multiple glyphs (one per action/step)
- Output ONLY a code block

---

## 10. Key Files Quick Reference

| File | What It Contains |
|------|-----------------|
| `hlf_mcp/hlf/grammar.py` | **Authoritative grammar** (Lark LALR(1)), glyph defs, tags, ASCII aliases, confusables |
| `hlf_mcp/hlf/compiler.py` | 5-pass compiler pipeline |
| `hlf_mcp/hlf/translator.py` | NLP↔HLF bidirectional translator (keyword heuristic) |
| `hlf_mcp/hlf/hlf_llm_bridge.py` | Ollama LLM bridge for HLF generation |
| `hlf_mcp/hlf/benchmark.py` | Benchmark data (_COMPLEX_WORKFLOW_NLP/HLF, _SWARM_WORKFLOW_NLP/HLF) |
| `hlf_mcp/rag/memory.py` | HKS memory store, exemplar, query, Merkle chain |
| `hlf_mcp/server_translation.py` | MCP translation tools, system prompt builder |
| `hlf_mcp/server.py` | FastMCP server entry point |
| `tests/test_compiler.py` | Valid HLF example fixtures (HELLO_WORLD, SECURITY_AUDIT, DELEGATION, etc.) |
| `compounding_benchmark.py` | 3-cycle HKS compounding benchmark |
| `hlf_source/hlf_programs/` | Gallery of 6 compilable HLF programs |
| `README.md` | Full vision, architecture, grammar reference |
| `SSOT_HLF_MCP.md` | Strict current-truth single source of truth |
| `BUILD_GUIDE.md` | Build, test, and server commands |
| `plan/architecture-hlf-reconstruction-2.md` | Master reconstruction sequencing |

---

## 11. Running Tests

```bash
# All tests
cd C:\Users\gerry\generic_workspace\HLF_MCP
$env:OLLAMA_HOST = 'http://localhost:11434'
python -m pytest tests/ -x -q

# Just compiler tests
python -m pytest tests/test_compiler.py -x -q

# Compounding benchmark
python compounding_benchmark.py

# Test all intents through LLM bridge
python _test_all_intents.py
```

---

## 12. Current State (as of 2026-05)

- **78/79 tests pass** (1 pre-existing capsule pointer trust failure)
- **HLF-v3 grammar**: implemented, LALR(1), 21 statement types
- **Compiler**: 5-pass pipeline operational
- **HKS memory**: store/recall/compound loop verified (0→25 memory hits in 3 cycles)
- **LLM bridge**: working with deepseek-v4-pro:cloud, 8/8 intents compile
- **Quality baseline**: 0.626 (up from 0.369 after grammar fix)
- **Token compression**: negative (HLF is larger than NLP for short intents — expected, compression value is semantic precision, not byte count)
- **Next**: seed HKS with hand-curated exemplars, add error-correction feedback loop, wire complex workflow benchmarks into benchmark.py
