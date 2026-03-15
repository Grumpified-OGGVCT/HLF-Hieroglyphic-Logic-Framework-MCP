"""
HLF Runtime — stack-machine bytecode interpreter.

Executes .hlb bytecode with:
  - Gas metering
  - Side-effect tracking
  - Host function dispatch
  - Variable bindings
  - Execution trace
"""

from __future__ import annotations

import struct
import sys
from typing import Any

from hlf_mcp.hlf.bytecode import OPCODES, HLFBytecode, _CODE_TO_NAME, _decode_pool

# ── Host function registry ────────────────────────────────────────────────────

HOST_FUNCTIONS: dict[str, dict[str, Any]] = {
    "analyze":           {"tier": "all",     "gas": 2, "effects": ["read_fs"],         "desc": "Analyze a file or resource"},
    "enforce_constraint": {"tier": "all",    "gas": 1, "effects": [],                  "desc": "Enforce a typed constraint"},
    "vote":              {"tier": "all",     "gas": 1, "effects": [],                  "desc": "Cast a consensus vote"},
    "delegate":          {"tier": "all",     "gas": 3, "effects": ["spawn_agent"],     "desc": "Delegate to a sub-agent"},
    "route":             {"tier": "all",     "gas": 2, "effects": ["model_call"],      "desc": "Route to a model"},
    "read_file":         {"tier": "all",     "gas": 2, "effects": ["read_fs"],         "desc": "Read a file"},
    "write_file":        {"tier": "operators","gas": 5, "effects": ["write_fs"],        "desc": "Write a file (operator+)"},
    "http_get":          {"tier": "all",     "gas": 4, "effects": ["network"],         "desc": "HTTP GET request"},
    "http_post":         {"tier": "operators","gas": 5, "effects": ["network"],         "desc": "HTTP POST request"},
    "spawn_agent":       {"tier": "operators","gas": 10,"effects": ["spawn_agent"],     "desc": "Spawn a new agent"},
    "memory_store":      {"tier": "all",     "gas": 5, "effects": ["memory_write"],    "desc": "Store to RAG memory"},
    "memory_recall":     {"tier": "all",     "gas": 5, "effects": ["memory_read"],     "desc": "Recall from RAG memory"},
    "log_emit":          {"tier": "all",     "gas": 1, "effects": [],                  "desc": "Emit a log event"},
    "assert_check":      {"tier": "all",     "gas": 1, "effects": [],                  "desc": "Check an assertion"},
    "get_vram":          {"tier": "all",     "gas": 1, "effects": [],                  "desc": "Get available VRAM"},
    "get_tier":          {"tier": "all",     "gas": 1, "effects": [],                  "desc": "Get deployment tier"},
    "hash_sha256":       {"tier": "all",     "gas": 2, "effects": [],                  "desc": "Compute SHA-256 hash"},
    "merkle_chain":      {"tier": "all",     "gas": 3, "effects": [],                  "desc": "Append to Merkle chain"},
    "align_verify":      {"tier": "all",     "gas": 4, "effects": [],                  "desc": "Verify ALIGN ledger rule"},
    "spec_gate_check":   {"tier": "all",     "gas": 4, "effects": [],                  "desc": "Check SPEC_GATE constraint"},
    "get_timestamp":     {"tier": "all",     "gas": 1, "effects": [],                  "desc": "Get current timestamp"},
    "generate_ulid":     {"tier": "all",     "gas": 1, "effects": [],                  "desc": "Generate a ULID"},
    "compress_tokens":   {"tier": "all",     "gas": 3, "effects": [],                  "desc": "Apply HLF token compression"},
    "summarize":         {"tier": "all",     "gas": 8, "effects": ["model_call"],      "desc": "Fractal summarization"},
    "embed_text":        {"tier": "all",     "gas": 5, "effects": ["model_call"],      "desc": "Generate text embeddings"},
    "cosine_similarity": {"tier": "all",     "gas": 2, "effects": [],                  "desc": "Cosine similarity score"},
    "cove_validate":     {"tier": "all",     "gas": 6, "effects": ["model_call"],      "desc": "CoVE adversarial validation"},
    "z3_verify":         {"tier": "operators","gas": 10,"effects": [],                  "desc": "Z3 formal verification"},
}


class HLFRuntimeError(Exception):
    """Raised when bytecode execution fails."""


