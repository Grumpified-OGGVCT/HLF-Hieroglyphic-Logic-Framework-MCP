from __future__ import annotations

import argparse
import json
from pathlib import Path

from hlf_mcp.weekly_artifacts import (
    ALLOWED_ARTIFACT_STATUSES,
    ALLOWED_DECISION_TYPES,
    ALLOWED_TRIAGE_LANES,
    build_persona_gate_status,
    find_weekly_artifact,
    load_verified_weekly_artifacts,
    record_weekly_artifact_decision,
    summarize_weekly_artifacts,
)


def print_payload(payload: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _comma_join(values: object, *, default: str = "none") -> str:
    if not isinstance(values, list):
        return default
    items = [str(item) for item in values if isinstance(item, str) and item]
    return ", ".join(items) if items else default


def _render_artifact_detail(artifact: dict[str, object]) -> str:
    verification = artifact.get("verification") or {}
    distribution = artifact.get("distribution_contract") or {}
    governed_review = artifact.get("governed_review") or {}
    persona_gate_status = build_persona_gate_status(artifact)
    lines = [
        f"Artifact: {artifact.get('artifact_id') or 'unknown'}",
        f"Status: {artifact.get('artifact_status') or 'unknown'}",
        f"Source: {artifact.get('source') or 'unknown'}",
        f"Generated: {artifact.get('generated_at') or 'unknown'}",
        f"Verified: {'yes' if isinstance(verification, dict) and verification.get('verified') else 'no'}",
        "Distribution eligible: "
        + (
            "yes"
            if isinstance(distribution, dict)
            and distribution.get("eligible_for_governed_distribution")
            else "no"
        ),
    ]

    gate_status_counts = persona_gate_status.get("gate_status_counts") or {}
    gate_status_text = (
        ", ".join(
            f"{gate_status}={count}"
            for gate_status, count in sorted(gate_status_counts.items())
            if isinstance(count, int)
        )
        if isinstance(gate_status_counts, dict) and gate_status_counts
        else "none"
    )
    lines.extend(
        [
            "",
            "Persona gate status:",
            f"  Contract source: {persona_gate_status.get('contract_source') or 'unknown'}",
            f"  Owner persona: {persona_gate_status.get('owner_persona') or 'unknown'}",
            "  Review personas: " + _comma_join(persona_gate_status.get("review_personas")),
            "  Required gates: " + _comma_join(persona_gate_status.get("required_gates")),
            f"  Gate status counts: {gate_status_text}",
            "  Pending gates: " + _comma_join(persona_gate_status.get("pending_gates")),
            f"  Operator promotion gate: {persona_gate_status.get('operator_promotion_status') or 'not-required'}",
            f"  Escalate to: {persona_gate_status.get('escalate_to_persona') or 'none'}",
            "  Handoff template: " + str(persona_gate_status.get("handoff_template_ref") or "none"),
        ]
    )

    if isinstance(governed_review, dict) and governed_review:
        lines.extend(
            [
                "",
                "Governed review:",
                f"  Summary: {governed_review.get('summary') or 'none'}",
                f"  Severity: {governed_review.get('severity') or 'unknown'}",
                f"  Change class: {persona_gate_status.get('change_class') or 'unknown'}",
                f"  Owner persona: {persona_gate_status.get('owner_persona') or 'unknown'}",
                "  Review personas: " + _comma_join(persona_gate_status.get("review_personas")),
                "  Required gates: " + _comma_join(persona_gate_status.get("required_gates")),
                f"  Escalate to: {persona_gate_status.get('escalate_to_persona') or 'none'}",
                f"  Operator summary: {persona_gate_status.get('operator_summary') or 'none'}",
                "  Handoff template: " + str(persona_gate_status.get("handoff_template_ref") or "none"),
            ]
        )

    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hlf-evidence",
        description="Query governed weekly evidence artifacts and distribution eligibility.",
    )
    parser.add_argument("--metrics-dir", type=Path, default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List evidence artifacts")
    list_parser.add_argument("--status", choices=sorted(ALLOWED_ARTIFACT_STATUSES), default=None)
    list_parser.add_argument("--decision", choices=sorted(ALLOWED_DECISION_TYPES), default=None)
    list_parser.add_argument("--source", default=None)
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--all", action="store_true", help="Include unverified artifacts")
    list_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show", help="Show a single artifact")
    show_parser.add_argument("artifact_id")
    show_parser.add_argument("--json", action="store_true")

    decide_parser = subparsers.add_parser(
        "decide", help="Append a governed decision record to an artifact"
    )
    decide_parser.add_argument("artifact_id")
    decide_parser.add_argument("--decision", required=True, choices=sorted(ALLOWED_DECISION_TYPES))
    decide_parser.add_argument("--actor", required=True)
    decide_parser.add_argument("--rationale", required=True)
    decide_parser.add_argument("--triage-lane", choices=sorted(ALLOWED_TRIAGE_LANES), default=None)
    decide_parser.add_argument("--evidence-ref", action="append", default=[])
    decide_parser.add_argument("--policy-basis", action="append", default=[])
    decide_parser.add_argument("--supersedes", default=None)
    decide_parser.add_argument("--json", action="store_true")

    summary_parser = subparsers.add_parser("summary", help="Summarize artifact history")
    summary_parser.add_argument("--json", action="store_true")
    return parser


def _list_command(args: argparse.Namespace) -> int:
    artifacts = load_verified_weekly_artifacts(
        args.metrics_dir,
        status=args.status,
        source=args.source,
        decision=args.decision,
        verified_only=not args.all,
        limit=args.limit,
    )
    if args.json:
        print_payload(artifacts, as_json=True)
        return 0

    if not artifacts:
        print("No artifacts matched the requested filters.")
        return 0

    for artifact in artifacts:
        distribution = artifact.get("distribution_contract") or {}
        verification = artifact.get("verification") or {}
        print(
            " | ".join(
                [
                    str(artifact.get("artifact_id") or "unknown"),
                    str(artifact.get("artifact_status") or "unknown"),
                    str(artifact.get("source") or "unknown"),
                    str(artifact.get("generated_at") or "unknown"),
                    "verified" if verification.get("verified") else "unverified",
                    "distribution-eligible"
                    if distribution.get("eligible_for_governed_distribution")
                    else "distribution-pending",
                ]
            )
        )
    return 0


def _show_command(args: argparse.Namespace) -> int:
    artifact = find_weekly_artifact(args.artifact_id, args.metrics_dir)
    if artifact is None:
        print(json.dumps({"status": "not_found", "artifact_id": args.artifact_id}, indent=2))
        return 1
    if args.json:
        print_payload(artifact, as_json=True)
    else:
        print_payload(_render_artifact_detail(artifact), as_json=False)
    return 0


def _decide_command(args: argparse.Namespace) -> int:
    try:
        artifact = record_weekly_artifact_decision(
            artifact_id=args.artifact_id,
            metrics_dir=args.metrics_dir,
            decision=args.decision,
            actor=args.actor,
            rationale=args.rationale,
            triage_lane=args.triage_lane,
            evidence_refs=list(args.evidence_ref or []),
            supersedes=args.supersedes,
            policy_basis=list(args.policy_basis or []),
        )
    except FileNotFoundError:
        print(json.dumps({"status": "not_found", "artifact_id": args.artifact_id}, indent=2))
        return 1

    print_payload(artifact, as_json=True if args.json else False)
    return 0


def _summary_command(args: argparse.Namespace) -> int:
    summary = summarize_weekly_artifacts(args.metrics_dir)
    if args.json:
        print_payload(summary, as_json=True)
        return 0

    print(f"Artifacts: {summary['artifact_count']}")
    print(f"Verified: {summary['verified_count']}")
    print(f"Distribution eligible: {summary['distribution_eligible_count']}")
    print(f"History path: {summary['history_path']}")
    persona_summary = summary.get("persona_review_summary") or {}
    if isinstance(persona_summary, dict):
        print(
            "Persona review artifacts: "
            f"{persona_summary.get('artifact_count', 0)} total, "
            f"{persona_summary.get('attached_contract_count', 0)} attached, "
            f"{persona_summary.get('fallback_contract_count', 0)} fallback"
        )
        owner_counts = persona_summary.get("owner_persona_counts") or {}
        if isinstance(owner_counts, dict) and owner_counts:
            owners = ", ".join(
                f"{persona}={count}" for persona, count in sorted(owner_counts.items())
            )
            print(f"Owner personas: {owners}")
        print(f"Pending persona gates: {persona_summary.get('pending_gate_count', 0)}")
    print(
        json.dumps(
            {"status_counts": summary["status_counts"], "source_counts": summary["source_counts"]},
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        return _list_command(args)
    if args.command == "show":
        return _show_command(args)
    if args.command == "decide":
        return _decide_command(args)
    if args.command == "summary":
        return _summary_command(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
