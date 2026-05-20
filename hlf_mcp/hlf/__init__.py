"""Canonical public HLF surface for the packaged product."""

from hlf_mcp.hlf.authority import (
    AUTHORITY_SURFACES,
    BRIDGE_RECOVERY_MATERIAL,
    FULL_ORIGINAL_HLF_AUTHORITY_TARGET,
    INVALID_MISTAKEN_CHECKOUT_ARTIFACTS,
    PRESENT_PACKAGED_CURRENT_TRUTH,
    AuthoritySurface,
    DownstreamTask,
    authority_matrix,
    downstream_guidance,
)
from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    CrossManifestConsistency,
    ManifestIntegrityProof,
    check_cross_manifest_consistency,
    prove_manifest_integrity,
)
from hlf_mcp.hlf.codegen import HLFCodeGenerator
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.effect_extractor import (
    EffectCompositionProof,
    EffectExtractor,
    prove_conditional_composition,
    prove_parallel_composition,
    prove_sequential_composition,
)
from hlf_mcp.hlf.embodied import (
    EmbodiedContractAssessment,
    assess_embodied_host_call,
    build_embodied_action_envelope,
    build_simulated_embodied_result,
    is_embodied_policy_trace,
)
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.operand_coverage import (
    CANONICAL_OPERATORS,
    OperandCoverage,
    OperandMatrix,
    Operator,
    OperatorFamily,
    find_operand_gaps,
    generate_coverage_report,
    prove_operand_completeness,
)
from hlf_mcp.hlf.parametric_proofs import (
    ParametricProofResult,
    ParametricProver,
    RefinementProofResult,
    prove_list_invariance,
    prove_map_key_uniqueness,
    prove_refinement_soundness,
    prove_set_uniqueness,
)
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.two_channel_executor import (
    ProvenanceChain,
    InstructionChannel,
    DataChannel,
    ExecutionResult,
    TwoChannelExecutor,
    build_instruction_channel,
    build_data_channel,
)
from hlf_mcp.hlf.swarm_mechanics import (
    SWARM_ARTIFACT_KIND,
    build_swarm_mechanics_artifact,
    materialize_swarm_hlf,
)

# Phase 7: Distributed Routing Fabric
from hlf_mcp.hlf.routing.node_registry import NodeRegistry, RegisteredNode
from hlf_mcp.hlf.routing.capability_router import CapabilityRouter, RouteMatch, WorkRequest
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer
from hlf_mcp.hlf.routing.failover import CircuitBreaker, FailoverManager, NodeFailureEvent
from hlf_mcp.hlf.routing.stress_testing import StressScenario, StressResult, RoutingStressTest
from hlf_mcp.hlf.routing.edge_cases import (
    EdgeCaseResult,
    RoutingEdgeCase,
    run_all_edge_cases,
    test_capability_mismatch,
    test_empty_registry,
    test_failover_cascade,
    test_health_check_flapping,
    test_load_balancer_starvation,
    test_race_condition_register_unregister,
    test_single_node_failure,
)

# Phase 7: Knowledge Memory Contracts
from hlf_mcp.hlf.knowledge.freshness_guarantee import FreshnessGuarantee, FreshnessGuaranteeChecker
from hlf_mcp.hlf.knowledge.consistency_proof import ConsistencyProof, ConsistencyProofResult
from hlf_mcp.hlf.knowledge.memory_lease import LeaseManager, LeaseViolationError, MemoryLease

# Phase 8: Orchestration Lifecycle Hardening — plan_versioning is
# safe to import eagerly; checkpoint_executor creates a circular
# dependency via multi_phase_executor → hlf.__init__, so we expose
# it through a lazy accessor.
from hlf_mcp.hlf.plan_versioning import PlanVersion, PlanHistory


def _get_checkpoint_types() -> tuple:
    """Lazy-load checkpoint executor types to avoid circular imports."""
    from hlf_mcp.hlf.checkpoint_executor import (  # noqa: PLC0415
        Checkpoint,
        CheckpointManager,
        CheckpointableExecutor,
        CheckpointedExecutionResult,
    )
    return Checkpoint, CheckpointManager, CheckpointableExecutor, CheckpointedExecutionResult


