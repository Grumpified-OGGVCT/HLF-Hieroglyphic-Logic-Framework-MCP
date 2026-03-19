# HLF MCP Positioning

This document explains how MCP should be understood in this repo.

It exists because MCP is important enough to shape how outsiders read HLF, but easy enough to misunderstand that it can accidentally shrink the whole project if left undefined.

The short answer is:

**MCP is the right front door, the right present-tense product lane, and the right bootstrap surface for bounded recursive build evidence. It is not the final ontology of HLF.**

## One-Sentence Position

**HLF is the governed meaning and coordination substrate. MCP is the interoperability and delivery surface through which HLF becomes usable now.**

## Why This Distinction Matters

If the distinction is lost, HLF gets flattened into:

- an MCP wrapper
- a tool catalog
- a transport story
- a practical integration surface without its larger semantic contract

That would preserve something useful, but it would understate what HLF is trying to become.

The north-star doctrine is larger:

- deterministic meaning
- governed execution
- explicit effect boundaries
- memory provenance and trust
- multi-agent coordination contracts
- human-readable audit and explanation
- real-code and real-action bridges

MCP can expose those surfaces.
It cannot by itself define all of them.

## What MCP Is Good At

MCP is strategically strong here because it gives HLF a real, adoptable product surface for:

- tools
- resources
- prompts
- transports
- agent integration
- practical interoperability with existing clients

That makes MCP the right delivery choice for the current build phase.

It lowers adoption friction.
It forces packaging discipline.
It exposes real contracts early.
It gives HLF a usable interface before the full target architecture is complete.

## What MCP Is Not

MCP is not, by itself:

- the stable meaning layer
- the full effect algebra
- the governed memory ontology
- the whole coordination contract
- the full human-trust interface
- the complete code/action bridge

Those belong to HLF more broadly.

So the correct framing is not:

"HLF is basically the MCP server."

It is:

"The MCP server is the main current product surface through which HLF is delivered."

## Current-Truth Position

In current truth, the packaged FastMCP server under `hlf_mcp/` is the main production-facing implementation line.

That matters because it already gives the repo a real governed interface for:

- compile
- validate
- execute
- translate
- explain
- inspect
- summarize
- memory-facing operations

The packaged MCP surface is therefore already enough to prove that HLF is more than a static grammar experiment.

But current truth must remain disciplined.

The repo does **not** currently earn the claim that MCP exhausts the HLF architecture.
It also does **not** earn the claim that every constitutive HLF pillar is equally restored in packaged form.

## Bridge Position

In bridge terms, MCP does three important jobs at once.

### 1. Adoption path

It lets agents and operators use HLF now without first learning the full language surface.

### 2. Product pressure

It forces the repo to name tools clearly, expose resources coherently, maintain usable transport paths, and keep the public surface honest.

### 3. Recursive build discipline

It provides the first stable lane through which HLF can help inspect, summarize, explain, and guide parts of its own build and recovery process.

That is why MCP is so important to the recursive-build story.

## North-Star Position

At the north-star level, HLF is supposed to become a governed language and coordination substrate that turns human intent into auditable machine action across:

- agents
- tools
- memory
- policy
- execution
- human trust
- real-code output

MCP should be understood as one major surface of that system, not the total definition of it.

This is why the repo must keep strengthening:

- semantic core
- effect algebra
- compiler and proof surfaces
- runtime discipline
- governed memory
- coordination contracts
- human-legible audits
- real-code bridge layers

If only the MCP surface gets stronger, HLF risks becoming a good wrapper around a partially realized core.

## What This Should Mean For Agents

If HLF is completed along its intended path, an agent using the finished HLF MCP should not mainly experience:

- a menu of tools
- a set of prompts
- a protocol with nicer wrappers

It should experience a governed operating environment where:

- intent can be expressed through a bounded meaning layer
- effects are explicit and inspectable
- policy is legible rather than opaque friction
- memory carries provenance, confidence, and trust structure
- delegation and handoff are governed rather than improvised
- explanations and audit trails are part of the normal action contract

That is the stronger product claim.

## Anti-Reduction Rule

The repo should continue repeating this internally and externally:

**The MCP server is the front door, not the house.**

And more precisely:

**If HLF survives only as an MCP wrapper, then the vision has been operationalized but also reduced.**

That is the conceptual danger this positioning brief exists to prevent.

## Practical Summary

Use these statements when describing MCP in relation to HLF:

- MCP is the right practical front door.
- MCP is the right present-tense product lane.
- MCP is the right bootstrap surface for bounded recursive-build evidence.
- MCP is not the full meaning layer.
- HLF remains larger than MCP in semantics, governance, memory, coordination, trust, and execution.

## Related Files

- `docs/HLF_CLAIM_LANES.md`
- `docs/HLF_VISION_PLAIN_LANGUAGE.md`
- `docs/HLF_VISION_MAP.md`
- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_RECURSIVE_BUILD_STORY.md`
- `docs/HLF_STITCHED_SYSTEM_VIEW.md`
- `HLF_VISION_DOCTRINE.md`
- `SSOT_HLF_MCP.md`
- `BUILD_GUIDE.md`