"""
ethics_compliance_check.py — Verify ethics module implementation status.

Checks:
  1. Whether ethics stub modules still contain placeholder logic (not yet implemented)
  2. Whether the compiler ethics hook comment remains a comment (not wired up)
  3. Whether MEMORY_STORE operations have any runtime PII check
  4. Whether ALIGN rules cover the full threat surface (>= 5 rules)

Outputs a JSON status report and summary text for LLM analysis.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
ETHICS_DIR  = ROOT / "hlf_mcp" / "hlf" / "ethics"
COMPILER_PY = ROOT / "hlf_mcp" / "hlf" / "compiler.py"
RUNTIME_PY  = ROOT / "hlf_mcp" / "hlf" / "runtime.py"
ALIGN_JSON  = ROOT / "governance" / "align_rules.json"


def _check_ethics_stubs() -> dict:
    """Check if ethics modules are still stubs vs implemented."""
    results: dict[str, dict] = {}
    stub_indicators = [
        "pass",
        "NotImplementedError",
        "TODO",
        "placeholder",
        "raise NotImplementedError",
    ]
    for module in ["constitution.py", "termination.py", "red_hat.py", "rogue_detection.py"]:
        path = ETHICS_DIR / module
        if not path.exists():
            results[module] = {"status": "MISSING", "is_stub": True}
            continue
        text = path.read_text(encoding="utf-8")
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        # Count meaningful non-stub lines
        stub_lines = sum(1 for l in lines if any(ind in l for ind in stub_indicators))
        real_lines = len(lines) - stub_lines
        is_stub = real_lines < 5 or stub_lines > real_lines
        results[module] = {
            "status": "STUB" if is_stub else "IMPLEMENTED",
            "is_stub": is_stub,
            "real_lines": real_lines,
            "stub_lines": stub_lines,
            "total_non_comment_lines": len(lines),
        }
    return results


def _check_compiler_ethics_hook() -> dict:
    """Check if compiler Pass 2 ethics hook is wired or still a comment."""
    if not COMPILER_PY.exists():
        return {"status": "MISSING_COMPILER", "wired": False}
    text = COMPILER_PY.read_text(encoding="utf-8")
    # Look for actual import or call of ethics module
    has_import = bool(re.search(r"from\s+.*ethics\s+import|import\s+.*ethics", text))
    has_call   = bool(re.search(r"ethics\.|constitution\.|check_ethics|ethics_check", text))
    # Check if it's just a comment
    comment_only = bool(re.search(r"#.*ethics|#.*constitutional|#.*governor", text, re.IGNORECASE))
    return {
        "wired": has_import or has_call,
        "has_import": has_import,
        "has_call": has_call,
        "comment_placeholder_present": comment_only,
        "status": "WIRED" if (has_import or has_call) else "COMMENT_ONLY",
    }


def _check_runtime_pii_guard() -> dict:
    """Check if MEMORY_STORE dispatch has any PII scanning."""
    if not RUNTIME_PY.exists():
        return {"status": "MISSING_RUNTIME", "has_pii_guard": False}
    text = RUNTIME_PY.read_text(encoding="utf-8")
    has_pii = bool(re.search(r"pii|personal.*data|privacy|redact|scrub", text, re.IGNORECASE))
    has_align_check_at_memory = bool(re.search(
        r"memory_store.*align|align.*memory_store|ALIGN.*MEMORY|memory.*pattern", text, re.IGNORECASE
    ))
    return {
        "has_pii_guard": has_pii or has_align_check_at_memory,
        "has_pii_keyword": has_pii,
        "has_align_at_memory": has_align_check_at_memory,
        "status": "GUARDED" if (has_pii or has_align_check_at_memory) else "UNGUARDED",
    }


def _check_align_rules() -> dict:
    """Check ALIGN rules count and coverage."""
    if not ALIGN_JSON.exists():
        return {"status": "MISSING", "rule_count": 0}
    data = json.loads(ALIGN_JSON.read_text(encoding="utf-8"))
    rules = data if isinstance(data, list) else data.get("rules", [])
    rule_names = [r.get("id", r.get("name", "?")) for r in rules]
    return {
        "rule_count": len(rules),
        "rules": rule_names,
        "adequate": len(rules) >= 5,
        "status": "ADEQUATE" if len(rules) >= 5 else "NEEDS_MORE_RULES",
    }


def build_summary(report: dict) -> str:
    """Build a human-readable summary string for LLM analysis."""
    lines = ["=== HLF Ethics Compliance Report ===\n"]
    stubs = report["ethics_stubs"]
    all_stubbed = all(v["is_stub"] for v in stubs.values())
    lines.append(f"Ethics Modules: {'ALL STUBS - not yet implemented' if all_stubbed else 'PARTIALLY IMPLEMENTED'}")
    for mod, info in stubs.items():
        lines.append(f"  {mod}: {info['status']}")

    hook = report["compiler_ethics_hook"]
    lines.append(f"\nCompiler Ethics Hook: {hook['status']}")
    if not hook["wired"]:
        lines.append("  ⚠ Constitutional check NOT wired into compiler pipeline")

    pii = report["runtime_pii_guard"]
    lines.append(f"\nRuntime PII Guard (MEMORY_STORE): {pii['status']}")
    if not pii["has_pii_guard"]:
        lines.append("  ⚠ No PII scanning before MEMORY_STORE execution")

    align = report["align_rules"]
    lines.append(f"\nALIGN Rules: {align['rule_count']} rules — {align['status']}")
    for r in align.get("rules", []):
        lines.append(f"  • {r}")

    lines.append(f"\nOverall Ethics Compliance: {'PARTIAL/SCAFFOLDED' if all_stubbed else 'IN PROGRESS'}")
    return "\n".join(lines)


def main() -> None:
    report = {
        "ethics_stubs": _check_ethics_stubs(),
        "compiler_ethics_hook": _check_compiler_ethics_hook(),
        "runtime_pii_guard": _check_runtime_pii_guard(),
        "align_rules": _check_align_rules(),
    }
    summary = build_summary(report)
    report["summary_text"] = summary
    print(json.dumps(report, indent=2))
    # Always exit 0 — this is a reporting tool, not a gate (ethics module is known-incomplete)


if __name__ == "__main__":
    main()
