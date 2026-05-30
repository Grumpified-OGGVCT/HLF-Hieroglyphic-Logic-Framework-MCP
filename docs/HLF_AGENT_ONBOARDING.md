# SwarmGlass Agent Onboarding

> **Zero to governed in 5 minutes.** This guide gets an agent connected to SwarmGlass and using governance tools immediately.

---

## Step 1: Install

```batch
git clone https://github.com/Grumpified-OGGVCT/SwarmGlass-MCP.git
cd SwarmGlass-MCP
install.bat
```

The installer:
- Creates a Python 3.12+ virtual environment
- Installs all dependencies
- Launches the setup wizard (prompts for critical keys)
- Builds the overwatch Docker container (if Docker is available)
- Verifies the MCP surface (136 tools)

**Done in ~2 minutes online, ~30 seconds if pre-cached.**

---

## Step 2: Configure (One-Time)

The setup wizard runs automatically on first install. It asks for:

| Setting | Required? | What It Does |
|---------|-----------|-------------|
| Master encryption key | Recommended | AES-256 key for secret encryption + Merkle signing |
| Session secret | Recommended | HMAC secret for session tokens |
| HLF_API_TOKEN | For HTTP | Bearer token for HTTP transport auth |
| Ollama host | Default works | Model server endpoint |

Re-run anytime: `python setup_wizard.py`

---

## Step 3: Connect Your MCP Client

### Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "swarmglass": {
      "type": "stdio",
      "command": "C:\\Users\\...\\HLF_MCP\\run.bat",
      "args": ["stdio"]
    }
  }
}
```

### Cursor / VS Code
Use `.mcp.json` (already in the repo):
```json
{
  "mcpServers": {
    "hlf-mcp": {
      "type": "stdio",
      "command": ".\\run.bat",
      "args": ["stdio"]
    }
  }
}
```

### Any HTTP MCP Client
```batch
run.bat http 8123
```
Then connect to `http://localhost:8123/mcp`

---

## Step 4: Verify Connection

Ask your agent:
> "List the SwarmGlass governance tools available to me"

The agent should list 136 tools across six categories.

Or run directly:
```batch
run.bat count
# Output: 136 6 5  (tools, resources, prompts)
```

---

## Step 5: First Governed Interaction

### Store your first memory fact:
> "Store this fact: SwarmGlass onboarding completed at [timestamp]. Source: agent-onboarding."

The agent calls `sg_memory_store` with provenance tracking.

### Verify it was stored:
> "Recall my most recent memory facts"

The agent calls `sg_memory_query` or `sg_memory_governed_recall`.

### Check the audit trail:
> "Show me the audit log for the last 5 events"

The agent calls `sg_audit_event_log_get`.

---

## Step 6: Enable Overwatch (Optional)

Overwatch monitors your running services and auto-recovers them.

```batch
run.bat overwatch
```

This starts the overwatch daemon (Docker if available, in-process otherwise). It:
- Scans registered targets every 30 seconds
- Alerts on CPU/memory/disk threshold breaches
- Auto-recovers dead processes (up to 3 restarts)

Verify:
> "Scan overwatch targets and report status"

---

## Common Agent Tasks

| Task | Tool | Example |
|------|------|---------|
| Store knowledge | `sg_memory_store` | "Store: deployment v2.3.1 completed" |
| Query memory | `sg_memory_query` | "Find all deployment records from this week" |
| Log decision | `sg_audit_event_log` | "Log: approved config change #42" |
| Verify integrity | `sg_audit_merkle_verify` | "Verify the last 100 audit events" |
| Pass work | `sg_coordinate_handoff_chain` | "Hand off security review to agent-7" |
| Check health | `sg_overwatch_scan` | "Scan all registered targets" |
| Store secret | `sg_secure_secret_store` | "Store: API key for production DB" |
| Find patterns | `sg_memory_dream_run` | "Find related facts about deployment failures" |

---

## Tier Levels

