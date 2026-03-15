# Ethical Governor Handoff (People-First Governance)

This repository copy does **not** include the local agent's edits. The ethics stack must be completed by the downstream agent using the instructions below. Human work and privacy stay the priority; AI remains the tool.

## Ethos Snapshot
- People-first: privacy by default; no covert surveillance or paternalistic blocking.
- Hard-law compliance over vague "guidance"; fail closed before allowing harm.
- Transparency: governance lives in-repo (ALIGN rules + ethics docs), not hidden model policies.
- Research is legitimate: provide a declared red-hat path instead of blanket denial.
- Shutdown beats violation: self-termination before executing illegal or abusive acts.

## Action Items for the Fill-In Agent
1. Sync in the full `HLF_ETHICAL_GOVERNOR_ARCHITECTURE.md` (and any updated `TODO.md` / `BUILD_GUIDE.md`) from the local working copy.
2. Flesh out the ethics module skeleton in `hlf_mcp/hlf/ethics/`:
   - `constitution.py` — hard-law/constitutional constraints; return violations list.
   - `termination.py` — decide when to fail closed and emit auditable reasons.
   - `red_hat.py` — declaration/attestation flow for legitimate security research.
   - `rogue_detection.py` — behavioral analysis over execution traces.
3. Wire the compiler hook in `hlf_mcp/hlf/compiler.py` (see the `Ethics Governor hook` comment) so constitutional checks run before Pass 3 and can halt compilation.
4. Update README + any build guides with the finalized ethics architecture and operational guidance (keep the people-first mission intact).
5. Add targeted tests around the new module behavior (constitution violations, termination path, red-hat declarations, rogue detection alerts).

## Integration Pointers
- **Code marker:** `hlf_mcp/hlf/compiler.py` contains a comment where ethics checks should be invoked.
- **Module skeleton:** `hlf_mcp/hlf/ethics/` holds stubs the downstream agent should replace with real logic.
- **Public messaging:** README section “Ethos — People First, Transparent Governance” sets the mission; expand it once the governor is implemented.

## Guardrails (Do / Do Not)
- Do keep decisions auditable and human-readable.
- Do enforce clear, lawful constraints; avoid opaque model-side censorship.
- Do provide a declared research path instead of blanket denials.
- Do fail closed (self-terminate) before executing harmful or unlawful instructions.
- Do not add surveillance-style behavioral logging that violates user privacy.
- Do not block legitimate research solely for "safety" optics; require declarations instead.

## Verification Checklist (post-implementation)
- Unit tests cover constitutional violations, termination triggers, red-hat declaration persistence, and rogue detection signals.
- Compiler fails closed on violation with explicit messages; VM honors termination signals.
- Docs updated to match shipped behavior; governance files remain transparent and discoverable.
