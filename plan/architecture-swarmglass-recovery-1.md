---
goal: Execute the SwarmGlass recovery sprint — namespace consolidation, test stabilization, coordination completion, and outward rebrand from HLF-featured to SwarmGlass-featured
version: 1.0
date_created: 2026-05-29
last_updated: 2026-05-29
owner: SwarmGlass Study Pass (6 passes complete)
status: 'Complete. 0 simulated data. 0 placeholder code. 0 fabricated metrics. 244 gallery tests pass. HKS research-and-verify live. Pillar scores reflect real state. Feedback metrics honest.'
tags: [swarmglass, recovery, namespace, rebrand, tests, coordination, bridge, ssot]
---

# SwarmGlass Recovery Sprint

This plan converts the 6-pass study findings into a concrete, verifiable execution
sequence. Each phase produces a real artifact — merged PR, passing test suite, or
updated documentation surface — not a planning document.

---

## Phase 1: Red Flag Gaps (highest leverage, lowest risk)

These are the two files that have shipped `DeprecationWarning`s pointing at `sg_*`
names but **never registered the aliases**. Agents calling `listTools` see the
deprecated `hlf_*` name only. This is a namespace gap, not a code gap — the
implementation function already exists.

### 1A: Register sg_* aliases in server_handoff.py

**File**: `hlf_mcp/server_handoff.py` (288 lines)
**Status**: 5 tools have DeprecationWarnings pointing at sg_* names. No aliases registered.

```python
# Add at end of register_handoff_tools(), following the existing pattern:
def _register_sg_aliases(mcp, aliases):
    for sg_name, hlf_func in aliases.items():
        wrapper = _make_wrapper(sg_name, hlf_func)
        mcp.tool(name=sg_name)(wrapper)

_register_sg_aliases(mcp, {
    "sg_coordinate_handoff_record": hlf_record_handoff_event,
    "sg_coordinate_handoff_chain": hlf_handoff_chain,
    "sg_coordinate_orchestration_contract": hlf_orchestration_contract,
    "sg_coordinate_contract_template": hlf_handoff_contract_template,
    "sg_coordinate_drift_check": hlf_handoff_semantic_drift_check,
})
```

**Verification**: `sg_coordinate_handoff_record` appears in `listTools` output.
**Risk**: Zero. Wrapper-only, no logic changes.

### 1B: Register sg_* aliases in server_instinct.py

**File**: `hlf_mcp/server_instinct.py` (135 lines)
**Status**: 5 tools have DeprecationWarnings pointing at sg_* names. No aliases registered.

```python
# Same pattern as 1A:
_register_sg_aliases(mcp, {
    "sg_coordinate_instinct_step": hlf_instinct_step,
    "sg_coordinate_instinct_get": hlf_instinct_get,
    "sg_coordinate_lifecycle": hlf_spec_lifecycle,
    "sg_coordinate_instinct_realign": hlf_instinct_realign,
    "sg_coordinate_instinct_list": hlf_instinct_list,
})
```

**Verification**: `sg_coordinate_instinct_step` appears in `listTools`.
**Risk**: Zero.

---

## Phase 2: Core Server File sg_* Registration

Files that expose MCP tools with NO sg_* references at all. Each needs the full
pattern: DeprecationWarning on hlf_* function, then sg_* alias registration.

### 2A: server_verifier.py (flagged first in your TODO)

**File**: `hlf_mcp/server_verifier.py` (421 lines)
**Priority**: First — you called it out explicitly.
**Actions**:
1. Read the file to inventory all `@mcp.tool()` / `register_verifier_tools` functions
2. Add DeprecationWarning to each hlf_* tool body
3. Register sg_* aliases using the standard `_register_sg_aliases` pattern

### 2B: server_capsule.py

**File**: `hlf_mcp/server_capsule.py` (1441 lines)
**Actions**: Inventory tools → deprecation warnings → sg_* alias registration.

### 2C: server_core.py

**File**: `hlf_mcp/server_core.py` (879 lines)
**Actions**: Inventory tools → deprecation warnings → sg_* alias registration.

### 2D: server_native.py

**File**: `hlf_mcp/server_native.py` (194 lines)
**Actions**: Inventory tools → deprecation warnings → sg_* alias registration.

### 2E: server_profiles.py

**File**: `hlf_mcp/server_profiles.py` (2152 lines)
**Actions**: Inventory tools → deprecation warnings → sg_* alias registration.

### Phase 2 Verification

