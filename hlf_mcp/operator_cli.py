from __future__ import annotations

import argparse
import json
from pathlib import Path

from hlf_mcp.evidence_query import print_payload
from hlf_mcp.server_context import build_server_context
from hlf_mcp.server_core import load_test_suite_summary
from hlf_mcp.server_memory import apply_memory_governance
from hlf_mcp.server_resources import render_resource_uri
from hlf_mcp.server_translation import run_hlf_do
from hlf_mcp.weekly_artifacts import summarize_weekly_artifacts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hlf-operator",
        description="Operator-facing packaged HLF actions for local shells and extension bridges.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    do_parser = subparsers.add_parser("do", help="Run the packaged natural-language front door")
    do_parser.add_argument("--intent", required=True)
    do_parser.add_argument("--tier", default="forge")
    do_parser.add_argument("--dry-run", action="store_true")
    do_parser.add_argument("--show-hlf", action="store_true")
    do_parser.add_argument("--language", default="auto")
    do_parser.add_argument("--json", action="store_true")

    summary_parser = subparsers.add_parser("test-summary", help="Show the latest pytest summary")
    summary_parser.add_argument("--metrics-dir", type=Path, default=None)
    summary_parser.add_argument("--include-output", action="store_true")
    summary_parser.add_argument("--json", action="store_true")

    evidence_parser = subparsers.add_parser(
        "weekly-evidence-summary",
        help="Summarize governed weekly evidence artifacts",
    )
    evidence_parser.add_argument("--metrics-dir", type=Path, default=None)
    evidence_parser.add_argument("--json", action="store_true")

    provenance_parser = subparsers.add_parser(
        "provenance-summary",
        help="Summarize packaged provenance across memory, governance, witness, and evidence",
    )
    provenance_parser.add_argument("--metrics-dir", type=Path, default=None)
    provenance_parser.add_argument("--json", action="store_true")

    agent_protocol_parser = subparsers.add_parser(
        "agent-protocol",
        help="Render the arriving-agent HLF protocol surface through a named command",
    )
    agent_protocol_parser.add_argument("--json", action="store_true")

    agent_quickstart_parser = subparsers.add_parser(
        "agent-quickstart",
        help="Render the arriving-agent quickstart loop through a named command",
    )
    agent_quickstart_parser.add_argument("--json", action="store_true")

    agent_handoff_parser = subparsers.add_parser(
        "agent-handoff-contract",
        help="Render the arriving-agent handoff contract through a named command",
    )
    agent_handoff_parser.add_argument("--json", action="store_true")

    agent_authority_parser = subparsers.add_parser(
        "agent-current-authority",
        help="Render the arriving-agent authority surface through a named command",
    )
    agent_authority_parser.add_argument("--json", action="store_true")

    witness_status_parser = subparsers.add_parser(
        "witness-status",
        help="Review packaged witness-governance status through a named operator command",
    )
    witness_status_parser.add_argument("--subject-agent-id", default=None)
    witness_status_parser.add_argument("--json", action="store_true")

    governed_route_parser = subparsers.add_parser(
        "governed-route",
        help="Review packaged governed-routing evidence through a named operator command",
    )
    governed_route_parser.add_argument("--agent-id", default=None)
    governed_route_parser.add_argument("--json", action="store_true")

    ingress_status_parser = subparsers.add_parser(
        "ingress-status",
        help="Inspect packaged ingress admission status through a named operator command",
    )
    ingress_status_parser.add_argument("--agent-id", default=None)
    ingress_status_parser.add_argument("--json", action="store_true")

    instinct_status_parser = subparsers.add_parser(
        "instinct-status",
        help="Inspect packaged Instinct lifecycle missions through a named operator command",
    )
    instinct_status_parser.add_argument("--mission-id", default=None)
    instinct_status_parser.add_argument("--json", action="store_true")

    formal_verifier_parser = subparsers.add_parser(
        "formal-verifier",
        help="Inspect packaged formal-verification status through a named operator command",
    )
    formal_verifier_parser.add_argument("--json", action="store_true")

    entropy_anchor_parser = subparsers.add_parser(
        "entropy-anchor",
        help="Inspect packaged entropy-anchor drift status through a named operator command",
    )
    entropy_anchor_parser.add_argument("--json", action="store_true")

    approval_review_parser = subparsers.add_parser(
        "approval-review",
        help="Review packaged approval queue state through a named operator command",
    )
    approval_review_parser.add_argument("--request-id", default=None)
    approval_review_parser.add_argument("--json", action="store_true")

    approval_bypass_parser = subparsers.add_parser(
        "approval-bypass-review",
        help="Review recent governed approval-bypass attempts through the packaged operator surface",
    )
    approval_bypass_parser.add_argument("--subject-agent-id", default=None)
    approval_bypass_parser.add_argument("--json", action="store_true")

    persona_review_parser = subparsers.add_parser(
        "persona-review",
        help="Review packaged persona ownership and gate state for weekly evidence artifacts",
    )
    persona_review_parser.add_argument("--artifact-id", default=None)
    persona_review_parser.add_argument("--json", action="store_true")

    daemon_transparency_parser = subparsers.add_parser(
        "daemon-transparency",
        help="Show the rolling packaged daemon transparency status surface",
    )
    daemon_transparency_parser.add_argument("--json", action="store_true")

    daemon_report_parser = subparsers.add_parser(
        "daemon-transparency-report",
        help="Render the packaged daemon transparency markdown report",
    )
    daemon_report_parser.add_argument("--json", action="store_true")

    governance_parser = subparsers.add_parser(
        "memory-govern",
        help="Apply a governed memory intervention through the packaged shell surface",
    )
    governance_parser.add_argument(
        "--action", required=True, choices=["revoke", "tombstone", "reinstate"]
    )
    governance_parser.add_argument("--fact-id", type=int, default=None)
    governance_parser.add_argument("--sha256", default=None)
    governance_parser.add_argument("--operator-summary", default="")
    governance_parser.add_argument("--reason", default="")
    governance_parser.add_argument("--operator-id", default="")
    governance_parser.add_argument("--operator-display-name", default="")
    governance_parser.add_argument("--operator-channel", default="")
    governance_parser.add_argument("--source", default="operator_cli.memory_govern")
    governance_parser.add_argument("--json", action="store_true")

    resource_parser = subparsers.add_parser(
        "resource",
        help="Render a packaged status resource without starting the MCP server",
    )
    resource_parser.add_argument("--uri", required=True)
    resource_parser.add_argument("--json", action="store_true")

    return parser