def __getattr__(name: str):
    """Deferred attribute access for checkpoint types."""
    _checkpoint_attrs = {
        "Checkpoint",
        "CheckpointManager",
        "CheckpointableExecutor",
        "CheckpointedExecutionResult",
    }
    if name in _checkpoint_attrs:
        idx = {
            "Checkpoint": 0,
            "CheckpointManager": 1,
            "CheckpointableExecutor": 2,
            "CheckpointedExecutionResult": 3,
        }[name]
        return _get_checkpoint_types()[idx]
    raise AttributeError(f"module 'hlf_mcp.hlf' has no attribute '{name}'")
# Phase 9: Audit & Trust Layer
from hlf_mcp.hlf.audit_trail import (
    AuditEvent,
    AuditTrail,
    generate_execution_audit,
    summarize_audit,
    audit_to_html,
)
from hlf_mcp.hlf.trust_surface import (
    TrustEdge,
    TrustSurface,
    build_default_trust_surface,
    validate_trust_against_constitution,
)
from hlf_mcp.hlf.review_proof import (
    ReviewRecord,
    ReviewProof,
    prove_review_completeness,
    generate_review_checklist,
    audit_review_gaps,
    generate_review_proof_markdown,
)
# Phase 10: Formal Verification Proof Depth Hardening
from hlf_mcp.hlf.formal_verifier import (
    ConstraintKind,
    FormalVerifier,
    GateDecision,
    VerificationBlockedError,
    VerificationGate,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    z3_available,
)
from hlf_mcp.hlf.counterexample_quality import (
    Counterexample,
    CounterexampleGenerator,
    compare_counterexamples,
    explain_counterexample,
    generate_minimal_counterexample,
    suggest_fix,
)
from hlf_mcp.hlf.proof_depth import (
    ProofDepth,
    ProofObligation,
    deepen_proof,
    generate_proof_obligations,
    measure_proof_depth,
    rank_obligations_by_impact,
)
from hlf_mcp.hlf.symbolic_surfaces import (
    audit_symbolic_surface,
    compile_symbolic_surface,
    explain_relation_edges,
    extract_relation_edges,
    project_relation_edges,
)
from hlf_mcp.hlf.translator import (
    Tone,
    TranslationRepairPlan,
    build_translation_repair_plan,
    canonicalize_translation_text,
    chinese_to_hlf,
    detect_input_language,
    detect_system_language,
    detect_tone,
    english_to_hlf,
    hlf_source_to_english,
    hlf_source_to_language,
    hlf_to_english,
    hlf_to_language,
    language_to_hlf,
    resolve_language,
    translation_diagnostics,
)

