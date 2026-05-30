# SwarmGlass Usage Guide for Agents

You are an agent that uses SwarmGlass — the universal AI governance layer. You do NOT need to build or modify the toolkit itself. This guide shows you how to load it, use its governance tools, and verify your output.

---

## 1. Quickstart — One Line

SwarmGlass exposes **136 governance tools** as MCP tools. No imports needed. Just call them:

```
Tool: sg_memory_store       → Store a fact with provenance tracking
Tool: sg_audit_event_log    → Record a governed decision  
Tool: sg_coordinate_handoff → Pass work between agents with cryptographic receipts
Tool: sg_overwatch_scan     → Check health of all registered processes
Tool: sg_secure_secret_store → Encrypt and store a secret
```

All tools work with natural language input. The governance layer validates, audits, and constrains automatically.

---

## 2. The Six Governance Pillars

SwarmGlass is organized into six pillars. Every agent workflow touches at least three.

### 🔍 Audit (12 tools) — Cryptographic Proof
Every decision gets Merkle-chained with SHA-256. Tools: `sg_audit_event_log`, `sg_audit_merkle_verify`, `sg_audit_witness_record`, `sg_audit_evidence_show`

### 🤝 Coordinate (9 tools) — Multi-Agent Orchestration
Handoff work between agents with cryptographic receipts. Tools: `sg_coordinate_handoff_chain`, `sg_coordinate_instinct_step`, `sg_coordinate_drift_check`, `sg_coordinate_orchestration_contract`

### 🧠 Memory (17 tools) — Provenance-Tracked Knowledge
Store and retrieve facts with source tracking and hybrid search. Tools: `sg_memory_store`, `sg_memory_query`, `sg_memory_governed_recall`, `sg_memory_dream_run`, `sg_memory_resolve`

### 👁️ Observe + Overwatch (7 tools) — Real-Time Monitoring
Process health, feedback collection, watchdog daemon. Tools: `sg_overwatch_scan`, `sg_overwatch_status`, `sg_overwatch_health`, `sg_observe_feedback_submit`

### 🔒 Secure (3 tools) — Encrypted Secrets
AES-256-GCM encryption at rest. Tools: `sg_secure_secret_store`, `sg_secure_secret_retrieve`, `sg_secure_secret_rotate`

### 📊 Model (1 tool)
`sg_model_version_check` — Verify model compatibility and health.

---

## 3. Core Workflow: NL → Govern → Execute

Every agent interaction follows this pattern:

1. **Classify** — What is the user asking? (read, write, deploy, configure)
2. **Validate** — Does it pass constraint checks? (`sg_coordinate_drift_check`)
3. **Execute** — Perform the action under governance
4. **Audit** — Record the decision (`sg_audit_event_log`)
5. **Store** — Save results with provenance (`sg_memory_store`)
6. **Report** — Return governed result to user

You don't write HLF. You speak natural language. SwarmGlass handles the governance.

---

## 4. Common Agent Workflows

### Store knowledge with provenance
```
sg_memory_store
  content: "Deployed v2.3.1 to production at 14:22 UTC"
  source: "deployment-pipeline"
  tags: ["deployment", "production", "v2.3.1"]
```

### Recall governed knowledge
```
sg_memory_governed_recall
  query: "last production deployment"
  tier: "forge"
```

### Check process health
```
sg_overwatch_scan
  targets: ["ollama", "chromadb", "hlf-mcp"]
```

### Pass work to another agent
```
sg_coordinate_handoff_chain
  task: "Review security scan results"
  to_agent: "security-reviewer"
  evidence: {"scan_id": "abc123"}
```

---

## 5. Quality Checklist

Before completing any agent task:
- □ Intent classified (`sg_coordinate_orchestration_contract`)
- □ Constraints validated (`sg_coordinate_drift_check`)
- □ Decision audited (`sg_audit_event_log`)
- □ Results stored with provenance (`sg_memory_store`)
- □ Handoff tracked if multi-agent (`sg_coordinate_handoff_record`)

---

## 6. Transport Modes

| Mode | Windows | Mac/Linux | When to Use |
|------|---------|-----------|-------------|
| stdio | `run.bat` | `./run.sh` | Local MCP clients (Claude Desktop, Cursor) |
| HTTP | `run.bat http 8123` | `./run.sh http 8123` | Networked MCP, Docker, remote agents |
| SSE | `run.bat sse 8123` | `./run.sh sse 8123` | Legacy MCP clients |

---

## 7. Configuration

On first run, the setup wizard prompts for:
- **SWARMGLASS_MASTER_KEY** — AES-256 encryption key (required for secrets)
- **SWARMGLASS_SESSION_SECRET** — HMAC signing secret
- **SWARMGLASS_API_TOKEN** — HTTP auth bearer token
- **OLLAMA_HOST** — Model server endpoint
- **SWARMGLASS_AGENT_TIER** — Capability boundary (hearth/forge/sovereign)

Run `python setup_wizard.py` anytime to reconfigure.

---

## 8. Key Files (Read-Only)

```
hlf_mcp/
  server.py              # All 136 MCP tool registrations
  server_audit.py        # Audit chain tools (12 sg_audit_*)
  server_coordinate.py   # Coordination tools (9 sg_coordinate_*)
  server_memory.py       # Memory tools (17 sg_memory_*)
  server_overwatch.py    # Overwatch tools (4 sg_overwatch_*)
  server_secure.py       # Secrets tools (3 sg_secure_*)
docs/
  SWARMGLASS_EXPLAINER.md  # Full architecture explainer
  AGENTS_CATALOG.md        # Complete 136-tool catalog
  AGENT_ONBOARDING.md      # Step-by-step onboarding
```

---

**You do not need to modify SwarmGlass source code. You only need to call its tools correctly.**

