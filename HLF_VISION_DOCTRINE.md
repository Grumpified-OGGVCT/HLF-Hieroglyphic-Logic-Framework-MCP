# HLF Vision Doctrine

**Purpose:** Preserve the full HLF ambition in an explicit, durable form without confusing vision, current implementation truth, and generated status.

This file exists because the repo needs all three of the following at the same time:

1. a truthful current-state lane
2. a full-scope north-star lane
3. a practical bridge from the current implementation to the full HLF vision

If any one of those three disappears, the repo becomes distorted:

- truth without vision becomes reductionist
- vision without truth becomes vapor
- implementation without a bridge becomes drift

---

## 1. The Core Claim

HLF is not just an MCP server, not just a glyph syntax, and not just a compiler experiment.

**HLF is meant to become an A2A-complete communications and programming language for governed, auditable, capability-bounded coordination across the full model spectrum.**

That means all of the following are part of the rightful target, not optional side quests:

- deterministic semantics
- governed execution
- explicit effect algebra
- portable executable artifacts
- human-trust audit surfaces
- real-code output
- persistent governed memory
- multi-agent coordination semantics
- cross-runtime interoperability
- layered adoption from weak/local models to frontier/cloud systems

Short version:

**HLF is supposed to be the meaning layer between intent, agents, tools, memory, governance, and execution.**

---

## 2. The Three Lanes Doctrine

The repo must preserve three distinct lanes.

### Lane A: Vision / north star

This is what HLF is ultimately trying to become.

Use these docs for that lane:

- `docs/HLF_DESIGN_NORTH_STAR.md`
- `RECOVERED_HLF_VISION_AND_MERGE_BRIEF_2026-03-15.md`
- this file

This lane is allowed to be larger than the current implementation.

### Lane B: Current truth

This is what is actually implemented, validated, and safe to claim in present tense.

Use these docs for that lane:

- `SSOT_HLF_MCP.md`
- `HLF_QUALITY_TARGETS.md`
- `BUILD_GUIDE.md`
- packaged code under `hlf_mcp/`

This lane must stay strict.

### Lane C: Bridge / convergence

This is how the current system grows into the vision without losing canonicality.

Use these docs for that lane:

- `HLF_ACTIONABLE_PLAN.md`
- `HLF_CANONICALIZATION_MATRIX.md`
- `HLF_IMPLEMENTATION_INDEX.md`

This lane translates ambition into implementable structure.

---

## 3. What The Full HLF Target Actually Includes

The domain examples used in this repo are intentionally illustrative, not exhaustive.

HLF is not being built for one user's current list of use cases, one transport, one product wrapper, or one domain such as coding, robotics, memory, or orchestration.

The intended target is a governed meaning layer that can keep absorbing additional domains without changing its core story:

- intent enters through bounded translation or structured authoring
- intent becomes canonical HLF meaning
- execution stays capability-bounded and auditable
- new domain knowledge is researched, governed, remembered, and promoted through explicit evidence and trust contracts
- human-readable ingress and egress remain operator surfaces, not the underlying ontology

That means future use-case families should be treated as candidates for disciplined absorption into HLF, not as exhaustive limits on what HLF is for.

If HLF is taken all the way down its intended road, the target stack includes at least these layers.

### 3.1 Semantic core

- canonical AST / IR
- deterministic grammar
- stable semantic interpretation rules
- reversible glyph and ASCII surfaces
- formal versioning and compatibility policy

### 3.2 Effect and capability algebra

- typed host functions
- explicit effect declarations
- effect composition rules
- capability proofs before execution
- approval and escalation semantics

### 3.3 Compiler and proof surface

- compile-time governance gates
- proof-producing validation
- counterexample and rejection explanation
- portable `.hlb` artifact generation
- replay and equivalence guarantees

### 3.4 Runtime and execution

- deterministic VM execution
- gas budgeting
- capsule enforcement
- replayability
- trace capture

### 3.5 A2A coordination layer

- delegation semantics
- consensus and vote semantics
- handoff contracts
- role and trust scopes
- coordination lineage and provenance

### 3.6 Memory layer

- governed memory writes
- exemplar and policy storage
- provenance, freshness, confidence, and trust tiers
- memory recall contracts
- historical lineage and revocation

### 3.7 Human trust interface

- English audit output
- explainable intent and effect summaries
- side-effect previews
- before/after interpretation diffing
- non-expert safety legibility

### 3.8 Real-code bridge

- codegen to Python, TypeScript, SQL, shell, infra, and API workflows
- reverse ingestion from real code into HLF-compatible structure where possible
- test, repair, and verification loops attached to generated outputs

