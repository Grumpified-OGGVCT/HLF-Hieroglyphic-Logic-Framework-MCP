#!/usr/bin/env python3
"""
HLF Fork Compliance Checker — warn-first, transparent, human-readable.

Validates that a fork of the HLF repository maintains upstream ethical
governance alignment.  Every check is documented here in plain code that any
fork maintainer can read.

This is NOT a kill-switch or an auto-ban.
  • Violations produce clear, actionable warnings with remediation steps.
  • Nothing is silently blocked.
  • The script exits 0 on warnings; exits 1 only on hard structural breaks
    (missing files that are required for the project to run at all).
  • Fork maintainers are free to extend — they just can't remove the core
    governance files that protect users.

Usage::

    python scripts/fork_compliance_check.py [--path /path/to/fork] [--strict]

Flags:
    --path    Path to the fork root (default: current directory).
    --strict  Exit 1 on any violation, not just hard breaks (for CI gates).
    --json    Output results as JSON instead of human-readable text.
    --quiet   Suppress informational output; print only violations.

People are the priority.  AI is the tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Required ethics files ─────────────────────────────────────────────────────
# These files form the governance backbone.  Their absence means the fork
# has lost the audit trail / constitutional layer that protects users.

REQUIRED_ETHICS_FILES: list[tuple[str, str]] = [
    (
        "HLF_ETHICAL_GOVERNOR.md",
        "Core ethics governance document — describes the 5-module system.",
    ),
    (
        "governance/align_rules.json",
        "ALIGN Ledger rules — security pattern checks (must have >= 5 rules).",
    ),
    (
        "hlf_mcp/hlf/ethics/constitution.py",
        "Constitutional constraint layer (C-1 through C-5).",
    ),
    (
        "hlf_mcp/hlf/ethics/governor.py",
        "Ethical Governor orchestrator — the main pipeline gate.",
    ),
    (
        "hlf_mcp/hlf/capsules.py",
        "Intent Capsule tier system (hearth / forge / sovereign).",
    ),
]

# These files are strongly recommended but their absence is a warning, not hard fail.
RECOMMENDED_FILES: list[tuple[str, str]] = [
    (
        "HLF_ETHICAL_GOVERNOR_ARCHITECTURE.md",
        "Detailed architecture doc — helps fork maintainers understand the system.",
    ),
    (
        "governance/update_governor.py",
        "HIL-gated update management.",
    ),
    (
        "governance/license_revocation.py",
        "Warn-first license revocation ledger.",
    ),
    (
        "hlf_mcp/hlf/ethics/termination.py",
        "Self-termination protocol — transparent halt with audit trail.",
    ),
    (
        "hlf_mcp/hlf/ethics/rogue_detection.py",
        "Rogue agent / injection detection.",
    ),
]

# Minimum number of ALIGN rules that must exist
MIN_ALIGN_RULES = 5

# Capsule tier identifiers — all three must be present
REQUIRED_CAPSULE_TIERS = ["hearth", "forge", "sovereign"]

# HIL gate pattern — tool_dispatch must still require approval before activation
HIL_PATTERN = "pending_hitl"

# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    level: str   # "hard" | "warn" | "info"
    message: str
    remediation: str = ""


@dataclass
class ComplianceReport:
    fork_path: str
    passed: bool
    hard_failures: list[CheckResult] = field(default_factory=list)
    warnings: list[CheckResult] = field(default_factory=list)
    passed_checks: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fork_path":    self.fork_path,
            "passed":       self.passed,
            "hard_failures": [_cr_dict(r) for r in self.hard_failures],
            "warnings":     [_cr_dict(r) for r in self.warnings],
            "passed_checks": [_cr_dict(r) for r in self.passed_checks],
            "summary": {
                "hard_failures": len(self.hard_failures),
                "warnings":      len(self.warnings),
                "passed":        len(self.passed_checks),
            },
        }


def _cr_dict(r: CheckResult) -> dict:
    return {
        "name":        r.name,
        "passed":      r.passed,
        "level":       r.level,
        "message":     r.message,
        "remediation": r.remediation,
    }


# ── Individual checks ─────────────────────────────────────────────────────────

def check_required_files(root: Path) -> list[CheckResult]:
    results = []
    for rel_path, description in REQUIRED_ETHICS_FILES:
        path = root / rel_path
        if path.exists():
            results.append(CheckResult(
                name    = f"required_file:{rel_path}",
                passed  = True,
                level   = "hard",
                message = f"✓ {rel_path} — present",
            ))
        else:
            results.append(CheckResult(
                name    = f"required_file:{rel_path}",
                passed  = False,
                level   = "hard",
                message = f"✗ Missing required file: {rel_path}",
                remediation = (
                    f"Restore '{rel_path}' from upstream HLF.\n"
                    f"  This file is required because: {description}\n"
                    "  Run: git checkout upstream/main -- "
                    + rel_path
                ),
            ))
    return results


def check_recommended_files(root: Path) -> list[CheckResult]:
    results = []
    for rel_path, description in RECOMMENDED_FILES:
        path = root / rel_path
        if path.exists():
            results.append(CheckResult(
                name    = f"recommended_file:{rel_path}",
                passed  = True,
                level   = "warn",
                message = f"✓ {rel_path} — present",
            ))
        else:
            results.append(CheckResult(
                name    = f"recommended_file:{rel_path}",
                passed  = False,
                level   = "warn",
                message = f"⚠ Recommended file missing: {rel_path}",
                remediation = (
                    f"Consider restoring '{rel_path}' from upstream.\n"
                    f"  Reason: {description}"
                ),
            ))
    return results


def check_align_rules(root: Path) -> CheckResult:
    align_path = root / "governance" / "align_rules.json"
    if not align_path.exists():
        return CheckResult(
            name    = "align_rule_count",
            passed  = False,
            level   = "hard",
            message = "✗ governance/align_rules.json not found — cannot count rules",
            remediation = "Restore governance/align_rules.json from upstream.",
        )
    try:
        data  = json.loads(align_path.read_text(encoding="utf-8"))
        rules = data if isinstance(data, list) else data.get("rules", [])
        count = len(rules)
        if count >= MIN_ALIGN_RULES:
            return CheckResult(
                name    = "align_rule_count",
                passed  = True,
                level   = "hard",
                message = f"✓ ALIGN rules: {count} (minimum {MIN_ALIGN_RULES})",
            )
        return CheckResult(
            name    = "align_rule_count",
            passed  = False,
            level   = "hard",
            message = (
                f"✗ ALIGN rules: {count} — below required minimum of {MIN_ALIGN_RULES}"
            ),
            remediation = (
                "Restore missing ALIGN rules from upstream governance/align_rules.json.\n"
                "  ALIGN rules protect users from credential leaks, SSRF, path traversal, etc."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name    = "align_rule_count",
            passed  = False,
            level   = "hard",
            message = f"✗ Could not parse governance/align_rules.json: {exc}",
            remediation = "Fix JSON syntax in governance/align_rules.json.",
        )


def check_capsule_tiers(root: Path) -> CheckResult:
    capsules_path = root / "hlf_mcp" / "hlf" / "capsules.py"
    if not capsules_path.exists():
        return CheckResult(
            name    = "capsule_tiers",
            passed  = False,
            level   = "hard",
            message = "✗ hlf_mcp/hlf/capsules.py not found",
            remediation = "Restore capsules.py from upstream.",
        )
    text = capsules_path.read_text(encoding="utf-8")
    missing = [tier for tier in REQUIRED_CAPSULE_TIERS if tier not in text]
    if not missing:
        return CheckResult(
            name    = "capsule_tiers",
            passed  = True,
            level   = "hard",
            message = "✓ Intent Capsule tiers: hearth / forge / sovereign — all present",
        )
    return CheckResult(
        name    = "capsule_tiers",
        passed  = False,
        level   = "hard",
        message = f"✗ Missing capsule tier(s): {missing}",
        remediation = (
            "Restore the missing tier definitions in hlf_mcp/hlf/capsules.py.\n"
            "  The tier system is what enforces per-context permission boundaries."
        ),
    )


def check_hil_gate(root: Path) -> CheckResult:
    dispatch_path = root / "hlf_mcp" / "hlf" / "tool_dispatch.py"
    if not dispatch_path.exists():
        return CheckResult(
            name    = "hil_gate",
            passed  = False,
            level   = "warn",
            message = "⚠ hlf_mcp/hlf/tool_dispatch.py not found — cannot verify HIL gate",
            remediation = "Restore tool_dispatch.py from upstream if you use tool dispatch.",
        )
    text = dispatch_path.read_text(encoding="utf-8")
    if HIL_PATTERN in text:
        return CheckResult(
            name    = "hil_gate",
            passed  = True,
            level   = "warn",
            message = "✓ HIL gate (pending_hitl) present in tool_dispatch.py",
        )
    return CheckResult(
        name    = "hil_gate",
        passed  = False,
        level   = "warn",
        message = "⚠ HIL gate pattern 'pending_hitl' not found in tool_dispatch.py",
        remediation = (
            "Ensure tool_dispatch.py still requires human approval before activating tools.\n"
            "  See: hlf_mcp/hlf/tool_dispatch.py in upstream."
        ),
    )


def check_governor_transparency(root: Path) -> CheckResult:
    gov_path = root / "hlf_mcp" / "hlf" / "ethics" / "governor.py"
    if not gov_path.exists():
        return CheckResult(
            name    = "governor_transparency",
            passed  = False,
            level   = "hard",
            message = "✗ ethics/governor.py not found",
            remediation = "Restore ethics/governor.py from upstream.",
        )
    text = gov_path.read_text(encoding="utf-8")
    # The design guarantees must remain in the governor
    markers = ["TRANSPARENT", "HUMAN-FIRST", "NON-REDUCTIVE"]
    missing = [m for m in markers if m not in text]
    if not missing:
        return CheckResult(
            name    = "governor_transparency",
            passed  = True,
            level   = "warn",
            message = "✓ Governor design guarantees (TRANSPARENT/HUMAN-FIRST/NON-REDUCTIVE) intact",
        )
    return CheckResult(
        name    = "governor_transparency",
        passed  = False,
        level   = "warn",
        message = f"⚠ Governor design guarantee markers missing: {missing}",
        remediation = (
            "Do not remove the design guarantee documentation from ethics/governor.py.\n"
            "  These comments are part of the governance contract with users."
        ),
    )


# ── Report builder ────────────────────────────────────────────────────────────

def run_compliance_check(fork_path: Path) -> ComplianceReport:
    """Run all checks and return a ComplianceReport."""
    all_results: list[CheckResult] = []

    all_results.extend(check_required_files(fork_path))
    all_results.extend(check_recommended_files(fork_path))
    all_results.append(check_align_rules(fork_path))
    all_results.append(check_capsule_tiers(fork_path))
    all_results.append(check_hil_gate(fork_path))
    all_results.append(check_governor_transparency(fork_path))

    hard_failures = [r for r in all_results if not r.passed and r.level == "hard"]
    warnings      = [r for r in all_results if not r.passed and r.level == "warn"]
    passed        = [r for r in all_results if r.passed]

    return ComplianceReport(
        fork_path     = str(fork_path),
        passed        = len(hard_failures) == 0,
        hard_failures = hard_failures,
        warnings      = warnings,
        passed_checks = passed,
    )


# ── CLI output ────────────────────────────────────────────────────────────────

def print_report(report: ComplianceReport, quiet: bool = False) -> None:
    """Print a human-readable compliance report."""
    width = 70
    print("=" * width)
    print("  HLF Fork Compliance Check")
    print(f"  Path: {report.fork_path}")
    print("=" * width)

    if report.hard_failures:
        print(f"\n❌  HARD FAILURES ({len(report.hard_failures)})")
        print("  These must be fixed — they break core governance for users.\n")
        for r in report.hard_failures:
            print(f"  {r.message}")
            if r.remediation:
                for line in r.remediation.strip().splitlines():
                    print(f"      {line}")
            print()

    if report.warnings:
        print(f"\n⚠   WARNINGS ({len(report.warnings)})")
        print("  These are strongly recommended but not blocking.\n")
        for r in report.warnings:
            print(f"  {r.message}")
            if r.remediation:
                for line in r.remediation.strip().splitlines():
                    print(f"      {line}")
            print()

    if not quiet and report.passed_checks:
        print(f"\n✓   PASSING CHECKS ({len(report.passed_checks)})")
        for r in report.passed_checks:
            print(f"  {r.message}")

    print()
    print("-" * width)
    summary_icon = "✅" if report.passed else "❌"
    print(
        f"  {summary_icon}  Result: {'COMPLIANT' if report.passed else 'NON-COMPLIANT'}  "
        f"| hard={len(report.hard_failures)}  warn={len(report.warnings)}  "
        f"ok={len(report.passed_checks)}"
    )
    if not report.passed:
        print()
        print("  This fork has removed governance that protects its users.")
        print("  Please restore the listed files from upstream HLF.")
        print("  Questions? Open an issue on the upstream repository.")
    print("=" * width)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="HLF Fork Compliance Checker — warn-first, transparent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Path to the fork root (default: current directory).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on any warning as well as hard failures (for strict CI gates).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output results as JSON.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress passing-check output; show only violations and warnings.",
    )
    args = parser.parse_args()

    fork_path = Path(args.path).resolve()
    if not fork_path.is_dir():
        print(f"ERROR: '{fork_path}' is not a directory.", file=sys.stderr)
        sys.exit(2)

    report = run_compliance_check(fork_path)

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report, quiet=args.quiet)

    if not report.passed:
        sys.exit(1)
    if args.strict and report.warnings:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
