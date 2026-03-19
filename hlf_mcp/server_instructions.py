from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_INTRO = """\
You are connected to the HLF (Hieroglyphic Logic Framework) MCP server.

HLF is a deterministic orchestration protocol that replaces natural language ambiguity
with a strictly-typed Hieroglyphic AST for zero-trust agent execution.

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
        _render_section("Available tools", tool_lines),
        _render_section("Resources", resource_lines),
        _OUTRO.rstrip(),
    ]
    return "\n\n".join(sections) + "\n"


SERVER_INSTRUCTIONS = build_server_instructions({}, {})
