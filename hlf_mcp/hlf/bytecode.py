"""
HLF Bytecode — binary .hlb format encoder, decoder, and disassembler.

Binary format:
  SHA-256   (32 bytes): hash of entire payload for integrity
  Header    (16 bytes): magic[4] version[2] code_len[4] crc32[4] flags[2]  (little-endian)
  Const Pool: uint32 count (LE), then per-constant typed entries
  Code Section: sequence of fixed 3-byte instructions (opcode[1] + operand[2 LE])
"""

from __future__ import annotations

import hashlib
import struct
import sys
import zlib
from enum import IntEnum
from typing import Any


# ── Opcode table ──────────────────────────────────────────────────────────────

class Op(IntEnum):
    NOP           = 0x00
    PUSH_CONST    = 0x01
    STORE         = 0x02
    LOAD          = 0x03
    STORE_IMMUT   = 0x04
    ADD           = 0x10
    SUB           = 0x11
    MUL           = 0x12
    DIV           = 0x13
    MOD           = 0x14
    NEG           = 0x15
    CMP_EQ        = 0x20
    CMP_NE        = 0x21
    CMP_LT        = 0x22
    CMP_LE        = 0x23
    CMP_GT        = 0x24
    CMP_GE        = 0x25
    AND           = 0x30
    OR            = 0x31
    NOT           = 0x32
    JMP           = 0x40
    JZ            = 0x41
    JNZ           = 0x42
    CALL_BUILTIN  = 0x50
    CALL_HOST     = 0x51
    CALL_TOOL     = 0x52
    OPENCLAW_TOOL = 0x53
    TAG           = 0x60
    INTENT        = 0x61
    RESULT        = 0x62
    MEMORY_STORE  = 0x63
    MEMORY_RECALL = 0x64
    SPEC_DEFINE   = 0x65
    SPEC_GATE     = 0x66
    SPEC_UPDATE   = 0x67
    SPEC_SEAL     = 0x68
    HALT          = 0xFF


# ── Gas costs ─────────────────────────────────────────────────────────────────

GAS_COSTS: dict[Op, int] = {
    Op.NOP:           0,
    Op.PUSH_CONST:    1,
    Op.STORE:         2,
    Op.LOAD:          1,
    Op.STORE_IMMUT:   3,
    Op.ADD:           2,
    Op.SUB:           2,
    Op.MUL:           3,
    Op.DIV:           5,
    Op.MOD:           3,
    Op.NEG:           1,
    Op.CMP_EQ:        1,
    Op.CMP_NE:        1,
    Op.CMP_LT:        1,
    Op.CMP_LE:        1,
    Op.CMP_GT:        1,
    Op.CMP_GE:        1,
    Op.AND:           1,
    Op.OR:            1,
    Op.NOT:           1,
    Op.JMP:           1,
    Op.JZ:            2,
    Op.JNZ:           2,
    Op.CALL_BUILTIN:  5,
    Op.CALL_HOST:     10,
    Op.CALL_TOOL:     15,
    Op.OPENCLAW_TOOL: 20,
    Op.TAG:           1,
    Op.INTENT:        2,
    Op.RESULT:        1,
    Op.MEMORY_STORE:  3,
    Op.MEMORY_RECALL: 2,
    Op.SPEC_DEFINE:   4,
    Op.SPEC_GATE:     4,
    Op.SPEC_UPDATE:   4,
    Op.SPEC_SEAL:     4,
    Op.HALT:          0,
}


# ── Constant Pool ─────────────────────────────────────────────────────────────

TYPE_INT    = 0x01
TYPE_FLOAT  = 0x02
TYPE_STRING = 0x03
TYPE_BOOL   = 0x04
TYPE_NULL   = 0x05


