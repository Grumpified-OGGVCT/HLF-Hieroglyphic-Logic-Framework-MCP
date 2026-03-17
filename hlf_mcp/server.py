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
import logging
import os
import sys
from typing import Any

_log = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.server_capsule import register_capsule_tools
from hlf_mcp.server_context import build_server_context, check_governance_manifest
from hlf_mcp.server_instinct import register_instinct_tools
from hlf_mcp.server_memory import register_memory_tools
from hlf_mcp.server_resources import register_resources
from hlf_mcp.server_translation import register_translation_tools

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  HLF EXPLAINED TO A 5TH GRADER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHAT IS IT?
  Imagine you want to send instructions to a robot friend. You could write a
  long paragraph in English — but your robot might misread it, get confused by
  a double meaning, or do something slightly different every time.

  HLF is like inventing your own tiny robot language made of special symbols
  (Δ Ж ⨝ ⌘ ∇ ⩕ ⊎ Ω) instead of long sentences. Every symbol means exactly
  one thing — no guessing, no ambiguity, same answer every single time.

HOW DOES IT WORK? (the pipeline, step by step)
  1. You write an HLF program using glyphs (special symbols) and tags like
     [INTENT], [CONSTRAINT], [EXPECT].  You can also write plain ASCII words
     like ANALYZE or ENFORCE — those get swapped for the right glyph
     automatically (that's called the ASCII surface / Pass 0 normalization).

  2. A SUPER-STRICT grammar (LALR(1)) reads the program.  Think of it like a
     grammar-checker that won't let a single typo slide.  If the grammar says
     "no", the whole thing stops — no partial results, no surprises.

  3. The Ethics Governor runs before anything else executes.  It's like a hall
     monitor that blocks dangerous instructions (e.g. "delete everything",
     "ignore my safety rules") before the robot ever touches them.
     Set HLF_STRICT=0 to let the governor warn instead of blocking — useful
     when you're experimenting and want to see violations without hard-stops.

  4. The compiler turns the program into a tiny bytecode stack machine (like
     Minecraft redstone logic, but for agents).  Gas metering counts every
     operation — once the gas runs out the VM stops, so you can NEVER have an
     infinite loop eating up resources forever.

  5. The output is a JSON AST (a tree of facts) with a SHA-256 fingerprint.
     That fingerprint is like a wax seal on a letter — if anyone tampers with
     the instructions, the seal breaks and you know immediately.

  6. A SHA-256 cache remembers recent programs.  If you send the exact same
     program twice, the second time skips all the work and returns the cached
     result instantly — like having the answer already written on a cheat sheet.

  7. The hlf_submit_ast fast lane lets you skip the text parsing entirely if
     you already have a valid JSON AST.  Useful for programmatic generators
     and polyglot transpilers that build HLF trees directly in code.

THE SPECIAL SYMBOLS (glyphs) AND WHAT THEY MEAN
  Δ  ANALYZE  — "think about / reason over this"
  Ж  ENFORCE  — "this is a hard rule, no exceptions"
  ⨝  JOIN     — "reach consensus / merge results from multiple sources"
  ⌘  CMD      — "delegate this task to a sub-agent or tool"
  ∇  SOURCE   — "pull data from this source"
  ⩕  PRIORITY — "this matters more than other things at the same level"
  ⊎  BRANCH   — "split here, run parallel paths"
  Ω  END      — "program is complete, stop here"

THE PERKS (why bother learning robot-glyphs?)
  • Reproducible — run the same program 1,000 times, get the same result.
    No LLM "creativity" sneaking in at execution time.
  • Compact — 12–30% fewer tokens than writing the same thing in English.
    On large agent pipelines that saves real money and real speed.
  • Safe — the Ethics Governor + gas metering + ALIGN Ledger mean you can
    deploy agents in zero-trust environments and sleep soundly.
  • Multilingual — the tag registry (tag_i18n.yaml) knows your tags in
    English, French, Spanish, German, Chinese, Japanese, Arabic, and
    Portuguese.  The compiler folds them all to the same canonical form.
  • Auditable — every compile produces a SHA-256 hash and an align-violations
    list.  Governance files are hashed into MANIFEST.sha256 and checked at
    startup, so drift is caught immediately.
  • Docker-friendly — spin up with just `docker compose up` (default) or add
    `--profile hot` to get a Valkey hot cache tier for sub-millisecond
    repeat-compile latency.  All images are official Docker Hub releases,
    user-installable, no vendor lock-in.
  • Model-agnostic — any AI model that can read text can read HLF.  The
    hlf_translate_to_hlf / hlf_translate_to_english tools bridge the gap for
    models that haven't learned the glyphs yet.

WHEN HLF IS THE WRONG TOOL (be honest about the limits)
  ✗ Creative / open-ended generation — if you need the model to write a poem,
    brainstorm 10 startup ideas, or have a friendly conversation, HLF adds
    friction with zero benefit.  Just use natural language.

  ✗ One-off scripts where you own the whole stack — if no other agent will ever
    read your output, the overhead of learning a new syntax is not worth it.

  ✗ Rapid solo prototyping — sketching a quick idea?  Markdown and pseudocode
    are faster to write and easier to throw away.  Reach for HLF once the idea
    is worth hardening.

  ✗ Highly dynamic free-form data — HLF is great at structured orchestration,
    but if your payload is a web-scraped article, a PDF, or a raw image
    description, the structured glyph layer adds nothing.  Store it in RAG
    memory and reference it by key instead.

  ✗ Teams with no tooling buy-in — HLF payoff compounds when every agent in
    the pipeline speaks the same language.  A single holdout that outputs plain
    English breaks the determinism chain.  Either onboard the team or stay NL.

  ✗ Latency-critical inference edges (sub-10 ms) — the LALR(1) parse +
    governor is fast (~0.5–2 ms on warm cache), but if you are hitting hard
    real-time constraints (robotics, high-frequency trading) even that budget
    matters.  Use hlf_submit_ast fast-lane or the in-process cache and
    benchmark your specific case.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Available tools:
    hlf_do                 - Plain-English front door: English in, governed HLF out
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
  hlf_submit_ast         — Fast-lane: validate pre-built JSON AST (skip parse)

Resources:
  hlf://grammar                   — LALR(1) Lark grammar specification
  hlf://opcodes                   — Bytecode opcode table (37 opcodes)
  hlf://host_functions            — Available host function registry
  hlf://examples/{name}           — Example HLF programs
  hlf://governance/host_functions — governance/host_functions.json
  hlf://governance/bytecode_spec  — governance/bytecode_spec.yaml
  hlf://governance/align_rules    — governance/align_rules.json
  hlf://governance/tag_i18n       — Multilingual tag registry (8 languages)
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

_ctx = build_server_context()
compiler = _ctx.compiler
formatter = _ctx.formatter
linter = _ctx.linter
_runtime = _ctx.runtime
bytecoder = _ctx.bytecoder
_benchmark = _ctx.benchmark
memory_store = _ctx.memory_store
instinct_mgr = _ctx.instinct_mgr
host_registry = _ctx.host_registry
tool_registry = _ctx.tool_registry

# ── Governance manifest integrity check ───────────────────────────────────────

check_governance_manifest(_log)

# Internal aliases kept for backward-compat with any imports referencing old names
_compiler = compiler
_formatter = formatter
_linter = linter
_bytecode = bytecoder
_memory = memory_store
_instinct = instinct_mgr


# ── Tools ──────────────────────────────────────────────────────────────────────
globals().update(register_translation_tools(mcp, _ctx))
globals().update(register_memory_tools(mcp, _ctx))
globals().update(register_instinct_tools(mcp, _ctx))
globals().update(register_capsule_tools(mcp, _ctx))


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
        runtime_variables = variables or {}
        return _runtime.run(
            bc,
            gas_limit=gas_limit,
            variables=runtime_variables,
            ast=result["ast"],
            source=source,
            tier=str(runtime_variables.get("DEPLOYMENT_TIER", "hearth")),
        )
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
def hlf_submit_ast(ast_json: str) -> dict[str, Any]:
    """Fast-lane AST submission: skip LALR parse for pre-built JSON ASTs.

    Accepts a JSON AST (e.g. produced by a polyglot transpiler or exported by
    hlf_compile on a previous call), runs ALIGN Ledger validation and the
    Ethics Governor only, and returns the validated result.

    This is the recommended entry point for programmatic HLF generation where
    the source text is synthesised externally and the full parse is unnecessary.

    Args:
        ast_json: JSON string of a valid HLF AST dict (must include "statements"
                  and optionally "version" keys)
    """
    try:
        ast = json.loads(ast_json)
    except json.JSONDecodeError as exc:
        return {"status": "error", "error": f"Invalid JSON: {exc}"}
    if not isinstance(ast, dict) or "statements" not in ast:
        return {"status": "error", "error": '"statements" key required in AST'}

    from hlf_mcp.hlf.compiler import _estimate_gas, _pass3_align_validate
    stmts = ast.get("statements", [])
    env: dict[str, Any] = {}
    try:
        from hlf_mcp.hlf.ethics.governor import GovernorError, check as _ethics_check
        import os as _os
        _gov_result = _ethics_check(ast=ast, env=env, source="", tier="hearth")
        _strict = _os.environ.get("HLF_STRICT", "1") != "0"
        if not _gov_result.passed:
            term = _gov_result.termination
            if term is not None:
                msg = (
                    f"Ethics Governor [{term.trigger}]: {term.message}\n"
                    f"Audit ID: {term.audit_id}"
                )
                if _strict:
                    return {"status": "blocked", "error": msg}
                _log.warning("[HLF_STRICT=0] Governor suppressed: %s", msg)
            elif _strict:
                return {"status": "blocked", "error": "; ".join(_gov_result.blocks)}
            else:
                _log.warning("[HLF_STRICT=0] Governor blocks: %s", "; ".join(_gov_result.blocks))
    except GovernorError as exc:
        return {"status": "blocked", "error": str(exc)}
    except Exception as exc:  # pragma: no cover
        return {"status": "blocked", "error": f"Governor error (fail-closed): {exc}"}

    try:
        violations = _pass3_align_validate(stmts, strict=compiler.strict_align)
    except CompileError as exc:
        return {"status": "blocked", "error": str(exc)}

    gas = _estimate_gas(stmts)
    return {
        "status": "ok",
        "node_count": len(stmts),
        "gas_estimate": gas,
        "align_violations": violations,
    }


register_resources(mcp)


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
