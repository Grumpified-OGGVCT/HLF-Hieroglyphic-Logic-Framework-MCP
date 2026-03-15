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
from hlf_mcp.hlf.translator import english_to_hlf, hlf_to_english
from hlf_mcp.hlf import insaits
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.registry import HostFunctionRegistry
from hlf_mcp.hlf.tool_dispatch import ToolRegistry
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
  hlf_compile            — Parse HLF source → JSON AST + bytecode
  hlf_format             — Canonicalize HLF source (uppercase tags, trailing Ω)
  hlf_lint               — Static analysis: token budget, gas, variables, specs
  hlf_run                — Execute HLF in the stack-machine VM
  hlf_validate           — Quick syntax validation (true/false + details)
  hlf_benchmark          — Token compression analysis vs NLP equivalents
  hlf_disassemble        — Disassemble .hlb bytecode to human-readable assembly
  hlf_memory_store       — Store a fact in the Infinite RAG memory
  hlf_memory_query       — Semantic search over the Infinite RAG memory
  hlf_memory_stats       — Memory store statistics
  hlf_instinct_step      — Advance an Instinct SDD lifecycle mission
  hlf_instinct_get       — Get current state of an Instinct mission
  hlf_benchmark_suite    — Run full compression benchmark suite
  hlf_translate_to_hlf   — Convert English text to HLF source
  hlf_translate_to_english — Convert HLF source to English summary
  hlf_decompile_ast      — Decompile HLF source → structured English docs (AST)
  hlf_decompile_bytecode — Decompile HLF source → structured English docs (bytecode)
  hlf_capsule_validate   — Validate AST against intent capsule for a tier
  hlf_capsule_run        — Capsule-sandboxed compile + run
  hlf_host_functions     — List host functions available for a tier
  hlf_host_call          — Call a host function from the registry
  hlf_tool_list          — List tools from the ToolRegistry
  hlf_similarity_gate    — Compare two HLF programs for semantic similarity
  hlf_spec_lifecycle     — Manage an Instinct spec lifecycle mission

Resources:
  hlf://grammar                   — LALR(1) Lark grammar specification
  hlf://opcodes                   — Bytecode opcode table (37 opcodes)
  hlf://host_functions            — Available host function registry
  hlf://examples/{name}           — Example HLF programs
  hlf://governance/host_functions — governance/host_functions.json
  hlf://governance/bytecode_spec  — governance/bytecode_spec.yaml
  hlf://governance/align_rules    — governance/align_rules.json
  hlf://stdlib                    — Available stdlib modules

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

compiler = HLFCompiler()
formatter = HLFFormatter()
linter = HLFLinter()
_runtime = HLFRuntime()
bytecoder = HLFBytecode()
_benchmark = HLFBenchmark()
memory_store = RAGMemory()
instinct_mgr = InstinctLifecycle()
host_registry = HostFunctionRegistry()
tool_registry = ToolRegistry()

