from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_INTRO = """\
You are connected to the SwarmGlass MCP server (formerly HLF — Hieroglyphic Logic Framework).

This MCP surface is the SwarmGlass governance delivery layer through Grumprolled for
native-agent use. It provides governed tool execution, audit trails, memory provenance,
and constraint enforcement — the stable governance shell around HLF's experimental DSL.

HLF is a deterministic orchestration protocol that replaces natural language ambiguity
with a strictly-typed Hieroglyphic AST for zero-trust agent execution. The HLF compiler,
runtime, and VM are available under SWARMGLASS_HLF_ENABLED=1.

Key properties:
  - LALR(1) deterministic parsing - 100% reproducible execution paths
  - 12-30% token compression over equivalent NLP (tiktoken cl100k_base)
  - Cryptographic governance - SHA-256 / Merkle chain audit trail
  - Gas metering - bounded execution, no infinite loops
  - Cross-model alignment - any agent can read and emit valid HLF

========================================================================
  HLF EXPLAINED TO A 5TH GRADER
========================================================================

WHAT IS IT?
  Imagine you want to send instructions to a robot friend. You could write a
  long paragraph in English - but your robot might misread it, get confused by
  a double meaning, or do something slightly different every time.

  HLF is like inventing your own tiny robot language made of special symbols
  instead of long sentences. Every symbol means exactly one thing - no guessing,
  no ambiguity, same answer every single time.

HOW DOES IT WORK? (the pipeline, step by step)
  1. You write an HLF program using glyphs and tags like [INTENT],
     [CONSTRAINT], and [EXPECT]. You can also write plain ASCII words like
     ANALYZE or ENFORCE - those get swapped for the right glyph automatically.

  2. A super-strict grammar (LALR(1)) reads the program. If the grammar says
     no, the whole thing stops - no partial results, no surprises.

  3. The Ethics Governor runs before anything else executes and blocks dangerous
     instructions before the runtime ever touches them.

  4. The compiler turns the program into a tiny bytecode stack machine. Gas
     metering counts every operation, so execution stays bounded.

  5. The output is a JSON AST with a SHA-256 fingerprint. If anyone tampers
     with the instructions, the seal breaks and you know immediately.

  6. A SHA-256 cache remembers recent programs so exact repeats can skip work.

  7. The hlf_submit_ast fast lane lets you skip text parsing if you already
     have a valid JSON AST.

THE PERKS
  * Reproducible - the same program yields the same execution contract.
  * Compact - fewer tokens than equivalent English prose.
  * Safe - governance, gas metering, and capsules bound behavior.
  * Multilingual - canonical tags normalize across multiple languages.
  * Auditable - compile and governance surfaces are hashable and inspectable.
  * Model-agnostic - natural language can stay the front door while HLF remains
    the execution contract.

WHEN HLF IS THE WRONG TOOL
  x Open-ended creative generation where strict determinism adds friction.
  x One-off scripts where no other agent or runtime needs to consume the output.
  x Highly dynamic unstructured payloads that are better stored as data than as
    execution contracts.
  x Ultra-low-latency edges where even parser and governance overhead matters.
"""

_MANDATORY_INTERNAL_LOOP = """\
  MANDATORY INTERNAL HLF LOOP
    Agent/native tool use must preserve this order for substantive work. Current
    packaged gates are current-true; broader swarm/sovereign restoration remains
    bridge-true or vision-true until separately proven:
      NLP ingress -> HLF translation -> validate/lint/compile -> governed execution
      or coordination -> NLP egress for humans.

    HLF is the internal coordination artifact, not a prose decoration. Use hlf_do
    for the full packaged loop, or hlf_translate_to_hlf followed by hlf_validate,
    hlf_compile, and the relevant execution/coordination surface. For swarm or
    sub-agent handoff, request handoff_mode=swarm/subagent/raw_hlf and pass the
    raw HLF artifact plus validation/compile proof; do not use a prose summary as
    the authoritative machine-to-machine payload.

    MCP mouthpiece enforcement is default-deny for protected tools: call bootstrap,
    validation, repair, read-only egress, and discovery tools first, then pass the resulting
    hlf_contract/translation_contract or hlf_governance_proof with protected tool
    calls. Protected outputs are JSON-egress checked before return.
  """


_AGENT_ARRIVAL = """\
  AGENT ARRIVAL
    Start here if you are encountering HLF for the first time in this server.

    1. Read hlf://agent/protocol to understand HLF as a shared meaning-and-handoff
      protocol for agents, tools, and governed execution.
    2. Read hlf://agent/current_authority before assuming forge or sovereign
      capability. Capsule tier, ingress posture, and approval surfaces are real
      authority boundaries in this checkout.
    3. Read hlf://agent/quickstart for the minimum working loop: establish
      authority, translate intent into governed HLF, inspect coordination and
      memory posture, then hand off canonical units instead of prose.
    4. Read hlf://agent/handoff_contract before treating conversational summaries
      as sufficient inter-agent payloads.

    Immediate next actions:
     - hlf_do                     for the packaged natural-language front door
     - hlf_translate_to_hlf       for explicit intent-to-HLF translation
     - hlf://status/ingress       to inspect current admission posture
     - hlf://status/operator_surfaces for packaged status/report discovery
  """

_OUTRO = """

Example HLF program (security audit):
  [HLF-v3]
  Delta analyze /security/seccomp.json
    Zhe [CONSTRAINT] mode="ro"
    Zhe [EXPECT] vulnerability_shorthand
    Join [VOTE] consensus="strict"
  Omega
"""


def _first_line(obj: Any, fallback: str) -> str:
    doc = getattr(obj, "__doc__", None)
    if not doc:
        return fallback
    for line in doc.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.rstrip(".")
    return fallback


def _render_section(title: str, items: list[str]) -> str:
    body = "\n".join(items) if items else "  (none)"
    return f"{title}:\n{body}"


def build_server_instructions(
    tools: Mapping[str, Any],
    resources: Mapping[str, Any],
) -> str:
    tool_lines = [
        f"  {name:<28} - {_first_line(func, 'HLF MCP tool')}" for name, func in tools.items()
    ]
    resource_lines = [
        f"  {uri:<32} - {_first_line(func, 'HLF MCP resource')}" for uri, func in resources.items()
    ]
    sections = [
        _INTRO.rstrip(),
        _MANDATORY_INTERNAL_LOOP.rstrip(),
        _AGENT_ARRIVAL.rstrip(),
        _render_section("Available tools", tool_lines),
        _render_section("Resources", resource_lines),
        _OUTRO.rstrip(),
    ]
    return "\n\n".join(sections) + "\n"


SERVER_INSTRUCTIONS = build_server_instructions({}, {})