def _do_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    payload = run_hlf_do(
        ctx,
        intent=args.intent,
        tier=args.tier,
        dry_run=args.dry_run,
        show_hlf=args.show_hlf,
        language=args.language,
    )
    print_payload(payload, as_json=True if args.json else False)
    return 0 if payload.get("success") else 1


def _test_summary_command(args: argparse.Namespace) -> int:
    payload = load_test_suite_summary(args.metrics_dir, include_output=args.include_output)
    print_payload(payload, as_json=True if args.json else False)
    return 0 if payload.get("status") == "ok" else 1


def _weekly_evidence_summary_command(args: argparse.Namespace) -> int:
    payload = summarize_weekly_artifacts(args.metrics_dir)
    print_payload(payload, as_json=True if args.json else False)
    return 0


def _provenance_summary_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    payload = {
        "status": "ok",
        "provenance_contract": ctx.summarize_provenance_contract(metrics_dir=args.metrics_dir),
    }
    print_payload(payload, as_json=True if args.json else False)
    return 0


def _agent_protocol_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, "hlf://agent/protocol", as_json=bool(args.json))


def _agent_quickstart_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, "hlf://agent/quickstart", as_json=bool(args.json))


def _agent_handoff_contract_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, "hlf://agent/handoff_contract", as_json=bool(args.json))


def _agent_current_authority_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, "hlf://agent/current_authority", as_json=bool(args.json))


def _memory_govern_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    payload = apply_memory_governance(
        ctx,
        action=args.action,
        fact_id=args.fact_id,
        sha256=args.sha256,
        operator_summary=args.operator_summary,
        reason=args.reason,
        operator_id=args.operator_id,
        operator_display_name=args.operator_display_name,
        operator_channel=args.operator_channel,
        source=args.source,
    )
    print_payload(payload, as_json=True if args.json else False)
    return 0 if payload.get("status") == "ok" else 1


def _render_json_resource(ctx: object, uri: str, *, as_json: bool) -> int:
    payload_text = render_resource_uri(ctx, uri)
    if as_json:
        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError:
            parsed = {"status": "error", "error": "resource_output_not_json", "raw": payload_text}
        print_payload(parsed, as_json=True)
        return 0 if parsed.get("status") == "ok" else 1

    print_payload(payload_text, as_json=False)
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError:
        return 1
    return 0 if parsed.get("status") == "ok" else 1


