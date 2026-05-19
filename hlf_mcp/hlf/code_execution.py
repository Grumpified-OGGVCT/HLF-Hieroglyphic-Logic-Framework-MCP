from __future__ import annotations

import ast as py_ast
import hashlib
import json
from typing import Any

from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.formal_verifier import (
    FormalVerifier,
    VerificationGate,
    GateDecision,
    VerificationBlockedError,
)
from hlf_mcp.hlf.governance_proofs import (
    build_anchor,
    build_governance_proof,
    governance_body,
    sha256_digest,
)
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.two_channel_executor import (
    TwoChannelExecutor,
    DataChannel,
    build_data_channel,
)

_HLF_LANGUAGES = {"hlf", "hlf-v3", "hieroglyphic-logic-framework"}


def execute_code_bearing_hlf(
    source: str,
    *,
    entrypoint: str = "",
    gas_limit: int = 500,
    tier: str = "hearth",
    variables: dict[str, Any] | None = None,
    dry_run: bool = False,
    compiler: HLFCompiler | None = None,
    linter: HLFLinter | None = None,
    verifier: FormalVerifier | None = None,
    runtime: HLFRuntime | None = None,
    bytecoder: HLFBytecode | None = None,
    audit_logger: Any | None = None,
) -> dict[str, Any]:
    """Compile, verify, and bounded-run code-bearing HLF blocks.

    This deliberately executes only HLF VM bytecode. Non-HLF language payloads
    are compiled and reported as governed artifacts, but are not executed.
    """

    compiler = compiler or HLFCompiler()
    linter = linter or HLFLinter()
    verifier = verifier or FormalVerifier()
    runtime = runtime or HLFRuntime()
    bytecoder = bytecoder or HLFBytecode()
    trace_ref = _trace_ref(source, entrypoint, gas_limit, dry_run)

    try:
        compile_result = compiler.compile(source)
    except Exception as exc:
        return _blocked_result(
            status="compile_error",
            trace_ref=trace_ref,
            message=str(exc),
            compiled=False,
            code=1,
        )

    ast = compile_result["ast"]
    diagnostics = linter.lint(source, gas_limit=gas_limit)
    lint_errors = [diag for diag in diagnostics if diag.get("level") == "error"]
    verification_report_obj = verifier.verify_ast(ast, gas_budget=gas_limit)
    verification_report = verification_report_obj.to_dict()
    gate_decision = VerificationGate.gate(verification_report_obj, tier)

    audit_start = _audit(
        audit_logger,
        "hlf_code_bearing_compile",
        {
            "trace_ref": trace_ref,
            "entrypoint": entrypoint,
            "gas_limit": gas_limit,
            "ast_sha256": ast.get("sha256", ""),
            "gate_decision": gate_decision,
            "tier": tier,
            "lint_error_count": len(lint_errors),
        },
    )

    blocks = _collect_code_blocks(ast)
    selected = _select_block(blocks, entrypoint)
    base_trace = {
        "trace_ref": trace_ref,
        "compile": {
            "version": compile_result.get("version"),
            "node_count": compile_result.get("node_count", 0),
            "gas_estimate": compile_result.get("gas_estimate", 0),
            "ast_sha256": ast.get("sha256", ""),
        },
        "lint": {"diagnostics": diagnostics, "error_count": len(lint_errors)},
        "verification": verification_report,
        "audit": {"compile": audit_start},
    }

    if lint_errors:
        return _blocked_result(
            status="lint_error",
            trace_ref=trace_ref,
            message="Lint errors blocked code-bearing execution.",
            trace=base_trace,
            blocks=blocks,
            code=1,
        )
    if gate_decision == GateDecision.BLOCK:
        blocked_error = VerificationBlockedError(verification_report_obj, tier)
        return _blocked_result(
            status="verification_blocked",
            trace_ref=trace_ref,
            message=str(blocked_error),
            trace=base_trace,
            blocks=blocks,
            code=1,
        )
    if gate_decision == GateDecision.WARN:
        # Log warning but proceed — the gate says WARN
        if audit_logger and hasattr(audit_logger, "log"):
            audit_logger.log(
                "hlf_verification_warning",
                {
                    "trace_ref": trace_ref,
                    "tier": tier,
                    "blocked_count": verification_report_obj.blocked_count,
                    "summary": verification_report_obj.summary(),
                },
                agent_role="code_bearing_hlf",
            )
    if selected is None:
        message = (
            f"No code-bearing block matched entrypoint '{entrypoint}'."
            if entrypoint
            else "No MODULE, FUNCTION, or [CODE] block was found."
        )
        return _blocked_result(
            status="no_code_blocks",
            trace_ref=trace_ref,
            message=message,
            trace=base_trace,
            blocks=blocks,
            code=1,
        )

    if dry_run:
        return _success_result(
            status="dry_run_ok",
            trace_ref=trace_ref,
            selected=selected,
            executed=False,
            sandbox_mode="hlf-vm-dry-run",
            runtime_result=None,
            trace=base_trace,
            blocks=blocks,
            audit_logger=audit_logger,
            gate_decision=gate_decision,
        )

    try:
        runnable_ast = _runnable_ast_for_block(selected, compiler)
    except Exception as exc:
        return _blocked_result(
            status="code_compile_error",
            trace_ref=trace_ref,
            message=f"Selected code block could not be compiled as HLF: {exc}",
            trace=base_trace,
            blocks=blocks,
            code=1,
        )
    if runnable_ast is None:
        return _success_result(
            status="unsupported_language",
            trace_ref=trace_ref,
            selected=selected,
            executed=False,
            sandbox_mode="compile-only-non-hlf-code",
            runtime_result={
                "status": "not_executed",
                "reason": "Only HLF code payloads are executed by the packaged sandbox.",
            },
            trace=base_trace,
            blocks=blocks,
            audit_logger=audit_logger,
            gate_decision=gate_decision,
            code=1,
        )

    try:
        bytecode = bytecoder.encode(runnable_ast)
        run_result = runtime.run(
            bytecode,
            gas_limit=gas_limit,
            variables=variables or {},
            ast=runnable_ast,
            source="",
            tier=tier,
            audit_logger=audit_logger,
        )
    except Exception as exc:
        run_result = {"status": "error", "error": str(exc), "result": None}
    executed = run_result.get("status") == "ok"
    return _success_result(
        status="ok" if executed else "runtime_error",
        trace_ref=trace_ref,
        selected=selected,
        executed=executed,
        sandbox_mode="hlf-vm-bytecode",
        runtime_result=run_result,
        trace=base_trace,
        blocks=blocks,
        audit_logger=audit_logger,
        gate_decision=gate_decision,
        code=0 if executed else 1,
    )


