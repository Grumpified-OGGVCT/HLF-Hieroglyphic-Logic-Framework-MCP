"""
HLF MCP Server — Hieroglyphic Logic Framework Model Context Protocol Server.

Provides the complete HLF toolchain as MCP tools accessible via:
  - stdio     (Claude Desktop, local agents)
  - sse       (HTTP/SSE, remote agents, Docker)
  - streamable-http (modern MCP clients)

Transport is selected via the HLF_TRANSPORT environment variable.
  HLF_TRANSPORT=stdio             (default)
  HLF_TRANSPORT=sse               HTTP + SSE on HLF_HOST:HLF_PORT
  HLF_TRANSPORT=streamable-http   Streamable HTTP on HLF_HOST:HLF_PORT

Quick start:
  docker run -e HLF_TRANSPORT=sse -p 8000:8000 hlf-mcp
  # → SSE endpoint:          GET  http://localhost:8000/sse
  # → Messages endpoint:     POST http://localhost:8000/messages/
  # → Streamable HTTP:       POST http://localhost:8000/mcp  (if transport=streamable-http)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.compiler import CompileError, HLFCompiler
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.bytecode import HLFBytecode, OPCODES
from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.rag.memory import RAGMemory
from hlf_mcp.instinct.lifecycle import InstinctLifecycle

# ── Server instance ────────────────────────────────────────────────────────────

_HOST = os.environ.get("HLF_HOST", "0.0.0.0")
_PORT = int(os.environ.get("HLF_PORT", "8000"))

mcp = FastMCP(
    name="HLF Hieroglyphic Logic Framework",
    instructions="""\
You are connected to the HLF (Hieroglyphic Logic Framework) MCP server.

HLF is a deterministic orchestration protocol that replaces natural language ambiguity
with a strictly-typed Hieroglyphic AST for zero-trust agent execution.

Key properties:
  - LALR(1) deterministic parsing — 100% reproducible execution paths
  - 12–30% token compression over equivalent NLP (tiktoken cl100k_base)
  - Cryptographic governance — SHA-256 / Merkle chain audit trail
  - Gas metering — bounded execution, no infinite loops
  - Cross-model alignment — any agent can read and emit valid HLF

Available tools:
  hlf_compile       — Parse HLF source → JSON AST + bytecode
  hlf_format        — Canonicalize HLF source (uppercase tags, trailing Ω)
  hlf_lint          — Static analysis: token budget, gas, variables, specs
  hlf_run           — Execute HLF in the stack-machine VM
  hlf_validate      — Quick syntax validation (true/false + details)
  hlf_benchmark     — Token compression analysis vs NLP equivalents
  hlf_disassemble   — Disassemble .hlb bytecode to human-readable assembly
  hlf_memory_store  — Store a fact in the Infinite RAG memory
  hlf_memory_query  — Semantic search over the Infinite RAG memory
  hlf_memory_stats  — Memory store statistics
  hlf_instinct_step — Advance an Instinct SDD lifecycle mission
  hlf_instinct_get  — Get current state of an Instinct mission
  hlf_benchmark_suite — Run full compression benchmark suite

Resources:
  hlf://grammar           — LALR(1) Lark grammar specification
  hlf://opcodes           — Bytecode opcode table (37 opcodes)
  hlf://host_functions    — Available host function registry
  hlf://examples/{name}   — Example HLF programs

Example HLF program (security audit):
  [HLF-v3]
  Δ analyze /security/seccomp.json
    Ж [CONSTRAINT] mode="ro"
    Ж [EXPECT] vulnerability_shorthand
    ⨝ [VOTE] consensus="strict"
  Ω
