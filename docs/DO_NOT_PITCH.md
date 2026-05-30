# SwarmGlass "Do Not Pitch" List

Date: 2026-05-23
Status: Active — enforced until benchmarked evidence exists

These claims are **explicitly forbidden** in any SwarmGlass marketing, documentation, README,
tool descriptions, or public communication until independently benchmarked with published results.

## Forbidden Claims

| # | Claim | Why Forbidden | What To Say Instead |
|---|-------|---------------|-------------------|
| 1 | "Replaces natural language coordination" | Benchmarks proved NL matches/beats HLF. We lost this argument. | "SwarmGlass governs whatever coordination style you already use." |
| 2 | "Saves tokens by default" | Only true in specific benchmarked scenarios, not general case. | "Token efficiency varies by workload. See benchmarks." |
| 3 | "Solves multi-agent orchestration" | Overreach. Governance ≠ orchestration. | "SwarmGlass observes, validates, and audits agent swarms." |
| 4 | "Self-governing AI operating system" | Hallucinated ambition. Not remotely true. | "SwarmGlass is an MCP server that provides governance tools." |
| 5 | "Recursive MAS" (Multi-Agent System) | Experimental research lane, not a product feature. | "Experimental recursive coordination patterns available gated behind SWARMGLASS_HLF_ENABLED=1." |
| 6 | "Universal agent runtime" | HLF VM is experimental. Governance doesn't require a custom runtime. | "SwarmGlass provides governance primitives callable from any MCP-compatible agent." |

## Enforcement

- Any PR adding these claims to README, docs, tool descriptions, or MCP resource summaries must be rejected.
- The CI import guard ensures governance code never depends on experimental modules.
- Gate reviews will explicitly check for these claims before approving phase transitions.

## Why This Exists

The old excitement pattern was: "HLF will teach the world how to coordinate agents." That framing
led to overpromising and underdelivering. The "do not pitch" list prevents the same pattern from
reappearing under the SwarmGlass brand.

SwarmGlass is observability and governance first. Everything else is secondary until benchmarked.
