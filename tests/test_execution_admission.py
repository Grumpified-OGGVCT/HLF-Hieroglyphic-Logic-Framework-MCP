from __future__ import annotations

from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.execution_admission import evaluate_verifier_admission
from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.runtime import HLFRuntime


def test_execution_admission_denies_counterexample() -> None:
    verifier = FormalVerifier()

    decision = evaluate_verifier_admission(
        {
            "statements": [
                {
                    "tag": "PARALLEL",
                    "tasks": [{} for _ in range(101)],
                }
            ]
        },
        verifier=verifier,
        tier="hearth",
    )

    assert decision.admitted is False
    assert decision.verdict == "verification_denied"
    assert decision.report["failed"] == 1


def test_runtime_blocks_when_verification_admission_denies() -> None:
    source = '[HLF-v3]\nΔ [INTENT] goal="sealed-run"\nЖ [ASSERT] status="ok"\n∇ [RESULT] message="sealed"\nΩ\n'
    compiler = HLFCompiler()
    bytecoder = HLFBytecode()
    compiled = compiler.compile(source)
    bytecode = bytecoder.encode(compiled["ast"])

    result = HLFRuntime().run(
        bytecode,
        ast=compiled["ast"],
        source=source,
        verification_admission={
            "admitted": False,
            "verdict": "verification_denied",
            "reasons": ["Counterexample found during proof preflight."],
        },
    )

    assert result["status"] == "verification_blocked"
    assert result["gas_used"] == 0
    assert result["verification"]["verdict"] == "verification_denied"