""",
    host=_HOST,
    port=_PORT,
)

# ── Module-level singletons ────────────────────────────────────────────────────

_compiler = HLFCompiler()
_formatter = HLFFormatter()
_linter = HLFLinter()
_runtime = HLFRuntime()
_bytecode = HLFBytecode()
_benchmark = HLFBenchmark()
_memory = RAGMemory()
_instinct = InstinctLifecycle()


# ── Tools ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def hlf_compile(source: str) -> dict[str, Any]:
    """Compile HLF source code to a JSON AST and bytecode.

    Parses using LALR(1) grammar and returns the full abstract syntax tree,
    SHA-256 integrity hash, gas estimate, and hex-encoded bytecode.

    Args:
        source: HLF source code (Unicode glyphs or ASCII keywords)
    """
    try:
        result = _compiler.compile(source)
        bc = _bytecode.encode(result["ast"])
        return {
            "status": "ok",
            "ast": result["ast"],
            "bytecode_hex": bc.hex(),
            "bytecode_size_bytes": len(bc),
            "node_count": result["node_count"],
            "gas_estimate": result["gas_estimate"],
            "version": result["version"],
            "errors": [],
        }
    except CompileError as exc:
        return {
            "status": "error",
            "ast": None,
            "bytecode_hex": None,
            "bytecode_size_bytes": 0,
            "node_count": 0,
            "gas_estimate": 0,
            "version": None,
            "errors": [{"message": str(exc), "line": exc.line, "col": exc.col}],
        }
    except Exception as exc:
        return {
            "status": "error",
            "ast": None,
            "bytecode_hex": None,
            "bytecode_size_bytes": 0,
            "node_count": 0,
            "gas_estimate": 0,
            "version": None,
            "errors": [{"message": str(exc), "line": 0, "col": 0}],
        }


@mcp.tool()
def hlf_format(source: str) -> dict[str, Any]:
    """Format HLF source to canonical form.

    Applies: uppercase tags, trailing Ω, sub-statement indentation (2 spaces),
    single-space separation, no whitespace drift, stripped comments.

    Args:
        source: Raw HLF source code (any formatting)
    """
    try:
        formatted = _formatter.format(source)
        diff = _formatter.diff_summary(source, formatted)
        return {"status": "ok", "formatted": formatted, "diff_summary": diff}
    except Exception as exc:
        return {"status": "error", "formatted": source, "diff_summary": str(exc)}


@mcp.tool()
def hlf_lint(source: str, gas_limit: int = 1000, token_limit: int = 30) -> dict[str, Any]:
    """Lint HLF source and return diagnostics.

    Checks: token budget, undefined variables, unused MEMORY, gas limit,
    duplicate SPEC_DEFINE tags, SPEC_SEAL without SPEC_DEFINE, missing header/Ω.

    Args:
        source: HLF source code
        gas_limit: Maximum allowed gas units (default 1000)
        token_limit: Per-line token budget (default 30)
    """
    diags = _linter.lint(source, gas_limit=gas_limit, token_limit=token_limit)
    return {
        "passed": all(d["level"] != "error" for d in diags),
        "diagnostics": diags,
        "error_count": sum(1 for d in diags if d["level"] == "error"),
        "warning_count": sum(1 for d in diags if d["level"] == "warning"),
        "info_count": sum(1 for d in diags if d["level"] == "info"),
    }


@mcp.tool()
def hlf_run(
    source: str,
    gas_limit: int = 1000,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute an HLF program in the stack-machine VM.

    Compiles source to .hlb bytecode and runs it through the 34-opcode VM.
    Returns execution trace, side effects, and gas used.

    Args:
        source: HLF source code
        gas_limit: Maximum gas units before halting (default 1000)
        variables: Initial variable bindings e.g. {"DEPLOYMENT_TIER": "hearth"}
    """
    try:
        result = _compiler.compile(source)
        if result.get("errors"):
            return {"status": "compile_error", "error": result["errors"], "gas_used": 0,
                    "trace": [], "side_effects": []}
        bc = _bytecode.encode(result["ast"])
        return _runtime.run(bc, gas_limit=gas_limit, variables=variables or {})
    except CompileError as exc:
        return {"status": "compile_error", "error": str(exc), "gas_used": 0,
                "trace": [], "side_effects": []}
    except Exception as exc:
        return {"status": "runtime_error", "error": str(exc), "gas_used": 0,
                "trace": [], "side_effects": []}


@mcp.tool()
def hlf_validate(source: str) -> dict[str, Any]:
    """Quickly validate HLF syntax without full compilation.

    Args:
        source: HLF source code
    """
    return _compiler.validate(source)


@mcp.tool()
def hlf_benchmark(source: str, compare_text: str | None = None, domain: str | None = None) -> dict[str, Any]:
    """Measure HLF token compression vs natural language.

    Uses tiktoken cl100k_base. Optionally compare against a provided NLP/JSON string
    or a named domain template (security_audit, hello_world, db_migration,
    content_delegation, log_analysis, stack_deployment).

    Args:
        source: HLF source code
        compare_text: Optional NLP/JSON string to compare against
        domain: Optional domain name for built-in NLP template
    """
    return _benchmark.analyze(source, compare_text=compare_text, domain=domain)


@mcp.tool()
def hlf_benchmark_suite() -> dict[str, Any]:
    """Run the full HLF benchmark suite against all 6 domain NLP templates.

    Returns compression ratios for: security_audit, hello_world, db_migration,
    content_delegation, log_analysis, stack_deployment.
    """
    return _benchmark.benchmark_suite()


