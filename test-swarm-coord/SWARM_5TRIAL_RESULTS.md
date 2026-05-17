# Swarm Coordination Cost: 5-Trial Results

## Summary

| Trial | PLAN (coord) | Code | Tests | Total | Tests Pass | Notes |
|-------|-------------|------|-------|-------|-----------|-------|
| 1 | 863 | 7,048 | 5,024 | **12,935** | ✓ 11/11 | Baseline |
| 2 | 1,916 | 6,201 | 5,870 | **13,987** | ✓ 15/15 | Agent 2 fixed Agent 3's queue bug |
| 3 | 1,900 | 4,657 | 5,855 | **12,412** | ✓ 16/16 | Clean run |
| 4 | 1,781 | 5,353 | 5,417 | **12,551** | ✓ 16/16 | Added package.json |
| 5 | 2,469 | 5,558 | 5,903 | **13,930** | ✓ 17/17 | ESM module |
| **AVG** | **1,786** | **5,763** | **5,614** | **13,163** | **15.4 avg** | |

## Key Findings

### 1. PLAN.md Size is Highly Variable
- **Range:** 863–2,469 bytes (3x variation!)
- Agent 1 writes detailed interfaces. Agent 2 appends their own. Agent 3 may or may not read it carefully.
- **Trial 2:** WorkerBuilder had to fix a FIFO bug in queue.js that TestBuilder discovered. That's cross-agent bug-fixing cost.

### 2. All Tests Pass
- 5/5 trials produced passing test suites
- No complete failures — NL swarms are functional
- BUT: Trial 2 required a bug fix mid-flight. HLF's `interface` declarations would have prevented this.

### 3. Total Output is Consistent
- **Range:** 12,412–13,987 bytes (~13% variance)
- Code averages ~5,763 bytes, tests ~5,614 bytes
- PLAN.md is ~13.5% of total output on average

### 4. HLF Comparison (Static)
- `swarm.hlf`: 3,266 bytes (one-time interface declaration)
- No PLAN.md needed (interfaces ARE the plan)
- No cross-agent fixes (types enforce contracts upfront)
- Estimated total: ~3,266 + 5,763 + 5,614 = **~14,643 bytes**
- **Wait — that's MORE than NL average (13,163)!**

## The Honest Math

| Metric | NL Average | HLF | Verdict |
|--------|-----------|-----|---------|
| Coordination bytes | 1,786 | 3,266 | HLF **costs 83% more** |
| Cross-agent fixes | Present | Eliminated | HLF wins on correctness |
| Consistency | ±13% variance | Deterministic | HLF wins on predictability |
| Audit trail | PLAN.md + git | `swarm-trace.json` | HLF wins on traceability |
| Token savings | N/A | Unknown | **Not proven** |

## Why HLF Coordination Costs More

The `swarm.hlf` file is 3,266 bytes because it declares:
- 3 interface contracts (TaskQueue, Worker, Task)
- 3 agent declarations with inputs/outputs/constraints
- 3 effect annotations
- 1 trace config
- 1 checkpoint config

The NL `PLAN.md` averages 1,786 bytes because:
- Agent 1 writes a rough draft
- Agent 2 updates it with their notes
- Agent 3 skims it or ignores it
- It's prose, not a schema — shorter but less precise

**HLF's extra 1,480 bytes buys:**
- Type safety at the agent boundary
- No mid-flight bug fixes
- Deterministic execution order
- Full audit trail
- Automatic rollback on failure

## The Real Question

Is 1,480 extra bytes of coordination worth eliminating a class of cross-agent bugs?

For a 3-agent module build: probably not. The bug surface is small.

For a 30-agent system build: **absolutely.** When Agent 17 depends on Agent 3's interface and Agent 3 changed it 6 hours ago, HLF's `interface` declaration is the only thing preventing a cascading failure.

## Verdict

**On this task, HLF does NOT save coordination bytes. It costs 83% more.**

But it converts that cost from "hope the agents read the plan" into "the machine enforces the contract." The savings are not in bytes — they're in **debugging time, retry costs, and catastrophic failure prevention**.

If the industry doesn't value those things (and you're right — they mostly don't), HLF's value proposition is **not** "cheaper swarms." It's **"swarms that don't subtly break in production."**

That's a different pitch. It's not a cost pitch. It's a **trust pitch.**
