# HLF Supportive Source Context Map

Purpose: capture high-value source surfaces from the broader Sovereign system that materially support HLF reconstruction even when they do not carry HLF in the filename.

Status: reconstruction input, not yet a merge plan.

## Selection Rule

These files were selected because they contribute one or more of the following:

- governance enforcement
- routing and model selection logic
- persona and operator doctrine
- orchestration lifecycle
- memory and provenance infrastructure
- ecosystem integration surfaces
- anti-reductionist constraints and review discipline

The reconstruction rule is: supportive architecture is constitutive if removing it narrows HLF from governed agent language into a mere syntax/compiler fragment.

## High-Value Recovery Clusters

### 1. Governance Spine

Classification: strong but not yet packaged

Why it matters:

- These files define the non-optional control plane around HLF execution.
- They show that HLF is not just parsed syntax; it is routed, constrained, audited, and privilege-bounded.

Candidate files:

- `hlf_source/governance/ALIGN_LEDGER.yaml`
- `hlf_source/agents/gateway/sentinel_gate.py`
- `hlf_source/governance/host_functions.json`
- `hlf_source/governance/hls.yaml`
- `hlf_source/governance/module_import_rules.yaml`
- `hlf_source/governance/openclaw_strategies.yaml`

Recovery notes:

- `ALIGN_LEDGER.yaml` plus `sentinel_gate.py` are the clearest evidence that governance is part of execution semantics, not external policy garnish.
- `host_functions.json` shows HLF as a typed capability/effect bridge across tiers.
- `hls.yaml` is a machine-readable grammar authority that helps preserve exact language scope during reconstruction.

### 2. Gateway and Routing Fabric

Classification: strong but not yet packaged

Why it matters:

- These files embody how intent moves through validation, gas accounting, nonce protection, routing, and dispatch.
- They preserve the claim that HLF is a governed coordination layer rather than a static DSL.

Candidate files:

- `hlf_source/agents/gateway/bus.py`
- `hlf_source/agents/gateway/router.py`
- `hlf_source/agents/gateway/ollama_dispatch.py`
- `hlf_source/agents/core/model_gateway.py`

Recovery notes:

- `bus.py` is a major constitutive file because it preserves the middleware chain: ingress, validation, ALIGN, gas, nonce, capsule checks, routing, publication.
- `router.py` contains the richer MoMA-style routing logic, specialization hooks, complexity short-circuiting, tier walk, allowlist gating, and routing traces.
- `ollama_dispatch.py` and `model_gateway.py` show the broader inference and provider-routing worldview that the current narrowed repo underrepresents.

### 3. Orchestration and Spec-Driven Lifecycle

Classification: strong but not yet packaged

Why it matters:

- These files show HLF participating in a larger execution lifecycle: specify, plan, execute, verify, merge.
- They preserve the program-to-workflow bridge and multi-agent DAG semantics.

Candidate files:

- `hlf_source/agents/core/crew_orchestrator.py`
- `hlf_source/agents/core/plan_executor.py`
- `hlf_source/agents/core/task_classifier.py`

Recovery notes:

- `crew_orchestrator.py` carries persona ordering, lifecycle rules, and CoVE-gated progression.
- `plan_executor.py` shows the concrete DAG execution model for turning plans into executable node sequences.
- `task_classifier.py` preserves provenance-only launcher doctrine and broader task vocabulary.

### 4. Formal Verification and Similarity Gate Direction

Classification: wrongly deleted or omitted

Why it matters:

- The source repo retains direct evidence that formal verification and semantic round-trip quality were intended parts of the system, not decorative extras.
- Their absence in the narrowed repo materially weakens the original promise of HLF as trustworthy coordination language.

Candidate files:

- `hlf_source/agents/core/formal_verifier.py`
- `hlf_source/docs/HLF_PROGRESS.md`

Recovery notes:

- `formal_verifier.py` directly encodes satisfiability, gas-budget, reachability, and invariant verification concepts.
- `docs/HLF_PROGRESS.md` explicitly records the round-trip semantic similarity gate as planned but unfinished, which matters for reconstruction sequencing.

### 5. Memory, Audit, and Context Substrate

Classification: strong but misaligned in current extraction

Why it matters:

- These files preserve the deeper claim that memory is curated, auditable, and governed rather than just stored.
- They support the user’s original meaning-layer goal, including provenance, compression, forgetting, and audit.

Candidate files:

- `hlf_source/agents/core/memory_scribe.py`
- `hlf_source/agents/core/context_pruner.py`
- `hlf_source/scripts/verify_chain.py`

Recovery notes:

- `memory_scribe.py` carries WAL-backed memory storage, vector search hooks, cold archive logic, dream findings, and metering-friendly design.
- `context_pruner.py` shows explicit forgetting-curve design rather than naive infinite accumulation.
- `verify_chain.py` is a lightweight but important audit-surface artifact for Merkle-chain integrity.

