# HLF Usage Guide for Non-Building Agents

You are an agent that uses HLF — you do NOT need to build or modify the HLF toolkit itself. This guide shows you how to load it, speak it, and verify your output.

---

## 1. Load HLF (One Line)

```python
from hlf_mcp.hlf.translator import language_to_hlf
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.pillar_auditor import PillarComplianceAuditor
```

No build steps. No config files. Just import and use.

---

## 2. Speak HLF: NLP → HLF → NLP

**Your job:** Receive user intent in natural language, process it through HLF, respond in natural language.

```python
# Step 1: Translate user intent to HLF
hlf = language_to_hlf("Analyze /security/seccomp.json for vulnerabilities")
# → produces structured HLF with Δ [INTENT], Ж [CONSTRAINT], etc.

# Step 2: Validate before delivery
compiler = HLFCompiler()
result = compiler.compile_with_recovery(hlf)
assert result["success"], f"HLF compile failed: {result}"

# Step 3: Audit pillar compliance
auditor = PillarComplianceAuditor()
audit = auditor.audit(hlf)
assert audit.compliant, f"Missing pillars: {audit.findings}"

# Step 4: Respond to user in natural language
# (HLF artifacts only shown if user explicitly requests them)
```

---

## 3. The 4 Pillars You MUST Check

Every HLF message you produce or receive must have:

| Pillar | Tag | Why It Matters |
|--------|-----|----------------|
| **Core** | `INTENT` | Every message declares its purpose |
| **Verify** | `ASSERT`, `EXPECT`, or `RESULT` | Commitments are verifiable |
| **Governance** | `VOTE`, `CONSTRAINT` | Multi-agent coordination is governed |
| **Delegation** | `DELEGATE`, `ROUTE` | Work handoffs are explicit |

**Quick check:**
```python
audit = PillarComplianceAuditor().audit(hlf_source)
print(f"Score: {audit.overall_score:.2f}")
print(f"Findings: {audit.findings}")
```

---

## 4. Use the Swarm (Multi-Agent)

```python
from hlf_mcp.hlf.swarm_orchestrator import SwarmOrchestrator
from hlf_mcp.hlf.swarm_observer import SwarmObserver

observer = SwarmObserver()
swarm = SwarmOrchestrator(observer=observer)

# Run a task through 3 agents
result = swarm.run_3_agent_stack(task, translator_fn)

# Check real-time progress
for phase in result.phases:
    print(f"{phase.role}: {phase.status} ({phase.metrics.get('time_ms', 0):.2f}ms)")
```

---

## 5. Available MCP Tools (What You Can Call)

| Tool | What It Does |
|------|-------------|
| `hlf_translate_to_hlf` | Convert natural language → HLF |
| `hlf_translate_to_english` | Convert HLF → natural language |
| `hlf_compile` | Compile and validate HLF source |
| `hlf_native_speak` | Validate your output before delivery |
| `hlf_validate_output` | Self-check your HLF for completeness |
| `hlf_pillar_audit` | Check pillar compliance of any HLF message |
| `hlf_pillar_audit_conversation` | Audit a full agent conversation |
| `hlf_cross_agent_consistency` | Compare how different agents handle the same task |
| `hlf_self_improvement_swarm` | Run a swarm on an HLF improvement task |
| `hlf_self_improvement_suite` | Run ALL improvement tasks and report |
| `hlf_swarm_progress` | Query real-time swarm phase status |
| `hlf_workflow_benchmark` | Benchmark a single task |
| `hlf_repair` | Auto-repair broken HLF syntax |
| `hlf_governance_event_log` | View audit trail |

---

## 6. Quality Checklist (Before Every Response)

```
□ HLF compiles successfully
□ INTENT tag is present
□ At least one verify pillar (ASSERT/EXPECT/RESULT)
□ No unknown tags
□ Pillar score >= 0.80
□ If delegating: DELEGATE or ROUTE tag present
```

---

## 7. Directory Map (Read-Only for You)

```
hlf_mcp/
  hlf/
    translator.py       # NLP ↔ HLF conversion
    compiler.py         # HLF compilation + recovery
    pillar_auditor.py   # Compliance checking
    swarm_orchestrator.py # Multi-agent coordination
    swarm_observer.py   # Real-time progress
    grammar.py          # Tag and glyph definitions
  server.py             # All MCP tool registrations
  server_swarm.py       # Swarm + compliance tools
  server_native.py      # Native speak + validation
  server_workflow_benchmark.py  # Benchmark tools
tests/                  # 1080 tests you can read
```

---

## 8. Self-Improvement Tasks (What the Swarm Works On)

The swarm does NOT run random tasks. It improves HLF itself:

- `add_tag_spec` — Add new HLF tags and grammar rules
- `improve_translator` — Fix translator accuracy
- `generate_test_cases` — Create edge-case tests
- `improve_corrector` — Enhance self-healing parser
- `optimize_gas_model` — Improve execution cost estimates
- `expand_benchmark_corpus` — Add new benchmark domains

Each task produces an actual artifact (code change, test file, config update).

---

## 9. Example: Complete Agent Turn

```python
from hlf_mcp.hlf.translator import language_to_hlf
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.pillar_auditor import PillarComplianceAuditor

# 1. User asks something
user_input = "Deploy the app with auto routing and strict consensus"

# 2. Translate to HLF
hlf = language_to_hlf(user_input)

# 3. Compile
result = HLFCompiler().compile_with_recovery(hlf)
if not result["success"]:
    hlf = HLFCorrector().repair(hlf).repaired_source

# 4. Audit pillars
audit = PillarComplianceAuditor().audit(hlf)
if not audit.compliant:
    # Add missing pillars before responding
    pass

# 5. Respond to user (NLP)
# HLF stays internal unless user asks to see it
```

---

**You do not need to modify HLF source code. You only need to use it correctly.**
