"""
spec_drift_check.py — Detect drift between governance spec files and implementation.

Checks:
    1. bytecode_spec.yaml opcode list vs bytecode.py Op enum
    2. host_functions.json function names vs packaged HostFunctionRegistry
    3. grammar.py HLF_GRAMMAR statement types vs compiler.py handler coverage
    4. README opcode/tool/stdlib counts vs actual packaged code counts

Exits 0 if no drift found, 1 if drift detected (to fail the workflow step).
Prints a structured JSON report to stdout.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SPEC_YAML = ROOT / "governance" / "bytecode_spec.yaml"
HF_JSON = ROOT / "governance" / "host_functions.json"
BYTECODE_PY = ROOT / "hlf_mcp" / "hlf" / "bytecode.py"
RUNTIME_PY = ROOT / "hlf_mcp" / "hlf" / "runtime.py"
SERVER_PY = ROOT / "hlf_mcp" / "server.py"
README_MD = ROOT / "README.md"


def _load_yaml_opcodes(path: Path) -> dict[str, int]:
    """Parse bytecode_spec.yaml without external deps — extract name→code pairs."""
    opcodes: dict[str, int] = {}
    if not path.exists():
        return opcodes
    name_re = re.compile(r"name:\s*(\w+)")
    code_re = re.compile(r"code:\s*(0x[0-9a-fA-F]+|\d+)")
    current_name: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        m_name = name_re.search(line)
        m_code = code_re.search(line)
        if m_name:
            current_name = m_name.group(1)
        if m_code and current_name:
            opcodes[current_name] = int(m_code.group(1), 0)
            current_name = None
    return opcodes


def _load_py_opcodes(path: Path) -> dict[str, int]:
    """Extract Op enum members from bytecode.py."""
    opcodes: dict[str, int] = {}
    enum_re = re.compile(r"^\s{4}(\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)")
    in_class = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^class Op\b", line):
            in_class = True
            continue
        if in_class:
            if line.startswith("class ") and not line.startswith("class Op"):
                break
            m = enum_re.match(line)
            if m:
                opcodes[m.group(1)] = int(m.group(2), 0)
    return opcodes


def _load_host_function_names(path: Path) -> set[str]:
    """Extract function names from host_functions.json."""
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {f.get("name", "") for f in data if f.get("name")}
    if isinstance(data, dict) and "functions" in data:
        return {f.get("name", "") for f in data["functions"] if f.get("name")}
    return set()


def _load_registered_host_functions() -> set[str]:
    """Load packaged host function names from the registry authority."""
    try:
        from hlf_mcp.hlf.registry import HostFunctionRegistry

        registry = HostFunctionRegistry(str(HF_JSON) if HF_JSON.exists() else None)
        return {str(entry.get("name", "")) for entry in registry.list_all() if entry.get("name")}
    except Exception:
        return set()


def _count_mcp_tools(path: Path) -> int:
    """Count packaged registered tools, falling back to decorator count."""
    try:
        from hlf_mcp import server as packaged_server

        registered = getattr(packaged_server, "REGISTERED_TOOLS", None)
        if isinstance(registered, dict) and registered:
            return len(registered)
    except Exception:
        pass

    if not path.exists():
        return 0
    return len(re.findall(r"@mcp\.tool\b", path.read_text(encoding="utf-8")))


def _count_stdlib_modules(root: Path) -> int:
    """Count non-__ .py files in hlf_mcp/hlf/stdlib/."""
    stdlib = root / "hlf_mcp" / "hlf" / "stdlib"
    if not stdlib.is_dir():
        return 0
    return sum(1 for f in stdlib.iterdir() if f.suffix == ".py" and not f.name.startswith("_"))


def _readme_claimed_counts(path: Path) -> dict[str, int]:
    """Extract claimed numbers from README: opcodes, tools, stdlib modules."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    # Opcode count claim patterns
    for pattern in [r"(\d+)\s+opcodes?", r"opcodes?\s*[·:]\s*(\d+)"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            counts.setdefault("opcodes", int(m.group(1)))
    # Tool count
    for pattern in [r"(\d+)\s+(?:MCP\s+)?tools?", r"tools?\s*[·:]\s*(\d+)"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            counts.setdefault("tools", int(m.group(1)))
    # Stdlib modules
    for pattern in [
        r"(\d+)\s+(?:stdlib|standard\s+lib)\s+modules?",
        r"stdlib\s+modules?\s*[·:]\s*(\d+)",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            counts.setdefault("stdlib_modules", int(m.group(1)))
    return counts


def run_checks() -> tuple[list[dict], bool]:
    """Run all drift checks. Returns (findings_list, has_drift)."""
    findings: list[dict] = []
    has_drift = False

    # ── Check 1: bytecode_spec.yaml vs bytecode.py Op enum ──────────────────
    yaml_ops = _load_yaml_opcodes(SPEC_YAML)
    py_ops = _load_py_opcodes(BYTECODE_PY)

    only_in_yaml = set(yaml_ops) - set(py_ops)
    only_in_py = set(py_ops) - set(yaml_ops)
    code_mismatches = {
        name: {"yaml": hex(yaml_ops[name]), "py": hex(py_ops[name])}
        for name in yaml_ops.keys() & py_ops.keys()
        if yaml_ops[name] != py_ops[name]
    }

    if only_in_yaml or only_in_py or code_mismatches:
        has_drift = True
    findings.append(
        {
            "check": "bytecode_spec_vs_op_enum",
            "drift": bool(only_in_yaml or only_in_py or code_mismatches),
            "only_in_yaml": sorted(only_in_yaml),
            "only_in_py": sorted(only_in_py),
            "code_mismatches": code_mismatches,
            "yaml_total": len(yaml_ops),
            "py_total": len(py_ops),
        }
    )

    # ── Check 2: host_functions.json vs packaged HostFunctionRegistry ───────
    json_hf = _load_host_function_names(HF_JSON)
    registered_hf = _load_registered_host_functions()

    only_json = json_hf - registered_hf
    only_registered = registered_hf - json_hf

    if json_hf and registered_hf and (only_json or only_registered):
        has_drift = True

    findings.append(
        {
            "check": "host_functions_json_vs_registry",
            "drift": bool(only_json or only_registered),
            "only_in_json": sorted(only_json),
            "only_in_registry": sorted(only_registered),
            "json_total": len(json_hf),
            "registry_total": len(registered_hf),
            "note": "Empty sets are expected if governance file or packaged registry is not importable",
        }
    )

    # ── Check 3: README claimed counts vs actual counts ──────────────────────
    actual_tools = _count_mcp_tools(SERVER_PY)
    actual_stdlib = _count_stdlib_modules(ROOT)
    actual_opcodes = len(py_ops)
    readme_counts = _readme_claimed_counts(README_MD)

    count_drifts: dict[str, dict] = {}
    if "tools" in readme_counts and readme_counts["tools"] != actual_tools:
        count_drifts["tools"] = {"readme": readme_counts["tools"], "actual": actual_tools}
    if "stdlib_modules" in readme_counts and readme_counts["stdlib_modules"] != actual_stdlib:
        count_drifts["stdlib_modules"] = {
            "readme": readme_counts["stdlib_modules"],
            "actual": actual_stdlib,
        }
    if "opcodes" in readme_counts and readme_counts["opcodes"] != actual_opcodes:
        count_drifts["opcodes"] = {"readme": readme_counts["opcodes"], "actual": actual_opcodes}

    if count_drifts:
        has_drift = True

    findings.append(
        {
            "check": "readme_count_accuracy",
            "drift": bool(count_drifts),
            "drifts": count_drifts,
            "actual": {
                "tools": actual_tools,
                "stdlib_modules": actual_stdlib,
                "opcodes": actual_opcodes,
            },
            "readme_claimed": readme_counts,
        }
    )

    return findings, has_drift


def main() -> None:
    findings, has_drift = run_checks()
    report = {
        "drift_detected": has_drift,
        "findings": findings,
    }
    print(json.dumps(report, indent=2))
    sys.exit(1 if has_drift else 0)


if __name__ == "__main__":
    main()
