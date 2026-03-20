from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hlf_mcp.governed_review import (  # noqa: E402
    build_code_quality_governed_review,
    build_doc_accuracy_governed_review,
    build_ethics_review_governed_review,
    build_evolution_governed_review,
    build_model_drift_governed_review,
    build_security_patterns_governed_review,
    build_spec_sentinel_governed_review,
    build_test_health_governed_review,
    evolution_plan_schema,
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _coerce_plan_content(payload: dict[str, Any]) -> dict[str, Any]:
    content = payload.get("content", {})
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _comma_join(values: Any, *, default: str = "none") -> str:
    if not isinstance(values, list):
        return default
    items = [str(item) for item in values if isinstance(item, str) and item]
    return ", ".join(items) if items else default


def _render_persona_handoff(review: dict[str, Any]) -> list[str]:
    return [
        "## Persona Handoff",
        "",
        f"- Change class: {review.get('change_class') or 'unknown'}",
        f"- Lane: {review.get('lane') or 'unknown'}",
        f"- Owner persona: {review.get('owner_persona') or 'unknown'}",
        f"- Review personas: {_comma_join(review.get('review_personas'))}",
        f"- Required gates: {_comma_join(review.get('required_gates'))}",
        f"- Escalate to: {review.get('escalate_to_persona') or 'none'}",
        f"- Operator summary: {review.get('operator_summary') or 'none'}",
        f"- Handoff template: `{review.get('handoff_template_ref') or 'none'}`",
        "",
    ]


def _render_evolution_issue(
    plan_payload: dict[str, Any],
    code_starter_payload: dict[str, Any],
    run_url: str,
    focus_area: str | None = None,
) -> str:
    plan = _coerce_plan_content(plan_payload)
    governed_review = build_evolution_governed_review(
        plan_payload,
        code_starter_payload=code_starter_payload,
        focus_area=focus_area,
    )
    planner_model = plan_payload.get("model") or "unknown-model"
    code_model = code_starter_payload.get("model") or "unknown-model"
    try:
        top_priority_index = int(plan.get("top_priority_index", 0))
    except (TypeError, ValueError):
        top_priority_index = 0
    items = plan.get("evolution_items") if isinstance(plan.get("evolution_items"), list) else []

    lines = []
    focus_tag = f" — Focus: {focus_area}" if focus_area else ""
    lines.append(f"## HLF Weekly Evolution Plan{focus_tag}")
    lines.append("")
    lines.append(f"Strategic planner: `{planner_model}`")
    lines.append(f"Code drafter: `{code_model}`")
    lines.append(f"Workflow: [{run_url}]({run_url})")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Strategic Summary")
    lines.append("")
    lines.append(plan.get("summary") or "No summary provided.")
    lines.append("")
    lines.extend(_render_persona_handoff(governed_review))
    lines.append("## Seven-Pillar Assessment")
    lines.append("")
    for assessment in plan.get("pillar_assessments") or []:
        if not isinstance(assessment, dict):
            continue
        lines.append(
            "- "
            + f"{assessment.get('pillar') or 'unknown'}: "
            + f"{assessment.get('status') or 'unknown'} — "
            + f"{assessment.get('rationale') or 'No rationale provided.'}"
        )
    lines.append("")
    lines.append("## Recommended Actions")
    lines.append("")
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        top = " (top priority)" if index - 1 == top_priority_index else ""
        lines.append(f"### {index}. {item.get('title') or 'Untitled item'}{top}")
        lines.append("")
        lines.append(f"- Why: {item.get('why') or 'No rationale provided.'}")
        lines.append(
            f"- Impact: {item.get('impact') or 'unknown'} ({item.get('impact_metric') or 'n/a'})"
        )
        lines.append(f"- Effort: {item.get('effort') or 'unknown'}")
        lines.append(f"- Priority: {item.get('priority') or 'unknown'}")
        lines.append(f"- Lane: {item.get('lane') or 'unknown'}")
        lines.append(f"- Phase: {item.get('phase') or 'unknown'}")
        lines.append(f"- Pillar: {item.get('pillar') or 'unknown'}")
        lines.append(
            "- First step: "
            + f"`{item.get('first_step_file') or 'unknown'}` :: "
            + f"`{item.get('first_step_function') or 'unknown'}`"
        )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Code Starter")
    lines.append("")
    lines.append(code_starter_payload.get("content") or "No code starter generated.")
    lines.append("")
    lines.append("---")
    lines.append("This issue is auto-generated weekly. Close when the top-priority item is merged.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build governed weekly review contracts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser("write-evolution-schema")
    schema_parser.add_argument("--output", type=Path, required=True)

    evolution_parser = subparsers.add_parser("build-evolution")
    evolution_parser.add_argument("--plan", type=Path, required=True)
    evolution_parser.add_argument("--code-starter", type=Path, default=None)
    evolution_parser.add_argument("--focus-area", default=None)
    evolution_parser.add_argument("--output", type=Path, required=True)

    drift_parser = subparsers.add_parser("build-drift")
    drift_parser.add_argument("--drift-report", type=Path, required=True)
    drift_parser.add_argument("--output", type=Path, required=True)

    spec_parser = subparsers.add_parser("build-spec-sentinel")
    spec_parser.add_argument("--drift-report", type=Path, required=True)
    spec_parser.add_argument("--ai-analysis", type=Path, default=None)
    spec_parser.add_argument("--output", type=Path, required=True)

    doc_parser = subparsers.add_parser("build-doc-accuracy")
    doc_parser.add_argument("--doc-drift", type=Path, required=True)
    doc_parser.add_argument("--output", type=Path, required=True)

    security_parser = subparsers.add_parser("build-security-patterns")
    security_parser.add_argument("--security-review", type=Path, required=True)
    security_parser.add_argument("--output", type=Path, required=True)

    test_health_parser = subparsers.add_parser("build-test-health")
    test_health_parser.add_argument("--coverage", type=Path, required=True)
    test_health_parser.add_argument("--test-suggestions", type=Path, default=None)
    test_health_parser.add_argument("--output", type=Path, required=True)

    ethics_parser = subparsers.add_parser("build-ethics-review")
    ethics_parser.add_argument("--ethics-report", type=Path, required=True)
    ethics_parser.add_argument("--ethics-review", type=Path, default=None)
    ethics_parser.add_argument("--output", type=Path, required=True)

    quality_parser = subparsers.add_parser("build-code-quality")
    quality_parser.add_argument("--code-quality", type=Path, required=True)
    quality_parser.add_argument("--security-findings", type=Path, default=None)
    quality_parser.add_argument("--output", type=Path, required=True)

    issue_parser = subparsers.add_parser("render-evolution-issue")
    issue_parser.add_argument("--plan", type=Path, required=True)
    issue_parser.add_argument("--code-starter", type=Path, required=True)
    issue_parser.add_argument("--run-url", required=True)
    issue_parser.add_argument("--focus-area", default=None)
    issue_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "write-evolution-schema":
        _write_json(args.output, evolution_plan_schema())
        return 0

    if args.command == "build-evolution":
        plan_payload = _load_json(args.plan)
        code_starter_payload = _load_json(args.code_starter) if args.code_starter else None
        payload = build_evolution_governed_review(
            plan_payload,
            code_starter_payload=code_starter_payload,
            focus_area=args.focus_area,
        )
        _write_json(args.output, payload)
        return 0

    if args.command == "build-drift":
        payload = build_model_drift_governed_review(_load_json(args.drift_report))
        _write_json(args.output, payload)
        return 0

    if args.command == "build-spec-sentinel":
        payload = build_spec_sentinel_governed_review(
            _load_json(args.drift_report),
            ai_analysis_payload=_load_json(args.ai_analysis) if args.ai_analysis else None,
        )
        _write_json(args.output, payload)
        return 0

    if args.command == "build-doc-accuracy":
        payload = build_doc_accuracy_governed_review(_load_json(args.doc_drift))
        _write_json(args.output, payload)
        return 0

    if args.command == "build-security-patterns":
        payload = build_security_patterns_governed_review(_load_json(args.security_review))
        _write_json(args.output, payload)
        return 0

    if args.command == "build-test-health":
        payload = build_test_health_governed_review(
            _load_json(args.coverage),
            test_suggestions_payload=_load_json(args.test_suggestions)
            if args.test_suggestions
            else None,
        )
        _write_json(args.output, payload)
        return 0

    if args.command == "build-ethics-review":
        payload = build_ethics_review_governed_review(
            _load_json(args.ethics_report),
            ethics_review_payload=_load_json(args.ethics_review) if args.ethics_review else None,
        )
        _write_json(args.output, payload)
        return 0

    if args.command == "build-code-quality":
        payload = build_code_quality_governed_review(
            _load_json(args.code_quality),
            security_findings_payload=_load_json(args.security_findings)
            if args.security_findings
            else None,
        )
        _write_json(args.output, payload)
        return 0

    if args.command == "render-evolution-issue":
        plan_payload = _load_json(args.plan)
        code_starter_payload = _load_json(args.code_starter)
        args.output.write_text(
            _render_evolution_issue(
                plan_payload,
                code_starter_payload,
                args.run_url,
                focus_area=args.focus_area,
            ),
            encoding="utf-8",
        )
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