class ConstantPool:
    """Typed constant pool for HLF bytecode."""

    def __init__(self) -> None:
        self._entries: list[Any] = []

    def add(self, value: Any) -> int:
        """Add a value and return its pool index."""
        self._entries.append(value)
        return len(self._entries) - 1

    def get(self, index: int) -> Any:
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    def __len__(self) -> int:
        return len(self._entries)

    def encode(self) -> bytes:
        """Encode pool to bytes with typed entries (little-endian)."""
        parts = [struct.pack("<I", len(self._entries))]
        for entry in self._entries:
            parts.append(_encode_const(entry))
        return b"".join(parts)

    @classmethod
    def decode(cls, data: bytes) -> tuple["ConstantPool", int]:
        """Decode pool from bytes; returns (pool, bytes_consumed)."""
        if len(data) < 4:
            return cls(), 0
        count = struct.unpack("<I", data[:4])[0]
        offset = 4
        pool = cls()
        for _ in range(count):
            if offset >= len(data):
                break
            val, size = _decode_const(data[offset:])
            pool.add(val)
            offset += size
        return pool, offset


def _encode_const(value: Any) -> bytes:
    if value is None:
        return bytes([TYPE_NULL])
    if isinstance(value, bool):
        return bytes([TYPE_BOOL]) + struct.pack("<B", 1 if value else 0)
    if isinstance(value, int):
        return bytes([TYPE_INT]) + struct.pack("<q", value)
    if isinstance(value, float):
        return bytes([TYPE_FLOAT]) + struct.pack("<d", value)
    # string (default)
    enc = str(value).encode("utf-8")
    return bytes([TYPE_STRING]) + struct.pack("<I", len(enc)) + enc


def _decode_const(data: bytes) -> tuple[Any, int]:
    if not data:
        return None, 1
    typ = data[0]
    if typ == TYPE_NULL:
        return None, 1
    if typ == TYPE_BOOL:
        if len(data) < 2:
            return False, 2
        return bool(data[1]), 2
    if typ == TYPE_INT:
        if len(data) < 9:
            return 0, 9
        return struct.unpack("<q", data[1:9])[0], 9
    if typ == TYPE_FLOAT:
        if len(data) < 9:
            return 0.0, 9
        return struct.unpack("<d", data[1:9])[0], 9
    if typ == TYPE_STRING:
        if len(data) < 5:
            return "", 5
        length = struct.unpack("<I", data[1:5])[0]
        raw = data[5: 5 + length]
        try:
            return raw.decode("utf-8"), 5 + length
        except UnicodeDecodeError:
            return raw.hex(), 5 + length
    # Unknown type — skip 1 byte
    return None, 1


# ── Binary header ─────────────────────────────────────────────────────────────

_MAGIC = b"HLB\x00"
_FORMAT_VERSION = 0x0004  # v0.4
_HEADER_SIZE = 16  # magic[4] + version[2] + code_len[4] + crc32[4] + flags[2]


def _encode_header(code_len: int, crc: int, flags: int = 0) -> bytes:
    return struct.pack("<4sHIIH", _MAGIC, _FORMAT_VERSION, code_len, crc, flags)


def _decode_header(data: bytes) -> dict[str, Any]:
    magic, version, code_len, crc32, flags = struct.unpack("<4sHIIH", data[:_HEADER_SIZE])
    return {
        "magic": magic,
        "format_version": version,
        "code_len": code_len,
        "crc32": crc32,
        "flags": flags,
    }


# ── Glyph → opcode mapping ────────────────────────────────────────────────────

_GLYPH_OP: dict[str, Op] = {
    "Δ": Op.CALL_HOST,
    "Ж": Op.TAG,
    "⨝": Op.INTENT,
    "⌘": Op.CALL_HOST,
    "∇": Op.PUSH_CONST,
    "⩕": Op.TAG,
    "⊎": Op.JZ,
}


# ── Operand flags and descriptions ───────────────────────────────────────────

_OP_HAS_OPERAND: dict[Op, bool] = {
    Op.NOP:           False,
    Op.PUSH_CONST:    True,
    Op.STORE:         True,
    Op.LOAD:          True,
    Op.STORE_IMMUT:   True,
    Op.ADD:           False,
    Op.SUB:           False,
    Op.MUL:           False,
    Op.DIV:           False,
    Op.MOD:           False,
    Op.NEG:           False,
    Op.CMP_EQ:        False,
    Op.CMP_NE:        False,
    Op.CMP_LT:        False,
    Op.CMP_LE:        False,
    Op.CMP_GT:        False,
    Op.CMP_GE:        False,
    Op.AND:           False,
    Op.OR:            False,
    Op.NOT:           False,
    Op.JMP:           True,
    Op.JZ:            True,
    Op.JNZ:           True,
    Op.CALL_BUILTIN:  True,
    Op.CALL_HOST:     True,
    Op.CALL_TOOL:     True,
    Op.OPENCLAW_TOOL: True,
    Op.TAG:           True,
    Op.INTENT:        True,
    Op.RESULT:        False,
    Op.MEMORY_STORE:  False,
    Op.MEMORY_RECALL: False,
    Op.SPEC_DEFINE:   True,
    Op.SPEC_GATE:     True,
    Op.SPEC_UPDATE:   True,
    Op.SPEC_SEAL:     True,
    Op.HALT:          False,
}

