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

import logging
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
from hlf_mcp.hlf.pii_guard import PIIGuard

logger = logging.getLogger(__name__)

# Module-level PII guard singleton sourced from governed repo policy when present.
_PII_GUARD = PIIGuard()


# ── Host function registry ────────────────────────────────────────────────────

# Environment variables that HLF programs must never be allowed to read.
# SYS_ENV will raise PermissionError for any name in this set.
_ENV_BLOCKLIST: frozenset[str] = frozenset({
    "HLF_STRICT",
    "VALKEY_URL", "REDIS_URL",
    "OLLAMA_API_KEY",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
    "GITHUB_TOKEN", "GITHUB_API_KEY",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "AZURE_CLIENT_SECRET", "AZURE_STORAGE_KEY",
    "DATABASE_URL", "POSTGRES_PASSWORD", "MYSQL_PASSWORD",
})

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
    """
    Dispatch a CALL_BUILTIN opcode.

    Routes to stdlib Python implementations where available; falls back
    to a structured echo for unknown builtins rather than swallowing the call.
    """
    import hashlib as _hashlib
    import time as _time
    import os as _os

    try:
        # ── Math builtins ────────────────────────────────────────────────────
        if name == "MATH_ABS":
            return abs(args[0]) if args else 0
        if name == "MATH_FLOOR":
            import math; return math.floor(args[0]) if args else 0
        if name == "MATH_CEIL":
            import math; return math.ceil(args[0]) if args else 0
        if name == "MATH_ROUND":
            return round(args[0]) if args else 0
        if name == "MATH_MIN":
            return min(args[0], args[1]) if len(args) >= 2 else (args[0] if args else 0)
        if name == "MATH_MAX":
            return max(args[0], args[1]) if len(args) >= 2 else (args[0] if args else 0)
        if name == "MATH_SQRT":
            import math; return math.sqrt(args[0]) if args else 0.0
        if name == "MATH_POW":
            import math; return math.pow(args[0], args[1]) if len(args) >= 2 else 0.0
        if name in ("MATH_PI", "PI"):
            import math; return math.pi
        if name in ("MATH_E", "E"):
            import math; return math.e
        if name == "MATH_SIN":
            import math; return math.sin(args[0]) if args else 0.0
        if name == "MATH_COS":
            import math; return math.cos(args[0]) if args else 1.0
        if name == "MATH_TAN":
            import math; return math.tan(args[0]) if args else 0.0
        if name == "MATH_LOG":
            import math; return math.log(args[0]) if args else 0.0

        # ── String builtins ──────────────────────────────────────────────────
        if name == "STRING_LENGTH":
            return len(str(args[0])) if args else 0
        if name == "STRING_UPPER":
            return str(args[0]).upper() if args else ""
        if name == "STRING_LOWER":
            return str(args[0]).lower() if args else ""
        if name == "STRING_TRIM":
            return str(args[0]).strip() if args else ""
        if name == "STRING_CONCAT":
            return str(args[0]) + str(args[1]) if len(args) >= 2 else (str(args[0]) if args else "")
        if name == "STRING_SPLIT":
            sep = str(args[1]) if len(args) >= 2 else " "
            return str(args[0]).split(sep) if args else []
        if name == "STRING_JOIN":
            sep = str(args[1]) if len(args) >= 2 else ""
            return sep.join(str(x) for x in (args[0] if args else []))
        if name == "STRING_CONTAINS":
            return str(args[1]) in str(args[0]) if len(args) >= 2 else False
        if name == "STRING_REPLACE":
            if len(args) >= 3:
                return str(args[0]).replace(str(args[1]), str(args[2]))
            return str(args[0]) if args else ""
        if name == "STRING_STARTS_WITH":
            return str(args[0]).startswith(str(args[1])) if len(args) >= 2 else False
        if name == "STRING_ENDS_WITH":
            return str(args[0]).endswith(str(args[1])) if len(args) >= 2 else False
        if name == "STRING_SUBSTRING":
            if len(args) >= 3:
                return str(args[0])[int(args[1]):int(args[2])]
            return str(args[0]) if args else ""

        # ── List / collection builtins ───────────────────────────────────────
        if name == "LIST_LENGTH":
            return len(args[0]) if args and hasattr(args[0], "__len__") else 0
        if name == "LIST_APPEND":
            lst = list(args[0]) if args else []
            lst.append(args[1] if len(args) >= 2 else None)
            return lst
        if name == "LIST_CONCAT":
            a = list(args[0]) if args else []
            b = list(args[1]) if len(args) >= 2 else []
            return a + b
        if name == "DICT_GET":
            if len(args) >= 2 and isinstance(args[0], dict):
                return args[0].get(args[1])
            return None
        if name == "DICT_KEYS":
            return list(args[0].keys()) if args and isinstance(args[0], dict) else []
        if name == "DICT_VALUES":
            return list(args[0].values()) if args and isinstance(args[0], dict) else []

        # ── Crypto builtins ──────────────────────────────────────────────────
        if name == "HASH" or name == "hash_sha256":
            data = str(args[0]) if args else ""
            algo = str(args[1]) if len(args) >= 2 else "sha256"
            h = _hashlib.new(algo.replace("-", "_"), data.encode("utf-8"))
            return h.hexdigest()
        if name == "HASH_VERIFY":
            if len(args) >= 2:
                data = str(args[0]); expected = str(args[1])
                algo = str(args[2]) if len(args) >= 3 else "sha256"
                import hmac as _hmac
                actual = _hashlib.new(algo.replace("-", "_"), data.encode("utf-8")).hexdigest()
                return _hmac.compare_digest(actual, expected.lower())
            return False
        if name == "MERKLE_ROOT":
            from hlf_mcp.hlf.stdlib.crypto_mod import MERKLE_ROOT
            return MERKLE_ROOT([str(x) for x in (args[0] if args else [])])
        if name == "MERKLE_CHAIN_APPEND":
            from hlf_mcp.hlf.stdlib.crypto_mod import MERKLE_CHAIN_APPEND
            prev = str(args[0]) if args else "0" * 64
            entry = str(args[1]) if len(args) >= 2 else ""
            return MERKLE_CHAIN_APPEND(prev, entry)
        if name == "KEY_GENERATE":
            import secrets as _sec
            return _sec.token_hex(32)
        if name == "KEY_DERIVE":
            from hlf_mcp.hlf.stdlib.crypto_mod import KEY_DERIVE
            password = str(args[0]) if args else ""
            salt_hex = str(args[1]) if len(args) >= 2 else ""
            return KEY_DERIVE(password, salt_hex)
        if name == "ENCRYPT":
            from hlf_mcp.hlf.stdlib.crypto_mod import ENCRYPT
            return ENCRYPT(str(args[0]) if args else "", str(args[1]) if len(args) >= 2 else "")
        if name == "DECRYPT":
            from hlf_mcp.hlf.stdlib.crypto_mod import DECRYPT
            return DECRYPT(str(args[0]) if args else "", str(args[1]) if len(args) >= 2 else "")
        if name in ("SIGN", "HMAC_SHA256"):
            import hmac as _hmac
            data = str(args[0]) if args else ""
            key  = str(args[1]) if len(args) >= 2 else ""
            return _hmac.new(key.encode("utf-8"), data.encode("utf-8"), _hashlib.sha256).hexdigest()
        if name == "SIGN_VERIFY":
            from hlf_mcp.hlf.stdlib.crypto_mod import SIGN_VERIFY
            if len(args) >= 3:
                return SIGN_VERIFY(str(args[0]), str(args[1]), str(args[2]))
            return False

        # ── System builtins ──────────────────────────────────────────────────
        if name in ("SYS_TIME", "get_timestamp"):
            return int(_time.time())
        if name == "SYS_OS":
            import platform; return platform.system()
        if name == "SYS_ARCH":
            import platform; return platform.machine()
        if name == "SYS_CWD":
            return _os.getcwd()
        if name == "SYS_ENV":
            var = str(args[0]) if args else ""
            if var in _ENV_BLOCKLIST:
                raise PermissionError(
                    f"SYS_ENV: read of sensitive variable '{var}' is not permitted"
                )
            return _os.environ.get(var, "")
        if name in ("SYS_SLEEP", "SLEEP"):
            ms = int(args[0]) if args else 0
            if ms > 0:
                _time.sleep(min(ms / 1000, 5.0))   # cap at 5 s in VM context
            return True
        if name == "generate_ulid":
            # ULID: timestamp (48-bit ms) + random (80-bit) encoded in Crockford base32
            import secrets as _sec
            ts_ms = int(_time.time() * 1000)
            ts_bytes = ts_ms.to_bytes(6, "big")
            rand_bytes = _sec.token_bytes(10)
            raw = ts_bytes + rand_bytes
            _CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
            bits = int.from_bytes(raw, "big")
            ulid = ""
            for _ in range(26):
                ulid = _CROCKFORD[bits & 0x1F] + ulid
                bits >>= 5
            return ulid

        # ── IO builtins (ACFS-confined) ──────────────────────────────────────
        if name in ("READ", "FILE_READ"):
            from hlf_mcp.hlf.stdlib.io_mod import FILE_READ
            return FILE_READ(str(args[0])) if args else ""
        if name in ("WRITE", "FILE_WRITE"):
            from hlf_mcp.hlf.stdlib.io_mod import FILE_WRITE
            if len(args) >= 2:
                FILE_WRITE(str(args[0]), str(args[1])); return True
            return False
        if name == "FILE_EXISTS":
            from hlf_mcp.hlf.stdlib.io_mod import FILE_EXISTS
            return FILE_EXISTS(str(args[0])) if args else False
        if name == "DIR_LIST":
            from hlf_mcp.hlf.stdlib.io_mod import DIR_LIST
            return DIR_LIST(str(args[0])) if args else []

        # ── Agent builtins ───────────────────────────────────────────────────
        if name == "AGENT_ID":
            from hlf_mcp.hlf.stdlib.agent import AGENT_ID
            return AGENT_ID()
        if name in ("AGENT_TIER", "get_tier"):
            from hlf_mcp.hlf.stdlib.agent import AGENT_TIER
            return AGENT_TIER()
        if name == "AGENT_CAPABILITIES":
            from hlf_mcp.hlf.stdlib.agent import AGENT_CAPABILITIES
            return AGENT_CAPABILITIES()
        if name == "GET_GOALS":
            from hlf_mcp.hlf.stdlib.agent import GET_GOALS
            return GET_GOALS()
        if name == "SET_GOAL":
            from hlf_mcp.hlf.stdlib.agent import SET_GOAL
            return SET_GOAL(str(args[0])) if args else False

        # ── Cosine similarity ────────────────────────────────────────────────
        if name == "cosine_similarity":
            import math as _math
            if len(args) >= 2:
                a = [float(x) for x in args[0]] if hasattr(args[0], "__iter__") else []
                b = [float(x) for x in args[1]] if hasattr(args[1], "__iter__") else []
                min_len = min(len(a), len(b))
                if min_len == 0:
                    return 0.0
                a, b = a[:min_len], b[:min_len]
                dot = sum(x * y for x, y in zip(a, b))
                mag_a = _math.sqrt(sum(x * x for x in a))
                mag_b = _math.sqrt(sum(x * x for x in b))
                return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0
            return 0.0

        # ── VRAM (environment-driven) ────────────────────────────────────────
        if name == "get_vram":
            import os as _os
            return _os.environ.get("HLF_VRAM", "8GB")

        # ── Compression token count (tiktoken) ──────────────────────────────
        if name == "compress_tokens":
            try:
                import tiktoken as _tt
                enc = _tt.get_encoding("cl100k_base")
                text = str(args[0]) if args else ""
                return len(enc.encode(text))
            except Exception:
                return len(str(args[0]).split()) if args else 0

        # ── ALIGN Ledger verify ──────────────────────────────────────────────
        if name == "align_verify":
            from hlf_mcp.hlf.compiler import _pass3_align_validate
            intent = str(args[0]) if args else ""
            violations = _pass3_align_validate([{"kind": "value", "value": intent}], strict=False)
            return len(violations) == 0

        # ── Assert check ────────────────────────────────────────────────────
        if name == "assert_check":
            val = args[0] if args else False
            if isinstance(val, dict) and "error" in val:
                return False
            return bool(val)

        # ── Log emit ────────────────────────────────────────────────────────
        if name == "log_emit":
            import logging as _log
            _log.getLogger("hlf.vm").info("[LOG_EMIT] %s", args[0] if args else "")
            return True

        # ── Unknown builtin — structured echo (never silently drop) ─────────
        return {
            "builtin": name,
            "status": "unresolved",
            "args": [str(a)[:80] for a in args[:4]],
            "note": f"No native implementation for builtin '{name}'; register via HostFunctionRegistry",
        }

    except PermissionError:
        raise  # Security errors must never be swallowed
    except Exception as exc:  # noqa: BLE001
        return {
            "builtin": name,
            "status": "error",
            "error": str(exc),
            "args": [str(a)[:80] for a in args[:4]],
        }