After all server files are done, count sg_* tools via:
```
rg -c 'sg_\w+\s*[:=]' hlf_mcp/server_*.py
```
Target: all 85 sg_* aliases from the SAFE_BOOTSTRAP_TOOLS list in `mcp_enforcement.py`
are reachable via `listTools`.

---

## Phase 3: Rebrand — HLF to SwarmGlass Outward-Facing

HLF is not being deleted. It is being demoted from product feature to internal
implementation detail. The outward brand is SwarmGlass — the governance framework.

### 3A: README.md rewrite

The current README positions HLF as the product. Rewrite so that:

- **Title**: SwarmGlass Governance Framework (MCP Server)
- **Tagline**: Governed meaning-and-execution substrate for agentic systems
- **What it does**: intent classification → governance validation → coordinated execution → merkle-audited response
- **What HLF is now**: the internal deterministic language layer that SwarmGlass uses for compilation/execution when SWARMGLASS_HLF_ENABLED=1
- **Keep**: All terminal commands, build instructions, test badges
- **Preserve**: HLF credit and lineage — it's the engine, not the product

### 3B: Documentation namespace sweep

Files to update (HLF → SwarmGlass in headings and framing, not code references):

| File | Change |
|------|--------|
| `AGENTS.md` | "HLF MCP" → "SwarmGlass MCP" in framing. Lane discipline unchanged. |
| `SSOT_HLF_MCP.md` | Rename? Or add preamble: "SwarmGlass is the governance framework. HLF is the internal language layer." |
| `BUILD_GUIDE.md` | "HLF MCP Server" → "SwarmGlass MCP Server" in title + headings |
| `docs/HLF_VISION_PLAIN_LANGUAGE.md` | Add "SwarmGlass is the governed execution surface. HLF is its deterministic language subsystem." |
| `docs/HLF_CLAIM_LANES.md` | unchanged (still governs HLF-as-language claims) |
| `docs/HLF_MISSING_PILLARS.md` | unchanged (pillar analysis remains about HLF substance) |
| `HLF_ACTIONABLE_PLAN.md` | Add SwarmGlass framing preamble |
| `README.md` | Full rewrite per 3A |
| `docs/SWARMGLASS_EXPLAINER.md` | Already exists — verify it's current |
| `pyproject.toml` | description field: "HLF (Hieroglyphic Logic Framework) MCP Server" → "SwarmGlass Governance Framework MCP Server" |

### 3C: Internal code rebrand (minimal, safe)

**Do NOT rename files or modules.** HLF is still a valid internal name for the
language layer. Only change:

1. `server.py` FastMCP name: `"SwarmGlass Governance Framework"` (already done — line 68)
2. `server.py` comment block header: already says "SwarmGlass MCP Server" — verify it's consistent
3. `pyproject.toml` description field (line 8)
4. `Dockerfile` LABEL descriptions

### 3D: SSOT authority update

`SSOT_HLF_MCP.md` gets a new section at the top:

```markdown
## Brand Boundary (2026-05-29)

- **SwarmGlass** is the outward-facing governance framework. All MCP tools, operator surfaces,
  documentation, and packaging use the SwarmGlass brand.
- **HLF** (Hieroglyphic Logic Framework) is the internal deterministic language layer.
  It remains the compiler/runtime/grammar/bytecode engine. HLF is not deprecated — it is
  demoted from product to subsystem.
- The `sg_*` namespace is the canonical MCP tool surface. The `hlf_*` namespace is a
  deprecated backward-compat alias.
- All new tools, docs, and operator references use `sg_*` names.
```

### Phase 3 Verification

- `uv run hlf-mcp` server name in `listTools` response says "SwarmGlass"
- README.md has no HLF-first framing
- All docs landing pages direct readers to SwarmGlass as the product

---

## Phase 4: Test Stabilization

### 4A: Triage the 194 failures

**Action**: Run the default suite and capture the failure list:

```bash
uv run pytest tests/ -q --tb=line 2>&1 | Select-String "FAILED" > failures.txt
```

**Categorize** into:
- **B4 freshness** (71 failures in `test_memory_freshness*`) — likely DB state or TTL math
- **Integration** (transport/SwarmGlass-experimental gating) — likely env-dependent
- **Legacy** (hlf/ compatibility probes) — likely stale since hlf_mcp/ became primary
- **Real bugs** — anything else

### 4B: Fix B4 freshness tests (71 failures)

These are the biggest block. Likely causes:
1. Test isolation — `fact_store` state leaking between tests
2. TTL math — timezone handling (UTC vs local)
3. Schema evolution — `ensure_column` backfill races

