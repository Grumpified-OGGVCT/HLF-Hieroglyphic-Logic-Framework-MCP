"""
InsAIts Decompiler — Glass-Box AST and bytecode → human-readable English.

Every compiled AST node carries a human_readable field (set by the transformer).
InsAIts reads these fields and produces structured documentation.
The decompile_bytecode() function disassembles .hlb and maps opcodes to prose.
"""

from __future__ import annotations

from typing import Any

_OPCODE_PROSE: dict[str, str] = {
    "NOP": "no operation",
    "PUSH_CONST": "push constant value onto stack",
    "STORE": "store top of stack into mutable variable",
    "LOAD": "load variable value onto stack",
    "STORE_IMMUT": "store top of stack into immutable variable",
    "ADD": "add two numbers",
    "SUB": "subtract two numbers",
    "MUL": "multiply two numbers",
    "DIV": "divide two numbers",
    "MOD": "compute modulo",
    "NEG": "negate top of stack",
    "CMP_EQ": "compare for equality",
    "CMP_NE": "compare for inequality",
    "CMP_LT": "compare less-than",
    "CMP_LE": "compare less-than-or-equal",
    "CMP_GT": "compare greater-than",
    "CMP_GE": "compare greater-than-or-equal",
    "AND": "logical AND",
    "OR": "logical OR",
    "NOT": "logical NOT",
    "JMP": "unconditional jump",
    "JZ": "jump if false (zero)",
    "JNZ": "jump if true (non-zero)",
    "CALL_BUILTIN": "call built-in function",
    "CALL_HOST": "call host function",
    "CALL_TOOL": "call registered tool",
    "OPENCLAW_TOOL": "call OpenClaw sandboxed tool",
    "TAG": "apply semantic tag",
    "INTENT": "express agent intent",
    "RESULT": "return result value",
    "MEMORY_STORE": "store data in RAG memory",
    "MEMORY_RECALL": "recall data from RAG memory",
    "SPEC_DEFINE": "define Instinct spec",
    "SPEC_GATE": "gate on Instinct spec constraint",
    "SPEC_UPDATE": "update Instinct spec",
    "SPEC_SEAL": "seal Instinct spec with SHA-256 checksum",
    "HALT": "halt execution",
}


def decompile(ast: dict[str, Any]) -> str:
    """Convert HLF AST to structured English documentation."""
    statements = ast.get("statements", [])
    version = ast.get("version", "?")
    program_hr = ast.get("human_readable", "")
    sha256 = ast.get("sha256", "")[:16] + "..."

    lines = [
        f"## HLF v{version} Program",
        f"*{program_hr}*",
        f"SHA-256 (first 16): `{sha256}`",
        "",
        "### Statements",
    ]
    for i, node in enumerate(statements, 1):
        if not isinstance(node, dict):
            continue
        hr = node.get("human_readable", node.get("kind", "unknown"))
        kind = node.get("kind", "")
        tag = node.get("tag", "")
        tag_str = f" [{tag}]" if tag else ""
        lines.append(f"{i}. **{kind}{tag_str}** — {hr}")
        # Show arguments
        args = node.get("arguments", [])
        for arg in args:
            if arg.get("kind") == "kv_arg":
                lines.append(f"   - `{arg['name']}` = `{arg.get('value', {}).get('value', '?')}`")
        # Show block contents
        body = node.get("body") or node.get("block")
        if isinstance(body, dict) and body.get("statements"):
            lines.append(f"   *block with {len(body['statements'])} statement(s)*")

    gas = ast.get("gas_estimate", "?")
    env = ast.get("env", {})
    if env:
        lines += ["", "### Variable Bindings"]
        for k, v in env.items():
            lines.append(f"- `{k}` = `{v}`")
    lines += ["", f"*Estimated gas: {gas}*"]
    return "\n".join(lines)


def decompile_bytecode(hlb_data: bytes) -> str:
    """Convert HLF .hlb bytecode to prose description."""
    from hlf_mcp.hlf.bytecode import Disassembler

    try:
        disasm = Disassembler().disassemble(hlb_data)
    except Exception as exc:
        return f"## Disassembly failed\n\nError: {exc}"

    header = disasm.get("header", {})
    pool = disasm.get("constant_pool", [])
    instructions = disasm.get("instructions", [])

    lines = [
        "## HLF Bytecode Decompilation",
        "",
        "### Header",
        f"- Format version: `{header.get('format_version', '?')}`",
        f"- Code length: {header.get('code_length', '?')} bytes",
        f"- Constants: {header.get('constant_pool_size', len(pool))} entries",
        f"- CRC32 OK: {header.get('crc32_ok', '?')}",
        f"- SHA-256 OK: {header.get('sha256_ok', '?')}",
        "",
        "### Instructions",
    ]
    for instr in instructions:
        pc = instr.get("pc", 0)
        op = instr.get("op", "?")
        prose = _OPCODE_PROSE.get(op, f"execute {op}")
        const = instr.get("const")
        const_str = f" — constant: `{const!r}`" if const is not None else ""
        lines.append(f"- `0x{pc:04X}` **{op}**{const_str}: {prose}")

    if pool:
        lines += ["", "### Constant Pool"]
        for i, val in enumerate(pool):
            lines.append(f"- [{i}] `{val!r}`")

    return "\n".join(lines)


def similarity_gate(
    original_text: str,
    decompiled_text: str,
    threshold: float = 0.95,
) -> dict[str, Any]:
    """Check round-trip semantic similarity between original and decompiled text.

    Uses bag-of-words cosine similarity as a lightweight proxy when an
    ML embedding model is unavailable.
    """
    import math
    import re

    def _tokens(text: str) -> dict[str, float]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        tf: dict[str, float] = {}
        for w in words:
            tf[w] = tf.get(w, 0) + 1
        if words:
            m = max(tf.values())
            tf = {k: v / m for k, v in tf.items()}
        return tf

    a = _tokens(original_text)
    b = _tokens(decompiled_text)
    keys = set(a) & set(b)
    if not keys:
        sim = 0.0
    else:
        dot = sum(a[k] * b[k] for k in keys)
        mag_a = math.sqrt(sum(v * v for v in a.values()))
        mag_b = math.sqrt(sum(v * v for v in b.values()))
        sim = dot / (mag_a * mag_b) if mag_a and mag_b else 0.0

    return {
        "similarity": round(sim, 4),
        "threshold": threshold,
        "passed": sim >= threshold,
        "original_tokens": len(a),
        "decompiled_tokens": len(b),
    }
