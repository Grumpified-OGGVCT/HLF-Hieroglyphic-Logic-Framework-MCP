# HLF Language Evolution And Bytecode Trust Spec

This document is a bridge specification.

It does not claim that every described surface is already fully implemented in packaged authority.

It does define what must remain true if HLF is to preserve its full language identity instead of shrinking into a parser-only or MCP-only fragment.

## Purpose

This spec joins four concerns that should not be split apart:

1. language evolution
2. grammar growth and syntax truth
3. bytecode and runtime trust
4. cryptographic provenance and operator-legible auditability

These concerns are coupled because HLF does not treat syntax, execution, and trust as separate worlds.

If the language evolves, the runtime and trust surfaces must know what changed.
If bytecode executes, operators must know which grammar and governance contract it was bound to.
If packets, pointers, tools, or traces are trusted, they must be tied back to explicit language and governance authority.

## Authority Model

This spec uses a three-lane authority split.

### 1. Executable authority

Current packaged executable truth lives in:

- `hlf_mcp/hlf/compiler.py`
- `hlf_mcp/hlf/bytecode.py`
- `hlf_mcp/hlf/runtime.py`
- `governance/bytecode_spec.yaml`
- `hlf/spec/vm/bytecode_spec.yaml`
- `governance/MANIFEST.sha256`

These files define what the repo may truthfully claim as executable now.

### 2. Semantic/refit authority

Recovery obligations are additionally informed by:

- RFC 9005 language-spec evidence
- RFC 9006 evolution/governance evidence
- RFC 9007 nuance/operator expansion evidence
- RFC 9008 verifier/security/deployment hardening evidence
- SAFE v4 and correction notes where they preserve bytecode, provenance, signing, or trust semantics by substance
- exact v0.4.0 syntax-diff evidence

These sources do not automatically become present-tense implementation claims.
They do remain authoritative evidence for what HLF still has to preserve or recover.

### 3. Bridge authority

This file exists in the bridge lane.

Its job is to keep packaged truth honest while preventing constitutive HLF evolution and trust semantics from disappearing into source archaeology.

## Version Clarification

The evidence currently under reconstruction does not establish a separately authoritative `HLF 4.0` release line.

The operative interpretation is:

- HLF v3.0 remains the last explicitly numbered language specification line
- RFC 9006 extends that line with governed language evolution
- RFC 9007 extends it with richer nuance, schema, and stylistic operator lanes
- RFC 9008 extends it with verifier, constraint, and hardened execution semantics

SAFE v4 material still matters when it preserves HLF-relevant bytecode, cryptographic, provenance, or compliance mechanics.

Version labels are therefore subordinate to semantic substance.

## Language Evolution Contract

HLF language evolution is not optional editorial drift.

It is a governed subsystem with at least these required elements:

- canonical registry authority for glyphs, operators, and meaning-bearing constructs
- explicit proposal and approval path such as HLIP-style changes
- additive, bugfix, and removal classes with distinct compatibility expectations
- anti-de-evolution rules that prevent regressions into weaker or more ambiguous forms
- semantic-gap detection between doctrine, grammar, compiler, runtime, and audit lanes
- dialect detection and control rather than silent fragmentation
- operator-visible evolution state rather than hidden grammar drift

### Required evolution invariants

Any accepted language change should be classifiable against the following invariants:

1. grammar delta
2. AST/IR delta
3. bytecode/runtime delta
4. governance and compatibility delta
5. audit/decompiler delta
6. migration or transpiler delta

If a change cannot be traced across those lanes, it is not yet a completed HLF evolution event.

## Exact Syntax Growth Matters

Broader doctrine is not enough to prove that a language feature actually existed in parser/compiler reality.

The recovered v0.4.0 syntax evidence matters because it closes grammar-level ambiguity for concrete constructs.

### Confirmed grammar/compiler additions from recovered evidence

- `tool_stmt`
- `cond_stmt`
- `assign_stmt`
- `parallel_stmt`
- `sync_stmt`
- `struct_stmt`
- `glyph_stmt`
- `type_ann`
- `ref_arg`
- `epistemic`
- boolean operators including `¬`, `∩`, and `∪`
- value comparisons
- arithmetic expressions with operator precedence

### Confirmed compiler-side governance and audit additions

- ALIGN-ledger style regex scanning in compiler passes
- dictionary and tag arity enforcement
- type enforcement beyond loose parsing
- forensic exception discipline such as `HlfAlignViolation` patterns
- InsAIts V2 `human_readable` payloads on AST nodes

### Interpretation rule

For every reconstructed HLF feature, classify it as one of:

1. conceptual only
2. grammar-real
3. runtime-real
4. governance-real
5. fully round-tripped

That prevents two failure modes:

- understating features that were already grammar-real
- overstating features that never advanced past grammar or doctrine

## Bytecode Trust Contract

HLF bytecode is not merely a serialization convenience.

It is part of the language's claim to deterministic, governed, auditable execution.

### Required bytecode trust properties

- one canonical bytecode spec for executable packaged truth
- stable opcode mapping with versioned meaning
- integrity binding between bytecode artifact and governing spec
- gas-accounted execution behavior
- disassembly and decompilation surfaces strong enough for operator inspection
- replayable trace semantics sufficient for governance and audit review
- explicit failure and violation surfaces rather than silent coercion

### Packaged authority now