def _dispatch_host(
    fn_name: str,
    args: list[Any],
    scope: dict[str, Any],
    side_effects: list[dict[str, Any]],
) -> Any:
    """
    Dispatch a CALL_HOST opcode.

    Execution order:
      1. Look up fn_name in HOST_FUNCTIONS for effect/gas metadata.
      2. Record all declared side-effects in the side_effects audit list.
      3. Route to the appropriate backend handler.
      4. Hash outputs of sensitive functions (SHA-256 prefix for logs).
      5. Return the result onto the VM stack.
    """
    import hashlib as _hashlib
    import os as _os
    import time as _time

    fn_info = HOST_FUNCTIONS.get(fn_name, {})
    # Record all declared effects for the audit trail
    for eff in fn_info.get("effects", []):
        side_effects.append({"type": eff, "fn": fn_name, "args": [str(a)[:80] for a in args[:2]]})

    sensitive = fn_info.get("sensitive", False)

    try:
        result: Any

        # ── Crypto / hash ────────────────────────────────────────────────────
        if fn_name == "hash_sha256":
            data = str(args[0]) if args else ""
            result = _hashlib.sha256(data.encode("utf-8")).hexdigest()

        elif fn_name == "merkle_chain":
            from hlf_mcp.hlf.stdlib.crypto_mod import MERKLE_CHAIN_APPEND
            prev = scope.get("_merkle_head", "0" * 64)
            entry = str(args[0]) if args else ""
            new_head = MERKLE_CHAIN_APPEND(str(prev), entry)
            scope["_merkle_head"] = new_head
            result = new_head

        # ── Memory (RAG bridge) ──────────────────────────────────────────────
        elif fn_name == "memory_store":
            key = str(args[0]) if args else "unknown"
            val = args[1] if len(args) >= 2 else None
            # ── PII Guard: scan value before writing to RAG memory ────────────
            _val_text = str(val) if val is not None else ""
            _scan = _PII_GUARD.scan(_val_text)
            if _scan.has_pii:
                logger.warning(
                    "PII detected in memory_store for key '%s'; "
                    "storing redacted value. categories=%s",
                    key,
                    [c.name for c in _scan.categories_found],
                )
                side_effects.append({
                    "type": "pii_redacted",
                    "key": key,
                    "categories": [c.name for c in _scan.categories_found],
                })
                val = _scan.redacted_text
            mem_key = f"_mem_{key}"
            existing = scope.get(mem_key, [])
            if not isinstance(existing, list):
                existing = [existing]
            existing.append(val)
            scope[mem_key] = existing
            side_effects.append({"type": "memory_write", "key": key, "count": len(existing)})
            result = True

        elif fn_name == "memory_recall":
            key = str(args[0]) if args else "unknown"
            mem_key = f"_mem_{key}"
            stored = scope.get(mem_key, [])
            result = stored if isinstance(stored, list) else ([stored] if stored is not None else [])

        # ── Agent identity ───────────────────────────────────────────────────
        elif fn_name == "get_tier":
            result = scope.get("_tier", _os.environ.get("HLF_TIER", "hearth"))

        elif fn_name == "get_vram":
            result = _os.environ.get("HLF_VRAM", "8GB")

        elif fn_name == "get_timestamp":
            result = int(_time.time())

        elif fn_name == "generate_ulid":
            result = _dispatch_builtin("generate_ulid", [])

        # ── Consensus / delegation / routing ────────────────────────────────
        elif fn_name == "vote":
            config = str(args[0]) if args else "strict"
            result = {
                "voted": True,
                "config": config,
                "quorum_required": config == "strict",
                "timestamp": int(_time.time()),
            }

        elif fn_name == "delegate":
            agent = str(args[0]) if args else "unknown"
            goal  = str(args[1]) if len(args) >= 2 else ""
            result = {
                "delegated": True,
                "agent":     agent,
                "goal":      goal,
                "task_id":   _dispatch_builtin("generate_ulid", []),
                "timestamp": int(_time.time()),
            }

        elif fn_name == "route":
            strategy = str(args[0]) if args else "auto"
            tier = scope.get("_tier", _os.environ.get("HLF_TIER", "hearth"))
            result = {
                "routed":    True,
                "strategy":  strategy,
                "tier":      tier,
                "model":     _os.environ.get("HLF_MODEL", "llm-default"),
                "timestamp": int(_time.time()),
            }

        # ── Analysis ─────────────────────────────────────────────────────────
        elif fn_name == "analyze":
            target = str(args[0]) if args else ""
            # Real analysis: try to read the target if it's a path
            content_preview = ""
            try:
                from hlf_mcp.hlf.stdlib.io_mod import FILE_READ
                content_preview = FILE_READ(target)[:200]
            except Exception:
                content_preview = f"(target: {target})"
            sha = _hashlib.sha256(content_preview.encode()).hexdigest()
            result = {
                "analyzed":       target,
                "content_hash":   sha,
                "content_preview": content_preview[:80],
                "timestamp":      int(_time.time()),
            }

        # ── Assertions / ALIGN ───────────────────────────────────────────────
        elif fn_name == "assert_check":
            val = args[0] if args else False
            passed = bool(val) and not (isinstance(val, dict) and "error" in val)
            if not passed:
                side_effects.append({"type": "assertion_failed", "fn": fn_name, "val": str(val)[:80]})
            result = passed

        elif fn_name == "align_verify":
            intent = str(args[0]) if args else ""
            from hlf_mcp.hlf.compiler import _pass3_align_validate
            violations = _pass3_align_validate([{"kind": "value", "value": intent}], strict=False)
            result = {"passed": len(violations) == 0, "violations": violations}

        # ── Logging ──────────────────────────────────────────────────────────
        elif fn_name == "log_emit":
            import logging as _log
            msg = str(args[0]) if args else ""
            _log.getLogger("hlf.vm").info("[HOST:log_emit] %s", msg)
            side_effects.append({"type": "log", "fn": fn_name, "msg": msg[:200]})
            result = True

        # ── Compression ──────────────────────────────────────────────────────
        elif fn_name == "compress_tokens":
            result = _dispatch_builtin("compress_tokens", args)

        elif fn_name == "cosine_similarity":
            result = _dispatch_builtin("cosine_similarity", args)

        # ── CoVE adversarial validation ──────────────────────────────────────
        elif fn_name == "cove_validate":
            # CoVE: re-run ALIGN pass as a structural integrity check
            artifact = args[0] if args else {}
            if isinstance(artifact, dict):
                strings = []
                def _collect(obj: Any) -> None:
                    if isinstance(obj, str): strings.append(obj)
                    elif isinstance(obj, dict):
                        for v in obj.values(): _collect(v)
                    elif isinstance(obj, list):
                        for v in obj: _collect(v)
                _collect(artifact)
                from hlf_mcp.hlf.compiler import _ALIGN_COMPILED
                violations = []
                for text in strings:
                    for rule_id, _, pattern, action in _ALIGN_COMPILED:
                        if pattern.search(text) and action == "block":
                            violations.append(rule_id)
                result = {"cove_passed": len(violations) == 0, "violations": violations}
            else:
                result = {"cove_passed": True, "violations": []}

        # ── Z3 formal verification ───────────────────────────────────────────
        elif fn_name == "z3_verify":
            constraints = args[0] if args else {}
            try:
                import z3  # type: ignore[import]
                # Build a simple satisfiability check from the constraints dict
                solver = z3.Solver()
                if isinstance(constraints, dict):
                    for name_c, val in constraints.items():
                        x = z3.Int(str(name_c))
                        if isinstance(val, (int, float)):
                            solver.add(x == int(val))
                chk = solver.check()
                result = {"satisfiable": str(chk) == "sat", "solver": "z3"}
            except ImportError:
                # Pure-Python fallback: all-integer constraints trivially satisfiable
                result = {"satisfiable": True, "solver": "python-fallback",
                          "note": "z3 not installed; fallback used"}

        # ── File I/O (ACFS-confined) ──────────────────────────────────────────
        elif fn_name in ("READ", "FILE_READ"):
            from hlf_mcp.hlf.stdlib.io_mod import FILE_READ
            result = FILE_READ(str(args[0])) if args else ""

        elif fn_name in ("WRITE", "FILE_WRITE"):
            from hlf_mcp.hlf.stdlib.io_mod import FILE_WRITE
            if len(args) >= 2:
                result = FILE_WRITE(str(args[0]), str(args[1]))
            else:
                result = False

        # ── HTTP (network-gated) ─────────────────────────────────────────────
        elif fn_name in ("HTTP_GET", "http_get"):
            import urllib.request as _req
            url = str(args[0]) if args else ""
            with _req.urlopen(url, timeout=10) as resp:  # noqa: S310
                result = resp.read().decode("utf-8")[:4096]

        elif fn_name in ("HTTP_POST", "http_post"):
            import urllib.request as _req
            url  = str(args[0]) if args else ""
            body = str(args[1]) if len(args) >= 2 else ""
            req  = _req.Request(url, data=body.encode("utf-8"), method="POST")
            with _req.urlopen(req, timeout=10) as resp:  # noqa: S310
                result = resp.read().decode("utf-8")[:4096]

        # ── Unknown host function — structured error, never silent ───────────
        else:
            result = {
                "host_fn": fn_name,
                "status":  "unresolved",
                "args":    [str(a)[:80] for a in args[:4]],
                "note":    f"No backend mapped for host function '{fn_name}'; "
                           "register via governance/host_functions.json backend field",
            }

    except Exception as exc:  # noqa: BLE001
        result = {"host_fn": fn_name, "status": "error", "error": str(exc)}
        side_effects.append({"type": "host_error", "fn": fn_name, "error": str(exc)})

    # Hash sensitive results in the audit trail
    if sensitive and not isinstance(result, dict):
        result_str = str(result)
        side_effects.append({
            "type": "sensitive_output",
            "fn": fn_name,
            "result_sha256": _hashlib.sha256(result_str.encode()).hexdigest()[:16] + "...",
        })

    return result