class HLFRuntime:
    """Execute HLF .hlb bytecode in a stack machine."""

    def run(
        self,
        bytecode: bytes,
        gas_limit: int = 1000,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute bytecode and return execution result.

        Returns:
            dict with: status, result, gas_used, trace, side_effects, error
        """
        variables = dict(variables or {})
        stack: list[Any] = []
        trace: list[dict[str, Any]] = []
        side_effects: list[dict[str, Any]] = []
        gas_used = 0

        try:
            # Parse header
            if len(bytecode) < 48:
                return _error_result("Bytecode too short", 0, trace, side_effects)

            sha256 = bytecode[:32].hex()
            payload = bytecode[32:]

            if payload[:4] != b"HLB\x00":
                return _error_result("Invalid magic bytes", 0, trace, side_effects)

            code_len = struct.unpack(">I", payload[6:10])[0]
            pool, pool_size = _decode_pool(payload[16:])
            code_start = 16 + pool_size
            code = payload[code_start : code_start + code_len]

            pc = 0
            result = None

            while pc < len(code):
                op_byte = code[pc]
                op_name = _CODE_TO_NAME.get(op_byte, f"UNKNOWN(0x{op_byte:02X})")
                op_info = OPCODES.get(op_name, {})
                has_operand = op_info.get("operand", False)

                operand = None
                const_val = None
                if has_operand and pc + 2 < len(code):
                    operand = struct.unpack(">H", code[pc + 1 : pc + 3])[0]
                    const_val = pool[operand] if operand < len(pool) else None

                # Trace entry
                trace_entry: dict[str, Any] = {"pc": pc, "op": op_name}
                if const_val is not None:
                    trace_entry["const"] = const_val

                # ── Execute instruction ──────────────────────────────────────
                if op_name == "HALT":
                    trace.append({**trace_entry, "stack_depth": len(stack)})
                    break

                elif op_name == "GAS_METER":
                    cost = operand or 1
                    gas_used += cost
                    if gas_used > gas_limit:
                        return _error_result(
                            f"Gas limit exceeded ({gas_used} > {gas_limit})",
                            gas_used, trace, side_effects
                        )

                elif op_name == "PUSH":
                    stack.append(const_val)

                elif op_name == "POP":
                    if stack:
                        stack.pop()

                elif op_name == "STORE":
                    val = stack[-1] if stack else None
                    variables[const_val or ""] = val

                elif op_name == "LOAD":
                    stack.append(variables.get(const_val or "", None))

                elif op_name == "SET_VAR":
                    val = stack.pop() if stack else None
                    variables[const_val or ""] = val

                elif op_name == "CALL_HOST":
                    fn_key = const_val or ""
                    args: list[Any] = []
                    # Collect args from stack (up to 4)
                    while stack and len(args) < 4:
                        args.insert(0, stack.pop())
                    fn_result = _dispatch_host(fn_key, args, variables, side_effects)
                    stack.append(fn_result)
                    gas_used += HOST_FUNCTIONS.get(fn_key, {}).get("gas", 1)

                elif op_name == "CALL_TOOL":
                    tool_name = const_val or ""
                    side_effects.append({"type": "tool_call", "name": tool_name})
                    stack.append({"tool_called": tool_name, "status": "simulated"})

                elif op_name == "MEMORY_STORE":
                    key = stack.pop() if stack else "unknown"
                    val = stack.pop() if stack else None
                    side_effects.append({"type": "memory_write", "key": key, "value": str(val)})
                    gas_used += 5

                elif op_name == "MEMORY_RECALL":
                    key = stack.pop() if stack else "unknown"
                    stack.append({"recalled": key, "value": None})  # placeholder
                    side_effects.append({"type": "memory_read", "key": key})
                    gas_used += 5

                elif op_name == "APPLY_CONSTRAINT":
                    constraint = const_val or ""
                    side_effects.append({"type": "constraint_applied", "constraint": constraint})
                    stack.append(True)

                elif op_name == "VOTE":
                    side_effects.append({"type": "vote_cast", "config": const_val})
                    stack.append({"vote": "cast", "config": const_val})

                elif op_name == "DELEGATE":
                    side_effects.append({"type": "delegation", "target": const_val})
                    stack.append({"delegated_to": const_val})

                elif op_name == "ROUTE":
                    side_effects.append({"type": "route", "strategy": const_val})
                    stack.append({"routed": const_val})

                elif op_name == "ASSERT":
                    val = stack.pop() if stack else None
                    if not val:
                        return _error_result("Assertion failed", gas_used, trace, side_effects)

                elif op_name in ("CMP_GT", "CMP_LT", "CMP_EQ", "CMP_NE", "CMP_GE", "CMP_LE"):
                    b = stack.pop() if stack else 0
                    a = stack.pop() if stack else 0
                    try:
                        a_n, b_n = float(a), float(b)
                        ops = {"CMP_GT": a_n > b_n, "CMP_LT": a_n < b_n, "CMP_EQ": a_n == b_n,
                               "CMP_NE": a_n != b_n, "CMP_GE": a_n >= b_n, "CMP_LE": a_n <= b_n}
                        stack.append(ops[op_name])
                    except (TypeError, ValueError):
                        stack.append(a == b)

                elif op_name == "JMP_IF":
                    cond = stack.pop() if stack else False
                    if cond and operand is not None:
                        pc = operand
                        trace.append({**trace_entry, "jumped": True})
                        continue

                elif op_name == "JMP":
                    if operand is not None:
                        pc = operand
                        trace.append({**trace_entry, "jumped": True})
                        continue

                elif op_name == "LOG_EMIT":
                    val = stack.pop() if stack else const_val
                    side_effects.append({"type": "log", "message": str(val)})

                elif op_name == "RETURN":
                    result = stack.pop() if stack else None
                    trace.append({**trace_entry, "return_value": result})
                    break

                elif op_name == "IMPORT_MOD":
                    side_effects.append({"type": "import", "path": const_val})

                elif op_name in ("SPEC_DEFINE", "SPEC_GATE", "SPEC_UPDATE", "SPEC_SEAL"):
                    side_effects.append({"type": "spec_lifecycle", "op": op_name, "tag": const_val})

                elif op_name == "OPENCLAW_TOOL":
                    tool = const_val or ""
                    side_effects.append({"type": "openclaw_tool", "tool": tool})

                elif op_name == "CALL_FUNC":
                    fn_name = const_val or ""
                    side_effects.append({"type": "func_call", "name": fn_name})
                    stack.append({"func_called": fn_name})

                trace.append({**trace_entry, "stack_depth": len(stack)})
                pc += 3 if has_operand else 1

        except Exception as exc:
            return _error_result(str(exc), gas_used, trace, side_effects)

        return {
            "status": "ok",
            "result": result if result is not None else (stack[-1] if stack else None),
            "gas_used": gas_used,
            "trace": trace[:50],  # limit trace to 50 entries for MCP response
            "side_effects": side_effects,
            "error": None,
        }


def _dispatch_host(
    fn_name: str,
    args: list[Any],
    variables: dict[str, Any],
    side_effects: list[dict[str, Any]],
) -> Any:
    """Dispatch a simulated host function call."""
    fn_info = HOST_FUNCTIONS.get(fn_name, {})
    effects = fn_info.get("effects", [])
    for eff in effects:
        side_effects.append({"type": eff, "fn": fn_name, "args": args[:2]})
    # Return a placeholder result
    return {"host_fn": fn_name, "status": "simulated", "args_count": len(args)}


def _error_result(
    error: str,
    gas_used: int,
    trace: list,
    side_effects: list,
) -> dict[str, Any]:
    return {
        "status": "error",
        "result": None,
        "gas_used": gas_used,
        "trace": trace[:50],
        "side_effects": side_effects,
        "error": error,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────


def main() -> None:
    """CLI: hlfrun <file.hlf>"""
    import json
    import argparse

    ap = argparse.ArgumentParser(description="Run an HLF program")
    ap.add_argument("file", help="HLF source file")
    ap.add_argument("--gas", type=int, default=1000, help="Gas limit")
    ap.add_argument("--var", action="append", default=[], metavar="KEY=VALUE", help="Variable binding")
    args = ap.parse_args()

    variables = {}
    for v in args.var:
        if "=" in v:
            k, val = v.split("=", 1)
            variables[k.strip()] = val.strip()

    from hlf_mcp.hlf.compiler import HLFCompiler
    from hlf_mcp.hlf.bytecode import HLFBytecode

    with open(args.file) as f:
        source = f.read()

    compiler = HLFCompiler()
    bytecode_enc = HLFBytecode()
    runtime = HLFRuntime()

    try:
        result = compiler.compile(source)
        bc = bytecode_enc.encode(result["ast"])
        run_result = runtime.run(bc, gas_limit=args.gas, variables=variables)
        print(json.dumps(run_result, indent=2, ensure_ascii=False))
        if run_result["status"] != "ok":
            sys.exit(1)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
