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

    governance_parser = subparsers.add_parser(
        "memory-govern",
        help="Apply a governed memory intervention through the packaged shell surface",
    )
    governance_parser.add_argument("--action", required=True, choices=["revoke", "tombstone", "reinstate"])
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


def _resource_command(args: argparse.Namespace) -> int:
    ctx = build_server_context()
    payload_text = render_resource_uri(ctx, args.uri)
    if args.json:
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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "do":
        return _do_command(args)
    if args.command == "test-summary":
        return _test_summary_command(args)
    if args.command == "weekly-evidence-summary":
        return _weekly_evidence_summary_command(args)
    if args.command == "provenance-summary":
        return _provenance_summary_command(args)
    if args.command == "memory-govern":
        return _memory_govern_command(args)
    if args.command == "resource":
        return _resource_command(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
