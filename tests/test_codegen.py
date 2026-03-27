from __future__ import annotations

from hlf_mcp.hlf.codegen import HLFCodeGenerator


def test_codegen_builds_packaged_v3_source() -> None:
    source = (
        HLFCodeGenerator()
        .set("target", "/srv/app")
        .intent("deploy", "/srv/app")
        .constraint(mode="ro")
        .delegate("builder", "ship")
        .result(0, "ok")
        .build()
    )

    assert source.startswith("[HLF-v3]\n")
    assert 'SET target = "/srv/app"' in source
    assert 'Δ [INTENT] goal="deploy" target="/srv/app"' in source
    assert 'Ж [CONSTRAINT] mode="ro"' in source
    assert '⌘ [DELEGATE] agent="builder" goal="ship"' in source
    assert source.rstrip().endswith("Ω")


def test_codegen_build_and_compile_returns_ast() -> None:
    result = (
        HLFCodeGenerator().set("name", "world").intent("hello").result(0, "ok").build_and_compile()
    )

    assert "ast" in result
    assert result["ast"]["kind"] == "program"
    assert result["gas_estimate"] >= 0


def test_codegen_build_target_artifact_returns_runtime_ready_bytecode_contract() -> None:
    artifact = (
        HLFCodeGenerator()
        .set("target", "/srv/app")
        .intent("deploy", "/srv/app")
        .constraint(mode="ro")
        .delegate("builder", "ship")
        .result(0, "ok")
        .build_target_artifact("hlf-bytecode")
    )

    assert artifact["target"] == "hlf-bytecode"
    assert artifact["source"].startswith("[HLF-v3]\n")
    assert artifact["compile"]["node_count"] >= 4
    assert artifact["compile"]["gas_estimate"] >= 0
    assert artifact["compile"]["ast_sha256"]
    assert artifact["artifact"]["bytecode_hex"]
    assert artifact["artifact"]["bytecode_size_bytes"] > 32
    assert artifact["artifact"]["runtime"] == "HLFRuntime"

    disassembly = artifact["artifact"]["disassembly"]
    assert disassembly["header"]["crc32_ok"] is True
    assert disassembly["header"]["sha256_ok"] is True
    assert len(disassembly["constant_pool"]) >= 1
    assert [instruction["op"] for instruction in disassembly["instructions"]][-1] == "HALT"
    assert any(instruction["op"] == "STORE_IMMUT" for instruction in disassembly["instructions"])
    assert any(instruction["op"] == "CALL_HOST" for instruction in disassembly["instructions"])

    bytecode_summary = artifact["artifact"]["bytecode_summary_en"]
    assert bytecode_summary.startswith("## HLF Bytecode Decompilation\n")
    assert "**STORE_IMMUT**" in bytecode_summary
    assert "**CALL_HOST**" in bytecode_summary
    assert "**HALT**" in bytecode_summary


def test_codegen_build_target_artifact_rejects_unknown_target() -> None:
    try:
        HLFCodeGenerator().set("name", "world").build_target_artifact("python")
    except ValueError as exc:
        assert "Unsupported code generation target 'python'" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported target")