### 6. Persona System and Anti-Reductionist Review Discipline

Classification: wrongly replaced or downgraded

Why it matters:

- These files are direct evidence that personas, hats, and review doctrines were architectural control surfaces, not just writing style or prompt garnish.
- They preserve the larger operator model that keeps HLF explainable, adversarially reviewed, and recursively improvable.

Candidate files:

- `hlf_source/AGENTS.md`
- `hlf_source/.github/agents/hats.agent.md`
- `hlf_source/.Jules/hats.md`
- `hlf_source/config/personas/_shared_mandates.md`
- `hlf_source/config/personas/strategist.md`
- `hlf_source/config/personas/steward.md`
- `hlf_source/config/personas/sentinel.md`
- `hlf_source/config/personas/scribe.md`
- `hlf_source/config/personas/weaver.md`
- `hlf_source/config/personas/scout.md`
- `hlf_source/config/personas/herald.md`
- `hlf_source/config/personas/cove.md`
- `hlf_source/config/agent_registry.json`

Recovery notes:

- `AGENTS.md` is a high-signal architecture document. It connects layers, hats, operator catalogs, invariants, and data flow.
- `steward.md` is especially important because it frames MCP and tool orchestration as a governed trust boundary.
- `weaver.md`, `scout.md`, and `herald.md` preserve how grammar evolution, ecosystem research, and documentation integrity feed back into HLF development.

### 7. Ecosystem and External Integration Surfaces

Classification: wrongly omitted

Why it matters:

- These files preserve the wider claim that HLF is intended to mediate a broader ecosystem, not just a local packaged runtime.
- They are essential if the repo is meant to recover toward the real end state rather than remain a narrow MCP package.

Candidate files:

- `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`
- `hlf_source/docs/JULES_COORDINATION.md`
- `hlf_source/docs/WALKTHROUGH.md`
- `hlf_source/scripts/persona_gambit.py`
- `hlf_source/scripts/local_autonomous.py`

Recovery notes:

- `UNIFIED_ECOSYSTEM_ROADMAP.md` is direct evidence that external systems and user repos were supposed to integrate via HLF host functions.
- `JULES_COORDINATION.md` shows the intended multi-agent collaboration protocol around the repo itself.
- `persona_gambit.py` reveals that persona coverage was operationalized, not just theorized.

### 8. Operator Reference, Gallery, and Human-Legibility Surfaces

Classification: strong but not yet packaged

Why it matters:

- These files preserve how HLF teaches itself, validates examples, and remains legible to humans.
- They are part of the bridge between formal language and operator trust.

Candidate files:

- `hlf_source/docs/HLF_REFERENCE.md`
- `hlf_source/docs/HLF_GRAMMAR_REFERENCE.md`
- `hlf_source/scripts/run_hlf_gallery.py`
- `hlf_source/gui/app.py`
- `hlf_source/docs/hlf_explainer.html`

Recovery notes:

- `run_hlf_gallery.py` is a concrete recovery candidate because it systematizes example compilation and reporting.
- `HLF_GRAMMAR_REFERENCE.md` and `HLF_REFERENCE.md` remain important for human-readable operator discipline and runtime/memory framing.
- The GUI and explainer surfaces preserve the operator-facing narrative that a narrow code-only extraction loses.

## Reconstruction Implications

### What this source map changes

- It confirms that the damaged fragment is missing more than docs polish.
- It shows the missing architecture is distributed across governance, routing, personas, orchestration, memory, audit, and ecosystem coordination.
- It invalidates any reconstruction method that looks only for files named `HLF*`.

### Immediate recovery priorities

1. Build a rejected-extraction audit using these clusters as input.
2. For each cluster, classify current repo state as:
   - strong but misaligned
   - strong but not yet packaged
   - wrongly replaced
   - wrongly deleted
3. Separate:
   - code that should be restored or ported
   - doctrine that should be preserved as doctrine
   - source-only context that should inform design without being copied blindly

## Initial Candidate Ranking

Top priority candidates for the next reconstruction pass:

1. `hlf_source/AGENTS.md`
2. `hlf_source/agents/gateway/bus.py`
3. `hlf_source/agents/gateway/router.py`
4. `hlf_source/agents/core/formal_verifier.py`
5. `hlf_source/agents/core/plan_executor.py`
6. `hlf_source/agents/core/crew_orchestrator.py`
7. `hlf_source/config/personas/steward.md`
8. `hlf_source/governance/ALIGN_LEDGER.yaml`
9. `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`
10. `hlf_source/scripts/run_hlf_gallery.py`

These ten files collectively cover doctrine, enforcement, routing, orchestration, verification, tool workflow integrity, ecosystem scope, and operator examples.

## Guardrail

Do not collapse these source surfaces into vague summaries or shallow placeholders. If a surface is constitutive, reconstruction must either:

- restore it,
- port its logic faithfully,
- or explicitly record why it remains source-only for now.