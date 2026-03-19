from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.formal_verifier import FormalVerifier

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
    tier: str = "hearth"
    requested_tier: str = "hearth"
    mode: str = "enforce"

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
            "tier": self.tier,
            "requested_tier": self.requested_tier,
            "mode": self.mode,
            "approval_requirements": self.approval_requirements(),
        }


def evaluate_verifier_admission(
    ast: Any,
    *,
    verifier: FormalVerifier,
    tier: str = "hearth",
    requested_tier: str | None = None,
    mode: str = "enforce",
) -> VerificationAdmissionDecision:
    normalized_mode = str(mode or "enforce").strip().lower()
    effective_mode = (
        normalized_mode if normalized_mode in {"enforce", "audit", "disabled", "off"} else "enforce"
    )
    effective_tier = _normalize_tier(tier)
    effective_requested_tier = _normalize_tier(requested_tier or tier)
    effect_summary = summarize_execution_effects(ast)

    if effective_mode in {"disabled", "off"}:
        return VerificationAdmissionDecision(
            verdict="verification_disabled",
            admitted=True,
            reasons=["Verifier-backed admission is disabled for this execution request."],
            report={},
            effect_summary=effect_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
        )

    try:
        report = verifier.verify_constraints(ast)
        report_payload = report.to_dict()
    except Exception as exc:  # noqa: BLE001
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
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
        )

    if report.failed_count > 0 or report.error_count > 0:
        return VerificationAdmissionDecision(
            verdict="verification_denied",
            admitted=False,
            reasons=[
                "Formal verifier reported a counterexample or proof error, so execution admission is denied.",
                str(report_payload.get("operator_summary", "")),
            ],
            report=report_payload,
            effect_summary=effect_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
        )

    if report.unknown_count > 0:
        requires_review = effective_mode == "enforce"
        return VerificationAdmissionDecision(
            verdict="verification_review_required" if requires_review else "verification_warning",
            admitted=not requires_review,
            reasons=[
                "Formal verifier returned unknown results, so the proof lane is incomplete for this execution.",
                str(report_payload.get("operator_summary", "")),
            ],
            requires_operator_review=requires_review,
            report=report_payload,
            effect_summary=effect_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
        )

    if report.total_count == 0 or (
        report.skipped_count == report.total_count
        and report.proven_count == 0
        and report.failed_count == 0
        and report.error_count == 0
        and report.unknown_count == 0
    ):
        return VerificationAdmissionDecision(
            verdict="verification_advisory_only",
            admitted=True,
            reasons=[
                "No executable proof constraints were extracted from this packaged AST, so admission remains advisory-only.",
                str(report_payload.get("operator_summary", "")),
            ],
            report=report_payload,
            effect_summary=effect_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
        )

    if report.all_proven:
        return VerificationAdmissionDecision(
            verdict="verification_admitted",
            admitted=True,
            reasons=[
                "Formal verifier proved every extracted packaged constraint for this execution."
            ],
            report=report_payload,
            effect_summary=effect_summary,
            tier=effective_tier,
            requested_tier=effective_requested_tier,
            mode=effective_mode,
        )

    return VerificationAdmissionDecision(
        verdict="verification_admitted_with_skips",
        admitted=True,
        reasons=[
            "Formal verifier admitted execution, but some extracted checks were skipped without producing a contradiction.",
            str(report_payload.get("operator_summary", "")),
        ],
        report=report_payload,
        effect_summary=effect_summary,
        tier=effective_tier,
        requested_tier=effective_requested_tier,
        mode=effective_mode,
    )
