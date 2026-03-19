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
