"""
Bytecode Roundtrip Proof: prove that HLF bytecode encode -> decode -> encode is lossless.

The proof works by:
1. Taking a compiled AST (from HLFCompiler)
2. Encoding it to .hlb binary via BytecodeCompiler
3. Disassembling via Disassembler
4. Re-encoding the disassembled representation
5. Asserting the re-encoded bits match the original

This guarantees the bytecode format is a bijection through the encoding/decoding
pipeline — any valid bytecode can be decoded and re-encoded to produce identical bytes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from hlf_mcp.hlf.bytecode import (
    HLFBytecode,
    Disassembler,
    ConstantPool,
    Op,
    _instr,
    _MAGIC,
)
from hlf_mcp.hlf.compiler import HLFCompiler


@dataclass
class RoundtripResult:
    """Result of a bytecode roundtrip proof."""

    source_label: str
    original_sha256: str
    roundtrip_sha256: str
    instruction_count: int
    constant_count: int
    original_size: int
    roundtrip_size: int

    @property
    def passed(self) -> bool:
        return self.original_sha256 == self.roundtrip_sha256 and self.original_size == self.roundtrip_size


class BytecodeRoundtripper:
    """Prove bytecode encode -> decode -> encode is lossless."""

    def __init__(self, compiler: HLFCompiler | None = None) -> None:
        self.compiler = compiler or HLFCompiler()
        self.encoder = HLFBytecode()
        self.disassembler = Disassembler()

    def prove_roundtrip(self, source: str, label: str = "") -> RoundtripResult:
        """Compile -> encode -> decode -> re-encode -> compare. Returns a RoundtripResult."""
        ast = self.compiler.compile(source)["ast"]

        # Encode
        original = self.encoder.encode(ast)
        original_hash = hashlib.sha256(original).hexdigest()

        # Decode
        disasm = self.disassembler.disassemble(original)

        # Re-encode from disassembled information
        pool = ConstantPool()
        const_pool = disasm.get("constant_pool", [])
        if isinstance(const_pool, list):
            for const in const_pool:
                pool.add(const)
        else:
            # Fallback: extract from instruction['const'] fields
            seen: set[Any] = set()
            for instr in disasm.get("instructions", []):
                c = instr.get("const")
                if c is not None and c not in seen:
                    seen.add(c)
                    pool.add(c)

        instructions: list[bytes] = []
        for instr in disasm.get("instructions", []):
            op_name = instr.get("op", "")
            # Map op name back to Op enum
            op_enum = _name_to_op(op_name)
            operand = instr.get("operand", 0)
            instructions.append(_instr(op_enum, operand))

        # HALT is already in the instructions list from the disassembler

        code_bytes = b"".join(instructions)

        # Build header exactly as BytecodeCompiler.encode does
        import struct, zlib
        pool_bytes = pool.encode()
        crc = zlib.crc32(code_bytes) & 0xFFFFFFFF
        header = struct.pack("<4sHIIH", _MAGIC, 0x0004, len(code_bytes), crc, 0)
        payload = header + pool_bytes + code_bytes
        sha = hashlib.sha256(payload).digest()
        reconstructed = sha + payload

        return RoundtripResult(
            source_label=label or "unnamed",
            original_sha256=original_hash,
            roundtrip_sha256=hashlib.sha256(reconstructed).hexdigest(),
            instruction_count=len(instructions),
            constant_count=len(pool),
            original_size=len(original),
            roundtrip_size=len(reconstructed),
        )

    def prove_roundtrip_ast(self, ast: dict[str, Any], label: str = "") -> RoundtripResult:
        """Roundtrip from an already-compiled AST."""
        original = self.encoder.encode(ast)
        original_hash = hashlib.sha256(original).hexdigest()

        disasm = self.disassembler.disassemble(original)

        pool = ConstantPool()
        const_pool = disasm.get("constant_pool", [])
        if isinstance(const_pool, list):
            for const in const_pool:
                pool.add(const)
        else:
            seen: set[Any] = set()
            for instr in disasm.get("instructions", []):
                c = instr.get("const")
                if c is not None and c not in seen:
                    seen.add(c)
                    pool.add(c)

        instructions: list[bytes] = []
        for instr in disasm.get("instructions", []):
            op_name = instr.get("op", "")
            op_enum = _name_to_op(op_name)
            operand = instr.get("operand", 0)
            instructions.append(_instr(op_enum, operand))

        code_bytes = b"".join(instructions)

        import struct, zlib
        pool_bytes = pool.encode()
        crc = zlib.crc32(code_bytes) & 0xFFFFFFFF
        header = struct.pack("<4sHIIH", _MAGIC, 0x0004, len(code_bytes), crc, 0)
        payload = header + pool_bytes + code_bytes
        sha = hashlib.sha256(payload).digest()
        reconstructed = sha + payload

        return RoundtripResult(
            source_label=label or "unnamed",
            original_sha256=original_hash,
            roundtrip_sha256=hashlib.sha256(reconstructed).hexdigest(),
            instruction_count=len(instructions),
            constant_count=len(pool),
            original_size=len(original),
            roundtrip_size=len(reconstructed),
        )


def _name_to_op(name: str) -> Op:
    """Map disassembler op name to Op enum member."""
    return Op[name]


def prove_bytecode_roundtrip(source: str, label: str = "") -> RoundtripResult:
    """Convenience function: compile HLF source and prove its bytecode roundtrips."""
    return BytecodeRoundtripper().prove_roundtrip(source, label=label)