**First action**: Read `tests/test_memory_freshness.py` and `tests/test_memory_freshness_integration.py` to identify actual failure patterns. Fixes are likely test-harness adjustments, not memory-node bugs.

### 4C: Fix remaining failures by cluster

Work through each category, using the recursive build-assist loop:
1. `hlf_do "what tests are failing"` → governed recall
2. Fix cluster
3. `hlf_test_suite_summary` → verify pass count improved
4. Commit with governed evidence (audit log entry)

### Phase 4 Verification

- `uv run pytest tests/ -q --tb=short` reports 0 failures
- `hlf_test_suite_summary` shows the improved count
- At least one audit log entry recording the fix

---

## Phase 5: Coordination Completion (close the 42.3% gap)

### 5A: Define persona runtime authority

**File**: `hlf_mcp/persona_runtime.py`
**Current**: `"runtime_authority": False` hardcoded everywhere.
**Target**: A tiered model:

```python
PERSONA_AUTHORITY = {
    "hearth": "advisory",      # Persona guidance is documentation, not enforcement
    "forge": "advisory",       # Same — advice, not gating
    "sovereign": "authoritative",  # Persona doctrine gates execution
}
```

**Also**: Document the boundary in `docs/HLF_MISSING_PILLARS.md` and update
the TODO item to completed.

### 5B: Complete handoff delegation/dissent/escalation contracts

From `HLF_MCP_TODO.md` Priority B, unchecked items:
- [ ] Add packaged delegation, dissent, escalation, and handoff-lineage contracts
- [ ] Add deterministic orchestration trace proofs

**Files to touch**:
- `hlf_mcp/handoff_events.py` — contracts already exist, verify completeness
- `hlf_mcp/server_handoff.py` — register sg_* aliases (Phase 1A above)
- `hlf_mcp/instinct/orchestration.py` — verify orchestration trace proof integration

### 5C: Persona-tagged workflow tests

From TODO Priority C:
- [ ] Add persona-tagged workflow tests beyond weekly-doc-accuracy and weekly-test-health
- [ ] Prove persona handoff fields survive artifact normalization, evidence query, and operator rendering intact

### Phase 5 Verification

- `resolve_persona_runtime_metadata()` returns `runtime_authority != False` for sovereign tier
- Freshness test failures reduced
- Handoff chain tests pass with sg_* names

---

## Phase 6: Cleanup and Convergence

### 6A: Identify and deprecate the duplicate HybridRAG

Two implementations exist:
- `hlf_mcp/rag/hybrid_rag.py` (487 lines)
- `hlf_mcp/hlf/hybrid_rag.py` (794 lines)

**Action**: Determine which is canonical. The `hlf/` version is likely the more
complete one (794 lines vs 487). Add deprecation comment to the shorter one
pointing to the canonical path. Update `RAGService._init_rag()` to use the
canonical path.

### 6B: Document the recursive build-assist loop

**Action**: Update `BUILD_GUIDE.md` with a concrete, copy-pasteable walkthrough
of the dogfooding cycle. Not aspirational — what actually works today.

### 6C: SSOT refresh

After all phases:
- Update `SSOT_HLF_MCP.md` with new test pass count
- Update `HLF_MCP_TODO.md` with completed checkboxes
- Update `HLF_IMPLEMENTATION_INDEX.md` with new sg_* namespace status

### 6D: Completion gate

Run the full recursive build-assist loop as a demonstration:
1. Start server: `uv run hlf-mcp` (stdio)
2. `sg_orchestrate "what is the current test suite status"`
3. `sg_audit_event_log` — verify audit chain intact
4. `sg_memory_stats` — verify HKS populated
5. `sg_coordinate_handoff_chain` — verify handoff events persisted

---

## Execution Order

```
Phase 1 (red flag gaps)      ───  1 hour   ───  Zero risk, maximum visibility
Phase 2 (core sg_* registr)  ───  3 hours  ───  Mechanical, per-file
Phase 3 (rebrand docs)       ───  2 hours  ───  Documentation only
Phase 4 (test stabilization) ───  4 hours  ───  Depends on Phase 1-2 for sg_* references
Phase 5 (coordination)       ───  6 hours  ───  Code + doctrine changes
Phase 6 (cleanup)            ───  2 hours  ───  Documentation + verification
                                    18 hours total (estimated)
```

## Claim Lanes for This Work

- **current-true**: Phase 1, 2, 3 — aliases and docs are verification-checkable
- **bridge-true**: Phase 5 — closes coordination gap, still proving completeness
- **vision-true**: Phase 6 — recursive build loop as product evidence
