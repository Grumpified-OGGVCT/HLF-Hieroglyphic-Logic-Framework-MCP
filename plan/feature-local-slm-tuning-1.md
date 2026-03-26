---
goal: Bridge plan for a local HLF-specialized SLM experiment using exact upstream Unsloth and Pinokio requirements while preserving MCP as the governed authority boundary
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-23
owner: GitHub Copilot
status: Planned
tags: [feature, bridge, local-models, tuning, evaluation, pinokio, unsloth]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

Define a bridge-lane experiment to test whether a locally tuned HLF-specialized small language model improves practical HLF fluency and operator usefulness over MCP-only routing, while keeping MCP as the authoritative governed execution, memory, and evidence boundary.

Current dependency boundary:

- the packaged MCP works today without any locally tuned HLF-specialized model
- this plan is future-only bridge work and should not be cited as evidence that the current repo requires a local model to function
- the intended future candidate is a bounded HLF-specialized local LoRA or QLoRA lane after the current build is complete and working, not before

## 1. Requirements & Constraints

- **REQ-001**: The experiment must evaluate four explicit conditions: base model without MCP, base model with MCP, tuned model without MCP, and tuned model with MCP.
- **REQ-002**: MCP remains the authority boundary for governed routing, tools, memory, evidence, and execution. The tuned model is an admitted candidate, not a governance replacement.
- **REQ-003**: Claims produced from this work are `bridge-true` until benchmarked and admitted by HLF qualification criteria.
- **REQ-004**: The experiment must fit the user's already-established minimum local hardware envelope before it becomes a serious build target.
- **REQ-005**: The implementation path must use exact upstream requirements from the public GitHub sources for `unslothai/unsloth` and `pinokiocomputer/pinokio` rather than inferred setup assumptions.
- **REQ-006**: Pinokio is the launcher and lifecycle authority for any Pinokio-managed local app flow.
- **REQ-007**: The plan must produce measurable evidence for whether local HLF tuning improves syntax fidelity, doctrine recall, translation quality, structured output discipline, and operator task completion.
- **CON-001**: This plan is `bridge-true`, not `current-true`, under [docs/HLF_CLAIM_LANES.md](docs/HLF_CLAIM_LANES.md).
- **CON-002**: Current packaged authority remains under `hlf_mcp/`; no training system is allowed to silently bypass governed routing or audit controls.
- **CON-003**: Local tuning work must not be described as self-improving HLF or autonomous model promotion until explicit qualification and promotion paths exist.
- **CON-004**: If the user's machine cannot support useful local tuning within the established minimum requirements, the plan must degrade to a lighter adapter-only experiment rather than forcing a full local-training stack.
- **GUD-001**: Use existing packaged local/hybrid routing seams documented in [BUILD_GUIDE.md](../BUILD_GUIDE.md) rather than inventing a parallel runtime path.
- **GUD-002**: Keep the experiment auditable: datasets, prompts, evaluation tasks, and admission outcomes must be versioned or logged.
- **PAT-001**: Treat tuned-local-plus-MCP as the primary candidate architecture because it preserves live truth and governance while improving HLF-native fluency.

## 2. Exact Upstream Requirement Baseline

### Unsloth upstream baseline from `unslothai/unsloth`

- **UP-REQ-001**: Unsloth Studio supports `Windows`, `Linux`, `WSL`, and `macOS`.
- **UP-REQ-002**: Studio currently supports CPU for chat and data recipes; training support is available for NVIDIA GPUs and is not yet the general path for AMD, Intel, or Apple MLX inside Studio.
- **UP-REQ-003**: Windows developer setup uses `Python 3.13`, `uv`, `unsloth studio setup`, and then `unsloth studio -H 0.0.0.0 -p 8888`.
- **UP-REQ-004**: Windows setup supports Python `>= 3.11 and < 3.14`, and the setup scripts install or require Python in that range.
- **UP-REQ-005**: Windows setup expects Node `>= 20` and npm `>= 11` when running from a git/developer install.
- **UP-REQ-006**: Windows setup auto-manages major prerequisites including Git, CMake, Visual Studio Build Tools, CUDA Toolkit alignment, Node.js, and PyTorch/CUDA wheels.
- **UP-REQ-007**: CUDA toolkit selection must not exceed the maximum CUDA version supported by the installed NVIDIA driver.
- **UP-REQ-008**: Windows setup sets `TORCHINDUCTOR_CACHE_DIR` to a short path to avoid MAX_PATH issues during Triton compilation.
- **UP-REQ-009**: Unsloth Studio estimates 4-bit model loading VRAM using approximately `0.90 bytes per parameter + 1.4 GB overhead`, which is useful for fit screening before training.
- **UP-REQ-010**: For Windows developer installs, the git-based path is a legitimate upstream-supported option, which aligns well with a controlled Pinokio-managed wrapper.

### Pinokio upstream baseline from `pinokiocomputer/pinokio` and `pinokiocomputer/program.pinokio.computer`

- **UP-REQ-011**: Pinokio is explicitly local, free, private, cross-platform, and intended to automate terminal-like install/run flows through a GUI launcher model.
- **UP-REQ-012**: Pinokio’s launcher model is built around install and start scripts plus UI surfaces such as `install.js`, `start.js`, and `pinokio.js`.
- **UP-REQ-013**: Pinokio supports per-platform and per-GPU branching in launcher scripts using runtime state such as `platform`, `gpu`, `which`, `port`, and script-local state.
- **UP-REQ-014**: Pinokio documents launcher generation and refinement through Gepeto, which can scaffold a launcher from an existing GitHub repository.
- **UP-REQ-015**: Pinokio can launch scripts from GitHub repositories and supports git-backed script references, making a repo-pinned launcher path viable.