# ── HLFRuntime (backward-compat wrapper) ─────────────────────────────────────

class HLFRuntime:
    """Backward-compatible wrapper around HlfVM."""

    def run(
        self,
        bytecode: bytes,
        gas_limit: int = 1000,
        variables: dict[str, Any] | None = None,
        *,
        ast: dict[str, Any] | None = None,
        source: str = "",
        tier: str | None = None,
        red_hat_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        effective_variables = variables or {}
        effective_tier = tier or str(effective_variables.get("DEPLOYMENT_TIER", "hearth"))

        if ast is not None or source or red_hat_metadata is not None:
            from hlf_mcp.hlf.ethics.governor import check as ethics_check

            governor_result = ethics_check(
                ast=ast,
                env=effective_variables,
                source=source,
                tier=effective_tier,
                red_hat_metadata=red_hat_metadata,
            )
            if not governor_result.passed:
                termination = governor_result.termination
                if termination is not None:
                    error = (
                        f"Ethics Governor [{termination.trigger}]: {termination.message} "
                        f"(Audit ID: {termination.audit_id})"
                    )
                else:
                    error = "Ethics Governor blocked execution: " + "; ".join(governor_result.blocks)
                return {
                    "status": "governor_blocked",
                    "result": None,
                    "gas_used": 0,
                    "trace": [],
                    "side_effects": [],
                    "error": error,
                    "governor": {
                        "passed": governor_result.passed,
                        "blocks": governor_result.blocks,
                        "warnings": governor_result.warnings,
                        "termination": (
                            {
                                "trigger": termination.trigger,
                                "message": termination.message,
                                "documentation": termination.documentation,
                                "audit_id": termination.audit_id,
                                "appealable": termination.appealable,
                            }
                            if termination is not None
                            else None
                        ),
                    },
                }

        vm = HlfVM(max_gas=gas_limit)
        if effective_variables:
            vm.scope.update(effective_variables)
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

    with open(args.file, encoding="utf-8") as f:
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
