# Constraint → HKS Handoff Architecture

*Version: 1.0 | Date: 2026-05-19*

## Overview

The HLF constraint system and the Hierarchical Knowledge Store (HKS) seed database
form a pipeline that flows typed effect declarations from compile-time analysis
into a queryable, validated knowledge base. This document explains how HLF
constraints become HKS exemplars — the "handoff" from the constraint layer to
the knowledge layer.

## Architecture: The Constraint Lifecycle

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   DEFINE    │───▶│   COMPILE    │───▶│   MANIFEST   │───▶│    SEED      │
│ typed_      │    │ effect_      │    │ capability_  │    │  hks_seed    │
│ contracts   │    │ extractor    │    │ manifest     │    │    .db       │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     │                    │                    │                   │
     ▼                    ▼                    ▼                   ▼
 EffectClass         _TOOL_TO_EFFECT    CapabilityManifest   HKSValidated
 enum (32 values)    +                 (effects[],          Exemplar rows
 Input/Output        _GLYPH_TAG_       trust_tier,          in SQLite
 contracts           TO_EFFECT         capabilities)        (domain,
 FailureMode         mappings                               category,
 ProofRequirement                                          compiled_json)
```

### Stage 1: DEFINE — `hlf_mcp/hlf/typed_contracts.py`

The foundational taxonomy lives here:

- **`EffectClass`** enum: 32 canonical effect categories (file_read, network_write,
  model_inference, safety_stop, etc.)
- **`FailureMode`** enum: 10 failure classifications (io_error, timeout_error,
  policy_denied, etc.)
- **`ProofRequirement`** enum: 4 proof gate levels (none → operator_review)
- **`TypedEffectDeclaration`**: The complete contract dataclass bundling input/output
  contracts, effect class, failure modes, proof requirements, safety posture, and
  egress validation
- **`ContractRegistry`**: Maps function names to their `TypedEffectDeclaration`
- **`@typed_contract`** decorator: Attaches contracts to Python callables at
  decoration time

This is the single source of truth for what every tool/function *can* do.

### Stage 2: COMPILE — `hlf_mcp/hlf/effect_extractor.py`

The `EffectExtractor` walks the compiled HLF AST and resolves every statement
into concrete `TypedEffectDeclaration` instances:

- **`_TOOL_TO_EFFECT`**: 50 tool-name → EffectClass mappings (e.g.,
  `"file_read" → FILE_READ`, `"web_search" → WEB_SEARCH`)
- **`_GLYPH_TAG_TO_EFFECT`**: 42 glyph+tag → EffectClass mappings (e.g.,
  `("Ж", "ENFORCE") → ASSERTION`, `("Δ", "SEARCH") → WEB_SEARCH`)
- **Glyph-only fallback**: 8 glyphs have fallback mappings when no tag matches
  (e.g., bare `Δ` → `LOCAL_ANALYSIS`)
- **Pattern-based resolution**: For unrecognized names, heuristics inspect the
  name for patterns like `*write*`, `*http*`, `*memory*` to infer effect class

The extractor produces a list of `TypedEffectDeclaration` objects, each with
inferred failure modes, proof requirements, safety class, and derived side effects.

### Stage 3: MANIFEST — `hlf_mcp/hlf/capability_manifest.py`

The `CapabilityManifest` bundles the extracted effects into a signed,
cryptographically verifiable declaration:

- **`EFFECT_TO_CAPABILITY`**: Maps each `EffectClass` to a system capability
  domain (filesystem, network, memory, model, exec, agent, governance, verifier,
  embodied, audit, crypto, environment, routing, local)
- **`EFFECT_TO_TRUST_TIER`**: Maps each `EffectClass` to the minimum trust tier
  required (advisory → approved → watched → trusted → hearth)
- **`check()`**: Validates the runtime environment has all required capabilities
- **`check_tier()`**: Validates the session has sufficient trust level
- **`sign()`**: Produces SHA-256 signature over canonical JSON for tamper detection

The manifest is the bridge between static analysis and runtime governance.
It answers: "What does this program need, and is this environment trusted
enough to give it?"

### Stage 4: SEED — `scripts/build_hks_seed.py` → `hks_seed.db`

The seed database takes the compiled effect taxonomy and creates curated
exemplars for the HKS. Each exemplar encodes:

- **category**: Maps to an `EffectClass` value or a derived category
- **hlf_source**: Reference to the originating file (e.g., `typed_contracts.py`,
  `effect_extractor.py`)
- **compiled_json**: A JSON-serialized `TypedEffectDeclaration` showing the
  complete contract shape
- **capability_tags**: The system capabilities required by this effect
- **difficulty**: Complexity classification (basic, intermediate, advanced)
- **created_at**: Timestamp for freshness tracking

These exemplars serve as day-1, high-quality reference patterns that HKS
consumers (the `agent_spawner._recall_hks_exemplars()` pipeline, the
`server_context` evaluation loop, and the `RAGMemory.store_exemplar()`
path) use immediately without requiring a cold-start bootstrapping period.

## Data Flow Diagram

```mermaid
flowchart TD
    subgraph "Phase 1: Type System"
        TC[typed_contracts.py<br/>EffectClass enum<br/>TypedEffectDeclaration]
        TR[tool_contracts.py<br/>B2 tool contract<br/>definitions]
    end

    subgraph "Phase 2: Compilation"
        EE[effect_extractor.py<br/>EffectExtractor<br/>_TOOL_TO_EFFECT<br/>_GLYPH_TAG_TO_EFFECT]
        CM[capability_manifest.py<br/>CapabilityManifest<br/>EFFECT_TO_CAPABILITY<br/>EFFECT_TO_TRUST_TIER]
    end

    subgraph "Phase 3: Execution Gate"
        FV[formal_verifier.py<br/>VerificationGate]
        EA[execution_admission.py<br/>Admission decision]
    end

    subgraph "Phase 4: Knowledge Store"
        SB[build_hks_seed.py<br/>Script: reads EffectClass enum<br/>creates curated exemplars]
        SD[(hks_seed.db<br/>SQLite<br/>exemplars table)]
        RM[RAGMemory<br/>store_exemplar()]
        AS[agent_spawner.py<br/>_recall_hks_exemplars()]
        SC[server_context.py<br/>HKS evaluation loop<br/>weekly freshness check]
    end

    TC --> EE
    TR --> EE
    EE --> CM
    CM --> FV
    CM --> EA
    TC --> SB
    CM --> SB
    SB --> SD
    SD --> RM
    RM --> AS
    RM --> SC
    AS --> |persona + exemplars| AG[Agent Worker<br/>Ollama inference]
