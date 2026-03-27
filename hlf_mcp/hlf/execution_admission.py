from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.formal_verifier import VerificationReport

_EFFECTFUL_TAGS: frozenset[str] = frozenset(
    {
        "ACTION",
        "CALL",
        "DELEGATE",
        "IMPORT",
        "MEMORY",
        "RECALL",
        "ROUTE",
        "SPAWN",
        "SHELL_EXEC",
        "TOOL",
    }
)


def _normalize_tier(tier: str | None) -> str:
    normalized = str(tier or "hearth").strip().lower()
    return normalized if normalized in {"hearth", "forge", "sovereign"} else "hearth"


def _normalize_trust_state(trust_state: str | None) -> str:
    normalized = str(trust_state or "healthy").strip().lower()
    aliases = {
        "trusted": "healthy",
        "approved": "healthy",
    }
    return aliases.get(normalized, normalized or "healthy")


def _program_nodes(ast: Any) -> list[dict[str, Any]]:
    if isinstance(ast, list):
        return [node for node in ast if isinstance(node, dict)]
    if not isinstance(ast, dict):
        return []
    if isinstance(ast.get("statements"), list):
        return [node for node in ast.get("statements", []) if isinstance(node, dict)]
    if isinstance(ast.get("program"), list):
        return [node for node in ast.get("program", []) if isinstance(node, dict)]
    if isinstance(ast.get("body"), list):
        return [node for node in ast.get("body", []) if isinstance(node, dict)]
    nested_ast = ast.get("ast")
    if nested_ast is not None:
        return _program_nodes(nested_ast)
    return []


def _walk_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    stack = list(reversed(nodes))
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        discovered.append(node)
        for key in ("then", "else", "body", "inner", "action", "statements", "tasks"):
            child = node.get(key)
            if isinstance(child, dict):
                stack.append(child)
            elif isinstance(child, list):
                for item in reversed(child):
                    if isinstance(item, dict):
                        stack.append(item)
    return discovered


def summarize_execution_effects(ast: Any) -> dict[str, Any]:
    nodes = _walk_nodes(_program_nodes(ast))
    tags: set[str] = set()
    tools: set[str] = set()
    for node in nodes:
        tag = str(node.get("tag", "") or "")
        if tag:
            tags.add(tag)
        kind = str(node.get("kind", "") or "")
        if kind in {"tool_stmt", "call_stmt"}:
            name = str(node.get("name", "") or "")
            if name:
                tools.add(name)
    effectful_tags = sorted(tag for tag in tags if tag in _EFFECTFUL_TAGS)
    return {
        "node_count": len(nodes),
        "tags": sorted(tags),
        "tools": sorted(tools),
        "effectful_tags": effectful_tags,
        "effectful": bool(effectful_tags or tools),
    }


@dataclass(slots=True)
class VerificationAdmissionDecision:
    verdict: str
    admitted: bool
    reasons: list[str] = field(default_factory=list)
    requires_operator_review: bool = False
    report: dict[str, Any] = field(default_factory=dict)
    effect_summary: dict[str, Any] = field(default_factory=dict)
    embodied_summary: dict[str, Any] = field(default_factory=dict)
    tier: str = "hearth"
    requested_tier: str = "hearth"
    mode: str = "enforce"
    trust_state: str = "healthy"
    operation_class: str = "read_only"
    policy_posture: str = "advisory"
    risk_factors: list[str] = field(default_factory=list)

    def approval_requirements(self) -> list[dict[str, str]]:
        if not self.requires_operator_review:
            return []
        return [
            {
                "type": "verification_review",
                "scope": "verification",
                "value": self.verdict,
            }
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "admitted": self.admitted,
            "requires_operator_review": self.requires_operator_review,
            "reasons": list(self.reasons),
            "report": dict(self.report),
            "effect_summary": dict(self.effect_summary),
            "embodied_summary": dict(self.embodied_summary),
            "tier": self.tier,
            "requested_tier": self.requested_tier,
            "mode": self.mode,
            "trust_state": self.trust_state,
            "operation_class": self.operation_class,
            "policy_posture": self.policy_posture,
            "risk_factors": list(self.risk_factors),
            "approval_requirements": self.approval_requirements(),
        }


def _merge_reports(*reports: VerificationReport) -> VerificationReport:
    merged = VerificationReport()
    for report in reports:
        for result in report.results:
            merged.add(result)
    return merged


