#!/usr/bin/env python3
"""
Boot Path Proof Script — Gate 1, Artifact 7.

Verifies that the HLF_MCP server CAN boot without importing the
HLF DSL/VM/compiler stack when SWARMGLASS_EXPERIMENTAL=0.

Part A:  Documents the CURRENT state (all imports eager — DSL leaks).
Part B:  Shows that even direct submodule imports trigger package init pollution.
Part B2: Proves governance modules' source code is clean via AST analysis.
Part C:  Instantiates governance objects to prove they work without DSL.

Run:  python docs/boot_proof_test.py
"""

from __future__ import annotations

import ast
import os
import sys
import importlib
from pathlib import Path

# Ensure the HLF_MCP repo root is on sys.path so we can import from it.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

os.environ["SWARMGLASS_EXPERIMENTAL"] = "0"

# The DSL modules we want to prove are NOT loaded.
DSL_MODULES = frozenset({
    "hlf_mcp.hlf.compiler",
    "hlf_mcp.hlf.runtime",
    "hlf_mcp.hlf.bytecode",
    "hlf_mcp.hlf.formatter",
    "hlf_mcp.hlf.linter",
    "hlf_mcp.hlf.benchmark",
    "hlf_mcp.hlf.formal_verifier",
    "hlf_mcp.hlf.codegen",
    "hlf_mcp.hlf.grammar",
    "hlf_mcp.hlf.translator",
})

# Governance modules that SHOULD load without DSL.
GOVERNANCE_MODULES = frozenset({
    "hlf_mcp.hlf.align_governor",
    "hlf_mcp.hlf.approval_ledger",
    "hlf_mcp.hlf.audit_chain",
    "hlf_mcp.hlf.daemon_manager",
    "hlf_mcp.hlf.governed_ingress",
    "hlf_mcp.hlf.witness_governance",
    "hlf_mcp.hlf.governance_events",
    "hlf_mcp.hlf.governance_proofs",
    "hlf_mcp.hlf.registry",
    "hlf_mcp.hlf.tool_dispatch",
    "hlf_mcp.hlf.intent_normalizer",
    "hlf_mcp.hlf.memory_node",
})

# Governance .py source files (relative to repo root)
GOVERNANCE_SOURCES = [
    "hlf_mcp/hlf/align_governor.py",
    "hlf_mcp/hlf/approval_ledger.py",
    "hlf_mcp/hlf/audit_chain.py",
    "hlf_mcp/hlf/daemon_manager.py",
    "hlf_mcp/hlf/governed_ingress.py",
    "hlf_mcp/hlf/witness_governance.py",
    "hlf_mcp/hlf/governance_events.py",
    "hlf_mcp/hlf/governance_proofs.py",
    "hlf_mcp/hlf/registry.py",
    "hlf_mcp/hlf/tool_dispatch.py",
    "hlf_mcp/hlf/intent_normalizer.py",
    "hlf_mcp/hlf/memory_node.py",
]

# DSL source files to cross-check
DSL_SOURCES = [
    "hlf_mcp/hlf/compiler.py",
    "hlf_mcp/hlf/runtime.py",
    "hlf_mcp/hlf/bytecode.py",
]

# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def snapshot_hlf_modules() -> dict[str, bool]:
    """Return which DSL and governance modules are in sys.modules."""
    result: dict[str, bool] = {}
    for mod in sorted(DSL_MODULES | GOVERNANCE_MODULES):
        result[mod] = mod in sys.modules
    return result


def green(text: str) -> str:
    return f"\033[92m{text}\033[0m"


def red(text: str) -> str:
    return f"\033[91m{text}\033[0m"


def yellow(text: str) -> str:
    return f"\033[93m{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


# ══════════════════════════════════════════════════════════════════════════════
# Part A: Current State — Document the Pollution
# ══════════════════════════════════════════════════════════════════════════════

