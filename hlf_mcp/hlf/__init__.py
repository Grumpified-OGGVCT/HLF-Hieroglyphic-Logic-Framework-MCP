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
from hlf_mcp.hlf.capability_manifest import CapabilityManifest
from hlf_mcp.hlf.codegen import HLFCodeGenerator
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.effect_extractor import EffectExtractor
from hlf_mcp.hlf.embodied import (
    EmbodiedContractAssessment,
    assess_embodied_host_call,
    build_embodied_action_envelope,
    build_simulated_embodied_result,
    is_embodied_policy_trace,
)
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.linter import HLFLinter
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
from hlf_mcp.hlf.routing.failover import FailoverManager, NodeFailureEvent

# Phase 7: Knowledge Memory Contracts
from hlf_mcp.hlf.knowledge.freshness_guarantee import FreshnessGuarantee, FreshnessGuaranteeChecker
from hlf_mcp.hlf.knowledge.consistency_proof import ConsistencyProof, ConsistencyProofResult
from hlf_mcp.hlf.knowledge.memory_lease import LeaseManager, LeaseViolationError, MemoryLease
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
    "HLFCodeGenerator",
    "HLFCompiler",
    "EffectExtractor",
    "HLFFormatter",
    "HLFLinter",
    "HLFRuntime",
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
    # Phase 7: Knowledge Memory Contracts
    "FreshnessGuarantee",
    "FreshnessGuaranteeChecker",
    "ConsistencyProof",
    "ConsistencyProofResult",
    "LeaseManager",
    "LeaseViolationError",
    "MemoryLease",
]