_OP_DESC: dict[Op, str] = {
    Op.NOP:           "No operation",
    Op.PUSH_CONST:    "Push constant from pool",
    Op.STORE:         "Store TOS to variable slot",
    Op.LOAD:          "Load variable slot onto stack",
    Op.STORE_IMMUT:   "Store immutable variable",
    Op.ADD:           "Add top two stack values",
    Op.SUB:           "Subtract top two stack values",
    Op.MUL:           "Multiply top two stack values",
    Op.DIV:           "Divide top two stack values",
    Op.MOD:           "Modulo top two stack values",
    Op.NEG:           "Negate top of stack",
    Op.CMP_EQ:        "== comparison",
    Op.CMP_NE:        "!= comparison",
    Op.CMP_LT:        "< comparison",
    Op.CMP_LE:        "<= comparison",
    Op.CMP_GT:        "> comparison",
    Op.CMP_GE:        ">= comparison",
    Op.AND:           "Logical AND",
    Op.OR:            "Logical OR",
    Op.NOT:           "Logical NOT",
    Op.JMP:           "Unconditional jump",
    Op.JZ:            "Jump if zero/false",
    Op.JNZ:           "Jump if nonzero/true",
    Op.CALL_BUILTIN:  "Call built-in function",
    Op.CALL_HOST:     "Call host function by name index",
    Op.CALL_TOOL:     "Call registered tool by name index",
    Op.OPENCLAW_TOOL: "OpenClaw sandboxed tool call",
    Op.TAG:           "Tag/label annotation",
    Op.INTENT:        "Declare intent",
    Op.RESULT:        "Push result value",
    Op.MEMORY_STORE:  "Store TOS to RAG memory",
    Op.MEMORY_RECALL: "Recall from RAG memory by key",
    Op.SPEC_DEFINE:   "Define Instinct spec",
    Op.SPEC_GATE:     "Gate on Instinct spec",
    Op.SPEC_UPDATE:   "Update Instinct spec",
    Op.SPEC_SEAL:     "Seal Instinct spec with SHA-256",
    Op.HALT:          "Halt execution",
}


# ── Backward-compat OPCODES dict ─────────────────────────────────────────────
# Maps op name → {"code": int, "operand": bool, "desc": str}

OPCODES: dict[str, dict[str, Any]] = {
    op.name: {
        "code": op.value,
        "operand": _OP_HAS_OPERAND[op],
        "desc": _OP_DESC[op],
    }
    for op in Op
}

# Reverse lookups
_CODE_TO_OP: dict[int, Op] = {op.value: op for op in Op}
_CODE_TO_NAME: dict[int, str] = {op.value: op.name for op in Op}


# ── Instruction helper ────────────────────────────────────────────────────────

def _instr(op: Op, operand: int = 0) -> bytes:
    """Encode a fixed 3-byte instruction (little-endian operand)."""
    return struct.pack("<BH", op.value, operand)


# ── BytecodeCompiler ──────────────────────────────────────────────────────────

class BytecodeCompiler:
    """Compile AST dicts to .hlb bytecode."""

    def encode(self, ast: dict[str, Any]) -> bytes:
        """Compile AST to binary .hlb bytecode."""
        pool = ConstantPool()
        instructions: list[bytes] = []

        statements = ast.get("statements", [])
        for stmt in statements:
            _emit_stmt(stmt, instructions, pool, pool.add)

        instructions.append(_instr(Op.HALT))

        code_bytes = b"".join(instructions)
        pool_bytes = pool.encode()

        crc = zlib.crc32(code_bytes) & 0xFFFFFFFF
        header = _encode_header(len(code_bytes), crc)
        payload = header + pool_bytes + code_bytes

        sha = hashlib.sha256(payload).digest()
        return sha + payload