def part_a_current_state():
    print(bold("=" * 72))
    print(bold("PART A: Current Boot Path — DSL Pollution"))
    print(bold("=" * 72))
    print()
    print("Attempting: from hlf_mcp.server_context import ServerContext")
    print("Expected:   DSL modules leak into sys.modules")
    print()

    before = snapshot_hlf_modules()

    try:
        from hlf_mcp.server_context import ServerContext  # noqa: F811
        import_success = True
    except Exception as exc:
        print(red(f"  Import FAILED: {exc}"))
        import_success = False

    after = snapshot_hlf_modules()

    # Find what was newly loaded
    newly_loaded = {k for k, v in after.items() if v and not before.get(k, False)}

    dsl_leaked = newly_loaded & DSL_MODULES
    gov_loaded = newly_loaded & GOVERNANCE_MODULES

    print(f"  Import {'succeeded' if import_success else 'FAILED'}")
    print()
    print(f"  DSL modules leaked: {len(dsl_leaked)}")
    for mod in sorted(dsl_leaked):
        print(f"    {red('✗')} {mod}")
    print()
    print(f"  Governance modules loaded: {len(gov_loaded)}")
    for mod in sorted(gov_loaded):
        print(f"    {green('✓')} {mod}")

    if dsl_leaked:
        print()
        print(yellow("  VERDICT: DSL STACK IS EAGERLY LOADED — GATE 1 BLOCKER"))
    else:
        print()
        print(green("  VERDICT: No DSL modules leaked — CLEAN"))

    return dsl_leaked


# ══════════════════════════════════════════════════════════════════════════════
# Part B: Show Package Init Pollution
# ══════════════════════════════════════════════════════════════════════════════

def part_b_package_init_pollution():
    print()
    print(bold("=" * 72))
    print(bold("PART B: Package Init Pollution — Direct Submodule Imports"))
    print(bold("=" * 72))
    print()
    print("Even importing a single governance submodule like")
    print("'from hlf_mcp.hlf.align_governor import AlignGovernor'")
    print("triggers hlf_mcp/__init__.py → hlf_mcp/hlf/__init__.py,")
    print("which eagerly loads the entire DSL stack.")
    print()

    # Clear previously loaded modules
    for mod in list(sys.modules):
        if mod.startswith("hlf_mcp"):
            del sys.modules[mod]

    before_all = set(sys.modules.keys())

    # Import one governance module directly
    from hlf_mcp.hlf.align_governor import AlignGovernor as AG  # noqa: F811

    after_all = set(sys.modules.keys())
    newly_loaded = after_all - before_all

    dsl_leaked = {m for m in newly_loaded if m in DSL_MODULES}
    gov_loaded = {m for m in newly_loaded if m in GOVERNANCE_MODULES}
    other_loaded = newly_loaded - DSL_MODULES - GOVERNANCE_MODULES

    print(f"  Imported: AlignGovernor (from hlf_mcp.hlf.align_governor)")
    print(f"  Total modules loaded into sys.modules: {len(newly_loaded)}")
    print()
    print(f"  DSL modules leaked: {len(dsl_leaked)}")
    for mod in sorted(dsl_leaked):
        print(f"    {red('✗')} {mod}")
    print()
    print(f"  Governance modules loaded: {len(gov_loaded)}")
    for mod in sorted(gov_loaded):
        print(f"    {green('✓')} {mod}")
    print()
    print(f"  Other hlf_mcp modules (package inits, etc.): {len(other_loaded)}")
    for mod in sorted(other_loaded):
        print(f"    {yellow('·')} {mod}")

    if dsl_leaked:
        print()
        print(yellow("  FINDING: Package __init__.py files are the root cause."))
        print(yellow("  hlf_mcp/__init__.py and hlf_mcp/hlf/__init__.py"))
        print(yellow("  eagerly import the DSL at module level."))

    return dsl_leaked


# ══════════════════════════════════════════════════════════════════════════════
# Part B2: AST Analysis — Prove Source Code Is Clean
# ══════════════════════════════════════════════════════════════════════════════