def _collect_code_blocks(ast: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []

    def visit(node: Any, parent: str = "") -> None:
        if not isinstance(node, dict):
            return
        kind = node.get("kind")
        if kind in {"module_block_stmt", "func_block_stmt"}:
            block = {
                "block_type": "module" if kind == "module_block_stmt" else "function",
                "name": str(node.get("name") or ""),
                "parent": parent,
                "language": "hlf",
                "runnable": True,
                "statement_count": len((node.get("body") or {}).get("statements", [])),
                "node": node,
            }
            blocks.append(block)
            next_parent = block["name"] or parent
            for child in (node.get("body") or {}).get("statements", []):
                visit(child, next_parent)
            return
        if kind == "glyph_stmt" and str(node.get("tag") or "").upper() == "CODE":
            args = _args_to_dict(node.get("arguments", []))
            language = str(args.get("language") or args.get("lang") or "hlf").lower()
            body = str(args.get("body") or args.get("code") or "")
            name = str(args.get("name") or f"code_{len(blocks) + 1}")
            blocks.append(
                {
                    "block_type": "code",
                    "name": name,
                    "parent": parent,
                    "language": language,
                    "runnable": language in _HLF_LANGUAGES,
                    "body": body,
                    "statement_count": 0,
                    "node": node,
                }
            )
        for key in ("statements", "body"):
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    visit(item, parent)
            elif isinstance(child, dict):
                for item in child.get("statements", []):
                    visit(item, parent)

    for statement in ast.get("statements", []):
        visit(statement)
    return blocks


def _select_block(blocks: list[dict[str, Any]], entrypoint: str) -> dict[str, Any] | None:
    if entrypoint:
        for block in blocks:
            if block.get("name") == entrypoint:
                return block
        return None
    for block in blocks:
        if block.get("block_type") == "function" and block.get("name") in {"main", "run"}:
            return block
    return blocks[0] if blocks else None


def _runnable_ast_for_block(
    block: dict[str, Any],
    compiler: HLFCompiler,
) -> dict[str, Any] | None:
    if not block.get("runnable"):
        return None
    if block.get("block_type") in {"module", "function"}:
        statements = ((block.get("node") or {}).get("body") or {}).get("statements", [])
        return {"kind": "program", "version": "3", "statements": list(statements)}
    body = str(block.get("body") or "").strip()
    if not body:
        return {"kind": "program", "version": "3", "statements": []}
    nested_source = body if body.startswith("[HLF-v") else f"[HLF-v3]\n{body}\nΩ\n"
    return compiler.compile(nested_source)["ast"]


def _args_to_dict(args: list[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arg in args:
        if not isinstance(arg, dict):
            continue
        if arg.get("kind") == "kv_arg":
            result[str(arg.get("name"))] = _value(arg.get("value"))
        elif arg.get("kind") == "pos_arg":
            result.setdefault("body", _value(arg.get("value")))
    return result


def _value(value: Any) -> Any:
    if isinstance(value, dict) and value.get("kind") == "value":
        scalar = value.get("value")
        if value.get("type") == "string" and isinstance(scalar, str):
            try:
                return py_ast.literal_eval(f'"{scalar}"')
            except (SyntaxError, ValueError):
                return scalar
        return scalar
    return value


def _success_result(
    *,
    status: str,
    trace_ref: str,
    selected: dict[str, Any],
    executed: bool,
    sandbox_mode: str,
    runtime_result: dict[str, Any] | None,
    trace: dict[str, Any],
    blocks: list[dict[str, Any]],
    audit_logger: Any | None,
    gate_decision: str = GateDecision.PROCEED,
    code: int = 0,
) -> dict[str, Any]:
    message = _result_message(status, trace_ref, selected, executed, runtime_result)
    verified = gate_decision != GateDecision.BLOCK
    audit = _audit(
        audit_logger,
        "hlf_code_bearing_result",
        {
            "trace_ref": trace_ref,
            "status": status,
            "selected_block": _public_block(selected),
            "executed": executed,
            "sandbox_mode": sandbox_mode,
        },
    )
    trace = {**trace, "audit": {**dict(trace.get("audit") or {}), "result": audit}}
    result = {
        "status": status,
        "compiled": True,
        "verified": verified,
        "gate_decision": gate_decision,
        "executed": executed,
        "sandbox_mode": sandbox_mode,
        "trace_ref": trace_ref,
        "blocks": [_public_block(block) for block in blocks],
        "selected_block": _public_block(selected),
        "runtime": runtime_result,
        "trace": trace,
        "hlf_result": _hlf_result(code, message),
        "result_artifact": {
            "kind": "RESULT",
            "code": code,
            "message": message,
            "trace_ref": trace_ref,
            "audit_ref": (audit or {}).get("trace_id") if isinstance(audit, dict) else None,
            "governed": True,
        },
    }
    result["governance_proof"] = _code_governance_proof(result)
    result["result_artifact"]["governance_proof_ref"] = result["governance_proof"].get("chain_head")
    return result


def execute_two_channel_hlf(
    source: str,
    *,
    entrypoint: str = "",
    gas_limit: int = 500,
    tier: str = "hearth",
    variables: dict[str, Any] | None = None,
    capabilities: set[str] | None = None,
    dry_run: bool = False,
    compiler: HLFCompiler | None = None,
    linter: HLFLinter | None = None,
    verifier: FormalVerifier | None = None,
    runtime: HLFRuntime | None = None,
    bytecoder: HLFBytecode | None = None,
    audit_logger: Any | None = None,
) -> dict[str, Any]:
    """Compile, verify, and execute HLF via the two-channel model.

    This is the Phase 6 execution path: instructions (compile-time, immutable,
    signed) are separated from data (runtime, provenance-tracked).  Every
    input carries a ProvenanceChain recording its source, trust, and
    transformation history.

    The two-channel path runs alongside the existing single-channel
    execute_code_bearing_hlf() — both paths are supported.
    """
    compiler = compiler or HLFCompiler()
    linter = linter or HLFLinter()
    verifier = verifier or FormalVerifier()
    runtime = runtime or HLFRuntime()
    bytecoder = bytecoder or HLFBytecode()

    # Build data channel with provenance
    data = build_data_channel(
        inputs=variables or {},
        capabilities=capabilities or set(),
        default_source="agent",
        default_trust=0.95,
    )

    trace_ref = _trace_ref(source, entrypoint, gas_limit, dry_run)

    try:
        instruction = compiler.compile_to_instruction_channel(
            source,
            tier=tier,
            bytecoder=bytecoder,
            verifier=verifier,
            gas_limit=gas_limit,
        )
    except Exception as exc:
        return _blocked_result(
            status="compile_error",
            trace_ref=trace_ref,
            message=str(exc),
            compiled=False,
            code=1,
        )

    # Lint check
    diagnostics = linter.lint(source, gas_limit=gas_limit)
    lint_errors = [diag for diag in diagnostics if diag.get("level") == "error"]
    if lint_errors:
        return _blocked_result(
            status="lint_error",
            trace_ref=trace_ref,
            message="Lint errors blocked two-channel execution.",
            code=1,
        )

    # Collect and select code block
    compile_result = compiler.compile(source)
    ast = compile_result["ast"]
    blocks = _collect_code_blocks(ast)
    selected = _select_block(blocks, entrypoint)

    if selected is None:
        message = (
            f"No code-bearing block matched entrypoint '{entrypoint}'."
            if entrypoint
            else "No MODULE, FUNCTION, or [CODE] block was found."
        )
        return _blocked_result(
            status="no_code_blocks",
            trace_ref=trace_ref,
            message=message,
            trace={"blocks": blocks},
            blocks=blocks,
            code=1,
        )

    if dry_run:
        return {
            "status": "dry_run_ok",
            "compiled": True,
            "verified": True,
            "gate_decision": GateDecision.PROCEED,
            "executed": False,
            "sandbox_mode": "two-channel-dry-run",
            "trace_ref": trace_ref,
            "blocks": [_public_block(block) for block in blocks],
            "selected_block": _public_block(selected),
            "runtime": None,
            "instruction_channel": instruction.to_dict(),
            "data_channel": data.to_dict(),
            "two_channel": True,
            "hlf_result": _hlf_result(0, f"Two-channel dry run: {trace_ref}"),
            "result_artifact": {
                "kind": "RESULT",
                "code": 0,
                "message": f"Two-channel dry run: {trace_ref}",
                "trace_ref": trace_ref,
                "governed": True,
                "model": "two-channel",
            },
        }

    # Two-channel execution
    executor = TwoChannelExecutor(
        verifier=verifier,
        runtime=runtime,
        audit_logger=audit_logger,
    )

    exec_result = executor.execute(
        instruction=instruction,
        data=data,
        tier=tier,
        gas_limit=gas_limit,
    )

    # Build response
    result = {
        "status": exec_result.status,
        "compiled": True,
        "verified": exec_result.gate_decision != GateDecision.BLOCK,
        "gate_decision": exec_result.gate_decision,
        "instruction_intact": exec_result.instruction_intact,
        "executed": exec_result.executed,
        "sandbox_mode": "two-channel-bytecode" if exec_result.executed else "two-channel-blocked",
        "trace_ref": trace_ref,
        "blocks": [_public_block(block) for block in blocks],
        "selected_block": _public_block(selected),
        "runtime": exec_result.runtime_result,
        "instruction_channel": instruction.to_dict(),
        "data_channel": data.to_dict(),
        "provenance": {
            name: chain.to_dict() for name, chain in exec_result.provenance.items()
        },
        "provenance_hashes": dict(exec_result.provenance_hashes),
        "two_channel": True,
        "hlf_result": _hlf_result(
            0 if exec_result.executed else 1,
            f"Two-channel: {exec_result.status}; trace={trace_ref}",
        ),
        "result_artifact": {
            "kind": "RESULT",
            "code": 0 if exec_result.executed else 1,
            "message": f"Two-channel: {exec_result.status}; trace={trace_ref}",
            "trace_ref": trace_ref,
            "governed": True,
            "model": "two-channel",
            "instruction_intact": exec_result.instruction_intact,
            "manifest_ok": exec_result.manifest_ok,
        },
    }

    if exec_result.error_message:
        result["error"] = exec_result.error_message

    return result


def _blocked_result(
    *,
    status: str,
    trace_ref: str,
    message: str,
    compiled: bool = True,
    trace: dict[str, Any] | None = None,
    blocks: list[dict[str, Any]] | None = None,
    code: int = 1,
) -> dict[str, Any]:
    result = {
        "status": status,
        "compiled": compiled,
        "verified": False,
        "executed": False,
        "sandbox_mode": "not_entered",
        "trace_ref": trace_ref,
        "blocks": [_public_block(block) for block in blocks or []],
        "trace": trace or {"trace_ref": trace_ref},
        "hlf_result": _hlf_result(code, message),
        "result_artifact": {
            "kind": "RESULT",
            "code": code,
            "message": message,
            "trace_ref": trace_ref,
            "governed": True,
        },
        "error": message,
    }
    result["governance_proof"] = _code_governance_proof(result)
    result["result_artifact"]["governance_proof_ref"] = result["governance_proof"].get("chain_head")
    return result


def _code_governance_proof(result: dict[str, Any]) -> dict[str, Any]:
    trace = result.get("trace") if isinstance(result.get("trace"), dict) else {}
    runtime = result.get("runtime") if isinstance(result.get("runtime"), dict) else {}
    audit = trace.get("audit") if isinstance(trace.get("audit"), dict) else {}
    compile_trace = trace.get("compile") if isinstance(trace.get("compile"), dict) else {}
    verification = trace.get("verification") if isinstance(trace.get("verification"), dict) else {}
    events = [
        {"event_type": "compile", "payload": compile_trace},
        {"event_type": "lint", "payload": trace.get("lint") if isinstance(trace.get("lint"), dict) else {}},
        {"event_type": "verification", "payload": verification},
        {"event_type": "selection", "payload": result.get("selected_block") or {}},
        {
            "event_type": "runtime",
            "payload": {
                "status": result.get("status"),
                "executed": result.get("executed"),
                "sandbox_mode": result.get("sandbox_mode"),
                "runtime_status": runtime.get("status"),
                "gas_used": runtime.get("gas_used"),
                "trace_hash": sha256_digest(runtime.get("trace") or []),
            },
        },
        {"event_type": "result", "payload": result.get("result_artifact") or {}},
    ]
    memory_anchors = []
    for name in ("compile", "result"):
        entry = audit.get(name)
        if isinstance(entry, dict):
            memory_anchors.append(build_anchor("memory", f"audit.{name}", entry))
    runtime_anchors = [build_anchor("runtime", "code_execution.trace", runtime.get("trace") or [])]
    runtime_audit = (runtime.get("audit") or {}).get("execution") if isinstance(runtime.get("audit"), dict) else None
    if isinstance(runtime_audit, dict):
        runtime_anchors.append(build_anchor("runtime", "runtime.audit.execution", runtime_audit))
    return build_governance_proof(
        artifact_kind="hlf_code_execute",
        artifact_id=str(result.get("trace_ref") or ""),
        events=events,
        memory_anchors=memory_anchors,
        runtime_anchors=runtime_anchors,
        replay_scope={
            "result_body_hash": sha256_digest(governance_body(result)),
            "trace_ref": result.get("trace_ref"),
            "sandbox_mode": result.get("sandbox_mode"),
            "boundary": "HLF VM bytecode execution only; non-HLF payloads are compile-only",
        },
    )


def _public_block(block: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in block.items() if key != "node"}


def _result_message(
    status: str,
    trace_ref: str,
    selected: dict[str, Any],
    executed: bool,
    runtime_result: dict[str, Any] | None,
) -> str:
    runtime_status = str((runtime_result or {}).get("status") or "not_run")
    runtime_value = str((runtime_result or {}).get("result") or "")[:120]
    return (
        f"status={status}; executed={str(executed).lower()}; "
        f"block={selected.get('block_type')}:{selected.get('name')}; "
        f"runtime={runtime_status}; result={runtime_value}; trace={trace_ref}"
    )


def _hlf_result(code: int, message: str) -> str:
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    return f'[HLF-v3]\nRESULT {code} "{escaped}"\nΩ\n'


def _trace_ref(source: str, entrypoint: str, gas_limit: int, dry_run: bool) -> str:
    payload = json.dumps(
        {
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "entrypoint": entrypoint,
            "gas_limit": gas_limit,
            "dry_run": dry_run,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _audit(audit_logger: Any | None, event: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if audit_logger is None or not hasattr(audit_logger, "log"):
        return None
    return audit_logger.log(event, payload, agent_role="code_bearing_hlf")


__all__ = ["execute_code_bearing_hlf", "execute_two_channel_hlf"]