__all__ = [
    "HLFBenchmark",
    "downstream_guidance",
    "authority_matrix",
    "DownstreamTask",
    "AuthoritySurface",
    "PRESENT_PACKAGED_CURRENT_TRUTH",
    "INVALID_MISTAKEN_CHECKOUT_ARTIFACTS",
    "FULL_ORIGINAL_HLF_AUTHORITY_TARGET",
    "BRIDGE_RECOVERY_MATERIAL",
    "AUTHORITY_SURFACES",
    "HLFBytecode",
    "CapabilityManifest",
    "CrossManifestConsistency",
    "ManifestIntegrityProof",
    "check_cross_manifest_consistency",
    "prove_manifest_integrity",
    "HLFCodeGenerator",
    "HLFCompiler",
    "EffectCompositionProof",
    "EffectExtractor",
    "prove_conditional_composition",
    "prove_parallel_composition",
    "prove_sequential_composition",
    "HLFFormatter",
    "HLFLinter",
    "HLFRuntime",
    # Phase 8: Operand Coverage & Parametric Proofs
    "CANONICAL_OPERATORS",
    "OperandCoverage",
    "OperandMatrix",
    "Operator",
    "OperatorFamily",
    "ParametricProofResult",
    "ParametricProver",
    "RefinementProofResult",
    "find_operand_gaps",
    "generate_coverage_report",
    "prove_list_invariance",
    "prove_map_key_uniqueness",
    "prove_operand_completeness",
    "prove_refinement_soundness",
    "prove_set_uniqueness",
    # Phase 7: Swarm / Embodied
    "SWARM_ARTIFACT_KIND",
    "EmbodiedContractAssessment",
    "assess_embodied_host_call",
    "audit_symbolic_surface",
    "build_embodied_action_envelope",
    "build_swarm_mechanics_artifact",
    "build_simulated_embodied_result",
    "Tone",
    "TranslationRepairPlan",
    "build_translation_repair_plan",
    "canonicalize_translation_text",
    "chinese_to_hlf",
    "compile_symbolic_surface",
    "detect_input_language",
    "detect_system_language",
    "detect_tone",
    "hlf_source_to_language",
    "english_to_hlf",
    "explain_relation_edges",
    "extract_relation_edges",
    "hlf_source_to_english",
    "hlf_to_language",
    "hlf_to_english",
    "is_embodied_policy_trace",
    "language_to_hlf",
    "materialize_swarm_hlf",
    "project_relation_edges",
    "resolve_language",
    "translation_diagnostics",
    # Phase 6: Two-Channel Execution Model
    "ProvenanceChain",
    "InstructionChannel",
    "DataChannel",
    "ExecutionResult",
    "TwoChannelExecutor",
    "build_instruction_channel",
    "build_data_channel",
    # Phase 7: Distributed Routing Fabric
    "NodeRegistry",
    "RegisteredNode",
    "CapabilityRouter",
    "RouteMatch",
    "WorkRequest",
    "LoadBalancer",
    "FailoverManager",
    "NodeFailureEvent",
    "CircuitBreaker",
    # Phase 7b: Routing Stress Testing & Edge Cases
    "StressScenario",
    "StressResult",
    "RoutingStressTest",
    "RoutingEdgeCase",
    "EdgeCaseResult",
    "test_empty_registry",
    "test_single_node_failure",
    "test_capability_mismatch",
    "test_race_condition_register_unregister",
    "test_load_balancer_starvation",
    "test_failover_cascade",
    "test_health_check_flapping",
    "run_all_edge_cases",
    # Phase 7: Knowledge Memory Contracts
    "FreshnessGuarantee",
    "FreshnessGuaranteeChecker",
    "ConsistencyProof",
    "ConsistencyProofResult",
    "LeaseManager",
    "LeaseViolationError",
    "MemoryLease",
    # Phase 8: Orchestration Lifecycle Hardening
    "PlanVersion",
    "PlanHistory",
    "Checkpoint",
    "CheckpointManager",
    "CheckpointableExecutor",
    "CheckpointedExecutionResult",
    # Phase 9: Audit & Trust Layer Hardening
    "AuditEvent",
    "AuditTrail",
    "generate_execution_audit",
    "summarize_audit",
    "audit_to_html",
    "TrustEdge",
    "TrustSurface",
    "build_default_trust_surface",
    "validate_trust_against_constitution",
    "ReviewRecord",
    "ReviewProof",
    "prove_review_completeness",
    "generate_review_checklist",
    "audit_review_gaps",
    "generate_review_proof_markdown",
    # Phase 10: Formal Verification Proof Depth Hardening
    "ConstraintKind",
    "FormalVerifier",
    "GateDecision",
    "VerificationBlockedError",
    "VerificationGate",
    "VerificationReport",
    "VerificationResult",
    "VerificationStatus",
    "z3_available",
    "Counterexample",
    "CounterexampleGenerator",
    "compare_counterexamples",
    "explain_counterexample",
    "generate_minimal_counterexample",
    "suggest_fix",
    "ProofDepth",
    "ProofObligation",
    "deepen_proof",
    "generate_proof_obligations",
    "measure_proof_depth",
    "rank_obligations_by_impact",
]
