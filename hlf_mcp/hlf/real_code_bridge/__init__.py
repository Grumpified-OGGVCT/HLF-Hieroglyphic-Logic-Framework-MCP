"""
HLF Real-Code Bridge: equivalence proofs, effect audits, and bytecode roundtrip verification.

This package provides:
  - equivalence.py: Prove HLF bytecode execution is equivalent to Python execution
  - effect_audit.py: Verify declared effects match actual side effects
  - bytecode_roundtrip.py: Prove bytecode encode->decode->encode is lossless
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
]