SwarmGlass has three capability tiers. Set `SWARMGLASS_AGENT_TIER` in `.env`:

| Tier | Access | Use Case |
|------|--------|----------|
| `hearth` | Read-only governance tools | Public-facing agents, untrusted contexts |
| `forge` | Read + write, constrained execution | Standard agent operations |
| `sovereign` | Full access, all tools | Admin agents, deployment pipelines |

Default: `sovereign` for local installs, `hearth` for HTTP transports.

---

## Troubleshooting

### "No .env found" on first run
The setup wizard runs automatically. If it fails: `python setup_wizard.py --quick`

### "136 tools not showing up"
Verify installation: `run.bat test` — all 274 tests should pass.

### "Overwatch daemon won't start"
Docker not required — it falls back to in-process mode. Check: `run.bat overwatch`

### "Master key warning"
For development, this is fine. For production, generate one: `python setup_wizard.py`

---

## Enterprise Tools

Beyond the core governance surface, SwarmGlass includes enterprise hardening tools for production deployments. These are registered as MCP tools and gated by agent tier (hearth/forge/sovereign). All 274 tests pass.

### Evidence (Commit 4)
Latent evidence capsules with provenance trails and Merkle chain integrity verification.
- `hlf_evidence_show` — Show a latent evidence capsule with provenance trail
- `hlf_evidence_list` — List recent latent evidence capsules
- `hlf_evidence_verify` — Verify a capsule's Merkle chain integrity

### Merkle Disaster Recovery (Commit 6)
Signed backup archives with HMAC-SHA256 and Merkle root verification. Requires `HLF_MASTER_KEY`.
- `hlf_merkle_export` — Export Merkle chain backups with HMAC signatures
- `hlf_merkle_verify` — Verify and restore from a Merkle backup archive
- `hlf_merkle_chain_status` — List all Merkle chains and current root hashes

### Secret Management (Commit 5)
AES-256-GCM encrypted secrets at rest. Plaintext never appears in logs or audit trails.
- `hlf_secret_store` — Store an encrypted secret
- `hlf_secret_retrieve` — Retrieve and decrypt a stored secret
- `hlf_secret_rotate` — Rotate encryption for a secret

### A/B Testing (Commit 8b)
Compare Ollama backend models on domain-specific corpora with statistical comparisons (Cohen's d, Wilson CI, p-value).
- `hlf_ab_test_define` — Define a new A/B test configuration
- `hlf_ab_test_run` — Run a defined A/B test against Ollama backends
- `hlf_ab_test_show` — Get formatted A/B test results
- `hlf_ab_test_list` — List all defined A/B test configurations

### Load Testing (Commit 7)
Simulate concurrent capsule processing with configurable backpressure and gas scheduling.
- `hlf_load_test_run` — Run a capsule load test
- `hlf_load_test_status` — Get load test queue status and capabilities

### HITL Gate (Commit 1)
Human-in-the-Loop approval gate for gated capsules. Operator identity is recorded in the audit trail.
- `hlf_hitl_approve` — Approve a HITL-gated capsule for merge
- `hlf_hitl_reject` — Reject a HITL-gated capsule with a reason
- `hlf_hitl_list` — List HITL-gated capsules by status

### Chaos Engineering (Commit 2)
OOM resilience, VRAM cleanup, and graceful degradation validation.
- `hlf_chaos_status` — Report chaos engineering readiness status

### Model Version Pinning (Commit 3)
Verify installed Ollama model digests against capability manifest declarations.
- `hlf_model_version_check` — Verify model versions against manifest declarations

## Next Steps

- Read the full architecture: `docs/SWARMGLASS_EXPLAINER.md`
- Browse all 136 tools: `docs/AGENTS_CATALOG.md`
- See agent usage patterns: `docs/AGENT_USAGE_GUIDE.md`
- Enable experimental DSL (193 tools): set `SWARMGLASS_HLF_ENABLED=1` in `.env`