# Internal aliases kept for backward-compat with any imports referencing old names
_compiler = compiler
_formatter = formatter
_linter = linter
_bytecode = bytecoder
_memory = memory_store
_instinct = instinct_mgr


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
        result = compiler.compile(source)
        bc = bytecoder.encode(result["ast"])
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
        formatted = formatter.format(source)
        diff = formatter.diff_summary(source, formatted)
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
    diags = linter.lint(source, gas_limit=gas_limit, token_limit=token_limit)
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
        result = compiler.compile(source)
        if result.get("errors"):
            return {"status": "compile_error", "error": result["errors"], "gas_used": 0,
                    "trace": [], "side_effects": []}
        bc = bytecoder.encode(result["ast"])
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
    return compiler.validate(source)


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
        result = bytecoder.disassemble(bc_bytes)
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
    return memory_store.store(content, topic=topic, confidence=confidence,
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
    return memory_store.query(query, top_k=top_k, topic=topic, min_confidence=min_confidence)


@mcp.tool()
def hlf_memory_stats() -> dict[str, Any]:
    """Return Infinite RAG memory store statistics.

    Includes: total facts, Merkle chain depth, hot tier topics, top topics.
    """
    return memory_store.stats()


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
    return instinct_mgr.step(
        mission_id, phase=phase, payload=payload or {},
        override=override, cove_result=cove_result,
    )


@mcp.tool()
def hlf_instinct_get(mission_id: str) -> dict[str, Any]:
    """Get the current state of an Instinct SDD mission.

    Args:
        mission_id: Mission identifier
    """
    mission = instinct_mgr.get_mission(mission_id)
    if mission is None:
        return {"error": f"Mission '{mission_id}' not found", "mission_id": mission_id}
    from hlf_mcp.instinct.lifecycle import _ok_state
    return _ok_state(mission)


# ── New tools ──────────────────────────────────────────────────────────────────


@mcp.tool()
def hlf_translate_to_hlf(english_text: str, version: str = "3") -> dict[str, Any]:
    """Convert English instructions to HLF source code.

    Uses tone detection and heuristic action extraction to produce a valid
    HLF program from natural language. The version parameter controls the
    [HLF-vN] header emitted (default "3").

    Args:
        english_text: Natural language description of the desired program
        version: HLF version string (default "3")
    """
    try:
        source = english_to_hlf(english_text, version=version)
        return {"status": "ok", "source": source}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_translate_to_english(source: str) -> dict[str, Any]:
    """Convert HLF source code to a human-readable English summary.

    Compiles the source to obtain an AST (with human_readable fields populated
    by InsAIts), then calls insaits.decompile() to produce structured prose.

    Args:
        source: HLF source code
    """
    try:
        result = compiler.compile(source)
        summary = insaits.decompile(result["ast"])
        return {"status": "ok", "summary": summary}
    except CompileError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_decompile_ast(source: str) -> dict[str, Any]:
    """Compile HLF source and return structured English documentation from the AST.

    Uses insaits.decompile() which reads human_readable fields on every AST node
    and produces annotated prose output.

    Args:
        source: HLF source code
    """
    try:
        result = compiler.compile(source)
        docs = insaits.decompile(result["ast"])
        return {"status": "ok", "docs": docs, "ast": result["ast"]}
    except CompileError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_decompile_bytecode(source: str) -> dict[str, Any]:
    """Compile HLF source → encode to bytecode → disassemble → produce English docs.

    Pipeline: compile → encode → disassemble → insaits.decompile_bytecode()

    Args:
        source: HLF source code
    """
    try:
        result = compiler.compile(source)
        bc = bytecoder.encode(result["ast"])
        docs = insaits.decompile_bytecode(bc)
        return {"status": "ok", "docs": docs, "bytecode_hex": bc.hex()}
    except CompileError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_capsule_validate(source: str, tier: str = "hearth") -> dict[str, Any]:
    """Validate HLF source AST against the intent capsule for the given tier.

    Tiers: hearth (minimal), forge (moderate), sovereign (full).
    Returns a list of capability violations if any exist.

    Args:
        source: HLF source code
        tier: Execution tier — hearth | forge | sovereign (default hearth)
    """
    try:
        result = compiler.compile(source)
        capsule = capsule_for_tier(tier)
        stmts = result["ast"].get("statements", [])
        violations = capsule.validate_ast(stmts)
        return {
            "status": "ok",
            "tier": tier,
            "violations": violations,
            "passed": len(violations) == 0,
        }
    except CompileError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_capsule_run(
    source: str,
    tier: str = "hearth",
    gas_limit: int = 1000,
) -> dict[str, Any]:
    """Compile, capsule-validate, then execute HLF source within a sandboxed tier.

    Tiers: hearth (gas≤100), forge (gas≤500), sovereign (gas≤1000).
    Raises an error listing all capsule violations before executing.

    Args:
        source: HLF source code
        tier: Execution tier — hearth | forge | sovereign (default hearth)
        gas_limit: Maximum gas units (capped to tier maximum)
    """
    try:
        result = compiler.compile(source)
        capsule = capsule_for_tier(tier)
        stmts = result["ast"].get("statements", [])
        violations = capsule.validate_ast(stmts)
        if violations:
            return {
                "status": "capsule_violation",
                "tier": tier,
                "violations": violations,
            }
        effective_gas = min(gas_limit, capsule.max_gas)
        bc = bytecoder.encode(result["ast"])
        run_result = _runtime.run(bc, gas_limit=effective_gas)
        run_result["tier"] = tier
        return run_result
    except CompileError as exc:
        return {"status": "compile_error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_host_functions(tier: str = "hearth") -> dict[str, Any]:
    """List host functions available for the given execution tier.

    Args:
        tier: Execution tier — hearth | forge | sovereign (default hearth)
    """
    try:
        functions = host_registry.list_for_tier(tier)
        return {"status": "ok", "tier": tier, "functions": functions, "count": len(functions)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_host_call(
    function_name: str,
    args_json: str = "[]",
    tier: str = "hearth",
) -> dict[str, Any]:
    """Call a host function from the registry.

    Parses args_json as a JSON array and dispatches to the named host function.
    The tier is used for access-control validation.

    Args:
        function_name: Name of the host function (e.g. "fs_read")
        args_json: JSON-encoded argument list (default "[]")
        tier: Execution tier for access control (default hearth)
    """
    try:
        args = json.loads(args_json)
        if not isinstance(args, list):
            return {"status": "error", "error": "args_json must be a JSON array"}
        result = host_registry.call(function_name, args, tier)
        return {"status": "ok", "result": result}
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"Invalid args_json: {exc}"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_tool_list() -> dict[str, Any]:
    """List all tools registered in the HLF ToolRegistry.

    Returns tool names, lifecycle states, and metadata from tool_registry.json.
    """
    try:
        tools = tool_registry.list_tools()
        return {"status": "ok", "tools": tools, "count": len(tools)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_similarity_gate(source_a: str, source_b: str) -> dict[str, Any]:
    """Compare two HLF programs for semantic similarity using InsAIts similarity gate.

    Compiles both programs, extracts their human-readable text, and computes
    a cosine similarity score over token frequency vectors.

    Args:
        source_a: First HLF source program
        source_b: Second HLF source program
    """
    try:
        result_a = compiler.compile(source_a)
        result_b = compiler.compile(source_b)
        text_a = insaits.decompile(result_a["ast"])
        text_b = insaits.decompile(result_b["ast"])
        score = insaits.similarity_gate(text_a, text_b)
        return {"status": "ok", "similarity": score}
    except CompileError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@mcp.tool()
def hlf_spec_lifecycle(
    mission_id: str,
    phase: str,
    action: str = "advance",
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Manage an Instinct spec lifecycle mission through SPECIFY→PLAN→EXECUTE→VERIFY→MERGE.

    Wraps instinct_mgr.step() with spec-oriented phase naming and returns the
    mission state dict. Use action="advance" to move forward or action="get" to
    read the current state without advancing.

    Args:
        mission_id: Unique mission identifier
        phase: One of: SPECIFY | PLAN | EXECUTE | VERIFY | MERGE
        action: "advance" (default) to step the phase, "get" to read state only
        evidence: Optional phase payload / evidence dict
    """
    _VALID_PHASES = {"SPECIFY", "PLAN", "EXECUTE", "VERIFY", "MERGE"}
    phase_upper = phase.upper()
    if phase_upper not in _VALID_PHASES:
        return {
            "status": "error",
            "error": f"Invalid phase {phase!r}. Must be one of: {', '.join(sorted(_VALID_PHASES))}",
        }

    if action == "get":
        mission = instinct_mgr.get_mission(mission_id)
        if mission is None:
            return {"status": "error", "error": f"Mission '{mission_id}' not found"}
        from hlf_mcp.instinct.lifecycle import _ok_state
        return {"status": "ok", "mission": _ok_state(mission)}

    try:
        result = instinct_mgr.step(
            mission_id,
            phase=phase_upper.lower(),
            payload=evidence or {},
        )
        return {"status": "ok", "mission": result}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Resources ──────────────────────────────────────────────────────────────────

_GOVERNANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "governance")


def _read_governance_file(filename: str) -> str:
    """Read a governance file, falling back to a clear error payload if absent.

    In a wheel-installed package the top-level ``governance/`` directory is
    not included by default (it lives outside ``hlf_mcp``).  Rather than
    raising an unhandled FileNotFoundError to MCP clients, return a structured
    JSON payload explaining where to find the file.  Operators should either
    install from source or add governance/ as package data.
    """
    path = os.path.join(_GOVERNANCE_DIR, filename)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return json.dumps({
        "error": "governance_file_not_found",
        "file": filename,
        "hint": (
            "The governance/ directory is not bundled in wheel installs. "
            "Install from source (`pip install -e .`) or mount the directory "
            "to the container's working directory."
        ),
    }, indent=2)


def _read_fixture_file(name: str) -> str:
    """Read a fixture .hlf file, with informative error on miss."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "fixtures", f"{name}.hlf"),
        os.path.join(os.path.dirname(__file__), "fixtures", f"{name}.hlf"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
    available = "hello_world, security_audit, delegation, routing, db_migration, log_analysis, stack_deployment"
    raise FileNotFoundError(
        f"Example '{name}' not found. Available: {available}"
    )


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
    return _read_fixture_file(name)


@mcp.resource("hlf://governance/host_functions")
def get_governance_host_functions() -> str:
    """Governance host_functions.json — full host function definitions."""
    return _read_governance_file("host_functions.json")


@mcp.resource("hlf://governance/bytecode_spec")
def get_governance_bytecode_spec() -> str:
    """Governance bytecode_spec.yaml — bytecode encoding specification."""
    return _read_governance_file("bytecode_spec.yaml")


@mcp.resource("hlf://governance/align_rules")
def get_governance_align_rules() -> str:
    """Governance align_rules.json — alignment and safety rules."""
    return _read_governance_file("align_rules.json")


@mcp.resource("hlf://stdlib")
def get_stdlib() -> str:
    """List all available HLF stdlib modules."""
    stdlib_dir = os.path.join(os.path.dirname(__file__), "hlf", "stdlib")
    if not os.path.isdir(stdlib_dir):
        return json.dumps({"modules": []})
    modules = sorted(
        name[:-3]
        for name in os.listdir(stdlib_dir)
        if name.endswith(".py") and not name.startswith("_")
    )
    return json.dumps({"modules": modules}, indent=2)


# ── Health endpoint (HTTP transports only) ────────────────────────────────────

def _make_health_app(mcp_app: Any) -> Any:
    """Wrap the MCP ASGI app with a /health liveness probe.

    Docker and docker-compose health checks need a plain HTTP GET /health → 200
    that can be queried before the MCP handshake completes.  We mount a tiny
    Starlette route in front of the MCP ASGI application so both live under
    the same uvicorn process.
    """
    try:
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Mount, Route

        async def health(request: Request) -> JSONResponse:
            return JSONResponse({
                "status": "ok",
                "transport": os.environ.get("HLF_TRANSPORT", "stdio"),
            })

        return Starlette(routes=[
            Route("/health", health),
            Mount("/", app=mcp_app),
        ])
    except ImportError:
        # Starlette not available (stdio-only installs) — skip health wrapper
        return mcp_app


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    """Start the HLF MCP server with the configured transport."""
    transport = os.environ.get("HLF_TRANSPORT", "stdio").lower().strip()
    host = os.environ.get("HLF_HOST", "0.0.0.0")
    port = int(os.environ.get("HLF_PORT", "8000"))

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport in ("sse", "http"):
        import uvicorn
        app = _make_health_app(mcp.sse_app())
        uvicorn.run(app, host=host, port=port)
    elif transport == "streamable-http":
        import uvicorn
        app = _make_health_app(mcp.streamable_http_app())
        uvicorn.run(app, host=host, port=port)
    else:
        print(f"Unknown transport: {transport!r}. Use: stdio, sse, streamable-http", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
