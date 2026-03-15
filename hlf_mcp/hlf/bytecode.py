"""
HLF Bytecode — binary .hlb format encoder, decoder, and disassembler.

Binary format:
  Header  (16 bytes): magic[4] version[2] code_len[4] crc32[4] flags[2]
  Const Pool: uint16 count, then per-constant: type[1] len[2] data[len]
  Code Section: sequence of instructions

Each instruction: opcode[1] [operand: uint16]?
  Opcodes with operand: PUSH, STORE, LOAD, CALL_HOST, CALL_TOOL, JMP, JMP_IF,
                        OPENCLAW_TOOL, SPEC_DEFINE, SPEC_GATE, SPEC_UPDATE, SPEC_SEAL
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Any

# ── Opcode table ──────────────────────────────────────────────────────────────

OPCODES: dict[str, dict[str, Any]] = {
    "PUSH":           {"code": 0x01, "operand": True,  "desc": "Push constant from pool"},
    "POP":            {"code": 0x02, "operand": False, "desc": "Pop top of stack"},
    "STORE":          {"code": 0x03, "operand": True,  "desc": "Store TOS to variable slot"},
    "LOAD":           {"code": 0x04, "operand": True,  "desc": "Load variable slot onto stack"},
    "CALL_HOST":      {"code": 0x05, "operand": True,  "desc": "Call host function by name index"},
    "CALL_TOOL":      {"code": 0x06, "operand": True,  "desc": "Call registered tool by name index"},
    "MEMORY_STORE":   {"code": 0x07, "operand": False, "desc": "Store TOS to RAG memory"},
    "MEMORY_RECALL":  {"code": 0x08, "operand": False, "desc": "Recall from RAG memory by key"},
    "APPLY_CONSTRAINT": {"code": 0x09, "operand": True, "desc": "Apply typed constraint"},
    "VOTE":           {"code": 0x0A, "operand": True,  "desc": "Consensus vote"},
    "DELEGATE":       {"code": 0x0B, "operand": True,  "desc": "Delegate to sub-agent"},
    "ROUTE":          {"code": 0x0C, "operand": True,  "desc": "Route to model"},
    "ASSERT":         {"code": 0x0D, "operand": False, "desc": "Assert TOS is truthy"},
    "JMP_IF":         {"code": 0x0E, "operand": True,  "desc": "Conditional jump"},
    "JMP":            {"code": 0x0F, "operand": True,  "desc": "Unconditional jump"},
    "HALT":           {"code": 0x10, "operand": False, "desc": "Halt execution"},
    "GAS_METER":      {"code": 0x11, "operand": True,  "desc": "Deduct gas units"},
    "LOG_EMIT":       {"code": 0x12, "operand": True,  "desc": "Emit log message"},
    "RETURN":         {"code": 0x13, "operand": False, "desc": "Return TOS"},
    "CMP_GT":         {"code": 0x20, "operand": False, "desc": "> comparison"},
    "CMP_LT":         {"code": 0x21, "operand": False, "desc": "< comparison"},
    "CMP_EQ":         {"code": 0x22, "operand": False, "desc": "== comparison"},
    "CMP_NE":         {"code": 0x23, "operand": False, "desc": "!= comparison"},
    "CMP_GE":         {"code": 0x24, "operand": False, "desc": ">= comparison"},
    "CMP_LE":         {"code": 0x25, "operand": False, "desc": "<= comparison"},
    "SET_VAR":        {"code": 0x30, "operand": True,  "desc": "Set variable binding"},
    "CALL_FUNC":      {"code": 0x31, "operand": True,  "desc": "Call user-defined function"},
    "IMPORT_MOD":     {"code": 0x32, "operand": True,  "desc": "Import module by path"},
    "OPENCLAW_TOOL":  {"code": 0x40, "operand": True,  "desc": "OpenClaw sandboxed tool call"},
    # Instinct SDD opcodes (0x65–0x68 per governance/bytecode_spec.yaml)
    "SPEC_DEFINE":    {"code": 0x65, "operand": True,  "desc": "Define Instinct spec"},
    "SPEC_GATE":      {"code": 0x66, "operand": True,  "desc": "Gate on Instinct spec"},
    "SPEC_UPDATE":    {"code": 0x67, "operand": True,  "desc": "Update Instinct spec"},
    "SPEC_SEAL":      {"code": 0x68, "operand": True,  "desc": "Seal Instinct spec with SHA-256"},
}

# Reverse lookup: code → name
_CODE_TO_NAME: dict[int, str] = {v["code"]: k for k, v in OPCODES.items()}

# Glyph → primary opcode
_GLYPH_OP: dict[str, str] = {
    "Δ": "CALL_HOST",
    "Ж": "APPLY_CONSTRAINT",
    "⨝": "VOTE",
    "⌘": "DELEGATE",
    "∇": "PUSH",
    "⩕": "GAS_METER",
    "⊎": "JMP_IF",
}

_MAGIC = b"HLB\x00"
_FORMAT_VERSION = 0x0004  # v0.4


class HLFBytecode:
    """Encode AST to .hlb bytecode and decode/disassemble .hlb files."""

    def encode(self, ast: dict[str, Any]) -> bytes:
        """Compile AST to binary .hlb bytecode."""
        const_pool: list[bytes] = []
        instructions: list[bytes] = []

        def add_const(value: str) -> int:
            enc = value.encode("utf-8")
            const_pool.append(bytes([0x00]) + struct.pack(">H", len(enc)) + enc)
            return len(const_pool) - 1

        statements = ast.get("statements", [])
        for stmt in statements:
            _emit_stmt(stmt, instructions, const_pool, add_const)

        # Emit HALT at end
        instructions.append(bytes([OPCODES["HALT"]["code"]]))

        code_bytes = b"".join(instructions)
        pool_bytes = _encode_pool(const_pool)

        # CRC32 over code section
        crc = zlib.crc32(code_bytes) & 0xFFFFFFFF

        header = (
            _MAGIC
            + struct.pack(">H", _FORMAT_VERSION)
            + struct.pack(">I", len(code_bytes))
            + struct.pack(">I", crc)
            + struct.pack(">H", 0x0000)  # flags
        )

        payload = header + pool_bytes + code_bytes

        # Prepend SHA-256 of payload (32 bytes) for integrity
        sha = hashlib.sha256(payload).digest()
        return sha + payload

    def disassemble(self, data: bytes) -> dict[str, Any]:
        """Disassemble .hlb binary to human-readable assembly."""
        if len(data) < 48:
            raise ValueError("Truncated .hlb file")

        sha256 = data[:32].hex()
        payload = data[32:]

        if payload[:4] != _MAGIC:
            raise ValueError("Invalid .hlb magic bytes")

        fmt_ver = struct.unpack(">H", payload[4:6])[0]
        code_len = struct.unpack(">I", payload[6:10])[0]
        stored_crc = struct.unpack(">I", payload[10:14])[0]
        flags = struct.unpack(">H", payload[14:16])[0]

        # Parse constant pool
        pool, pool_size = _decode_pool(payload[16:])
        code_start = 16 + pool_size
        code_bytes = payload[code_start : code_start + code_len]

        # Verify CRC
        actual_crc = zlib.crc32(code_bytes) & 0xFFFFFFFF
        crc_ok = actual_crc == stored_crc

        # Verify SHA-256
        sha_ok = hashlib.sha256(payload).digest().hex() == sha256

        instructions: list[dict[str, Any]] = []
        disasm_lines: list[str] = []
        pc = 0
        while pc < len(code_bytes):
            op_byte = code_bytes[pc]
            op_name = _CODE_TO_NAME.get(op_byte, f"UNKNOWN(0x{op_byte:02X})")
            op_info = OPCODES.get(op_name, {})
            has_operand = op_info.get("operand", False)

            if has_operand and pc + 2 < len(code_bytes):
                operand = struct.unpack(">H", code_bytes[pc + 1 : pc + 3])[0]
                const_val = pool[operand] if operand < len(pool) else f"<idx {operand}>"
                disasm_lines.append(f"  {pc:04X}  {op_name:<18} #{operand}  ; {const_val!r}")
                instructions.append({"pc": pc, "op": op_name, "operand": operand, "const": const_val})
                pc += 3
            else:
                disasm_lines.append(f"  {pc:04X}  {op_name}")
                instructions.append({"pc": pc, "op": op_name})
                pc += 1

        header_info = {
            "format_version": f"0x{fmt_ver:04X}",
            "code_length": code_len,
            "constant_pool_size": len(pool),
            "crc32_ok": crc_ok,
            "sha256_ok": sha_ok,
            "sha256": sha256,
            "flags": f"0x{flags:04X}",
        }

        return {
            "header": header_info,
            "constant_pool": pool,
            "instructions": instructions,
            "disassembly": "\n".join(disasm_lines),
        }


# ── Internal helpers ──────────────────────────────────────────────────────────


def _emit_stmt(
    stmt: dict[str, Any],
    instructions: list[bytes],
    const_pool: list[bytes],
    add_const,
) -> None:
    """Emit bytecode instructions for one AST statement."""
    kind = stmt.get("kind", "")

    if kind == "glyph_stmt":
        glyph = stmt.get("glyph", "Δ")
        tag = stmt.get("tag", "")
        args = stmt.get("arguments", [])
        op_name = _GLYPH_OP.get(glyph, "CALL_HOST")
        desc = f"{glyph} [{tag}]" if tag else str(glyph)
        idx = add_const(desc)
        # Emit GAS_METER first
        instructions.append(bytes([OPCODES["GAS_METER"]["code"]]) + struct.pack(">H", 2))
        # Push arguments
        for arg in args:
            _emit_arg(arg, instructions, add_const)
        # Emit primary opcode
        instructions.append(bytes([OPCODES[op_name]["code"]]) + struct.pack(">H", idx))

    elif kind == "set_stmt":
        name = stmt.get("name", "")
        value = stmt.get("value", {})
        _emit_value(value, instructions, add_const)
        idx = add_const(name)
        instructions.append(bytes([OPCODES["SET_VAR"]["code"]]) + struct.pack(">H", idx))

    elif kind == "memory_stmt":
        name = stmt.get("name", "")
        args = stmt.get("arguments", [])
        for arg in args:
            _emit_arg(arg, instructions, add_const)
        idx = add_const(name)
        instructions.append(bytes([OPCODES["MEMORY_STORE"]["code"]]))

    elif kind == "recall_stmt":
        name = stmt.get("name", "")
        idx = add_const(name)
        instructions.append(bytes([OPCODES["PUSH"]["code"]]) + struct.pack(">H", idx))
        instructions.append(bytes([OPCODES["MEMORY_RECALL"]["code"]]))

    elif kind in ("spec_define_stmt", "spec_gate_stmt", "spec_update_stmt", "spec_seal_stmt"):
        op_map = {
            "spec_define_stmt": "SPEC_DEFINE",
            "spec_gate_stmt":   "SPEC_GATE",
            "spec_update_stmt": "SPEC_UPDATE",
            "spec_seal_stmt":   "SPEC_SEAL",
        }
        op_name = op_map[kind]
        tag = stmt.get("tag", "")
        idx = add_const(tag)
        instructions.append(bytes([OPCODES[op_name]["code"]]) + struct.pack(">H", idx))

    elif kind == "import_stmt":
        path = stmt.get("path", "")
        idx = add_const(path)
        instructions.append(bytes([OPCODES["IMPORT_MOD"]["code"]]) + struct.pack(">H", idx))

    elif kind == "log_stmt":
        value = stmt.get("value", {})
        _emit_value(value, instructions, add_const)
        idx = add_const("log")
        instructions.append(bytes([OPCODES["LOG_EMIT"]["code"]]) + struct.pack(">H", idx))

    elif kind == "if_stmt":
        # Simplified: push condition, emit JMP_IF (target filled later)
        name = stmt.get("name", "")
        value = stmt.get("value", {})
        idx_name = add_const(name)
        instructions.append(bytes([OPCODES["LOAD"]["code"]]) + struct.pack(">H", idx_name))
        _emit_value(value, instructions, add_const)
        cmp_op = {"<": "CMP_LT", ">": "CMP_GT", "==": "CMP_EQ",
                  "!=": "CMP_NE", ">=": "CMP_GE", "<=": "CMP_LE"}.get(
            stmt.get("cmp", "=="), "CMP_EQ"
        )
        instructions.append(bytes([OPCODES[cmp_op]["code"]]))
        instructions.append(bytes([OPCODES["JMP_IF"]["code"]]) + struct.pack(">H", 0x0000))

    elif kind == "return_stmt":
        value = stmt.get("value")
        if value:
            _emit_value(value, instructions, add_const)
        instructions.append(bytes([OPCODES["RETURN"]["code"]]))

    elif kind == "call_stmt":
        name = stmt.get("name", "")
        args = stmt.get("arguments", [])
        for arg in args:
            _emit_arg(arg, instructions, add_const)
        idx = add_const(name)
        instructions.append(bytes([OPCODES["CALL_FUNC"]["code"]]) + struct.pack(">H", idx))

    else:
        # Fallback: no-op with comment
        pass


def _emit_arg(arg: dict[str, Any], instructions: list[bytes], add_const) -> None:
    kind = arg.get("kind", "")
    if kind == "kv_arg":
        _emit_value(arg.get("value", {}), instructions, add_const)
        idx = add_const(arg.get("name", ""))
        instructions.append(bytes([OPCODES["STORE"]["code"]]) + struct.pack(">H", idx))
    elif kind in ("path_arg", "var_arg", "pos_arg"):
        val_str = str(arg.get("value", ""))
        idx = add_const(val_str)
        instructions.append(bytes([OPCODES["PUSH"]["code"]]) + struct.pack(">H", idx))


def _emit_value(value: dict[str, Any], instructions: list[bytes], add_const) -> None:
    if not value:
        return
    v = str(value.get("value", ""))
    idx = add_const(v)
    instructions.append(bytes([OPCODES["PUSH"]["code"]]) + struct.pack(">H", idx))


def _encode_pool(pool: list[bytes]) -> bytes:
    return struct.pack(">H", len(pool)) + b"".join(pool)


def _decode_pool(data: bytes) -> tuple[list[str], int]:
    if len(data) < 2:
        return [], 0
    count = struct.unpack(">H", data[:2])[0]
    offset = 2
    pool: list[str] = []
    for _ in range(count):
        if offset >= len(data):
            break
        _type = data[offset]
        offset += 1
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        raw = data[offset : offset + length]
        offset += length
        try:
            pool.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            pool.append(raw.hex())
    return pool, offset