# Backward compat alias
HLFBytecode = BytecodeCompiler


# ── Disassembler ──────────────────────────────────────────────────────────────

class Disassembler:
    """Disassemble .hlb bytecode to human-readable form."""

    def disassemble(self, data: bytes) -> dict[str, Any]:
        """Disassemble .hlb binary; returns structured result dict."""
        if len(data) < 32 + _HEADER_SIZE:
            raise ValueError("Truncated .hlb file")

        stored_sha = data[:32].hex()
        payload = data[32:]

        if payload[:4] != _MAGIC:
            raise ValueError("Invalid .hlb magic bytes")

        hdr = _decode_header(payload[:_HEADER_SIZE])
        fmt_ver  = hdr["format_version"]
        code_len = hdr["code_len"]
        stored_crc = hdr["crc32"]
        flags    = hdr["flags"]

        pool, pool_size = ConstantPool.decode(payload[_HEADER_SIZE:])
        code_start = _HEADER_SIZE + pool_size
        code_bytes = payload[code_start: code_start + code_len]

        actual_crc = zlib.crc32(code_bytes) & 0xFFFFFFFF
        crc_ok  = actual_crc == stored_crc
        sha_ok  = hashlib.sha256(payload).digest().hex() == stored_sha

        instructions: list[dict[str, Any]] = []
        disasm_lines: list[str] = []
        pc = 0
        while pc < len(code_bytes):
            op_byte = code_bytes[pc]
            op = _CODE_TO_OP.get(op_byte)
            op_name = op.name if op is not None else f"UNKNOWN(0x{op_byte:02X})"
            has_operand = _OP_HAS_OPERAND.get(op, False) if op is not None else False

            if pc + 2 < len(code_bytes):
                operand = struct.unpack("<H", code_bytes[pc + 1: pc + 3])[0]
            else:
                operand = 0

            if has_operand:
                const_val = pool.get(operand)
                disasm_lines.append(
                    f"  {pc:04X}  {op_name:<18} #{operand}  ; {const_val!r}"
                )
                instructions.append({"pc": pc, "op": op_name, "operand": operand, "const": const_val})
            else:
                disasm_lines.append(f"  {pc:04X}  {op_name}")
                instructions.append({"pc": pc, "op": op_name})

            pc += 3  # fixed 3-byte instruction width

        pool_values = [pool.get(i) for i in range(len(pool))]
        header_info = {
            "format_version": f"0x{fmt_ver:04X}",
            "code_length": code_len,
            "constant_pool_size": len(pool),
            "crc32_ok": crc_ok,
            "sha256_ok": sha_ok,
            "sha256": stored_sha,
            "flags": f"0x{flags:04X}",
        }

        return {
            "header": header_info,
            "constant_pool": pool_values,
            "instructions": instructions,
            "disassembly": "\n".join(disasm_lines),
        }


# ── AST emission helpers ──────────────────────────────────────────────────────