### 3.9 Standardization layer

- independent conformance suite
- reference runtimes
- interoperability mappings
- package/module ecosystem
- public change-control and compatibility rules

---

## 4. The Layered Standard We Are Actually Building Toward

The intended layered standard is:

1. `HLF-Core`
2. `HLF-Effects`
3. `HLF-Agent`
4. `HLF-Memory`
5. `HLF-VM`

Meaning:

- weak agents can participate at Core
- governed tool use appears at Effects
- swarm coordination appears at Agent
- persistent governed knowledge appears at Memory
- portable deterministic execution appears at VM

That layered adoption model is one of HLF's strongest strategic advantages. It allows the language to scale from a laptop-tier local model to a full sovereign swarm without splitting into unrelated products.

It also means the packaged HLF MCP surface can legitimately become the main operational access path for that broader stack.

The important distinction is not "MCP versus HLF."

The important distinction is:

- HLF remains the governed meaning, memory, execution, and audit substrate
- HLF MCP is the packaged server surface through which agents, robots, operator tools, and other systems access those capabilities

So saying "HLF is larger than MCP" should never be read as "the system will not use HLF MCP."

The intended outcome is that HLF MCP exposes as much of the real HLF stack as can be packaged honestly.

---

## 5. What "A2A-Complete" Should Mean Here

HLF should not merely ride on top of an external A2A transport. The target is deeper.

HLF becomes A2A-complete when it can express and govern:

- intent transfer
- delegation terms
- trust and identity scope
- effect boundaries
- approval requirements
- consensus and dissent
- memory anchoring
- provenance of every handoff
- recoverable audit of the whole coordination graph

Transport standards can carry packets.

HLF is supposed to carry governed meaning.

---

## 6. Why The Current MVP Still Matters

The current implementation is not the full vision.

It is still strategically useful because it already proves several parts of the intended stack are real, not imaginary:

- packaged MCP delivery surface
- deterministic compiler/runtime path
- governance assets
- capsule model
- multilingual translation work
- memory substrate work
- plain-English front door via `hlf_do`
- structured metrics and scheduled artifact paths

That means the current system is not just a demo. It is an executable seed crystal.

It can and should be used during the build-out of the larger vision for:

- exercising the language surface
- validating translation and audit loops
- testing governance boundaries
- trying effect-system upgrades
- evolving memory contracts
- prototyping multi-agent handoff semantics
- generating examples, fixtures, and conformance cases

In other words:

**yes, current HLF should be loaded and employed in the process of building fuller HLF.**

But that recursion has to be staged correctly.

### 6.1 First credible self-build milestone

The first honest milestone is not "HLF remotely self-hosts all of HLF over every MCP transport."

The first honest milestone is narrower and stronger:

- the packaged MCP surface is used locally for bounded build assistance
- `stdio` is treated as the first reliable operator path
- build-observation and audit tools are used to inspect, summarize, and guide implementation work
- the system helps finish itself without overstating transport completeness

Concretely, the first credible "HLF helps finish HLF" milestone is:

- `hlf_do` for plain-English intent-to-HLF build actions
- `hlf_test_suite_summary` for regression-state awareness
- `_toolkit.py status` and related build-observation surfaces for repo health checks
- witness, memory, and audit surfaces for recording what happened and why

### 6.2 Transport gating rule

This doctrine does not treat every transport as equally ready for the recursive build story.

- local bounded assistance may be centered immediately on packaged tools and `stdio`
- HTTP transport health is useful, but health alone is not enough to claim full self-hosting readiness
- remote `streamable-http` self-build positioning must remain gated until real MCP initialization succeeds end to end

The vision therefore includes recursive HLF-assisted development, but the bridge path must earn that claim by stage.

That is one of its main purposes.

---

## 7. Non-Negotiable Doctrine Going Forward

From this point forward, repo cleanup should follow this rule:

**Never solve drift by deleting the vision lane. Solve drift by separating vision, truth, and bridge lanes clearly.**

Concrete implications:

- do not treat current-state docs as the place to carry every aspirational claim
- do not strip north-star docs until they become timid and unhelpful
- do not confuse package authority with vision authority
- do keep the full HLF ambition visible and explicit in-repo
- do force implementation plans to point back to that ambition

---

## 8. Immediate Operating Answer

No, a new discussion is not required to start the next phase.

The repo now has enough baseline structure to continue directly, provided work stays disciplined about the three-lane split.

The right operating model is:

1. vision lane defines the full target
2. truth lane defines what is real now
3. bridge lane defines what gets built next
4. current HLF surfaces are used to help build, validate, and pressure-test the fuller HLF system

That is the correct continuation path from here.