@mcp.tool()
def hlf_disassemble(bytecode_hex: str) -> dict[str, Any]:
    """Disassemble HLF .hlb bytecode to human-readable assembly.

    Args:
        bytecode_hex: Hex-encoded .hlb bytecode (from hlf_compile result)
    """
    try:
        bc_bytes = bytes.fromhex(bytecode_hex.strip())
        result = _bytecode.disassemble(bc_bytes)
        return {"status": "ok", **result}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_memory_store(
    content: str,
    topic: str = "general",
    confidence: float = 1.0,
    provenance: str = "agent",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Store a fact in the Infinite RAG memory.

    Uses SHA-256 dedup and vector race protection (cosine>0.98) to prevent
    duplicate storage. Each write appends to the Merkle provenance chain.

    Args:
        content: Text content to store
        topic: Topic/category for retrieval grouping
        confidence: Confidence score 0.0–1.0
        provenance: Source identifier (agent name, tool, etc.)
        tags: Optional list of retrieval tags
    """
    return _memory.store(content, topic=topic, confidence=confidence,
                         provenance=provenance, tags=tags or [])


@mcp.tool()
def hlf_memory_query(
    query: str,
    top_k: int = 5,
    topic: str | None = None,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    """Query the Infinite RAG memory by semantic similarity.

    Performs cosine similarity search over stored fact vectors.
    Results are ranked by similarity and filtered by confidence.

    Args:
        query: Natural language or HLF query string
        top_k: Maximum results to return (default 5)
        topic: Optional topic filter
        min_confidence: Minimum confidence threshold (default 0.0)
    """
    return _memory.query(query, top_k=top_k, topic=topic, min_confidence=min_confidence)


@mcp.tool()
def hlf_memory_stats() -> dict[str, Any]:
    """Return Infinite RAG memory store statistics.

    Includes: total facts, Merkle chain depth, hot tier topics, top topics.
    """
    return _memory.stats()


@mcp.tool()
def hlf_instinct_step(
    mission_id: str,
    phase: str,
    payload: dict[str, Any] | None = None,
    override: bool = False,
    cove_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance an Instinct SDD lifecycle mission.

    Enforces: Specify → Plan → Execute → Verify → Merge
    Phase skips and backward transitions are blocked (use override=True to force).
    The Verify→Merge transition requires CoVE gate pass.

    Args:
        mission_id: Unique mission identifier (ULID or UUID recommended)
        phase: Target phase: specify | plan | execute | verify | merge
        payload: Phase-specific data to record
        override: Force backward/skip transitions (use with caution)
        cove_result: CoVE verification result dict with 'passed' boolean
    """
    return _instinct.step(
        mission_id, phase=phase, payload=payload or {},
        override=override, cove_result=cove_result,
    )


@mcp.tool()
def hlf_instinct_get(mission_id: str) -> dict[str, Any]:
    """Get the current state of an Instinct SDD mission.

    Args:
        mission_id: Mission identifier
    """
    mission = _instinct.get_mission(mission_id)
    if mission is None:
        return {"error": f"Mission '{mission_id}' not found", "mission_id": mission_id}
    from hlf_mcp.instinct.lifecycle import _ok_state
    return _ok_state(mission)


# ── Resources ──────────────────────────────────────────────────────────────────


@mcp.resource("hlf://grammar")
def get_grammar() -> str:
    """HLF grammar specification (LALR(1) Lark format)."""
    from hlf_mcp.hlf.grammar import HLF_GRAMMAR
    return HLF_GRAMMAR


@mcp.resource("hlf://opcodes")
def get_opcodes() -> str:
    """HLF bytecode opcode table (37 opcodes)."""
    return json.dumps(OPCODES, indent=2)


@mcp.resource("hlf://host_functions")
def get_host_functions() -> str:
    """Available HLF host function registry (28 functions)."""
    from hlf_mcp.hlf.runtime import HOST_FUNCTIONS
    return json.dumps(HOST_FUNCTIONS, indent=2)


@mcp.resource("hlf://examples/{name}")
def get_example(name: str) -> str:
    """Return a named example HLF program.

    Available names: hello_world, security_audit, delegation, routing,
                     db_migration, log_analysis, stack_deployment
    """
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures")
    path = os.path.join(fixtures_dir, f"{name}.hlf")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Example '{name}' not found. Available: hello_world, security_audit, delegation, routing, db_migration, log_analysis, stack_deployment")
    with open(path) as f:
        return f.read()


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    """Start the HLF MCP server with the configured transport."""
    transport = os.environ.get("HLF_TRANSPORT", "stdio").lower().strip()

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport in ("sse", "http"):
        mcp.run(transport="sse")
    elif transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        print(f"Unknown transport: {transport!r}. Use: stdio, sse, streamable-http", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
