---
goal: Record the verified external technique baselines reviewed for HLF bridge planning without promoting them into packaged current truth
version: 1.0
date_created: 2026-03-23
last_updated: 2026-03-23
owner: GitHub Copilot
status: 'In progress'
tags: [bridge, source-audit, research, hks, robotics, verification]
---

# HLF External Technique Source Audit (2026-03-23)

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

## Purpose

This document is the repo-owned bridge artifact for the 2026-03-23 review of external memory, context-rot, reasoning, robotics, and domain-language baselines.

It exists to do three things cleanly:

- record which external techniques were actually source-checked during the review
- classify whether each item is verified, partial, or needs re-check before further promotion
- map each item onto the correct HLF lane so external research does not silently become current-truth product language

## Working Rule

This document is not a claim that HLF already implements these systems.

Unless a capability is also represented in packaged code, tests, operator-readable proof surfaces, and [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md), treat the material here as bridge input only.

Use this audit as a clean-room extraction aid:

- extract portable patterns, not product mythology
- do not copy external naming into active HLF implementation surfaces unless there is a deliberate compatibility reason
- do not import patented, copyrighted, or vendor-shaped phrasing as if it were HLF-native doctrine
- require any future promotion to pass through [docs/HLF_CLAIM_LANES.md](HLF_CLAIM_LANES.md), [docs/HLF_README_OPERATIONALIZATION_MATRIX.md](HLF_README_OPERATIONALIZATION_MATRIX.md), and [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md)

Comparator-specific extension of that rule:

- if an external system is used to compare HKS outputs against web or code search results, that system remains an optional `bridge` comparator until packaged HKS code, tests, and operator surfaces prove otherwise
- comparator outputs are advisory only unless locally re-evaluated inside HKS
- no comparator backend may silently become the admission authority for governed memory, exemplar promotion, route evidence, or verifier evidence

## Source Audit Table

Status meanings used here:

- `verified`: a primary or near-primary public source was checked during the review and was strong enough to support bounded extraction
- `partial`: an authoritative signal was verified, but the exact source set is still too thin, too old, too broad, or too proxy-based for stronger promotion
- `needs re-check`: the technique may still matter, but the review state is not yet strong enough for bridge planning

