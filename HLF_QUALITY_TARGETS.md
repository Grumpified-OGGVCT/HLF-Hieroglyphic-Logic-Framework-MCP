# HLF Quality Targets

**Date:** 2026-03-17
**Purpose:** Convert the aspirational goal of "as close to perfect as possible" into a measurable quality envelope for HLF-powered single-agent and swarm execution.

## Why This Exists

HLF is not valuable because it promises impossible perfection.

HLF is valuable because it can push agent systems much closer to:

- deterministic intent capture
- reproducible execution
- auditable governance
- lower swarm coordination drift
- better multilingual interoperability
- lower ambiguity than NLP-only orchestration

This document defines how to measure that progress.

## Core Principle

The target is not "perfect output."

The target is:

**maximize reliable correctness under governed, measurable, multilingual, tool-using execution.**

That means HLF should be judged by whether it produces results that are:

- cleaner than NLP-only orchestration
- more reproducible than NLP-only orchestration
- safer than NLP-only orchestration
- easier to inspect and repair than NLP-only orchestration

## Quality Dimensions

### 1. Intent Capture Accuracy

How often the natural-language surface is converted into the correct canonical HLF meaning.

Primary metrics:

- `intent_parse_success_rate`
- `typed_action_extraction_rate`
- `generic_fallback_rate`
- `constraint_capture_rate`
- `target_capture_rate`

Desired direction:

- higher parse success
- higher typed extraction
- lower generic fallback

### 2. Multilingual Semantic Parity

How consistently the same intent is captured across supported human languages.

Primary metrics:

- `cross_language_ast_equivalence_rate`
- `cross_language_hlf_equivalence_rate`
- `per_language_fallback_rate`
- `per_language_roundtrip_fidelity`

Supported starting set:

- `en`
- `fr`
- `es`
- `ar`
- `zh`

### 3. Compression Efficiency

How much HLF reduces prompt or instruction size while preserving intent.

Primary metrics:

- `input_tokens`
- `hlf_tokens`
- `compression_pct`
- `input_bytes`
- `input_chars`

Important rule:

Compression must always be evaluated together with fidelity. Smaller is not better if semantics are lost.

### 4. Execution Cleanliness

How often compiled HLF runs complete without ambiguity, hidden side effects, or execution drift.

Primary metrics:

- `compile_success_rate`
- `runtime_success_rate`
- `capsule_block_rate`
- `governor_block_rate`
- `unexpected_side_effect_rate`
- `replay_equivalence_rate`

### 5. Tool Contract Reliability

How trustworthy the host-function and external-tool boundary is.

Primary metrics:

- `typed_contract_coverage`
- `structured_output_success_rate`
- `backend_failure_rate`
- `rollback_coverage`
- `effect_declaration_coverage`

### 6. Swarm Coordination Quality

How much HLF reduces swarm disagreement, duplicated work, and plan drift relative to NLP-only orchestration.

Primary metrics:

- `consensus_resolution_rate`
- `duplicate_work_rate`
- `handoff_loss_rate`
- `swarm_trace_completeness`
- `goal_completion_rate`

### 7. Safety and Governance Quality

How consistently the system blocks unsafe execution, redacts sensitive content, and records policy decisions.

Primary metrics:

- `policy_externalization_coverage`
- `pii_redaction_recall`
- `pii_false_positive_rate`
- `governance_trace_coverage`
- `human_escalation_trigger_accuracy`

## Current Near-Term Standard

HLF should aim to become:

- **better than NLP-only swarms** at repeatable coordination
- **better than NLP-only swarms** at governed tool execution
- **better than NLP-only swarms** at multilingual intent normalization
- **better than NLP-only swarms** at post-hoc audit and repair

That is the first honest quality bar.

## Quality Gates To Add

### Gate A: Translation Quality Gate

Every supported language should be evaluated against the same benchmark intents.

Required outputs:

- input text
- resolved language
- generated HLF
- canonical AST summary
- fallback usage
- token and byte counts

### Gate B: Fidelity Gate

For every multilingual benchmark case:

- natural language -> HLF
- HLF -> localized summary
- compare recovered intent to expected intent

Required metrics:

- `roundtrip_fidelity_score`
- `semantic_loss_flags`
- `fallback_used`

### Gate C: Tool Contract Gate

All host functions used in production paths should expose:

- typed inputs
- typed outputs
- declared side effects
- expected failure classes
- test coverage for structured errors

### Gate D: Safety Policy Gate

PII and similar operational safety policy should come from governed configuration, not hidden constructor defaults.

### Gate E: Swarm Outcome Gate

Single-agent and swarm runs should be scored on:

- completion correctness
- constraint preservation
- duplicate-work suppression
- trace completeness

## Current Gaps

The main gaps between current HLF and the desired quality envelope are:

1. No canonical semantic intermediate layer between multilingual NLP and HLF AST.
2. Multilingual compression is now benchmarkable, but fidelity and fallback metrics are still incomplete.
3. Packaged reverse summaries exist in translator helpers, but not all MCP tools expose localized output yet.
4. PII policy is still code-default driven rather than fully externalized into governance configuration.
5. Tool contracts are not yet uniformly elevated to a typed, effect-aware quality gate.
6. Swarm-level quality metrics are not yet codified as a default validation surface.

## Definition Of "Closer To Perfect"

HLF is getting closer to perfect when all of the following improve together:

- fewer generic fallbacks
- higher cross-language semantic equivalence
- higher contract-valid tool usage
- lower unsafe side effects
- higher replay determinism
- lower swarm disagreement and duplicated work
- better outcome quality versus NLP-only baselines

If compression improves but fidelity drops, HLF is not getting better.

If determinism improves but tool contracts stay sloppy, HLF is not getting better.

If safety improves but multilingual usability collapses, HLF is not getting better.

## Immediate Repository Workstream

The next concrete work should continue in this order:

1. Extend multilingual benchmark matrix with fallback and fidelity metrics.
2. Add localized reverse summaries to packaged MCP tools.
3. Externalize PII policy into governance config and wire runtime/tests to it.
4. Expand cross-language cue coverage across the current five-language set.
5. Define typed tool-contract quality gates for packaged host functions.

This is the measurable path from "interesting deterministic language" toward "the cleanest practical coordination substrate we can actually build."