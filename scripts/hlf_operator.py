#!/usr/bin/env python3
"""hlf-operator — Human-in-the-Loop gate CLI for HLF capsule approval.

Usage:
    hlf-operator approve --capsule-id <id> [--operator-id <name>]
    hlf-operator reject  --capsule-id <id> --reason <text> [--operator-id <name>]
    hlf-operator status   --capsule-id <id>
    hlf-operator list     [--pending]
    hlf-operator check-timeouts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from hlf_mcp.hlf.hitl_gate import HITLGate, ApprovalRequest


def cmd_approve(args: argparse.Namespace) -> None:
    gate = HITLGate.get_instance()
    try:
        req = gate.approve(args.capsule_id, args.operator_id or "operator")
        print(f"[OK] Capsule {args.capsule_id} APPROVED")
        print(f"   Status: {req.status}")
        print(f"   Approved by: {req.approved_by}")
        if req.approved_at:
            print(f"   Approved at: {req.approved_at}")
        print(f"   Output hash: {req.output_hash[:16]}...")
    except FileNotFoundError:
        print(f"[NOT_FOUND] No pending approval for capsule {args.capsule_id}")
        sys.exit(1)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)


def cmd_reject(args: argparse.Namespace) -> None:
    if not args.reason:
        print("[ERROR] --reason is required for reject")
        sys.exit(1)
    gate = HITLGate.get_instance()
    try:
        req = gate.reject(args.capsule_id, args.reason, args.operator_id or "operator")
        print(f"[REJECTED] Capsule {args.capsule_id} REJECTED")
        print(f"   Reason: {req.rejection_reason}")
        print(f"   Rejected by: {req.approved_by}")
        if req.approved_at:
            print(f"   Rejected at: {req.approved_at}")
    except FileNotFoundError:
        print(f"[NOT_FOUND] No pending approval for capsule {args.capsule_id}")
        sys.exit(1)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:
    gate = HITLGate.get_instance()
    status = gate.get_status(args.capsule_id)
    if status is None:
        print(f"[NOT_FOUND] No approval record for capsule {args.capsule_id}")
        sys.exit(1)

    print(f"Capsule: {status['capsule_id']}")
    print(f"Status:  {status['status']}")
    print(f"Agent:   {status['agent_id']} ({status['tier']})")
    print(f"Intent:  {status['intent_summary'][:100]}")
    print(f"Gas:     {status['gas_consumed']}/{status['gas_limit']}")
    print(f"Output:  {status['output_preview'][:80]}...")
    print(f"Created: {status['created_at']}")
    if status.get("approved_by"):
        print(f"Approved by: {status['approved_by']} at {status.get('approved_at', 'N/A')}")
    if status.get("rejection_reason"):
        print(f"Rejection: {status['rejection_reason']}")
    if status.get("provenance_hashes"):
        print(f"Provenance hashes: {len(status['provenance_hashes'])}")
    if status.get("timeout_seconds"):
        print(f"Timeout: {status['timeout_seconds']}s")


def cmd_list(args: argparse.Namespace) -> None:
    gate = HITLGate.get_instance()
    pending = gate.list_pending()
    if not pending:
        print("No pending approvals.")
        return

    print(f"{'CAPSULE ID':<40} {'STATUS':<25} {'AGENT':<20} {'CREATED':<20}")
    print("-" * 105)
    for p in pending:
        cid = p.get("capsule_id", "N/A")[:38]
        status = p.get("status", "N/A")
        agent = p.get("agent_id", "N/A")[:18]
        created = p.get("created_at", "N/A")[:19]
        print(f"{cid:<40} {status:<25} {agent:<20} {created:<20}")


def cmd_check_timeouts(args: argparse.Namespace) -> None:
    gate = HITLGate.get_instance()
    expired = gate.check_timeouts()
    if not expired:
        print("[OK] No expired approvals.")
        return
    print(f"[TIMEOUT] {len(expired)} approval(s) timed out:")
    for req in expired:
        print(f"   {req.capsule_id} -- {req.rejection_reason}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HLF Operator — Human-in-the-Loop approval gate CLI",
        prog="hlf-operator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # approve
    p_approve = sub.add_parser("approve", help="Approve a pending capsule")
    p_approve.add_argument("--capsule-id", required=True, help="Capsule ID to approve")
    p_approve.add_argument("--operator-id", help="Operator identifier (default: operator)")

    # reject
    p_reject = sub.add_parser("reject", help="Reject a pending capsule")
    p_reject.add_argument("--capsule-id", required=True, help="Capsule ID to reject")
    p_reject.add_argument("--reason", required=True, help="Reason for rejection")
    p_reject.add_argument("--operator-id", help="Operator identifier")

    # status
    p_status = sub.add_parser("status", help="Check approval status of a capsule")
    p_status.add_argument("--capsule-id", required=True, help="Capsule ID to check")

    # list
    p_list = sub.add_parser("list", help="List all pending approvals")
    p_list.add_argument("--pending", action="store_true", default=True, help="Show pending only")

    # check-timeouts
    p_timeout = sub.add_parser("check-timeouts", help="Check and reject timed-out approvals")

    args = parser.parse_args()

    handlers = {
        "approve": cmd_approve,
        "reject": cmd_reject,
        "status": cmd_status,
        "list": cmd_list,
        "check-timeouts": cmd_check_timeouts,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)


if __name__ == "__main__":
    main()
