from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

AuthorityLane = Literal[
    "full-original-target",
    "present-packaged-current-truth",
    "bridge-recovery-material",
    "invalid-mistaken-checkout-artifact",
]


class DownstreamTask(StrEnum):
    RESTORE_GRAMMAR = "restore-grammar"
    MANDATORY_INTERNAL_HLF = "mandatory-internal-hlf"


@dataclass(frozen=True, slots=True)
class AuthoritySurface:
    lane: AuthorityLane
    status: str
    summary: str
    authorities: tuple[str, ...]
    implementation_scope: tuple[str, ...]
    downstream_guidance: tuple[str, ...] = ()


FULL_ORIGINAL_HLF_AUTHORITY_TARGET = AuthoritySurface(
    lane="full-original-target",
    status="vision-true target authority; not present-tense packaged completion",
    summary=(
        "HLF is the intended governed language and coordination substrate joining human "
        "intent, agents, tools, memory, verification, audit, and execution through a bounded "
        "meaning layer."
    ),
    authorities=(
        "AGENTS.md",
        "docs/HLF_VISION_PLAIN_LANGUAGE.md",
        "docs/HLF_CLAIM_LANES.md",
        "HLF_SOURCE_EXTRACTION_LEDGER.md",
    ),
    implementation_scope=(
        "language core: glyph and ASCII forms, AST/IR, compiler, formatter, linter, portable execution form",
        "effect and governance layer: typed host functions, explicit effects, gas/capsule bounds, policy gates",
        "runtime layer: replayable VM behavior, traces, side-effect tracking, execution proofs",
        "memory layer: provenance, freshness, confidence, trust tier, revocation, lineage",
        "agent coordination layer: delegation, consensus, dissent, role boundaries, handoff lineage",
        "human trust layer: effect previews, plain-language audit, before/after explanations",
        "real-code bridge: governed generation of code, workflows, SQL, shell-safe operations, infrastructure actions",
    ),
)


PRESENT_PACKAGED_CURRENT_TRUTH = AuthoritySurface(
    lane="present-packaged-current-truth",
    status="current-true only where backed by this checkout and tests",
    summary=(
        "The packaged product authority is the hlf_mcp FastMCP surface plus the current "
        "compiler/runtime/governance assets. It is real, useful, and intentionally narrower "
        "than the full HLF target."
    ),
    authorities=(
        "SSOT_HLF_MCP.md",
        "hlf_mcp/server.py",
        "hlf_mcp/hlf/grammar.py",
        "governance/tag_i18n.yaml",
        "governance/templates/dictionary.json",
        "hlf_mcp/hlf/benchmark.py",
    ),
    implementation_scope=(
        "packaged entry point and MCP tool/resource surface under hlf_mcp",
        "current v3 grammar and compiler/runtime behavior, not a full recovered language spec",
        "current governance dictionaries and multilingual aliases as implementation assets, not source doctrine",
        "current benchmarks as bounded measurement surfaces, not proof of total language promotion",
    ),
)


BRIDGE_RECOVERY_MATERIAL = AuthoritySurface(
    lane="bridge-recovery-material",
    status="bridge-true mining material; requires validation before promotion",
    summary=(
        "Recovery files and docs preserve useful HLF-bearing ideas but are not automatically "
        "canonical. Mine them for contracts, then re-implement or validate inside HLF_MCP."
    ),
    authorities=(
        "HLF_MCP_WORKING:hlf_mcp/hlf/swarm_orchestrator.py",
        "HLF_MCP_WORKING:hlf_mcp/hlf/swarm_observer.py",
        "HLF_MCP_WORKING:hlf_mcp/hlf/witness_governance.py",
        "HLF_MCP_WORKING:hlf_mcp/hlf/symbolic_surfaces.py",
        "HLF_MCP_WORKING:hlf_mcp/hlf/formal_verifier.py",
        "recovery docs under docs/HLF_*_RECOVERY_SPEC.md",
    ),
    implementation_scope=(
        "compare semantics and tests before copying behavior",
        "promote only repo-relative, dependency-clean, test-backed contracts",
        "do not import stale runtime databases, generated artifacts, or local environment assumptions",
    ),
)


INVALID_MISTAKEN_CHECKOUT_ARTIFACTS = AuthoritySurface(
    lane="invalid-mistaken-checkout-artifact",
    status="not source truth; concepts may be re-derived only",
    summary=(
        "Mistaken concept-only edits in the wrong checkout are rejected as authority. They can "
        "inspire questions, but not direct code, path, test, grammar, or TextMate changes."
    ),
    authorities=(
        "msty_playground/hlf_repo authority module and tool edits",
        "msty_playground/hlf_repo authority tests",
        "msty_playground/hlf_repo TextMate and grammar widening edits",
    ),
    implementation_scope=(
        "never copy hardcoded checkout paths",
        "never promote unvalidated claims into SSOT current truth",
        "redo any useful concept against HLF_MCP files, tests, and claim lanes",
    ),
)


AUTHORITY_SURFACES: tuple[AuthoritySurface, ...] = (
    FULL_ORIGINAL_HLF_AUTHORITY_TARGET,
    PRESENT_PACKAGED_CURRENT_TRUTH,
    BRIDGE_RECOVERY_MATERIAL,
    INVALID_MISTAKEN_CHECKOUT_ARTIFACTS,
)

_DOWNSTREAM_GUIDANCE: dict[DownstreamTask, tuple[str, ...]] = {
    DownstreamTask.RESTORE_GRAMMAR: (
        "Treat hlf_mcp/hlf/grammar.py, governance/tag_i18n.yaml, governance/templates/dictionary.json, generated docs, and TextMate output as one consistency surface.",
        "Restore only grammar semantics that are supported by parser/compiler/runtime behavior and tests in HLF_MCP.",
        "Use bridge/recovery material as requirements evidence, not as copy-paste source authority.",
        "Reject wrong-checkout grammar widening unless re-derived, claim-lane classified, and verified in this repo.",
    ),
    DownstreamTask.MANDATORY_INTERNAL_HLF: (
        "Make internal HLF usage mandatory only where current packaged tools can validate, explain, and fail closed.",
        "Keep self-hosting and recursive-build language bridge-qualified unless backed by executable evidence.",
        "Represent missing orchestration, memory, governance, verification, and human-trust semantics as bridge obligations instead of optional extras.",
        "Use SSOT_HLF_MCP.md for present-tense claims and vision docs for target-state pressure.",
    ),
}


def authority_matrix() -> dict[str, dict[str, object]]:
    return {
        surface.lane: {
            "status": surface.status,
            "summary": surface.summary,
            "authorities": list(surface.authorities),
            "implementation_scope": list(surface.implementation_scope),
        }
        for surface in AUTHORITY_SURFACES
    }


def downstream_guidance(task: DownstreamTask | str) -> tuple[str, ...]:
    key = task if isinstance(task, DownstreamTask) else DownstreamTask(task)
    return _DOWNSTREAM_GUIDANCE[key]