| Technique | Status | Source footing used in the 2026-03-23 review | Why this status was assigned | Safe immediate HLF use |
| --- | --- | --- | --- | --- |
| STaR | `verified` | Primary paper: `STaR: Bootstrapping Reasoning With Reasoning` ([arXiv:2203.14465](https://arxiv.org/abs/2203.14465)) | Sufficient to justify bounded extraction of self-improving reasoning and exemplar bootstrapping patterns | offline proposal, repair, and explanation benchmark design |
| A-MEM | `verified` | Primary paper: `A-MEM: Agentic Memory for LLM Agents` ([arXiv:2502.12110](https://arxiv.org/abs/2502.12110)) | Strong enough to treat as a real memory-organization donor because the paper explicitly centers dynamic memory organization, contextualized notes, and graph-like linking instead of vague memory rhetoric | HKS memory structure and retention-policy design |
| MemER | `verified` | Primary paper-level research source; see `[MemER 2025]` anchor below | The reviewed source describes a hierarchical policy that selects and tracks previous relevant keyframes and combines those with recent frames for long-horizon instruction generation, which is concrete enough to justify bounded extraction for context-rot mitigation | governed memory update, exemplar repair, and supersession patterns |
| TempoFit | `verified` | Primary paper: `TempoFit: Plug-and-Play Layer-Wise Temporal KV Memory for Long-Horizon Vision-Language-Action Manipulation` ([arXiv:2603.07647](https://arxiv.org/abs/2603.07647)) | Strong enough to inform adaptive context-fit and retrieval-budget decisions because it gives a concrete, training-free memory retrofit rather than a generic long-context claim | bounded context-fit scoring for HKS retrieval and routing |
| QwenLong-L1.5 | `verified` | Exact public model card: `Tongyi-Zhiwen/QwenLong-L1.5-30B-A3B` ([Hugging Face](https://huggingface.co/Tongyi-Zhiwen/QwenLong-L1.5-30B-A3B)) with linked paper citation `arXiv:2512.12967` | Strong enough to inform long-context and retrieval-compression thinking without treating model branding as doctrine because the public model card and linked paper make the training and memory-management claims inspectable | long-context bridge benchmarks and compression-with-fidelity evaluation |
| Think, Act, Learn | `verified` | Primary paper: `Think, Act, Learn: A Framework for Autonomous Robotic Agents using Closed-Loop Large Language Models` ([arXiv:2507.19854](https://arxiv.org/abs/2507.19854)) | Strong enough to justify iterative evidence-to-action-to-learning loop extraction | governed observe-propose-verify-promote workflow refinement |
| Robot Skill Language (RSL) | `verified` | Public language and robotics research source; see `[RSL / NRTrans 2025]` anchor below | The reviewed source defines Robot Skill Language as an abstraction over control-program detail and explicitly ties correctness to a compiler-and-debugger verification loop before robot execution, which is strong enough for contract-shape comparison | embodied host-function and contract-shape design |
| CRCL | `partial` | Authoritative standard page: NIST `Canonical Robot Command Language (CRCL)` ([nist.gov](https://www.nist.gov/el/intelligent-systems-division-73500/canonical-robot-command-language-crcl)) plus the linked formal model repository | The baseline is real, but this review did not preserve a richer modern source set and the source age matters | typed command-status contract comparison only |
| URScript | `verified` | Official vendor documentation: Universal Robots `URScript` script manual introduction ([universal-robots.com](https://www.universal-robots.com/manuals/EN/HTML/SW5_19/Content/prod-scriptmanual/G5/Introduction.htm)) | Strong enough to compare industrial action-language structure and controller boundary assumptions | supervisory industrial-actuation contract comparison |
| LTLCodeGen | `verified` | Primary paper: `LTLCodeGen: Code Generation of Syntactically Correct Temporal Logic for Robot Task Planning` ([arXiv:2503.07902](https://arxiv.org/abs/2503.07902)) | Strong enough to compare formal-spec-to-action translation and verification seams | verifier-backed intent-to-action bridge design |
| Behavior-tree and state-machine DSL family | `partial` | Family-level review anchored by BehaviorTree.CPP implementation and docs ([github.com/BehaviorTree/BehaviorTree.CPP](https://github.com/BehaviorTree/BehaviorTree.CPP)) | Useful as a strong family proxy, but this row still stands in for a broader class rather than one canonical source set | lifecycle, delegation, and execution-guard pattern comparison |

### Precise Source Anchors

- `[STaR 2022]` — `STaR: Bootstrapping Reasoning With Reasoning` ([arXiv:2203.14465](https://arxiv.org/abs/2203.14465)). The paper describes the Self-Taught Reasoner loop as: generate rationales, retry from the correct answer when necessary, fine-tune on rationales that yielded correct answers, and repeat. That is the bounded bridge donor for proposal bootstrap and verified exemplar accumulation.
- `[A-MEM 2025]` — `A-MEM: Agentic Memory for LLM Agents` ([arXiv:2502.12110](https://arxiv.org/abs/2502.12110)). The public paper framing is precise enough to anchor this row because it describes a memory system for LLM agents that dynamically organizes memories and, following Zettelkasten principles, builds interconnected knowledge networks through indexing and linking.
- `[MemER 2025]` — hierarchical key-frame selection for long-horizon memory use. The reviewed source states: "Humans routinely rely on memory ... we propose a hierarchical policy ... the high-level policy is trained to select and track previous relevant keyframes ... the high-level policy uses selected keyframes and the most recent frames when generating text instructions for a low-level policy" (lines 10-18 of the cited source used in the 2026-03-23 review).
- `[TempoFit 2026]` — `TempoFit: Plug-and-Play Layer-Wise Temporal KV Memory for Long-Horizon Vision-Language-Action Manipulation` ([arXiv:2603.07647](https://arxiv.org/abs/2603.07647)). The paper explicitly presents TempoFit as a training-free temporal retrofit that upgrades frozen VLAs through state-level memory, which is the bounded donor relevant to adaptive context-fit and retrieval-budget shaping.
- `[Think, Act, Learn 2025]` — `Think, Act, Learn: A Framework for Autonomous Robotic Agents using Closed-Loop Large Language Models` ([arXiv:2507.19854](https://arxiv.org/abs/2507.19854)). The reviewed source explicitly frames a closed-loop cycle where the system thinks, acts, learns from multimodal feedback, stores experiential memory, and uses that memory to improve future planning.
- `[RSL / NRTrans 2025]` — Robot Skill Language as a verified DSL boundary. The reviewed source states: "To achieve this, a Robot Skill Language (RSL) is proposed to abstract away from the intricate details of the control programs ... The RSL compiler and debugger are constructed to verify RSL programs generated by the LLM and provide error feedback ... This provides correctness guarantees for the LLM-generated programs before being offloaded to the robots for execution" (lines 29-38 of the cited source used in the 2026-03-23 review).
- `[CRCL / NIST]` — `Canonical Robot Command Language (CRCL)` ([nist.gov](https://www.nist.gov/el/intelligent-systems-division-73500/canonical-robot-command-language-crcl)). The NIST description defines CRCL as a low-level messaging language for sending commands to and receiving status from a robot, with commands executed by a low-level device controller and a formal XML Schema-based model linked from the page.
- `[URScript / Universal Robots]` — official `URScript` script manual introduction ([universal-robots.com](https://www.universal-robots.com/manuals/EN/HTML/SW5_19/Content/prod-scriptmanual/G5/Introduction.htm)). The vendor docs explicitly state that at the script level, `URScript` is the programming language controlling the robot and that it includes variables, flow control, and built-in functions for I/O and robot movement.
- `[LTLCodeGen 2025]` — `LTLCodeGen: Code Generation of Syntactically Correct Temporal Logic for Robot Task Planning` ([arXiv:2503.07902](https://arxiv.org/abs/2503.07902)). The paper directly anchors the spec-to-action bridge by translating natural-language instructions to syntactically correct LTL and feeding that LTL into planning with real and simulated robotic evaluation.
- `[BehaviorTree.CPP]` — `BehaviorTree.CPP` implementation and documentation ([github.com/BehaviorTree/BehaviorTree.CPP](https://github.com/BehaviorTree/BehaviorTree.CPP)). The project explicitly presents behavior trees as a DSL-based coordination framework with runtime-loaded XML trees, asynchronous actions, and logging or replay infrastructure, making it a bounded family-level donor for lifecycle and execution-guard comparisons.
- `[QwenLong-L1.5 2025]` — exact public model card `Tongyi-Zhiwen/QwenLong-L1.5-30B-A3B` ([Hugging Face](https://huggingface.co/Tongyi-Zhiwen/QwenLong-L1.5-30B-A3B)) with linked citation `QwenLong-L1.5: Post-Training Recipe for Long-Context Reasoning and Memory Management` ([arXiv:2512.12967](https://arxiv.org/abs/2512.12967)). This is the stable public anchor for the long-context and memory-management claims used in the audit.

Exact public-citation normalization items from the second pass are closed in this artifact.

## Lane Promotion Table

The lane below is the safe HLF lane for using each technique as an input.

It is not a statement that the external technique itself belongs to HLF. It is a statement about what HLF may currently claim or plan after reviewing it.

| Technique | Safe HLF lane now | What HLF can honestly extract now | What HLF must not claim yet |
| --- | --- | --- | --- |
| STaR | `bridge` | offline reasoning-improvement and exemplar-bootstrap patterns for repair, explanation, and proposal lanes | that HLF already ships STaR-style autonomous self-improvement as current truth |
| A-MEM | `bridge` | memory-organization and retention heuristics for HKS contract design | that HKS is already a finished A-MEM-equivalent system |
| MemER | `bridge` | governed memory edit, replacement, and supersession patterns | that current packaged memory already performs learned memory editing at that level |
| TempoFit | `bridge` | adaptive context-fit scoring and retrieval-budget ideas | that packaged routing or HKS already implements TempoFit-class adaptation |
| QwenLong-L1.5 | `bridge` | long-context evaluation patterns, compression tradeoff measurement, and retrieval fallback thinking | that HLF inherits model-specific long-context capability just by referencing the paper |
| Think, Act, Learn | `bridge` | disciplined evidence-to-action-to-learning loop design for weekly artifacts and proposal lanes | that packaged autonomous evolution is already complete or self-improving in production terms |
| Robot Skill Language (RSL) | `bridge` | typed embodied skill contracts and supervisory semantics | that HLF is already a robot skill language or real-time robotics stack |
| CRCL | `bridge` | command/status contract comparison for embodied interfaces | that packaged HLF already implements a CRCL-equivalent robotics interchange layer |
| URScript | `bridge` | industrial action-language boundary lessons and guardrail comparisons | that HLF already replaces controller-native industrial robot languages |
| LTLCodeGen | `bridge` | formal-spec-to-execution and verifier-binding ideas | that packaged verifier and execution admission already deliver LTLCodeGen-class guarantees |
| Behavior-tree and state-machine DSL family | `bridge` | lifecycle, task-graph, and guarded execution structure comparisons | that HLF already ships a full behavior-tree or state-machine orchestration product surface |

## Current-Truth Guardrail

No external technique in this audit should be promoted to `current-truth` merely because it has a verified source.

Current truth remains narrower:

- packaged HKS-adjacent memory, provenance, and audit surfaces
- packaged translation, verifier, lifecycle, and routing-adjacent seams
- packaged embodied bridge slices only where code, tests, and operator-readable proof already exist

If a future change wants to promote any row beyond bridge planning, it must update:

1. [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md)
2. [docs/HLF_README_OPERATIONALIZATION_MATRIX.md](HLF_README_OPERATIONALIZATION_MATRIX.md)
3. the relevant bridge spec or plan
4. packaged tests and operator-readable proof surfaces

## Extraction Notes By Family

### 1. Memory and context-rot family

The memory-oriented items in this audit are best treated as donors for HKS evolution, not as substitutes for HKS.

The strongest portable patterns from this family are:

- multi-timescale recall discipline
- freshness, supersession, and replacement rules
- adaptive context packing based on fit rather than raw accumulation
- explicit benchmark design for compression with fidelity instead of context-window vanity

Comparator quarantine rule for this family:

- external web or code retrieval stacks may be used to challenge HKS, compare recall quality, or seed bridge-lane benchmark sets
- they must not become the authoritative memory substrate for packaged HKS
- they must be represented as optional comparator surfaces, not merged into governed truth by default

### 2. Reasoning and self-improvement family

The reasoning-oriented items are useful for the governed proposal lane only if they remain bounded by evidence and promotion discipline.

The strongest portable patterns from this family are:

- proposal generation from observed failures or weak traces
- explicit improvement loops with review gates
- exemplar accumulation only after successful verification

### 3. Robotics and domain-language family

The robotics and formal-domain-language baselines are strongest when treated as contract-shape donors.

The strongest portable patterns from this family are:

- typed command and status surfaces
- explicit execution and failure envelopes
- supervisory semantics above low-level control loops
- tighter verifier coupling between intent, action, and audit

## Related Repo Authorities

- [docs/HLF_CLAIM_LANES.md](HLF_CLAIM_LANES.md)
- [docs/HLF_MCP_POSITIONING.md](HLF_MCP_POSITIONING.md)
- [docs/HLF_README_OPERATIONALIZATION_MATRIX.md](HLF_README_OPERATIONALIZATION_MATRIX.md)
- [docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md](HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md)
- [plan/architecture-hks-local-evaluation-bounded-comparator-1.md](../plan/architecture-hks-local-evaluation-bounded-comparator-1.md)
- [docs/HLF_ROBOTICS_EMBODIED_FIT_ASSESSMENT.md](HLF_ROBOTICS_EMBODIED_FIT_ASSESSMENT.md)
- [HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
- [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md)