## 3. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Bound the experiment so it does not distort current-truth HLF claims or interrupt the real build.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Record this plan as a `bridge-true` artifact and explicitly define tuned-local-plus-MCP as an experiment, not a shipped repo capability. | ✅ | 2026-03-20 |
| TASK-002 | Define the experiment success criteria around HLF syntax fidelity, doctrine recall, translation quality, structured outputs, and operator task completion. |  |  |
| TASK-003 | Define the hard stop rule: if local tuning exceeds the user's minimum hardware envelope, reduce scope to LoRA/QLoRA or inference-only comparison. |  |  |

### Implementation Phase 2

- **GOAL-002**: Build an exact-requirements setup lane for the local experiment using upstream-supported tools.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Create a Pinokio-managed launcher path for the chosen Unsloth setup route, using upstream requirements from `unslothai/unsloth` and Pinokio launcher conventions instead of ad hoc local shell instructions. |  |  |
| TASK-005 | Choose the initial candidate base model size by matching Unsloth VRAM fit guidance against the user's hardware floor before any tuning work starts. |  |  |
| TASK-006 | Define whether the first experiment uses Unsloth Studio, Unsloth Core, or a Pinokio-wrapped git/developer install based on the user’s actual machine constraints and need for repeatability. |  |  |

### Implementation Phase 3

- **GOAL-003**: Define the HLF-specific training corpus and evaluation harness.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Curate a bounded HLF training set from grammar references, doctrine files, examples, operator surfaces, and safe current-truth artifacts without flattening vision and current truth into one label stream. |  |  |
| TASK-008 | Define eval sets that separately measure no-MCP and MCP-assisted behavior so the value of tuning is not confused with the value of live tooling. |  |  |
| TASK-009 | Define evaluation prompts that test HLF parsing, symbol translation, doctrine classification, governed task framing, and operator-safe output discipline. |  |  |

### Implementation Phase 4

- **GOAL-004**: Connect tuned candidates to governed HLF admission rather than direct uncontrolled use.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Add a bounded admission workflow so tuned local candidates can be evaluated through existing HLF routing and governance seams instead of direct promotion. |  |  |
| TASK-011 | Record comparison results for the four experiment conditions in a durable artifact that can be audited and revisited. |  |  |
| TASK-012 | Define a promotion threshold for when a tuned local model becomes an allowed local reasoning lane candidate in MCP-governed routing. |  |  |

## 4. Alternatives

- **ALT-001**: MCP-only with no tuning. Rejected as the sole path because it cannot test whether HLF-native local specialization materially improves performance.
- **ALT-002**: Tuned local model without MCP. Rejected as the primary target because it removes the repo’s strongest current-truth governance and execution boundary.
- **ALT-003**: Full local retraining from scratch. Rejected for the first experiment because it is far more resource-intensive than adapter-based tuning and does not respect the user’s minimum-system constraint.
- **ALT-004**: Cloud fine-tuning first. Rejected because the explicit goal is local-only experimentation before any broader deployment story.

## 5. Dependencies

- **DEP-001**: Existing hybrid and local model routing guidance in [BUILD_GUIDE.md](../BUILD_GUIDE.md).
- **DEP-002**: Existing HLF doctrine and claim-lane rules in [HLF_VISION_DOCTRINE.md](../HLF_VISION_DOCTRINE.md) and [docs/HLF_CLAIM_LANES.md](../docs/HLF_CLAIM_LANES.md).
- **DEP-003**: Existing local/hybrid profile and model-governance seams under `hlf_mcp/`.
- **DEP-004**: Upstream sources `unslothai/unsloth`, `pinokiocomputer/pinokio`, and `pinokiocomputer/program.pinokio.computer`.

## 6. Files

- **FILE-001**: `plan/feature-local-slm-tuning-1.md`
- **FILE-002**: Potential future launcher files under a Pinokio-managed experiment folder, not yet created in this phase.
- **FILE-003**: Potential future evaluation artifact under `plan/` or `docs/`, not yet created in this phase.

## 7. Testing

- **TEST-001**: Verify that the selected Unsloth setup path installs successfully on the user’s machine within the documented upstream prerequisite range.
- **TEST-002**: Verify that the four experiment conditions can be run against the same eval set.
- **TEST-003**: Verify that tuned-local-plus-MCP does not bypass governed routing, evidence capture, or policy checks.
- **TEST-004**: Verify that resource usage remains inside the user’s acceptable local compute envelope.

## 8. Risks & Assumptions

- **RISK-001**: The user’s machine may support local inference but not practically useful local tuning for the first chosen model size.
- **RISK-002**: Pinokio launcher convenience can obscure the true hardware and dependency cost unless the setup is benchmarked explicitly.
- **RISK-003**: A tuned model may appear stronger simply because the eval set overlaps too closely with doctrine/training material.
- **RISK-004**: Overstating the experiment as a shipped HLF capability would violate repo claim-lane discipline.
- **ASSUMPTION-001**: The most credible first serious architecture is tuned local SLM plus MCP rather than tuned local SLM alone.
- **ASSUMPTION-002**: The user prefers the exact-upstream-requirements path over a faster but less verifiable local shortcut.

## 9. Related Specifications / Further Reading

- [docs/HLF_CLAIM_LANES.md](../docs/HLF_CLAIM_LANES.md)
- [BUILD_GUIDE.md](../BUILD_GUIDE.md)
- [HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
- [plan/architecture-model-intelligence-sync-1.md](architecture-model-intelligence-sync-1.md)