def _embodied_summary(contract: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(contract, dict) or not contract.get("embodied"):
        return {}
    evidence_refs = contract.get("evidence_refs") if isinstance(contract.get("evidence_refs"), list) else []
    return {
        "function_name": str(contract.get("function_name") or ""),
        "safety_class": str(contract.get("safety_class") or "none"),
        "review_posture": str(contract.get("review_posture") or "none"),
        "simulation_only": bool(contract.get("simulation_only", False)),
        "supervisory_only": bool(contract.get("supervisory_only", False)),
        "bounded_spatial_envelope": bool(contract.get("bounded_spatial_envelope", False)),
        "proof_obligations": [str(item) for item in contract.get("proof_obligations", []) if str(item)],
        "evidence_ref_count": len(evidence_refs),
        "world_state_ref_present": bool(str(contract.get("world_state_ref") or "")),
    }


def _derive_operation_class(
    effect_summary: dict[str, Any],
    embodied_effect: dict[str, Any],
) -> str:
    if embodied_effect:
        return "embodied"
    effectful_tags = {str(tag) for tag in effect_summary.get("effectful_tags", []) if str(tag)}
    tool_names = [str(name) for name in effect_summary.get("tools", []) if str(name)]
    if effectful_tags.intersection({"DELEGATE", "SPAWN", "TOOL", "CALL", "ROUTE"}) or tool_names:
        return "delegated"
    if bool(effect_summary.get("effectful", False)):
        return "effectful"
    return "read_only"


def _risk_factors(
    *,
    tier: str,
    requested_tier: str,
    trust_state: str,
    operation_class: str,
) -> list[str]:
    factors: list[str] = []
    if requested_tier != tier:
        factors.append("tier_escalation")
    if requested_tier in {"forge", "sovereign"}:
        factors.append("elevated_tier")
    if trust_state in {"watched", "probation", "restricted"}:
        factors.append(f"trust_{trust_state}")
    if operation_class != "read_only":
        factors.append(f"operation_{operation_class}")
    return factors


def _review_required_for_unknown(
    *,
    tier: str,
    requested_tier: str,
    trust_state: str,
    operation_class: str,
) -> bool:
    if trust_state == "restricted" and operation_class != "read_only":
        return True
    if trust_state in {"watched", "probation"}:
        return True
    if requested_tier != tier or requested_tier in {"forge", "sovereign"}:
        return True
    return operation_class != "read_only"


def _review_required_for_incomplete_proof(
    *,
    tier: str,
    requested_tier: str,
    trust_state: str,
    operation_class: str,
) -> bool:
    if trust_state == "restricted" and operation_class in {"delegated", "embodied"}:
        return True
    if trust_state == "probation":
        return True
    if requested_tier != tier or requested_tier in {"forge", "sovereign"}:
        return operation_class != "read_only"
    return operation_class in {"delegated", "embodied"}


def evaluate_verification_report_admission(
    report: VerificationReport,
    *,
    tier: str = "hearth",
    requested_tier: str | None = None,
    mode: str = "enforce",
    trust_state: str = "healthy",
    effect_summary: dict[str, Any] | None = None,
    embodied_summary: dict[str, Any] | None = None,
    operation_class: str | None = None,
    unknown_reason: str = "Formal verifier returned unknown results, so the proof lane is incomplete for this execution.",
    incomplete_reason: str = "No executable proof constraints were extracted from this packaged AST, so admission remains advisory-only.",
    skipped_reason: str = "Formal verifier admitted execution, but some extracted checks were skipped without producing a contradiction.",
) -> VerificationAdmissionDecision:
    normalized_mode = str(mode or "enforce").strip().lower()
    effective_mode = (
        normalized_mode if normalized_mode in {"enforce", "audit", "disabled", "off"} else "enforce"
    )
    effective_tier = _normalize_tier(tier)
    effective_requested_tier = _normalize_tier(requested_tier or tier)
    effective_trust_state = _normalize_trust_state(trust_state)
    effective_effect_summary = dict(effect_summary or {})
    effective_embodied_summary = dict(embodied_summary or {})
    effective_operation_class = operation_class or _derive_operation_class(
        effective_effect_summary,
        effective_embodied_summary,
    )
    risk_factors = _risk_factors(
        tier=effective_tier,
        requested_tier=effective_requested_tier,
        trust_state=effective_trust_state,
        operation_class=effective_operation_class,
    )

    if effective_mode in {"disabled", "off"}:
        return VerificationAdmissionDecision(
            verdict="verification_disabled",
            admitted=True,
            reasons=["Verifier-backed admission is disabled for this execution request."],
            report={},
            effect_summary=effective_effect_summary,
            embodied_summary=effective_embodied_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
            trust_state=effective_trust_state,
            operation_class=effective_operation_class,
            policy_posture="disabled",
            risk_factors=risk_factors,
        )

    report_payload = report.to_dict()

    if report.failed_count > 0 or report.error_count > 0:
        return VerificationAdmissionDecision(
            verdict="verification_denied",
            admitted=False,
            reasons=[
                "Formal verifier reported a counterexample or proof error, so execution admission is denied.",
                str(report_payload.get("operator_summary", "")),
            ],
            report=report_payload,
            effect_summary=effective_effect_summary,
            embodied_summary=effective_embodied_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
            trust_state=effective_trust_state,
            operation_class=effective_operation_class,
            policy_posture="deny",
            risk_factors=risk_factors,
        )

    if report.unknown_count > 0:
        requires_review = effective_mode == "enforce" and _review_required_for_unknown(
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            trust_state=effective_trust_state,
            operation_class=effective_operation_class,
        )
        return VerificationAdmissionDecision(
            verdict="verification_review_required" if requires_review else "verification_warning",
            admitted=not requires_review,
            reasons=[
                unknown_reason,
                str(report_payload.get("operator_summary", "")),
            ],
            requires_operator_review=requires_review,
            report=report_payload,
            effect_summary=effective_effect_summary,
            embodied_summary=effective_embodied_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
            trust_state=effective_trust_state,
            operation_class=effective_operation_class,
            policy_posture="review" if requires_review else "warning",
            risk_factors=risk_factors,
        )

    if report.total_count == 0 or (
        report.skipped_count == report.total_count
        and report.proven_count == 0
        and report.failed_count == 0
        and report.error_count == 0
        and report.unknown_count == 0
    ):
        requires_review = effective_mode == "enforce" and _review_required_for_incomplete_proof(
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            trust_state=effective_trust_state,
            operation_class=effective_operation_class,
        )
        return VerificationAdmissionDecision(
            verdict="verification_review_required" if requires_review else "verification_advisory_only",
            admitted=not requires_review,
            reasons=[
                incomplete_reason,
                str(report_payload.get("operator_summary", "")),
            ],
            requires_operator_review=requires_review,
            report=report_payload,
            effect_summary=effective_effect_summary,
            embodied_summary=effective_embodied_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
            trust_state=effective_trust_state,
            operation_class=effective_operation_class,
            policy_posture="review" if requires_review else "advisory",
            risk_factors=risk_factors,
        )

    if report.all_proven:
        return VerificationAdmissionDecision(
            verdict="verification_admitted",
            admitted=True,
            reasons=[
                "Formal verifier proved every extracted packaged constraint for this execution."
            ],
            report=report_payload,
            effect_summary=effective_effect_summary,
            embodied_summary=effective_embodied_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
            trust_state=effective_trust_state,
            operation_class=effective_operation_class,
            policy_posture="allow",
            risk_factors=risk_factors,
        )

    requires_review = effective_mode == "enforce" and _review_required_for_incomplete_proof(
        tier=effective_tier,
        requested_tier=effective_requested_tier,
        trust_state=effective_trust_state,
        operation_class=effective_operation_class,
    )

    return VerificationAdmissionDecision(
        verdict="verification_review_required" if requires_review else "verification_admitted_with_skips",
        admitted=not requires_review,
        reasons=[
            skipped_reason,
            str(report_payload.get("operator_summary", "")),
        ],
        requires_operator_review=requires_review,
        report=report_payload,
        effect_summary=effective_effect_summary,
        embodied_summary=effective_embodied_summary,
        tier=effective_tier,
        requested_tier=effective_requested_tier,
        mode=effective_mode,
        trust_state=effective_trust_state,
        operation_class=effective_operation_class,
        policy_posture="review" if requires_review else "allow_with_skips",
        risk_factors=risk_factors,
    )


def evaluate_verifier_admission(
    ast: Any,
    *,
    verifier: FormalVerifier,
    tier: str = "hearth",
    requested_tier: str | None = None,
    mode: str = "enforce",
    embodied_contract: dict[str, Any] | None = None,
    trust_state: str = "healthy",
) -> VerificationAdmissionDecision:
    effect_summary = summarize_execution_effects(ast)
    embodied_effect = _embodied_summary(embodied_contract)

    try:
        report = verifier.verify_constraints(ast)
        if embodied_effect:
            report = _merge_reports(report, verifier.verify_embodied_contract(embodied_contract))
    except Exception as exc:  # noqa: BLE001
        effective_tier = _normalize_tier(tier)
        effective_requested_tier = _normalize_tier(requested_tier or tier)
        effective_trust_state = _normalize_trust_state(trust_state)
        operation_class = _derive_operation_class(effect_summary, embodied_effect)
        risk_factors = _risk_factors(
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            trust_state=effective_trust_state,
            operation_class=operation_class,
        )
        return VerificationAdmissionDecision(
            verdict="verification_denied",
            admitted=False,
            reasons=[f"Verifier execution failed before admission could be established: {exc}"],
            report={
                "total": 0,
                "proven": 0,
                "failed": 0,
                "unknown": 0,
                "skipped": 0,
                "errors": 1,
                "all_proven": False,
                "results": [],
                "operator_summary": f"Verification error: {exc}",
            },
            effect_summary=effect_summary,
            embodied_summary=embodied_effect,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
            trust_state=effective_trust_state,
            operation_class=operation_class,
            policy_posture="deny",
            risk_factors=risk_factors,
        )
    return evaluate_verification_report_admission(
        report,
        tier=tier,
        requested_tier=requested_tier,
        mode=mode,
        trust_state=trust_state,
        effect_summary=effect_summary,
        embodied_summary=embodied_effect,
    )