def _emit_stmt(
    stmt: dict[str, Any],
    instructions: list[bytes],
    pool: ConstantPool,
    add_const,
) -> None:
    """Emit bytecode instructions for one AST statement."""
    kind = stmt.get("kind", "")

    if kind == "glyph_stmt":
        glyph = stmt.get("glyph", "Δ")
        tag   = stmt.get("tag", "")
        args  = stmt.get("arguments", [])
        op    = _GLYPH_OP.get(glyph, Op.CALL_HOST)
        desc  = f"{glyph} [{tag}]" if tag else str(glyph)
        idx   = add_const(desc)
        for arg in args:
            _emit_arg(arg, instructions, add_const)
        instructions.append(_instr(op, idx))

    elif kind == "set_stmt":
        _emit_value(stmt.get("value", {}), instructions, add_const)
        idx = add_const(stmt.get("name", ""))
        instructions.append(_instr(Op.STORE, idx))

    elif kind == "immut_stmt":
        _emit_value(stmt.get("value", {}), instructions, add_const)
        idx = add_const(stmt.get("name", ""))
        instructions.append(_instr(Op.STORE_IMMUT, idx))

    elif kind == "memory_stmt":
        for arg in stmt.get("arguments", []):
            _emit_arg(arg, instructions, add_const)
        instructions.append(_instr(Op.MEMORY_STORE))

    elif kind == "recall_stmt":
        idx = add_const(stmt.get("name", ""))
        instructions.append(_instr(Op.PUSH_CONST, idx))
        instructions.append(_instr(Op.MEMORY_RECALL))

    elif kind in ("spec_define_stmt", "spec_gate_stmt", "spec_update_stmt", "spec_seal_stmt"):
        op_map = {
            "spec_define_stmt": Op.SPEC_DEFINE,
            "spec_gate_stmt":   Op.SPEC_GATE,
            "spec_update_stmt": Op.SPEC_UPDATE,
            "spec_seal_stmt":   Op.SPEC_SEAL,
        }
        idx = add_const(stmt.get("tag", ""))
        instructions.append(_instr(op_map[kind], idx))

    elif kind == "tag_stmt":
        idx = add_const(stmt.get("tag", ""))
        instructions.append(_instr(Op.TAG, idx))

    elif kind == "intent_stmt":
        idx = add_const(stmt.get("intent", ""))
        instructions.append(_instr(Op.INTENT, idx))

    elif kind == "if_stmt":
        idx_name = add_const(stmt.get("name", ""))
        instructions.append(_instr(Op.LOAD, idx_name))
        _emit_value(stmt.get("value", {}), instructions, add_const)
        cmp_op = {
            "<": Op.CMP_LT, ">": Op.CMP_GT, "==": Op.CMP_EQ,
            "!=": Op.CMP_NE, ">=": Op.CMP_GE, "<=": Op.CMP_LE,
        }.get(stmt.get("cmp", "=="), Op.CMP_EQ)
        instructions.append(_instr(cmp_op))
        instructions.append(_instr(Op.JZ, 0x0000))

    elif kind == "return_stmt":
        value = stmt.get("value")
        if value:
            _emit_value(value, instructions, add_const)
        instructions.append(_instr(Op.RESULT))

    elif kind == "call_stmt":
        for arg in stmt.get("arguments", []):
            _emit_arg(arg, instructions, add_const)
        idx = add_const(stmt.get("name", ""))
        instructions.append(_instr(Op.CALL_HOST, idx))

    elif kind == "tool_stmt":
        for arg in stmt.get("arguments", []):
            _emit_arg(arg, instructions, add_const)
        idx = add_const(stmt.get("name", ""))
        instructions.append(_instr(Op.CALL_TOOL, idx))

    else:
        instructions.append(_instr(Op.NOP))


def _emit_arg(arg: dict[str, Any], instructions: list[bytes], add_const) -> None:
    kind = arg.get("kind", "")
    if kind == "kv_arg":
        _emit_value(arg.get("value", {}), instructions, add_const)
        idx = add_const(arg.get("name", ""))
        instructions.append(_instr(Op.STORE, idx))
    elif kind in ("path_arg", "var_arg", "pos_arg"):
        idx = add_const(str(arg.get("value", "")))
        instructions.append(_instr(Op.PUSH_CONST, idx))


def _emit_value(value: dict[str, Any], instructions: list[bytes], add_const) -> None:
    if not value:
        return
    v = value.get("value", "")
    # Preserve Python types where possible
    if not isinstance(v, (bool, int, float)):
        v = str(v)
    idx = add_const(v)
    instructions.append(_instr(Op.PUSH_CONST, idx))


# ── Legacy pool helpers (kept for any remaining callers) ──────────────────────

def _decode_pool(data: bytes) -> tuple[list[Any], int]:
    """Legacy shim: decode pool and return (list_of_values, bytes_consumed)."""
    pool, consumed = ConstantPool.decode(data)
    return [pool.get(i) for i in range(len(pool))], consumed


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI: hlfdis <file.hlb>  — disassemble an HLF bytecode file."""
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Disassemble HLF .hlb bytecode")
    ap.add_argument("file", help=".hlb file to disassemble")
    args = ap.parse_args()

    with open(args.file, "rb") as f:
        data = f.read()

    d = Disassembler()
    try:
        result = d.disassemble(data)
        print(result["disassembly"])
        print("\n; Header:", json.dumps(result["header"], indent=2))
        print("; Constant pool:", result["constant_pool"])
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