```

## Decision Rationale

### Why seed the HKS from constraints?

1. **Cold-start problem**: Without seed exemplars, HKS consumers (agent spawner,
   evaluation loop) start with empty recall. The first N queries produce no results,
   degrading agent output quality until enough exemplars accumulate organically.

2. **Curated quality > organic accumulation**: EffectClass taxonomy represents
   carefully designed categories. Organic exemplars may be noisy, incomplete, or
   biased toward frequently-used effects. Seeding from the taxonomy ensures
   every effect category has at least one high-quality exemplar.

3. **Contract shape exemplars**: The `TypedEffectDeclaration` structure is rich
   (input_contract, output_contract, failure_modes, proof_requirement, safety_class,
   side_effects, egress_validation). Having exemplars that demonstrate the complete
   contract shape helps agents produce well-formed contracts.

4. **Domain coverage**: The HKS has 9 domains (general-coding, ai-engineering,
   hlf-specific, devops, security, data-engineering, frontend, backend,
   infrastructure). Each effect class maps naturally to one or more HKS domains,
   ensuring balanced domain coverage from day one.

### Why SQLite for the seed DB?

- **Zero-dependency deployment**: SQLite is in Python's stdlib. No server, no
  connection strings, no authentication. Drop the `.db` file and it works.
- **RAGMemory compatibility**: The existing `RAGMemory` class already uses SQLite.
  The seed DB uses the same schema patterns, making integration trivial.
- **Embeddable**: The seed DB can be bundled with the HLF MCP server, checked into
  git, or distributed as a release artifact.

### What about the CONSTRAINT_GLOSSARY.md tags?

The glossary tags (COMMONJS, FACTORY-EXPORT, etc.) represent *output-quality*
constraints — they describe what agent output should look like. The EffectClass
taxonomy represents *capability* constraints — what side effects a tool can
produce. Both feed into the HKS, but through different paths:

- **EffectClass → hks_seed.db**: Compiled into structural exemplars at build time
- **Glossary tags → constraint_glossary_bridge.py → agent_spawner.py**:
  Injected as prompt-level constraints at agent spawn time
- **Glossary tags → HKS**: Could be seeded as "code pattern" exemplars (future)

## Integration Points

| File | Role |
|------|------|
| `hlf_mcp/hlf/typed_contracts.py` | Defines EffectClass, TypedEffectDeclaration |
| `hlf_mcp/hlf/effect_extractor.py` | Resolves tool names → EffectClass; walks AST |
| `hlf_mcp/hlf/capability_manifest.py` | Bundles effects into signed manifest; trust tier gating |
| `scripts/build_hks_seed.py` | Reads taxonomy, creates seed DB |
| `hlf_mcp/rag/memory.py` | RAGMemory.store_exemplar(); HKSValidatedExemplar |
| `hlf_mcp/hlf/agent_spawner.py` | _recall_hks_exemplars() feeds exemplars to spawned agents |
| `hlf_mcp/server_context.py` | HKS evaluation loop; weekly freshness; exemplar promotion |

## Future Directions

- **Auto-regeneration**: Rebuild `hks_seed.db` whenever `typed_contracts.py`
  changes (CI hook or pre-commit).
- **Glossary tag exemplars**: Seed the HKS with code-pattern exemplars
  demonstrating each glossary constraint (e.g., "here is what a FACTORY-EXPORT
  looks like").
- **Versioned seeds**: Tag seed DBs with the HLF compiler version so consumers
  can detect schema drift.