The current packaged bytecode trust base is already materially real:

- `hlf_mcp/hlf/bytecode.py`
- `hlf_mcp/hlf/runtime.py`
- `governance/bytecode_spec.yaml`
- `hlf/spec/vm/bytecode_spec.yaml`
- `hlf_mcp/hlf/insaits.py`
- `scripts/verify_chain.py`

### Remaining bridge obligations

The packaged line does not yet fully establish all of the stronger trust semantics preserved in doctrine and local corpora, including:

- stronger constitution-hash compatibility rules across grammar, compiler, and runtime
- richer disassembly or proof-oriented round-trip guarantees
- explicit signed-registry and signed-tool trust binding
- clearer packet/pointer/trace identity chaining
- stronger proof that operator-facing decompilation matches executable meaning under drift pressure

## Cryptographic Provenance Contract

HLF trust is not only about code integrity in the abstract.

It governs what syntax, packets, tools, pointers, and traces may be accepted as meaning-bearing execution inputs.

### Trust-bearing surfaces confirmed by evidence

- constitution-hash compatibility for language and governance binding
- registry trust for meaning-bearing operators and tool families
- signed tools or equivalent trust-bearing tool identity assumptions
- signed agent identity or agent-card trust assumptions where they materially gate execution
- Merkle-style or chained trace logging
- content pinning for pointers and external references
- provenance chains for memory nodes, summaries, and execution artifacts

### Current local authority already carrying part of this load

- `governance/MANIFEST.sha256`
- `governance/host_functions.json`
- `governance/bytecode_spec.yaml`
- `hlf_mcp/hlf/memory_node.py`
- `hlf_mcp/rag/memory.py`
- `hlf_mcp/hlf/insaits.py`
- `scripts/verify_chain.py`

### Remaining bridge work

- define one explicit trust-chain model that spans grammar hash, bytecode artifact, tool registry, pointer provenance, and trace identity
- make signed-registry and signed-tool assumptions explicit rather than implicit
- define when content-addressed pointers are mandatory versus optional
- specify how memory-node lineage, freshness, and anti-poisoning checks interact with execution trust

## Two-Channel Execution And Pointer Trust

Recovered evidence confirms that HLF was designed to separate:

- the instruction channel
- the data channel

That matters because pass-by-reference is not merely an optimization.
It is part of the language's strategy for preserving semantic control while keeping raw payloads out of the instruction lane.

### Required implications

- pointer references must carry provenance and trust metadata
- external content must be pin-able or hash-bindable when it materially changes execution meaning
- memory and runtime docs must state when referenced data is trusted, stale, untrusted, or conflict-bearing
- decompiled operator views must reveal the presence of referenced external data rather than hiding it

## Verifier And Constraint Lane

RFC 9008-class evidence confirms that HLF was intended to support a stronger constraint and verification lane than is currently packaged as product truth.

This includes:

- explicit negative constraints such as `⊖`
- cognitive load and density checks
- pre-execution formal safety queries
- verifier-gated high-stakes execution

This repo should not falsely claim those surfaces are complete now.
It should preserve them as constitutive bridge obligations tied to language evolution and runtime trust.

## Operator-Legible Audit Rule

HLF does not end at symbolic compression.

Any trusted execution story must also preserve operator-legible auditability through:

- InsAIts-style decompilation
- human-readable AST or bytecode explanations
- trace identity and provenance visibility
- explainable failure surfaces for governance or verifier blocks

If a change strengthens machine execution but weakens human auditability, it is not a complete HLF improvement.

## Implementation Matrix

| Concern | Packaged truth now | Bridge requirement |
| --- | --- | --- |
| Canonical bytecode execution | `hlf_mcp/hlf/bytecode.py`, `hlf_mcp/hlf/runtime.py` | Preserve richer proof, compatibility, and provenance semantics without creating a parallel runtime authority |
| Grammar growth truth | packaged compiler/grammar plus recovered syntax evidence | Keep grammar-real vs runtime-real distinctions explicit in docs, tests, and future migration work |
| Language evolution governance | recovery docs and source evidence | Create explicit registry/change-control surfaces instead of leaving evolution only in doctrine |
| Cryptographic provenance | manifest, registry, chain verification, memory lineage fragments | Unify grammar-hash, tool trust, pointer pinning, and trace identity into one trust contract |
| Two-channel execution | partial pass-by-reference and memory design evidence | Make pointer provenance and trust-bearing data references first-class contracts |
| Verifier lane | recovery-only today | Define the packaged bridge without claiming the verifier subsystem is already complete |

## Required Next Refit Steps

1. define constitution-hash compatibility rules for packaged grammar and runtime authority
2. publish a packaged-facing registry/evolution policy for additive, bugfix, and removal changes
3. define a trust-chain model spanning bytecode artifact, registry/tool trust, pointers, and traces
4. separate grammar-real, runtime-real, and fully round-tripped status in future feature accounting
5. tighten memory governance so provenance, freshness, anti-poisoning, and pointer trust are explicit execution inputs
6. expand operator-facing audit surfaces so decompilation and trace identity remain constitutive rather than optional

## Final Rule

Do not reduce HLF language evolution into a changelog.
Do not reduce bytecode trust into a checksum.

HLF treats meaning, execution, governance, and audit as one bounded system.

This spec exists to keep that system intact while packaged authority continues to converge.
