"""
HLF Persona Package — operator doctrine contracts and constitutional gate integration.

Modules:
  operator_doctrine  — per-persona DoctrineContract, compliance validation, HLF conversion
  gate_integration   — PersonaGate, constitutional check integration, transition proofs

Primary entry points::

    from hlf_mcp.persona import (
        OperatorDoctrine,
        DoctrineContract,
        DoctrineComplianceReport,
        HandoffContract,
        validate_doctrine_compliance,
        doctrine_to_hlf,
        get_handoff_contract,
        PersonaGate,
        PersonaGateResult,
        CapabilityManifest,
        check_persona_assignment,
        PersonaTransitionProof,
        prove_persona_transition,
    )
"""

from .operator_doctrine import (
    DoctrineComplianceReport,
    DoctrineContract,
    HandoffContract,
    OperatorDoctrine,
    build_operator_doctrine,
    doctrine_to_hlf,
    get_handoff_contract,
    tier_allows,
    validate_doctrine_compliance,
)
from .gate_integration import (
    CapabilityManifest,
    PersonaGate,
    PersonaGateResult,
    PersonaTransitionProof,
    check_persona_assignment,
    prove_persona_transition,
)

__all__ = [
    # operator_doctrine
    "OperatorDoctrine",
    "DoctrineContract",
    "DoctrineComplianceReport",
    "HandoffContract",
    "build_operator_doctrine",
    "validate_doctrine_compliance",
    "doctrine_to_hlf",
    "get_handoff_contract",
    "tier_allows",
    # gate_integration
    "PersonaGate",
    "PersonaGateResult",
    "CapabilityManifest",
    "check_persona_assignment",
    "PersonaTransitionProof",
    "prove_persona_transition",
]
