"""
HLF Runtime — stack-machine bytecode interpreter.

Executes .hlb bytecode with:
  - Gas metering (checked BEFORE each instruction)
  - Side-effect tracking
  - Host function dispatch
  - Variable bindings with immutability enforcement
  - Execution trace
"""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.bytecode import (
    ConstantPool,
    GAS_COSTS,
    OPCODES,
    Op,
    _CODE_TO_NAME,
    _CODE_TO_OP,
    _HEADER_SIZE,
    _MAGIC,
    _OP_HAS_OPERAND,
    _decode_header,
    _decode_pool,
    HLFBytecode,
)


# ── Host function registry ────────────────────────────────────────────────────

HOST_FUNCTIONS: dict[str, dict[str, Any]] = {
    "analyze":            {"tier": "all",       "gas": 2,  "effects": ["read_fs"],      "desc": "Analyze a file or resource"},
    "enforce_constraint": {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Enforce a typed constraint"},
    "vote":               {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Cast a consensus vote"},
    "delegate":           {"tier": "all",       "gas": 3,  "effects": ["spawn_agent"],  "desc": "Delegate to a sub-agent"},
    "route":              {"tier": "all",       "gas": 2,  "effects": ["model_call"],   "desc": "Route to a model"},
    "read_file":          {"tier": "all",       "gas": 2,  "effects": ["read_fs"],      "desc": "Read a file"},
    "write_file":         {"tier": "operators", "gas": 5,  "effects": ["write_fs"],     "desc": "Write a file (operator+)"},
    "http_get":           {"tier": "all",       "gas": 4,  "effects": ["network"],      "desc": "HTTP GET request"},
    "http_post":          {"tier": "operators", "gas": 5,  "effects": ["network"],      "desc": "HTTP POST request"},
    "spawn_agent":        {"tier": "operators", "gas": 10, "effects": ["spawn_agent"],  "desc": "Spawn a new agent"},
    "memory_store":       {"tier": "all",       "gas": 5,  "effects": ["memory_write"], "desc": "Store to RAG memory"},
    "memory_recall":      {"tier": "all",       "gas": 5,  "effects": ["memory_read"],  "desc": "Recall from RAG memory"},
    "log_emit":           {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Emit a log event"},
    "assert_check":       {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Check an assertion"},
    "get_vram":           {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Get available VRAM"},
    "get_tier":           {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Get deployment tier"},
    "hash_sha256":        {"tier": "all",       "gas": 2,  "effects": [],               "desc": "Compute SHA-256 hash"},
    "merkle_chain":       {"tier": "all",       "gas": 3,  "effects": [],               "desc": "Append to Merkle chain"},
    "align_verify":       {"tier": "all",       "gas": 4,  "effects": [],               "desc": "Verify ALIGN ledger rule"},
    "spec_gate_check":    {"tier": "all",       "gas": 4,  "effects": [],               "desc": "Check SPEC_GATE constraint"},
    "get_timestamp":      {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Get current timestamp"},
    "generate_ulid":      {"tier": "all",       "gas": 1,  "effects": [],               "desc": "Generate a ULID"},
    "compress_tokens":    {"tier": "all",       "gas": 3,  "effects": [],               "desc": "Apply HLF token compression"},
    "summarize":          {"tier": "all",       "gas": 8,  "effects": ["model_call"],   "desc": "Fractal summarization"},
    "embed_text":         {"tier": "all",       "gas": 5,  "effects": ["model_call"],   "desc": "Generate text embeddings"},
    "cosine_similarity":  {"tier": "all",       "gas": 2,  "effects": [],               "desc": "Cosine similarity score"},
    "cove_validate":      {"tier": "all",       "gas": 6,  "effects": ["model_call"],   "desc": "CoVE adversarial validation"},
    "z3_verify":          {"tier": "operators", "gas": 10, "effects": [],               "desc": "Z3 formal verification"},
}


# ── Exceptions ────────────────────────────────────────────────────────────────

class HlfVMGasExhausted(Exception):
    """Raised when the gas limit is exceeded during execution."""


class HLFRuntimeError(Exception):
    """Raised when bytecode execution fails."""


# ── VMResult ──────────────────────────────────────────────────────────────────

@dataclass
class VMResult:
    code: int                                                    # 0 = ok, non-zero = error
    message: str
    gas_used: int
    stack: list[Any]          = field(default_factory=list)
    scope: dict[str, Any]     = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    side_effects: list[dict[str, Any]] = field(default_factory=list)
    error: str | None         = None


# ── HlfVM ─────────────────────────────────────────────────────────────────────

class HlfVM:
    """HLF stack-machine virtual machine."""

    def __init__(self, tier: str = "hearth", max_gas: int = 100) -> None:
        self.tier     = tier
        self.max_gas  = max_gas
        self.gas_used = 0
        self.stack:      list[Any]          = []
        self.scope:      dict[str, Any]     = {}
        self.immutables: set[str]           = set()
        self.trace:      list[dict[str, Any]] = []
        self._halted         = False
        self._result_code    = 0
        self._result_message = "ok"
        self._side_effects:  list[dict[str, Any]] = []

    def execute(self, hlb_data: bytes) -> VMResult:
        """Execute .hlb bytecode and return a VMResult."""
        if len(hlb_data) < 32 + _HEADER_SIZE:
            return VMResult(code=1, message="Bytecode too short", gas_used=0, error="Bytecode too short")

        payload = hlb_data[32:]
        if payload[:4] != _MAGIC:
            return VMResult(code=1, message="Invalid magic bytes", gas_used=0, error="Invalid magic bytes")

        hdr      = _decode_header(payload[:_HEADER_SIZE])
        code_len = hdr["code_len"]

        pool, pool_size = ConstantPool.decode(payload[_HEADER_SIZE:])
        code_start = _HEADER_SIZE + pool_size
        code_bytes = payload[code_start: code_start + code_len]

        try:
            self._execute_code(code_bytes, pool)
        except HlfVMGasExhausted as exc:
            return VMResult(
                code=2, message=str(exc), gas_used=self.gas_used,
                stack=list(self.stack), scope=dict(self.scope),
                trace=self.trace[:50], side_effects=self._side_effects,
                error=str(exc),
            )
        except HLFRuntimeError as exc:
            return VMResult(
                code=1, message=str(exc), gas_used=self.gas_used,
                stack=list(self.stack), scope=dict(self.scope),
                trace=self.trace[:50], side_effects=self._side_effects,
                error=str(exc),
            )
        except Exception as exc:
            return VMResult(
                code=1, message=str(exc), gas_used=self.gas_used,
                stack=list(self.stack), scope=dict(self.scope),
                trace=self.trace[:50], side_effects=self._side_effects,
                error=str(exc),
            )

        return VMResult(
            code=self._result_code, message=self._result_message,
            gas_used=self.gas_used,
            stack=list(self.stack), scope=dict(self.scope),
            trace=self.trace[:50], side_effects=self._side_effects,
        )

    def _execute_code(self, code: bytes, pool: ConstantPool) -> None:
        """Inner execution loop — fixed 3-byte instructions."""
        pc = 0
        while pc < len(code):
            op_byte = code[pc]
            op = _CODE_TO_OP.get(op_byte)
            if op is None:
                raise HLFRuntimeError(f"Unknown opcode 0x{op_byte:02X} at pc={pc}")

            # Decode 2-byte little-endian operand (always present in fixed format)
            operand = struct.unpack("<H", code[pc + 1: pc + 3])[0] if pc + 2 < len(code) else 0

            # Charge gas BEFORE executing
            cost = GAS_COSTS.get(op, 1)
            if self.gas_used + cost > self.max_gas:
                raise HlfVMGasExhausted(
                    f"Gas exhausted at pc={pc}: {self.gas_used}+{cost} > {self.max_gas}"
                )
            self.gas_used += cost

            trace_entry: dict[str, Any] = {"pc": pc, "op": op.name, "gas": self.gas_used}

            # ── Dispatch ────────────────────────────────────────────────────────
            if op == Op.NOP:
                pass

            elif op == Op.PUSH_CONST:
                val = pool.get(operand)
                self.stack.append(val)
                trace_entry["push"] = val

            elif op == Op.STORE:
                val  = self.stack[-1] if self.stack else None
                name = pool.get(operand)
                if name in self.immutables:
                    raise HLFRuntimeError(f"Cannot reassign immutable variable '{name}'")
                self.scope[name] = val

            elif op == Op.LOAD:
                name = pool.get(operand)
                self.stack.append(self.scope.get(name))

            elif op == Op.STORE_IMMUT:
                val  = self.stack[-1] if self.stack else None
                name = pool.get(operand)
                if name in self.immutables:
                    raise HLFRuntimeError(f"Cannot reassign immutable variable '{name}'")
                self.scope[name] = val
                self.immutables.add(name)

            elif op == Op.ADD:
                b = self.stack.pop() if self.stack else 0
                a = self.stack.pop() if self.stack else 0
                self.stack.append(_to_num(a) + _to_num(b))

            elif op == Op.SUB:
                b = self.stack.pop() if self.stack else 0
                a = self.stack.pop() if self.stack else 0
                self.stack.append(_to_num(a) - _to_num(b))

            elif op == Op.MUL:
                b = self.stack.pop() if self.stack else 0
                a = self.stack.pop() if self.stack else 0
                self.stack.append(_to_num(a) * _to_num(b))

            elif op == Op.DIV:
                b = self.stack.pop() if self.stack else 1
                a = self.stack.pop() if self.stack else 0
                bn = _to_num(b)
                if bn == 0:
                    raise HLFRuntimeError("Division by zero")
                result = _to_num(a) / bn
                self.stack.append(int(result) if result == int(result) else result)

            elif op == Op.MOD:
                b = self.stack.pop() if self.stack else 1
                a = self.stack.pop() if self.stack else 0
                bn = _to_num(b)
                if bn == 0:
                    raise HLFRuntimeError("Modulo by zero")
                self.stack.append(_to_num(a) % bn)

            elif op == Op.NEG:
                a = self.stack.pop() if self.stack else 0
                self.stack.append(-_to_num(a))

            elif op == Op.AND:
                b = self.stack.pop() if self.stack else False
                a = self.stack.pop() if self.stack else False
                self.stack.append(bool(a) and bool(b))

            elif op == Op.OR:
                b = self.stack.pop() if self.stack else False
                a = self.stack.pop() if self.stack else False
                self.stack.append(bool(a) or bool(b))

            elif op == Op.NOT:
                a = self.stack.pop() if self.stack else False
                self.stack.append(not bool(a))

            elif op == Op.CMP_EQ:
                b = self.stack.pop() if self.stack else None
                a = self.stack.pop() if self.stack else None
                self.stack.append(a == b)

            elif op == Op.CMP_NE:
                b = self.stack.pop() if self.stack else None
                a = self.stack.pop() if self.stack else None
                self.stack.append(a != b)

            elif op == Op.CMP_LT:
                b = self.stack.pop() if self.stack else 0
                a = self.stack.pop() if self.stack else 0
                self.stack.append(_to_num(a) < _to_num(b))

            elif op == Op.CMP_LE:
                b = self.stack.pop() if self.stack else 0
                a = self.stack.pop() if self.stack else 0
                self.stack.append(_to_num(a) <= _to_num(b))

            elif op == Op.CMP_GT:
                b = self.stack.pop() if self.stack else 0
                a = self.stack.pop() if self.stack else 0
                self.stack.append(_to_num(a) > _to_num(b))

            elif op == Op.CMP_GE:
                b = self.stack.pop() if self.stack else 0
                a = self.stack.pop() if self.stack else 0
                self.stack.append(_to_num(a) >= _to_num(b))

            elif op == Op.JMP:
                trace_entry["jump_to"] = operand
                self.trace.append(trace_entry)
                pc = operand
                continue

            elif op == Op.JZ:
                cond = self.stack.pop() if self.stack else False
                if not bool(cond):
                    trace_entry["jump_to"] = operand
                    self.trace.append(trace_entry)
                    pc = operand
                    continue

            elif op == Op.JNZ:
                cond = self.stack.pop() if self.stack else False
                if bool(cond):
                    trace_entry["jump_to"] = operand
                    self.trace.append(trace_entry)
                    pc = operand
                    continue

            elif op == Op.CALL_BUILTIN:
                name = pool.get(operand)
                args = [self.stack.pop()] if self.stack else []
                self.stack.append(_dispatch_builtin(name, args))

            elif op == Op.CALL_HOST:
                fn_key: str = pool.get(operand) or ""
                fn_args: list[Any] = []
                while self.stack and len(fn_args) < 4:
                    fn_args.insert(0, self.stack.pop())
                self.stack.append(_dispatch_host(fn_key, fn_args, self.scope, self._side_effects))

            elif op == Op.CALL_TOOL:
                tool_name = pool.get(operand) or ""
                self._side_effects.append({"type": "tool_call", "name": tool_name})
                self.stack.append({"tool_called": tool_name, "status": "simulated"})

            elif op == Op.OPENCLAW_TOOL:
                tool = pool.get(operand) or ""
                self._side_effects.append({"type": "openclaw_tool", "tool": tool})
                self.stack.append({"openclaw": tool, "status": "sandboxed"})

            elif op == Op.TAG:
                tag = pool.get(operand) or ""
                self._side_effects.append({"type": "tag", "value": tag})

            elif op == Op.INTENT:
                intent = pool.get(operand) or ""
                self._side_effects.append({"type": "intent", "value": intent})

            elif op == Op.RESULT:
                val = self.stack[-1] if self.stack else None
                self._result_message = str(val)

            elif op == Op.MEMORY_STORE:
                key = self.stack.pop() if self.stack else "unknown"
                val = self.stack.pop() if self.stack else None
                self._side_effects.append({"type": "memory_write", "key": key, "value": str(val)})

            elif op == Op.MEMORY_RECALL:
                key = self.stack.pop() if self.stack else "unknown"
                self.stack.append({"recalled": key, "value": None})
                self._side_effects.append({"type": "memory_read", "key": key})

            elif op == Op.SPEC_DEFINE:
                tag = pool.get(operand) or ""
                self._side_effects.append({"type": "spec_lifecycle", "op": "SPEC_DEFINE", "tag": tag})

            elif op == Op.SPEC_GATE:
                tag = pool.get(operand) or ""
                self._side_effects.append({"type": "spec_lifecycle", "op": "SPEC_GATE", "tag": tag})

            elif op == Op.SPEC_UPDATE:
                tag = pool.get(operand) or ""
                self._side_effects.append({"type": "spec_lifecycle", "op": "SPEC_UPDATE", "tag": tag})

            elif op == Op.SPEC_SEAL:
                tag = pool.get(operand) or ""
                self._side_effects.append({"type": "spec_lifecycle", "op": "SPEC_SEAL", "tag": tag})

            elif op == Op.HALT:
                self._halted = True
                trace_entry["halted"] = True
                self.trace.append(trace_entry)
                break

            self.trace.append({**trace_entry, "stack_depth": len(self.stack)})
            pc += 3  # fixed 3-byte instruction width


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_num(v: Any) -> float | int:
    """Convert a value to a numeric type (int preferred over float)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    try:
        f = float(str(v))
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return 0


def _dispatch_builtin(name: str, args: list[Any]) -> Any:
    """Dispatch a built-in function call (simulated)."""
    return {"builtin": name, "status": "simulated", "args_count": len(args)}


def _dispatch_host(
    fn_name: str,
    args: list[Any],
    scope: dict[str, Any],
    side_effects: list[dict[str, Any]],
) -> Any:
    """Dispatch a simulated host function call."""
    fn_info = HOST_FUNCTIONS.get(fn_name, {})
    for eff in fn_info.get("effects", []):
        side_effects.append({"type": eff, "fn": fn_name, "args": args[:2]})
    return {"host_fn": fn_name, "status": "simulated", "args_count": len(args)}


# ── HLFRuntime (backward-compat wrapper) ─────────────────────────────────────

class HLFRuntime:
    """Backward-compatible wrapper around HlfVM."""

    def run(
        self,
        bytecode: bytes,
        gas_limit: int = 1000,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        vm = HlfVM(max_gas=gas_limit)
        if variables:
            vm.scope.update(variables)
        result = vm.execute(bytecode)
        status = "ok" if result.code == 0 else "error"
        top    = result.stack[-1] if result.stack else None
        return {
            "status":       status,
            "result":       top,
            "gas_used":     result.gas_used,
            "trace":        result.trace,
            "side_effects": result.side_effects,
            "error":        result.error,
        }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    """CLI: hlfrun <file.hlf>"""
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Run an HLF program")
    ap.add_argument("file", help="HLF source file")
    ap.add_argument("--gas", type=int, default=1000, help="Gas limit")
    ap.add_argument("--var", action="append", default=[], metavar="KEY=VALUE", help="Variable binding")
    args = ap.parse_args()

    variables: dict[str, Any] = {}
    for v in args.var:
        if "=" in v:
            k, val = v.split("=", 1)
            variables[k.strip()] = val.strip()

    from hlf_mcp.hlf.compiler import HLFCompiler

    with open(args.file) as f:
        source = f.read()

    compiler    = HLFCompiler()
    bytecode_enc = HLFBytecode()
    runtime     = HLFRuntime()

    try:
        result  = compiler.compile(source)
        bc      = bytecode_enc.encode(result["ast"])
        run_result = runtime.run(bc, gas_limit=args.gas, variables=variables)
        print(json.dumps(run_result, indent=2, ensure_ascii=False))
        if run_result["status"] != "ok":
            sys.exit(1)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
