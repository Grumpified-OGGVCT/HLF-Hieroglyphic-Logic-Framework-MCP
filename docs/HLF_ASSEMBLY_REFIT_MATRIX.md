# HLF Assembly Refit Matrix

This document treats HLF reconstruction as an assembly problem, not a replacement problem.

It exists because much of the external material predates the repo's current local enhancements, but that does not make the earlier material disposable.

The rule is:

- older evidence is not invalid just because local implementation moved forward
- newer local implementation is not invalid just because earlier doctrine described the same pillar differently
- the job is to refit each piece into the assembled HLF whole

## Refit Principle

For every major HLF pillar, ask four questions:

1. What did the earlier material prove or preserve?
2. What local authority exists now?
3. What local adjustments or upgrades have already changed the shape?
4. What still has to be refit so the pillar acts as intended in the assembled system?

## Refit Matrix

| Pillar | Earlier Evidence Preserved | Current Local Authority | Local Adjustments Already Made | Remaining Refit Work |
| --- | --- | --- | --- | --- |
| Mathematical-symbolic foundation | HLF as information-theoretic semantic compression; glyphs as minimum-entropy intent units; lossless round-trip claims | `docs/HLF_LOCAL_CORPORA_EXTRACTION.md`, `docs/HLF_REFERENCE.md`, `docs/HLF_GRAMMAR_REFERENCE.md`, `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/compiler.py` | Packaged grammar/compiler/translator/bytecode are already real; public docs already frame HLF as a language, not a prompt trick | Make the math foundation explicit in canonical docs and validation language instead of leaving it implicit behind grammar and runtime code |
| Dual-surface language model | Compressed intent notation plus typed/compiled execution notation are both real HLF surfaces | `hlf_do`, `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/bytecode.py`, repo math memory note | Packaged surface already exposes plain-English-to-HLF front door and compiler/runtime path | Add explicit surface-boundary docs and make sure validators, docs, and tests do not collapse both surfaces into one simplified story |
| Runtime / bytecode / decompile loop | HLF-VM, AST hierarchy, bytecode, standard library, InsAIts, replay, proof-oriented execution | `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/bytecode.py`, `hlf_mcp/hlf/insaits.py`, `governance/bytecode_spec.yaml` | Canonical runtime/bytecode ownership boundary is already documented in `HLF_CANONICALIZATION_MATRIX.md` | Refit richer VM semantics, disassembly/proof surfaces, and stronger round-trip guarantees into the packaged authority without replacing the current runtime line |
| Cryptographic governance and trust chain | Constitution hash, signed registries, signed tools, agent identity, cryptographic trace binding, Merkle/chained logs | `governance/MANIFEST.sha256`, `governance/bytecode_spec.yaml`, `governance/host_functions.json`, `hlf_mcp/hlf/insaits.py`, `scripts/verify_chain.py` | Local repo already has manifest integrity, governance assets, bytecode contract, and trace tooling; extraction docs now recognize these as HLF-relevant | Create one integrated trust spec covering grammar hash compatibility, signed registries/tools, content pinning for pointers, and trace-chain verification |
| Language evolution governance | Canonical registry, HLIP, anti-de-evolution, dialect control, Evolution Dial, ITEA | `docs/HLF_LOCAL_CORPORA_EXTRACTION.md`, planning docs, `hlf_source/governance/hls.yaml` as evidence | Local planning now explicitly recognizes evolution as a missing/undercounted HLF pillar | Create packaged-facing bridge docs and future authority rules so language evolution is recoverable without importing the entire broader system |
| RFC 9007 nuance/operator layer | Struct, Expression, and Aesthetic operator families; richer schema/style lane | Local extraction doc, grammar/reference docs, source evidence | Current repo already has richer public HLF framing and some operator docs, but not a full packaged nuance recovery line | Refit schema/style/qualitative operator semantics under governed registries and explicit scope rules instead of leaving them as half-remembered theory |
| Two-channel execution / pass-by-reference | Instruction lane and data lane separation; pointer resolution outside LLM context window | `docs/HLF_REFERENCE.md`, `docs/HLF_GRAMMAR_REFERENCE.md`, runtime/memory surfaces | Current repo already preserves memory and retrieval work plus packaged runtime/bytecode authority | Refactor memory and runtime docs so pass-by-reference, provenance, and pointer trust become explicit first-class contracts |
| Constraint / verifier lane | Negative constraints, cognitive load limits, verifier gates, high-stakes proof checks | `docs/HLF_LOCAL_CORPORA_EXTRACTION.md`, `HLF_MISSING_PILLARS.md`, upstream verifier evidence | Current planning already calls out formal verification as a source-only pillar needing recovery | Refit verifier and constraint semantics into a future packaged verification bridge without pretending they already exist in runtime truth |
| Memory governance | Hash-linked memory lineage, entropic sanitization, provenance, freshness, trust tiers | `hlf_mcp/rag/memory.py`, `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md`, `hlf/infinite_rag_hlf.py` | Local HLF knowledge substrate and governed-memory spine is present and now correctly classified as fragmented rather than absent | Extend the recovery spec so memory contracts explicitly absorb hash chains, pointer trust, evidence discipline, and anti-poisoning logic |
| Operator-legible trust surface | InsAIts V2, SOC-facing translation, A2UI/AVC-like operator visibility, trace IDs | `hlf_mcp/hlf/insaits.py`, `README.md`, `docs/HLF_REFERENCE.md`, `docs/HLF_STITCHED_SYSTEM_VIEW.md` | Public docs and extracted surfaces already retain operator-legibility as a core HLF claim | Refit operator-facing trust panels, trace identity, and decompiled proof views into gallery/spec work instead of treating them as UI extras |

## What Refit Means In Practice

Refit does not mean:

- replace current local authority with older notes
- import every broader-system layer wholesale
- throw away local enhancements because the earlier notes were more expansive

Refit does mean:

- preserve local authority where the repo has already advanced
- mine older evidence for still-missing semantics, contracts, and upgrade intent
- record explicit bridge work for every constitutive piece that has not yet been restored into packaged truth

## Assembly Rule

Nothing is lost.

Some pieces are now:

- canonical authority
- semantic mines
- bridge requirements
- source-only context for now

But every real HLF piece still has a place in the final assembled system.
