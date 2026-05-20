"""
HLF Persona Package — operator doctrine contracts, constitutional gate integration,
doctrine drift detection, composition proofs, and capability decay tracking.

Modules:
  operator_doctrine  — per-persona DoctrineContract, compliance validation, HLF conversion
  gate_integration   — PersonaGate, constitutional check integration, transition proofs
  doctrine_drift     — DoctrineDriftDetector, drift analysis, corrective HLF constraints
  composition_proofs — PersonaCompositionProver, handoff composition verification
  capability_decay   — CapabilityDecayModel, freshness tracking, re-certification triggers

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
        DoctrineDriftDetector,
        DriftReport,
        DriftConstraint,
        PersonaCompositionProver,
        CompositionProof,
        CompositionConflict,
        CompositionConstraint,
        CapabilityDecayModel,
        CapabilityRecord,
        DecayReport,
        RecertificationTrigger,
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
from .doctrine_drift import (
    DoctrineDriftDetector,
    DriftConstraint,
    DriftReport,
)
from .composition_proofs import (
    CompositionConflict,
    CompositionConstraint,
    CompositionProof,
    PersonaCompositionProver,
)
from .capability_decay import (
    CapabilityDecayModel,
    CapabilityRecord,
    DecayReport,
    RecertificationTrigger,
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
    # doctrine_drift
    "DoctrineDriftDetector",
    "DriftReport",
    "DriftConstraint",
    # composition_proofs
    "PersonaCompositionProver",
    "CompositionProof",
    "CompositionConflict",
    "CompositionConstraint",
    # capability_decay
    "CapabilityDecayModel",
    "CapabilityRecord",
    "DecayReport",
    "RecertificationTrigger",
]
