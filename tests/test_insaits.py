from __future__ import annotations

from hlf_mcp.hlf.bytecode import BytecodeCompiler
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.insaits import decompile, decompile_bytecode, similarity_gate

COMPILER = HLFCompiler()


def _program(body: str) -> str:
    return f"[HLF-v3]\n{body}\nΩ\n"


def test_decompile_ast_produces_structured_markdown() -> None:
    result = COMPILER.compile(_program('SET target = "/app"\nRESULT 0 "ok"'))
    text = decompile(result["ast"])

    assert text.startswith("## HLF v3 Program")
    assert "### Statements" in text
    assert "set_stmt" in text.lower() or "result_stmt" in text.lower()
    assert "Estimated gas" in text


def test_decompile_includes_variable_bindings_when_present() -> None:
    result = COMPILER.compile(_program('SET target = "/app"\nSET mode = "ro"\nRESULT 0 "ok"'))
    text = decompile(result["ast"])

    assert "### Variable Bindings" in text
    assert "target" in text
    assert "/app" in text


def test_decompile_bytecode_renders_header_and_instruction_prose() -> None:
    ast = COMPILER.compile(_program('SET count = 42\nRESULT 0 "ok"'))["ast"]
    hlb = BytecodeCompiler().encode(ast)
    text = decompile_bytecode(hlb)

    assert text.startswith("## HLF Bytecode Decompilation")
    assert "### Header" in text
    assert "### Instructions" in text
    assert "PUSH_CONST" in text or "STORE_IMMUT" in text or "HALT" in text


def test_decompile_bytecode_fails_closed_for_invalid_input() -> None:
    text = decompile_bytecode(b"not-valid-hlb")
    assert text.startswith("## Disassembly failed")


def test_similarity_gate_passes_for_near_equivalent_text() -> None:
    result = similarity_gate(
        "analyze deploy target and return success",
        "analyze target deploy then return success",
        threshold=0.5,
    )

    assert result["passed"] is True
    assert result["similarity"] >= 0.5


def test_similarity_gate_fails_for_semantically_distant_text() -> None:
    result = similarity_gate("deploy application", "banana orbit taxonomy", threshold=0.2)

    assert result["passed"] is False
    assert result["similarity"] < 0.2
