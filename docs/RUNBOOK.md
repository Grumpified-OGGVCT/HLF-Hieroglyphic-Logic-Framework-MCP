# HLF Operator Runbook

> **If you're reading this at 3 AM, the system is down.**  
> Stay calm. Follow the section that matches your symptoms. Commands are copy-paste ready.
>
> Every command assumes you're in the repository root (`HLF_MCP/`).
> Use the virtual environment: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux).

---

## Table of Contents

1. [Disaster Recovery (3 AM Scenario)](#1-disaster-recovery-3-am-scenario)
2. [Secret Rotation](#2-secret-rotation)
3. [HITL Gate Operations](#3-hitl-gate-operations)
4. [Model Version Incidents](#4-model-version-incidents)
5. [Merkle Chain Integrity Breach](#5-merkle-chain-integrity-breach)
6. [Performance Degradation](#6-performance-degradation)
7. [A/B Test Promotion](#7-ab-test-promotion)
8. [Auth & Tier Incidents](#8-auth--tier-incidents)
9. [Health Check & Monitoring](#9-health-check--monitoring)
10. [Emergency Contacts / Escalation](#10-emergency-contacts--escalation)

---

## 1. Disaster Recovery (3 AM Scenario)

### Symptom

The database is gone. The observability JSONL files are corrupted, deleted, or unreachable. Inference capsules are failing with "chain not found" errors.

### Before You Begin

The Merkle DR system requires the `HLF_MASTER_KEY` environment variable. Verify it's set:

```powershell
$env:HLF_MASTER_KEY
```

If this returns empty, find the master key in your secret manager and set it:

```powershell
$env:HLF_MASTER_KEY = "<your-master-key>"
```

### Step 1: Check What's Available

List current chain status to understand the scope of the damage:

```powershell
python -m hlf_mcp.scripts.hlf_backup verify
```

Or from the MCP tool (if the server is running):

```
GET /health
```

### Step 2: Verify Backup Integrity

Verify the latest backup archive before attempting restore. This checks:
- Manifest HMAC-SHA256 signature
- Per-chain file signatures
- Merkle root consistency for each chain
- Combined Merkle root across all chains

```powershell
python -m hlf_mcp.scripts.hlf_backup verify --backup-dir observability\merkle_backups\latest
```

Expected output on success:

```
[OK] Backup verified — 2 chains intact
     Combined Merkle root: abc123def456...
```

### Step 3: Restore from Backup

If verification passes, restore the chain files:

```powershell
# Always dry-run first
python -m hlf_mcp.scripts.hlf_backup restore --backup-dir observability\merkle_backups\latest --dry-run

# If dry-run looks correct, do the real restore
python -m hlf_mcp.scripts.hlf_backup restore --backup-dir observability\merkle_backups\latest
```

Expected output:

```
[OK] Restored 2 chains to observability\openllmetry
       latent_traces.jsonl
       hlf_mcp.audit.jsonl
     Merkle root: abc123def456...
```

### Step 4: Verify Chain Integrity After Restore

After restore, verify each restored chain's Merkle root matches:

```powershell
python -m hlf_mcp.scripts.hlf_evidence verify --capsule-id <any-recent-capsule-id>
```

You can list available capsules first:

```powershell
python -m hlf_mcp.scripts.hlf_evidence list
```

Then verify one:

```powershell
python -m hlf_mcp.scripts.hlf_evidence verify --capsule-id <capsule-id>
```

Expected output:

```
[OK] Merkle chain integrity verified for <capsule-id>
  Depth: 47 hashes
  Root: abc123def456789...
  Attestations: 12 handoffs
```

### Backup Storage Locations

| Path | Purpose |
|------|---------|
| `observability/openllmetry/` | **Source** — live JSONL chain files (what you're restoring) |
| `observability/merkle_backups/latest/` | **Default backup** — signed archive |
| `observability/merkle_backups/latest/manifest.json` | Signed manifest with Merkle roots |
| `observability/merkle_backups/latest/chains/` | Per-chain JSONL copies |
| `observability/merkle_backups/latest/signatures/` | HMAC-SHA256 signatures per file |

### What If Backup Signature Verification Fails?

If `hlf-backup verify` returns `[FAIL]` errors:

1. **Manifest signature invalid**: The backup may have been tampered with or `HLF_MASTER_KEY` is wrong. Try a different backup directory (rotate backups are stored by timestamp):

   ```powershell
   dir observability\merkle_backups\
   ```

2. **Chain file signature invalid**: An individual chain file is corrupted. Try restoring only the intact chains:

   ```powershell
   python -m hlf_mcp.scripts.hlf_backup verify --backup-dir observability\merkle_backups\<older-backup>
   ```

3. **All backups fail**: You need to rebuild from the last known good state. Locate the most recent `manifest.json` that passes verification in any backup subdirectory. If none exist, escalate to the engineering team (see [Section 10](#10-emergency-contacts--escalation)).

4. **HLF_MASTER_KEY is lost**: Without the master key, signatures cannot be verified and secrets cannot be decrypted. This is a **SEV1 incident** — escalate immediately.

### Creating a Fresh Backup (for ongoing protection)

```powershell
python -m hlf_mcp.scripts.hlf_backup export
```

To back up specific chains only:

```powershell
python -m hlf_mcp.scripts.hlf_backup export --chains latent_traces.jsonl hlf_mcp.audit.jsonl
```

---

## 2. Secret Rotation

### When to Rotate

- `HLF_MASTER_KEY` has been exposed or is suspected compromised
- Scheduled rotation (per your security policy)
- After a personnel change with access to the key

### How HLF Secret Encryption Works

Secrets are stored as AES-256-GCM ciphertexts. Each secret has:
- A unique **salt** (32 bytes) used for PBKDF2 key derivation
- A unique **nonce** (12 bytes) for AES-GCM
- The derived key comes from `HLF_MASTER_KEY` via PBKDF2-HMAC-SHA256 (600,000 iterations)

The ciphertext is what's persisted. The plaintext is never written to disk or logs.

### Rotating HLF_MASTER_KEY Without Losing Secrets

**Critical**: If you change `HLF_MASTER_KEY` without re-encrypting, all existing secrets become permanently unreadable.

The correct rotation procedure:

#### Step 1: With the OLD key still set, decrypt and re-encrypt each secret

```powershell
# Set the old key
$env:HLF_MASTER_KEY = "<old-key>"

# For each secret, rotate encryption (re-encrypt with fresh salt/nonce)
python -c "
from hlf_mcp.hlf.secret_capsule import SecretCapsule, SecretNotFoundError
capsule = SecretCapsule()
# List all known secrets from your inventory
for name in ['db_password', 'api_key']:
    try:
        old_hash = capsule.get_hash(name)
        value = capsule.decrypt(name)
        new_hash = capsule.add(name, value)
        print(f'{name}: {old_hash[:16]}... -> {new_hash[:16]}...')
    except SecretNotFoundError:
        print(f'{name}: NOT FOUND')
"
```

#### Step 2: Export secrets to a temporary secure store (if available)

If you have many secrets, use the MCP tools:

```
MCP tool: hlf_secret_retrieve --key <name>   # get plaintext
MCP tool: hlf_secret_rotate --key <name>     # re-encrypt with current key
```

#### Step 3: Switch to the new key, re-store

```powershell
$env:HLF_MASTER_KEY = "<new-key>"

# Re-store each secret with the new key. The old ciphertext is now unreadable.
python -c "
from hlf_mcp.hlf.secret_capsule import SecretCapsule
capsule = SecretCapsule()
capsule.add('db_password', '<plaintext-value>')
capsule.add('api_key', '<plaintext-value>')
# Verify
print(capsule.decrypt('db_password'))
"
```

### What Happens to In-Flight Capsules During Rotation

- **Capsules already merged**: Unaffected. Their secrets were encrypted with the old key at merge time.
- **Capsules in HITL pending**: They reference the old ciphertext hash. After rotation, the hash changes. You must re-submit any pending capsule that carries secrets.
- **Live inference capsules**: If they hold a `SecretCapsule` instance in memory, that instance still has the old key in-memory and can decrypt until the process restarts.

### Emergency: Old Key Lost, Need Secrets

If the old `HLF_MASTER_KEY` is lost and secrets were only encrypted with it:

1. The ciphertexts cannot be decrypted — AES-256-GCM with PBKDF2 at 600K iterations is not brute-forceable.
2. Restore secrets from an external secret manager (Vault, AWS Secrets Manager, etc.).
3. If no external copy exists, this is a **SEV1** incident.

---

## 3. HITL Gate Operations

### Architecture

The HITL (Human-in-the-Loop) gate is a file-based approval queue. Pending requests are JSON files in:

```
state\pending_approvals\<capsule_id>.json
```

The operator CLI reads and writes these files. There is no server process required for HITL operations.

### Listing Pending Approvals

```powershell
python -m hlf_mcp.scripts.hlf_operator list
```

Example output:

```
CAPSULE ID                               STATUS                    AGENT                CREATED
---------------------------------------------------------------------------------------------------------
cap_abc123def456                         AWAITING_HUMAN_APPROVAL   med-agent           2026-06-15T03:12:00
cap_xyz789abc012                         AWAITING_HUMAN_APPROVAL   code-agent          2026-06-15T03:14:00
```

### Checking a Specific Capsule's Status

```powershell
python -m hlf_mcp.scripts.hlf_operator status --capsule-id cap_abc123def456
```

Example output:

```
Capsule: cap_abc123def456
Status:  AWAITING_HUMAN_APPROVAL
Agent:   med-agent (sovereign)
Intent:  Generate differential diagnosis for chest pain presentation
Gas:     350/500
Output:  Based on the presented symptoms of acute chest pain radiating...
Created: 2026-06-15T03:12:00+00:00
Timeout: 600s
```

### Approving a Capsule

```powershell
python -m hlf_mcp.scripts.hlf_operator approve --capsule-id cap_abc123def456 --operator-id "your.name"
```

Expected output:

```
[OK] Capsule cap_abc123def456 APPROVED
   Status: COMPLETED
   Approved by: your.name
   Approved at: 2026-06-15T03:16:30+00:00
   Output hash: abc123def4567890...
```

### Rejecting a Capsule

```powershell
python -m hlf_mcp.scripts.hlf_operator reject --capsule-id cap_abc123def456 --reason "Output contains PHI in plaintext" --operator-id "your.name"
```

Expected output:

```
[REJECTED] Capsule cap_abc123def456 REJECTED
   Reason: Output contains PHI in plaintext
   Rejected by: your.name
   Rejected at: 2026-06-15T03:17:00+00:00
```

### Timeout Behavior

The default timeout is **600 seconds (10 minutes)**. After timeout, the capsule transitions to `REJECTED_TIMEOUT` automatically when `check-timeouts` runs.

To check for and process timed-out approvals:

```powershell
python -m hlf_mcp.scripts.hlf_operator check-timeouts
```

Example output:

```
[TIMEOUT] 2 approval(s) timed out:
   cap_old001 -- Timed out after 600s
   cap_old002 -- Timed out after 600s
```

**Run `check-timeouts` as a cron job** every 5 minutes:

```
*/5 * * * * cd /path/to/HLF_MCP && python -m hlf_mcp.scripts.hlf_operator check-timeouts
```

### What If the Pending Queue Grows Unbounded

If `hlf-operator list` shows more than ~50 pending items:

1. **Check if the HITL gate daemon has stopped running.** If nothing is calling `check-timeouts`, timed-out requests accumulate indefinitely.
2. **Mass-reject stale requests.** The approval files are just JSON on disk — you can script bulk rejection:

   ```powershell
   Get-ChildItem state\pending_approvals\*.json | ForEach-Object {
       $data = Get-Content $_.FullName | ConvertFrom-Json
       if ($data.status -eq 'AWAITING_HUMAN_APPROVAL') {
           $created = [datetime]$data.created_at
           if (((Get-Date).ToUniversalTime() - $created).TotalSeconds -gt 600) {
               python -m hlf_mcp.scripts.hlf_operator reject --capsule-id $data.capsule_id --reason "Bulk cleanup: exceeded timeout" --operator-id "automation"
           }
       }
   }
   ```

3. **Investigate root cause**: Are agents submitting too many governed capsules? Check `HLF_AGENT_TIER` settings — maybe a rogue hearth agent is generating sovereign-tier capsules.
4. **If the queue is genuinely legitimate**, add more operators or increase automation thresholds. The queue itself is bounded only by disk space.

---

## 4. Model Version Incidents

### Symptom

Inference fails with:

```
CapsuleViolation: Model version verification FAILED:
  llama3.2:latest: Digest mismatch: expected abc123..., got def456...
```

Or:

```
CapsuleViolation: Model version verification FAILED:
  medgemma:4b: NOT FOUND (expected abc123...)
```

### What Happens When a Model Digest Doesn't Match

HLF verifies every declared model's SHA-256 digest against the live Ollama model before inference. If the digest doesn't match:

1. The capsule is **aborted** with a `CapsuleViolation`
2. No inference runs — the system fails closed
3. The mismatch is logged with both expected and actual digests

Common causes:
- Ollama auto-updated a model (newer quantization or weights)
- A model was pulled with a different tag variant
- The model file was tampered with or corrupted
- The capability manifest has a stale digest

### How to Update Pinned Versions

#### Option A: Scan and Update from Live Models

1. List currently running Ollama models and their digests:

   ```powershell
   curl http://localhost:11434/api/tags | python -m json.tool
   ```

   Or use `ollama list`:

   ```powershell
   ollama list
   ```

2. Get the exact SHA-256 digest for a model:

   ```powershell
   curl http://localhost:11434/api/show -d '{"name": "llama3.2:latest"}' | python -m json.tool
   ```

   Look for the `digest` field in the response.

3. Update the capability manifest (`capability_manifest.json` or the equivalent in your deployment) with the new digest.

#### Option B: Re-Pin from a Known Good State

If you have a manifest with known-good digests, re-pull the exact model version:

```powershell
ollama pull llama3.2:latest
```

Then verify:

```powershell
python -c "
from hlf_mcp.hlf.model_version import verify_model_versions
from hlf_mcp.hlf.capability_manifest import CapabilityManifest
manifest = CapabilityManifest(program_id='check')
manifest.model_versions = {'llama3.2:latest': '<expected-sha256>'}
results = verify_model_versions(manifest, live_models={'llama3.2:latest': '<actual-sha256>'})
for r in results:
    print(f'{r.model_name}: match={r.match}')
"
```

### How to Temporarily Bypass Pinning (and Why You Shouldn't)

**You should not bypass model pinning in production.** It exists to prevent exactly the class of incident where a silently-updated model produces different (potentially worse) outputs.

If you absolutely must bypass (e.g., emergency failover while the correct model downloads):

1. Remove the model from the capability manifest's `model_versions` dict. Models not declared in the manifest are **not verified** and run with a warning log.
2. **Set a 30-minute timer.** After 30 minutes, the correct model must be restored and pinned.
3. Log the bypass as an incident with justification.

Bypass detection: The system logs a warning when model verification is skipped due to missing manifest entries.

---

## 5. Merkle Chain Integrity Breach

### Symptoms of Chain Corruption

- `hlf-evidence verify` returns `[TAMPER ALERT]` or `[FAIL]`
- Trace entries have malformed hashes (not 64 hex characters)
- Provenance hashes in attestations don't appear in the Merkle chain
- `hlf_merkle_chain_status` returns a root hash that doesn't match the expected value from the last backup manifest

### How to Identify the Corrupted Entry

The `hlf-evidence verify` command pinpoints the exact handoff where the break occurred:

```powershell
python -m hlf_mcp.scripts.hlf_evidence verify --capsule-id <capsule-id>
```

If tamper is detected:

```
[TAMPER ALERT] Handoff #7 provenance hash abc123... not found in Merkle chain. Chain integrity may be broken.
[FAIL] Tampered provenance detected for <capsule-id>
  Attestation hashes missing from Merkle chain
```

This tells you exactly which handoff (#7) is the problem. Cross-reference with:

```powershell
python -m hlf_mcp.scripts.hlf_evidence show --capsule-id <capsule-id> --latent
```

This renders the full latent handoff trail so you can see which agent handoff produced the discrepancy.

### Recovery Procedure

#### If a single trace is corrupted

1. Identify the corrupted capsule ID
2. Remove the corrupted entry from the JSONL file:

   ```powershell
   # Find the line with the corrupted capsule
   python -c "
   import json
   with open('observability/openllmetry/latent_traces.jsonl', 'r') as f:
       for i, line in enumerate(f, 1):
           if '<capsule-id>' in line:
               print(f'Line {i}: corrupted')
   "
   ```

3. Remove that specific line (manually, or with a script that filters it out).
4. Re-verify the chain:

   ```powershell
   python -m hlf_mcp.scripts.hlf_evidence verify --capsule-id <next-capsule-id>
   ```

#### If the entire chain is corrupted (multiple entries)

Restore from backup (see [Section 1](#1-disaster-recovery-3-am-scenario)):

```powershell
python -m hlf_mcp.scripts.hlf_backup restore --backup-dir observability\merkle_backups\latest
```

#### If the backup is also corrupted

1. Check for older rotating backups:

   ```powershell
   Get-ChildItem observability\merkle_backups\ -Directory | Sort-Object Name -Descending
   ```

2. Try each backup with `verify` until you find an intact one:

   ```powershell
   python -m hlf_mcp.scripts.hlf_backup verify --backup-dir observability\merkle_backups\<backup-name>
   ```

3. Restore from the oldest intact backup. You will lose entries created after that backup — those capsules will need re-execution.

---

## 6. Performance Degradation

### Symptoms

- Capsule wait times exceeding 30 seconds
- Increasing rejection rate (capsules hitting `max_queue_depth`)
- Agents reporting timeouts on tool calls
- System feels "slow" under normal load

### Run a Load Test

```powershell
python -c "
from hlf_mcp.hlf.load_tester import CapsuleQueueConfig, run_load_test

config = CapsuleQueueConfig(
    max_concurrent=3,
    max_queue_depth=100,
    gas_per_round=25,
)

completed, metrics = run_load_test(capsule_count=50, config=config, max_rounds=200)
s = metrics.summary()
print(f'Submitted:  {s[\"submitted\"]}')
print(f'Completed:  {s[\"completed\"]}')
print(f'Rejected:   {s[\"rejected\"]}  (backpressure)')
print(f'Aborted:    {s[\"aborted\"]}   (timeouts)')
print(f'Peak Queue: {s[\"peak_queue_depth\"]}')
print(f'Peak Conc:  {s[\"peak_concurrent\"]}')
print(f'Avg Wait:   {s[\"avg_wait_time_ms\"]:.0f} ms')
print(f'Max Wait:   {s[\"max_wait_time_ms\"]:.0f} ms')
print(f'Chains OK:  {s[\"chains_verified\"]}')
print(f'Chains BAD: {s[\"chains_broken\"]}')
"
```

### Interpreting Load Test Metrics

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| **Rejection rate** | 0% | 1-5% | >5% |
| **Avg wait time** | <500ms | 500-2000ms | >2000ms |
| **Max wait time** | <2000ms | 2000-5000ms | >5000ms |
| **Peak concurrent** | ≤ `max_concurrent` | = `max_concurrent` | = `max_concurrent` (saturated) |
| **Chains broken** | 0 | 0 | >0 (integrity issue!) |
| **Aborted (timeouts)** | 0 | <5% | >5% |

### When to Adjust max_concurrent or max_depth

#### Increase `max_concurrent` if:
- Wait times are high but CPU/GPU utilization is low
- The system has spare VRAM and compute headroom
- `peak_concurrent` is consistently at the cap

Increase in steps of 1-2 and re-test:

```powershell
python -c "
from hlf_mcp.hlf.load_tester import CapsuleQueueConfig, run_load_test
config = CapsuleQueueConfig(max_concurrent=5, max_queue_depth=100)  # was 3
completed, metrics = run_load_test(capsule_count=50, config=config)
print(metrics.summary())
"
```

#### Decrease `max_concurrent` if:
- Chains are breaking under contention
- OOM/VRAM errors appear in logs
- Aborted capsules increase with higher concurrency

#### Increase `max_queue_depth` if:
- Rejection rate is high but system has memory headroom
- You need more buffering during traffic spikes

#### Decrease `max_queue_depth` if:
- Memory usage is climbing during sustained load
- You want faster fail-fast behavior under overload

### Production Tuning Command (via MCP)

If the MCP server is running:

```
MCP tool: hlf_load_test_run
  config: {"capsule_count": 100, "max_concurrent": 5, "max_queue_depth": 200}
```

The response includes `throughput_capsules_per_sec` — use this as your baseline for capacity planning.

---

## 7. A/B Test Promotion

### Running an A/B Test

#### Step 1: Define the test

```powershell
python -m hlf_mcp.scripts.hlf_ab_test define --name medical_dx_v1 --domain medical --backends "medgemma:4b,llama3.2:latest"
```

Expected output:

```
Test 'medical_dx_v1' defined:
  Domain: medical
  Backends: medgemma:4b, llama3.2:latest
  Config saved to: C:\Users\<user>\.hlf\ab_tests\medical_dx_v1.json
```

Available domains: `medical`, `code`, `math`, `general`.

#### Step 2: Run the test

Requires Ollama running at `http://localhost:11434`:

```powershell
python -m hlf_mcp.scripts.hlf_ab_test run --test-name medical_dx_v1 --prompts 10
```

Example output:

```
Running A/B test 'medical_dx_v1'...
  Domain: medical
  Backends: medgemma:4b, llama3.2:latest
  Prompts: 10

Benchmark complete in 45.3s
Results saved to: C:\Users\<user>\.hlf\ab_tests\medical_dx_v1_results.json

  medgemma:4b vs llama3.2:latest (medical):
    medgemma:4b: 0.700
    llama3.2:latest: 0.800
    Winner: llama3.2:latest (p=0.0234, d=0.650)
```

#### Step 3: Review results

```powershell
python -m hlf_mcp.scripts.hlf_ab_test show --test-name medical_dx_v1
```

Example output:

```
Test: medical_dx_v1
Backends: medgemma:4b, llama3.2:latest
Prompts: 10

Comparisons:
  medgemma:4b vs llama3.2:latest (medical domain)
    medgemma:4b: 0.70 ± 0.15 (95% CI)
    llama3.2:latest: 0.80 ± 0.13 (95% CI)
    Difference: +0.100
    Cohen's d: 0.650 (medium)
    p-value: 0.0234
    Winner: llama3.2:latest ✓
    Recommendation: PROMOTE llama3.2:latest for medical domain: 8/10 correct vs 7/10 (p=0.023, d=0.65 [medium]), 95% CI: [0.02, 0.35]
```

### What Constitutes Statistical Significance

The framework uses **three criteria** in combination:

| Criterion | Threshold | Meaning |
|-----------|-----------|---------|
| **p-value** | < 0.05 | Probability the observed difference is due to chance (paired t-test on keyword match ratios) |
| **Cohen's d** | \|d\| > 0.2 (small), > 0.5 (medium), > 0.8 (large) | Effect size — how large the difference is in practical terms |
| **Confidence interval** | 95% CI does not cross zero | Difference is directionally reliable |

A winner is declared when **both** `p < 0.05` **and** `|diff_mean| > 0.05`.

A result is a **tie** when statistical significance is not reached. The recommendation will suggest retaining the current backend or choosing based on cost/latency.

### Promoting a Winning Backend

When you have a statistically significant winner:

1. **Review the effect size**: A "small" effect (d < 0.5) with marginal significance may not warrant a production change.
2. **Consider latency**: The benchmark includes per-response latency. If the winner is correct but 2x slower, factor that in.
3. **Update the routing configuration** to prefer the winning backend for the domain:

   ```
   MCP tool: hlf_ab_test_show --test-name medical_dx_v1
   ```

   Review the `recommendation` field. If it says `PROMOTE`, update the HKS exemplar or routing config.

4. **Run a canary**: Deploy the promotion to a subset of traffic first. Monitor for 24 hours before full rollout.

### Rejecting a Promotion

If the tests show no significant difference or the "winner" has practical issues:

- **No action needed** — the system continues using the current backend
- Document the test results and re-test after model updates
- If a previously promoted backend regresses, re-run the A/B test to confirm and roll back

---

## 8. Auth & Tier Incidents

### Architecture

HLF uses a single static bearer token (`HLF_API_TOKEN`) for HTTP transports. Three agent tiers control tool visibility:

| Tier | Access Level | Set Via |
|------|-------------|---------|
| `hearth` | Read-only audit, benchmark queries, status checks | `HLF_AGENT_TIER=hearth` |
| `forge` | Medium operations: load tests, Merkle export, secret retrieve | `HLF_AGENT_TIER=forge` |
| `sovereign` | Full access: secrets management, HITL approval/rejection | Default (stdio) or `HLF_AGENT_TIER=sovereign` |

### Symptom: Agent Gets 401

```
HTTP 401 Unauthorized
{"error": "Unauthorized", "detail": "Valid HLF_API_TOKEN required"}
```

**Cause**: The agent is not sending the correct `Authorization` header.

**Fix**:

1. Verify the server has `HLF_API_TOKEN` set:

   ```powershell
   $env:HLF_API_TOKEN
   ```

2. Have the agent send the header:

   ```
   Authorization: Bearer <token-value>
   ```

   Or as a raw token (the server accepts both):

   ```
   Authorization: <token-value>
   ```

3. If `HLF_API_TOKEN` is NOT set on the server, auth is **disabled** and no token is required. The warning log at startup confirms this:

   ```
   WARNING - HLF_API_TOKEN not set — MCP server running without authentication.
   ```

### Symptom: Agent Gets 403

There is no explicit 403 in the current auth system. If an agent can authenticate but cannot see a tool, the tool simply won't appear in `listTools`. This is **tier gating**.

### How to Verify Tier Visibility

Check what tier an agent is running at:

```powershell
$env:HLF_AGENT_TIER
```

If empty, the agent defaults to `sovereign` (full access) on stdio, or `sovereign` on HTTP unless explicitly set.

Verify which tools are visible to a specific tier by checking `ENTERPRISE_TOOL_TIERS` in `hlf_mcp/server_enterprise.py`.

### How to Rotate the Bearer Token

1. Generate a new token (any cryptographically random string):

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Update the server environment:

   ```powershell
   $env:HLF_API_TOKEN = "<new-token>"
   ```

3. **Restart the MCP server** for the change to take effect. Auth middleware is installed at startup.

4. Distribute the new token to all authorized agents.

5. **Verify**: Send a request with the old token — it should return 401. Send with the new token — it should succeed.

### Important Security Notes

- **This is a single static bearer token.** It gates access, not identity.
- Suitable for single-tenant deployments and CI pipelines.
- **NOT suitable** for multi-tenant production — layer an external auth proxy (OAuth, mTLS) in front.
- The `/health` endpoint is **always unauthenticated** — it bypasses auth middleware regardless of `HLF_API_TOKEN`.
- `stdio` transport is always exempt from authentication.

---

## 9. Health Check & Monitoring

### Health Endpoint

```
GET /health
```

This endpoint returns 200 when the server is reachable. It bypasses authentication — no bearer token needed.

```powershell
curl http://localhost:8000/health
```

### What Metrics to Monitor

| Metric | Source | Healthy Range | Alert If |
|--------|--------|---------------|----------|
| **Server reachable** | `GET /health` | 200 OK | Non-200 or timeout |
| **Pending HITL approvals** | `hlf-operator list` | <10 | >50 |
| **Timed-out approvals** | `hlf-operator check-timeouts` | 0 | >5 per check |
| **Load test rejection rate** | `hlf_load_test_run` response | 0% | >5% |
| **Chains broken** | `hlf_merkle_chain_status` | 0 | >0 |
| **Model version mismatches** | `hlf_model_version_check` | 0 mismatches | Any mismatch |
| **Backup age** | `manifest.json` timestamp | <24 hours | >7 days |
| **Disk usage (pending_approvals/)** | `dir state\pending_approvals\` | <100 files | >1000 files |
| **Ollama reachable** | `curl http://localhost:11434/api/tags` | 200 OK | Non-200 |

### Log File Locations

| Log | Path |
|-----|------|
| **Server runtime logs** | `dev.log` (development), `state/` (production) |
| **Observability traces** | `observability/openllmetry/latent_traces.jsonl` |
| **Audit trail** | `observability/openllmetry/hlf_mcp.audit.jsonl` |
| **Pending approvals** | `state/pending_approvals/*.json` |
| **Merkle backup latest** | `observability/merkle_backups/latest/` |
| **HITL gate state** | `state/pending_approvals/` |
| **A/B test configs** | `~/.hlf/ab_tests/*.json` |
| **A/B test results** | `~/.hlf/ab_tests/*_results.json` |

### Quick Health Check Script

```powershell
# Run this to get a 30-second system overview
Write-Host "=== HLF Health Check ===" -ForegroundColor Cyan

# 1. Server health
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
    Write-Host "[OK] Server reachable" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Server not reachable" -ForegroundColor Red
}

# 2. Ollama health
try {
    $ollama = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5
    Write-Host "[OK] Ollama reachable" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Ollama not reachable" -ForegroundColor Red
}

# 3. Pending approvals
$pendingDir = "state\pending_approvals"
if (Test-Path $pendingDir) {
    $pendingCount = (Get-ChildItem $pendingDir -Filter "*.json" | Where-Object {
        $data = Get-Content $_.FullName | ConvertFrom-Json
        $data.status -eq "AWAITING_HUMAN_APPROVAL"
    }).Count
    if ($pendingCount -gt 50) {
        Write-Host "[WARN] $pendingCount pending approvals" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] $pendingCount pending approvals" -ForegroundColor Green
    }
}

# 4. Chain integrity
python -m hlf_mcp.scripts.hlf_evidence list 2>&1 | Select-Object -Last 1

# 5. Backup age
$manifest = "observability\merkle_backups\latest\manifest.json"
if (Test-Path $manifest) {
    $lastWrite = (Get-Item $manifest).LastWriteTime
    $age = (Get-Date) - $lastWrite
    if ($age.TotalHours -gt 24) {
        Write-Host "[WARN] Last backup: $($age.TotalHours.ToString('0.0')) hours ago" -ForegroundColor Yellow
    } else {
        Write-Host "[OK] Last backup: $($age.TotalHours.ToString('0.0')) hours ago" -ForegroundColor Green
    }
}

Write-Host "=== Health Check Complete ===" -ForegroundColor Cyan
```

---

## 10. Emergency Contacts / Escalation

> **This section is a placeholder. Fill in your team's contact information.**

### Severity Levels

| Level | Definition | Response Time |
|-------|-----------|---------------|
| **SEV1** | System down, data loss, security breach | Immediate — wake someone up |
| **SEV2** | Degraded service, high error rate | Within 30 minutes |
| **SEV3** | Non-critical issue, single component | Within 4 hours |

### Escalation Path

| Role | Name | Phone | Email | Notes |
|------|------|-------|-------|-------|
| **Primary on-call** | [Name] | [Phone] | [Email] | First responder |
| **Secondary on-call** | [Name] | [Phone] | [Email] | Escalation if primary unavailable |
| **HLF platform lead** | [Name] | [Phone] | [Email] | Architecture decisions |
| **Security lead** | [Name] | [Phone] | [Email] | Key compromise, auth incidents |
| **Infrastructure lead** | [Name] | [Phone] | [Email] | Host/network/Ollama issues |
| **Engineering manager** | [Name] | [Phone] | [Email] | Business impact decisions |

### External Dependencies

| Service | Status Page | Support Contact |
|---------|------------|-----------------|
| **Ollama** | [ollama status/support URL] | [Contact] |
| **Host/Cloud Provider** | [Provider status page] | [Contact] |

### What to Include in an Incident Report

When escalating, provide:

1. **Capsule ID(s)** affected
2. **Exact error message** (copy-paste, don't paraphrase)
3. **What you've already tried** (commands run, their output)
4. **Backup status**: When was the last good backup? Does `hlf-backup verify` pass?
5. **HLF_MASTER_KEY status**: Is the key available? Has it changed recently?
6. **Recent changes**: Any deploys, config changes, or model pulls in the last 24 hours?

---

## Appendix A: Environment Variables Reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `HLF_MASTER_KEY` | Yes (for DR, secrets) | Master key for HMAC signing and AES-256-GCM secret encryption |
| `HLF_API_TOKEN` | Optional | Bearer token for HTTP transport authentication |
| `HLF_AGENT_TIER` | Optional | Agent tier override: `hearth`, `forge`, `sovereign` (default: `sovereign`) |
| `HLF_STATE_DIR` | Optional | Override the state directory (default: `state/`) |

## Appendix B: CLI Tools Quick Reference

| CLI Tool | Module Path | Purpose |
|----------|------------|---------|
| `hlf-backup` | `hlf_mcp.scripts.hlf_backup` | Merkle disaster recovery (export, verify, restore) |
| `hlf-operator` | `hlf_mcp.scripts.hlf_operator` | HITL gate (approve, reject, list, status, check-timeouts) |
| `hlf-evidence` | `hlf_mcp.scripts.hlf_evidence` | Latent evidence rendering (show, list, verify) |
| `hlf-ab-test` | `hlf_mcp.scripts.hlf_ab_test` | A/B backend benchmarking (define, run, show) |

All CLI tools support `--help` for full usage details:

```powershell
python -m hlf_mcp.scripts.hlf_backup --help
python -m hlf_mcp.scripts.hlf_operator --help
python -m hlf_mcp.scripts.hlf_evidence --help
python -m hlf_mcp.scripts.hlf_ab_test --help
```

## Appendix C: Common Recovery Patterns

### "Everything is broken and I don't know where to start"

1. `curl http://localhost:8000/health` — is the server alive?
2. `curl http://localhost:11434/api/tags` — is Ollama alive?
3. `python -m hlf_mcp.scripts.hlf_operator list` — is the HITL queue backing up?
4. `python -m hlf_mcp.scripts.hlf_backup verify` — is the backup intact?
5. Check `dev.log` for the most recent ERROR lines.

### "I need to restart the server"

```powershell
# Stop the running process (find it first)
Get-Process -Name python | Where-Object { $_.CommandLine -like "*hlf_mcp*" } | Stop-Process

# Start again
.venv\Scripts\activate
python -m hlf_mcp
```

### "I need to clear the HITL backlog immediately"

```powershell
# Reject all approvals older than 10 minutes
python -m hlf_mcp.scripts.hlf_operator check-timeouts

# If that doesn't catch them all, list and bulk reject:
python -m hlf_mcp.scripts.hlf_operator list
# Then manually reject each one
```
