from __future__ import annotations

from hlf_mcp.hlf.code_execution import execute_code_bearing_hlf
from hlf_mcp.hlf.compiler import HLFCompiler


def test_function_block_executes_in_hlf_vm_sandbox() -> None:
    source = (
        "[HLF-v3]\n"
        "MODULE demo {\n"
        "  FUNCTION main {\n"
        "    RESULT 0 \"function-ok\"\n"
        "  }\n"
        "}\n"
        "Ω\n"
    )

    result = execute_code_bearing_hlf(source, entrypoint="main", tier="sovereign")

    assert result["status"] == "ok"
    assert result["compiled"] is True
    assert result["verified"] is True
    assert result["executed"] is True
    assert result["sandbox_mode"] == "hlf-vm-bytecode"
    assert result["selected_block"]["block_type"] == "function"
    assert result["runtime"]["result"] == "function-ok"
    assert result["result_artifact"]["kind"] == "RESULT"
    assert result["trace_ref"] in result["hlf_result"]
    assert HLFCompiler().compile(result["hlf_result"])["errors"] == []


def test_hlf_code_glyph_body_executes_when_language_is_hlf() -> None:
    source = '[HLF-v3]\nΔ [CODE] name="inline" language="hlf" body="RESULT 0 \\"inline-ok\\""\nΩ\n'

    result = execute_code_bearing_hlf(source, entrypoint="inline", tier="sovereign")

    assert result["status"] == "ok"
    assert result["executed"] is True
    assert result["selected_block"]["block_type"] == "code"
    assert result["runtime"]["result"] == "inline-ok"


def test_non_hlf_code_payload_is_compile_only_not_faked() -> None:
    source = '[HLF-v3]\nΔ [CODE] name="py" language="python" body="print(1)"\nΩ\n'

    result = execute_code_bearing_hlf(source, entrypoint="py", tier="sovereign")

    assert result["status"] == "unsupported_language"
    assert result["compiled"] is True
    assert result["verified"] is True
    assert result["executed"] is False
    assert result["sandbox_mode"] == "compile-only-non-hlf-code"
    assert "Only HLF code payloads" in result["runtime"]["reason"]


def test_code_bearing_dry_run_returns_governed_result_without_execution() -> None:
    source = "[HLF-v3]\nFUNCTION main {\n  RESULT 0 \"dry\"\n}\nΩ\n"

    result = execute_code_bearing_hlf(source, dry_run=True, tier="sovereign")

    assert result["status"] == "dry_run_ok"
    assert result["executed"] is False
    assert result["sandbox_mode"] == "hlf-vm-dry-run"
    assert result["result_artifact"]["governed"] is True
    assert HLFCompiler().compile(result["hlf_result"])["errors"] == []
