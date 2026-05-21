"""
HLF Real-Code Bridge: equivalence proofs, effect audits, bytecode roundtrip
verification, and unified proof matrix.

This package provides:
  - equivalence.py: Prove HLF bytecode execution is equivalent to Python execution
  - effect_audit.py: Verify declared effects match actual side effects
  - bytecode_roundtrip.py: Prove bytecode encode->decode->encode is lossless
  - proof_matrix.py: Aggregate all 3 proof types into a single report per fixture
"""

from hlf_mcp.hlf.real_code_bridge.equivalence import (
    EquivalenceProver,
    EquivalenceResult,
    prove_equivalence,
)
from hlf_mcp.hlf.real_code_bridge.effect_audit import (
    EffectAuditor,
    AuditResult,
    audit_effects,
)
from hlf_mcp.hlf.real_code_bridge.bytecode_roundtrip import (
    BytecodeRoundtripper,
    RoundtripResult,
    prove_bytecode_roundtrip,
)
from hlf_mcp.hlf.real_code_bridge.proof_matrix import (
    ProofMatrix,
    ProofMatrixEntry,
    FixtureCatalog,
    ProofMatrixReport,
)

__all__ = [
    "EquivalenceProver",
    "EquivalenceResult",
    "prove_equivalence",
    "EffectAuditor",
    "AuditResult",
    "audit_effects",
    "BytecodeRoundtripper",
    "RoundtripResult",
    "prove_bytecode_roundtrip",
    "ProofMatrix",
    "ProofMatrixEntry",
    "FixtureCatalog",
    "ProofMatrixReport",
]