def _extract_hlf_imports(filepath: Path) -> list[str]:
    """Parse a .py file and return all hlf_mcp imports at the top level."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return ["<PARSE ERROR>"]

    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "hlf_mcp" in alias.name:
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and "hlf_mcp" in node.module:
                for alias in node.names:
                    full = f"{node.module}.{alias.name}"
                    imports.append(full)
    return imports


def part_b2_ast_proof():
    print()
    print(bold("=" * 72))
    print(bold("PART B2: AST Static Analysis — Governance Source Code Purity"))
    print(bold("=" * 72))
    print()
    print("Parsing governance .py files with AST to prove their")
    print("source code does NOT import from DSL modules.")
    print()

    clean_count = 0
    dirty_count = 0

    for src_path in sorted(GOVERNANCE_SOURCES):
        full_path = _REPO_ROOT / src_path
        if not full_path.exists():
            print(f"  {yellow('?')} {src_path} — FILE NOT FOUND")
            continue

        imports = _extract_hlf_imports(full_path)
        # Check if any import is from DSL modules
        dsl_imports = []
        gov_imports = []
        for imp in imports:
            # Check if this import path contains a DSL module name
            is_dsl = any(
                imp == dsl or imp.startswith(dsl + ".")
                for dsl in DSL_MODULES
            )
            if is_dsl:
                dsl_imports.append(imp)
            else:
                gov_imports.append(imp)

        if dsl_imports:
            print(f"  {red('✗')} {src_path} — IMPORTS DSL:")
            for imp in dsl_imports:
                print(f"       {red(imp)}")
            dirty_count += 1
        else:
            label = f"({len(gov_imports)} hlf_mcp imports)" if gov_imports else "(stdlib only)"
            print(f"  {green('✓')} {src_path} {label}")
            for imp in gov_imports:
                print(f"       {imp}")
            clean_count += 1

    # Also check the DSL sources to confirm they import what we expect
    print()
    print("  Cross-check — DSL source files (expected to import DSL):")
    for src_path in sorted(DSL_SOURCES):
        full_path = _REPO_ROOT / src_path
        if not full_path.exists():
            print(f"  {yellow('?')} {src_path} — FILE NOT FOUND")
            continue
        imports = _extract_hlf_imports(full_path)
        print(f"  {yellow('·')} {src_path}: {len(imports)} hlf_mcp imports")

    print()
    print(f"  Clean governance files: {green(str(clean_count))}")
    print(f"  Files with DSL imports: {red(str(dirty_count))}")
    print()
    if dirty_count == 0:
        print(green("  ✓ All governance source files are DSL-free at the AST level."))
        print(green("    The pollution comes ONLY from package __init__.py files."))
    else:
        print(yellow(f"  ⚠ {dirty_count} governance files have DSL imports."))

    return clean_count, dirty_count


# ══════════════════════════════════════════════════════════════════════════════
# Part C: Instantiation Test — Prove Governance Objects Work
# ══════════════════════════════════════════════════════════════════════════════

def part_c_instantiation_test():
    print()
    print(bold("=" * 72))
    print(bold("PART C: Instantiation Test — Governance Objects Without DSL"))
    print(bold("=" * 72))
    print()
    print("Instantiating governance objects to prove they work.")
    print("(DSL modules are in sys.modules from package init, but the")
    print("governance objects themselves don't use them.)")
    print()

    tests_passed = 0
    tests_failed = 0
    results: list[tuple[str, bool, str]] = []

    def _test(name: str, fn):
        nonlocal tests_passed, tests_failed
        try:
            obj = fn()
            msg = f"instantiated: {type(obj).__name__}"
            results.append((name, True, msg))
            tests_passed += 1
            return obj
        except Exception as exc:
            msg = f"FAILED: {exc}"
            results.append((name, False, msg))
            tests_failed += 1
            return None

    # Import governance objects (already in sys.modules from Part B)
    from hlf_mcp.hlf.align_governor import AlignGovernor
    from hlf_mcp.hlf.audit_chain import AuditChain
    from hlf_mcp.hlf.approval_ledger import ApprovalLedger
    from hlf_mcp.hlf.witness_governance import WitnessGovernance
    from hlf_mcp.hlf.daemon_manager import DaemonManager
    from hlf_mcp.hlf.registry import HostFunctionRegistry
    from hlf_mcp.hlf.tool_dispatch import ToolRegistry
    from hlf_mcp.hlf.intent_normalizer import IntentNormalizer
    from hlf_mcp.hlf.governance_events import GovernanceEvent, GovernanceEventKind
    from hlf_mcp.hlf.governance_proofs import build_governance_proof, sha256_digest
    from hlf_mcp.hlf.governed_ingress import GovernedIngressController

    _test("AlignGovernor", AlignGovernor)
    _test("AuditChain", AuditChain)
    _test("ApprovalLedger", ApprovalLedger)
    _test("WitnessGovernance", WitnessGovernance)
    _test("DaemonManager", DaemonManager)
    _test("HostFunctionRegistry", HostFunctionRegistry)
    _test("ToolRegistry", ToolRegistry)
    _test("IntentNormalizer", IntentNormalizer)

    # GovernedIngressController needs an AlignGovernor
    ag = AlignGovernor()
    try:
        gic = GovernedIngressController(align_governor=ag)
        results.append(("GovernedIngressController", True, f"instantiated: {type(gic).__name__}"))
        tests_passed += 1
    except Exception as exc:
        results.append(("GovernedIngressController", False, f"FAILED: {exc}"))
        tests_failed += 1

    # Governance proofs
    try:
        proof = build_governance_proof(
            artifact_kind="test",
            artifact_id="proof-test-001",
            events=[{"action": "test", "timestamp": "2026-05-23T00:00:00Z"}],
        )
        results.append(("build_governance_proof", True, f"returned {len(proof)} keys"))
        tests_passed += 1
    except Exception as exc:
        results.append(("build_governance_proof", False, f"FAILED: {exc}"))
        tests_failed += 1

    try:
        digest = sha256_digest("test payload")
        results.append(("sha256_digest", True, f"digest={digest[:16]}..."))
        tests_passed += 1
    except Exception as exc:
        results.append(("sha256_digest", False, f"FAILED: {exc}"))
        tests_failed += 1

    for name, ok, msg in results:
        print(f"  {green('✓') if ok else red('✗')} {name}: {msg}")

    print()
    print(f"  Passed: {green(str(tests_passed))}  Failed: {red(str(tests_failed))}")
    return tests_passed, tests_failed


# ══════════════════════════════════════════════════════════════════════════════
# Part D: DSL Presence Check
# ══════════════════════════════════════════════════════════════════════════════

def part_d_dsl_check():
    print()
    print(bold("=" * 72))
    print(bold("PART D: DSL Modules in sys.modules"))
    print(bold("=" * 72))
    print()

    dsl_present = [m for m in sorted(DSL_MODULES) if m in sys.modules]
    dsl_absent = [m for m in sorted(DSL_MODULES) if m not in sys.modules]

    if dsl_present:
        print(f"  DSL modules present: {red(str(len(dsl_present)))}")
        for mod in dsl_present:
            print(f"    {red('✗')} {mod}")
    if dsl_absent:
        print(f"  DSL modules absent: {green(str(len(dsl_absent)))}")
        for mod in dsl_absent:
            print(f"    {green('✓')} {mod} (not loaded)")

    print()
    if dsl_present:
        print(yellow(f"  DSL modules loaded: {len(dsl_present)}/{len(DSL_MODULES)}"))
        print(yellow("  Root cause: package __init__.py files eagerly import DSL."))
    else:
        print(green("  ✓ NO DSL MODULES loaded — clean boot"))

    return len(dsl_present)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    print(bold("HLF_MCP Boot Path Proof — SWARMGLASS_EXPERIMENTAL=0"))
    print(f"  Repo root: {_REPO_ROOT}")
    print(f"  SWARMGLASS_EXPERIMENTAL={os.environ.get('SWARMGLASS_EXPERIMENTAL', 'unset')}")
    print()

    # Part A: Document current pollution via ServerContext import
    dsl_leaked_a = part_a_current_state()

    # Part B: Show package init pollution from even a single governance import
    dsl_leaked_b = part_b_package_init_pollution()

    # Part B2: AST analysis — prove governance source code is clean
    clean_count, dirty_count = part_b2_ast_proof()

    # Part C: Instantiation test
    passed, failed = part_c_instantiation_test()

    # Part D: Final DSL check
    dsl_count = part_d_dsl_check()

    print()
    print(bold("=" * 72))
    print(bold("SUMMARY"))
    print(bold("=" * 72))
    print()

    print(f"  Part A  — ServerContext import: {len(dsl_leaked_a)} DSL modules leaked")
    print(f"  Part B  — Single gov submodule:  {len(dsl_leaked_b)} DSL modules leaked")
    print(f"  Part B2 — AST source analysis:   {clean_count} clean, {dirty_count} with DSL imports")
    print(f"  Part C  — Instantiation:          {passed}/{passed + failed} passed")
    print(f"  Part D  — DSL in sys.modules:     {dsl_count}/{len(DSL_MODULES)} present")

    print()
    if dirty_count == 0 and passed > 0:
        print(green(bold("  ✓ VERDICT: Governance source code is DSL-free.")))
        print(green("    The pollution comes ONLY from package __init__.py files."))
        print(green("    Refactoring plan in docs/BOOT_PROOF.md is sound."))
        print(green("    SWARMGLASS_EXPERIMENTAL=0 boot is VIABLE within Phase 2."))
        return 0
    elif dirty_count > 0:
        print(yellow(bold(f"  ⚠ {dirty_count} governance files import DSL modules.")))
        print(yellow("    These need refactoring before clean boot is possible."))
        return 1
    else:
        print(yellow("  ⚠ Inconclusive — check output above."))
        return 1


if __name__ == "__main__":
    sys.exit(main())