def _approval_bypass_review_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    uri = (
        f"hlf://status/approval_bypass/{args.subject_agent_id}"
        if args.subject_agent_id
        else "hlf://status/approval_bypass"
    )
    return _render_json_resource(ctx, uri, as_json=bool(args.json))


def _persona_review_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    uri = (
        f"hlf://status/persona_review/{args.artifact_id}"
        if args.artifact_id
        else "hlf://status/persona_review"
    )
    return _render_json_resource(ctx, uri, as_json=bool(args.json))


def _daemon_transparency_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, "hlf://status/daemon_transparency", as_json=bool(args.json))


def _witness_status_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    uri = (
        f"hlf://status/witness_governance/{args.subject_agent_id}"
        if args.subject_agent_id
        else "hlf://status/witness_governance"
    )
    return _render_json_resource(ctx, uri, as_json=bool(args.json))


def _governed_route_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    uri = (
        f"hlf://status/governed_route/{args.agent_id}"
        if args.agent_id
        else "hlf://status/governed_route"
    )
    return _render_json_resource(ctx, uri, as_json=bool(args.json))


def _ingress_status_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    uri = f"hlf://status/ingress/{args.agent_id}" if args.agent_id else "hlf://status/ingress"
    return _render_json_resource(ctx, uri, as_json=bool(args.json))


def _instinct_status_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    uri = (
        f"hlf://status/instinct/{args.mission_id}"
        if args.mission_id
        else "hlf://status/instinct"
    )
    return _render_json_resource(ctx, uri, as_json=bool(args.json))


def _formal_verifier_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, "hlf://status/formal_verifier", as_json=bool(args.json))


def _entropy_anchor_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, "hlf://status/entropy_anchor", as_json=bool(args.json))


def _approval_review_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    uri = (
        f"hlf://status/approval_queue/{args.request_id}"
        if args.request_id
        else "hlf://status/approval_queue"
    )
    return _render_json_resource(ctx, uri, as_json=bool(args.json))


def _daemon_transparency_report_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    report_text = render_resource_uri(ctx, "hlf://reports/daemon_transparency")
    if args.json:
        print_payload(
            {
                "status": "ok",
                "resource_uri": "hlf://reports/daemon_transparency",
                "report": report_text,
            },
            as_json=True,
        )
        return 0
    print_payload(report_text, as_json=False)
    return 0 if bool(str(report_text).strip()) else 1


def _resource_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    return _render_json_resource(ctx, args.uri, as_json=bool(args.json))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "memory-govern" and args.fact_id is None and not args.sha256:
        parser.error("memory-govern requires --fact-id or --sha256")

    if args.command == "do":
        return _do_command(args)
    if args.command == "test-summary":
        return _test_summary_command(args)
    if args.command == "weekly-evidence-summary":
        return _weekly_evidence_summary_command(args)
    if args.command == "provenance-summary":
        return _provenance_summary_command(args)
    if args.command == "agent-protocol":
        return _agent_protocol_command(args)
    if args.command == "agent-quickstart":
        return _agent_quickstart_command(args)
    if args.command == "agent-handoff-contract":
        return _agent_handoff_contract_command(args)
    if args.command == "agent-current-authority":
        return _agent_current_authority_command(args)
    if args.command == "witness-status":
        return _witness_status_command(args)
    if args.command == "governed-route":
        return _governed_route_command(args)
    if args.command == "ingress-status":
        return _ingress_status_command(args)
    if args.command == "instinct-status":
        return _instinct_status_command(args)
    if args.command == "formal-verifier":
        return _formal_verifier_command(args)
    if args.command == "entropy-anchor":
        return _entropy_anchor_command(args)
    if args.command == "approval-review":
        return _approval_review_command(args)
    if args.command == "approval-bypass-review":
        return _approval_bypass_review_command(args)
    if args.command == "persona-review":
        return _persona_review_command(args)
    if args.command == "daemon-transparency":
        return _daemon_transparency_command(args)
    if args.command == "daemon-transparency-report":
        return _daemon_transparency_report_command(args)
    if args.command == "memory-govern":
        return _memory_govern_command(args)
    if args.command == "resource":
        return _resource_command(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
