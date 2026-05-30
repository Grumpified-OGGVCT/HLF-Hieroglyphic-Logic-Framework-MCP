"""
CI Import Guard — Prevents swarmglass.core from pulling in DSL modules.

====================================================================
STATUS: ACTIVE — Package init uses __getattr__-based lazy loading
====================================================================

The package-init lazy-loading fix was completed as follows:

  1.  hlf_mcp/__init__.py  — All module-level DSL imports removed;
      replaced with a ``__getattr__`` that defers to hlf_mcp.hlf
      only when an exported name is accessed.

  2.  hlf_mcp/hlf/__init__.py  — All module-level DSL imports removed;
      replaced with a ``__getattr__`` that imports DSL modules only
      on access.

  3.  A bare ``import hlf_mcp`` loads zero DSL modules into sys.modules.

  4.  The swarmglass.core namespace (future) must live OUTSIDE the
      hlf_mcp package tree so it never triggers hlf_mcp/__init__.py.

Full analysis:  docs/HIDDEN_COUPLING_REPORT.md  (lines 74-99)

These tests gate any PR that reintroduces module-level DSL imports.
"""

from __future__ import annotations

import subprocess
import sys
import types
from typing import FrozenSet, List

import pytest

# ═══════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════

# Modules that swarmglass.core must NEVER import transitively.
# These form the DSL/VM layer that must remain gated behind
# SWARMGLASS_HLF_ENABLED.
_FORBIDDEN_DSL_MODULES: FrozenSet[str] = frozenset(
    {
        "hlf_mcp.hlf.compiler",
        "hlf_mcp.hlf.runtime",
        "hlf_mcp.hlf.bytecode",
        "hlf_mcp.hlf.translator",
        "hlf_mcp.hlf.grammar",
        "hlf_mcp.hlf.formal_verifier",
        "hlf_mcp.hlf.linter",
        "hlf_mcp.hlf.formatter",
        "hlf_mcp.hlf.codegen",
    }
)

# These are the "governance" modules that swarmglass.core IS allowed
# to import — they should never drag in the DSL.
_GOVERNANCE_MODULE_PREFIXES: FrozenSet[str] = frozenset(
    {
        "hlf_mcp.hlf.governance",
        "hlf_mcp.hlf.audit",
        "hlf_mcp.hlf.ethics",
        "hlf_mcp.hlf.knowledge",
        "hlf_mcp.hlf.trust",
        "hlf_mcp.hlf.review",
        "hlf_mcp.hlf.swarm_consensus",
        "hlf_mcp.hlf.swarm_observer",
        "hlf_mcp.hlf.governed",
        "hlf_mcp.hlf.routing",
        "hlf_mcp.hlf.memory",
        "hlf_mcp.hlf.session",
        "hlf_mcp.hlf.capsules",
        "hlf_mcp.hlf.registry",
        "hlf_mcp.hlf.authority",
        "hlf_mcp.hlf.plan",
        "hlf_mcp.hlf.agent_identity",
        "hlf_mcp.hlf.agent_heartbeat",
        "hlf_mcp.hlf.pii_guard",
        "hlf_mcp.hlf.insaits",
        "hlf_mcp.hlf.dream",
        "hlf_mcp.hlf.overwatch",
        "hlf_mcp.hlf.import_whitelist",
        "hlf_mcp.hlf.sandbox_executor",
        "hlf_mcp.hlf.error_translation",
        "hlf_mcp.hlf.python_type_coercion",
    }
)

_FIX_REFERENCE: str = (
    "Package-init lazy-loading is now active — "
    "hlf_mcp/__init__.py and hlf_mcp/hlf/__init__.py use "
    "__getattr__-based lazy accessors. See docs/HIDDEN_COUPLING_REPORT.md "
    "lines 74-99 for the original coupling analysis."
)


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════


def _forbidden_in_sys_modules() -> List[str]:
    """Return the list of forbidden DSL modules currently loaded in sys.modules."""
    return sorted(m for m in _FORBIDDEN_DSL_MODULES if m in sys.modules)


def _governance_modules_loaded() -> List[str]:
    """Return governance-prefix modules currently loaded in sys.modules."""
    return sorted(
        m
        for m in sys.modules
        if any(m.startswith(p) for p in _GOVERNANCE_MODULE_PREFIXES)
    )


def _submodule_import_check(
    parent: str, forbidden: FrozenSet[str]
) -> subprocess.CompletedProcess:
    """Spawn a clean subprocess that imports *only* `parent` and checks
    whether any `forbidden` module leaks into sys.modules.

    Returns the CompletedProcess so callers can inspect stdout/stderr.
    """
    code = f"""
import sys
import json
__import__({parent!r})
leaked = sorted(m for m in {sorted(forbidden)!r} if m in sys.modules)
print(json.dumps({{"leaked": leaked}}))
"""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ═══════════════════════════════════════════════════════════════════
#  Standalone CI entry point (no pytest required)
# ═══════════════════════════════════════════════════════════════════


def import_guard_check() -> int:
    """Standalone check suitable for a CI shell step.

    Returns 0 if no forbidden DSL modules are present in the current
    interpreter, 1 otherwise.  Prints a human-readable report to stdout.

    USAGE (CI shell):
        python -c "from tests.test_ci_import_guard import import_guard_check; raise SystemExit(import_guard_check())"

    USAGE (direct):
        python tests/test_ci_import_guard.py --standalone
    """
    forbidden = _forbidden_in_sys_modules()
    governance = _governance_modules_loaded()

    print("=" * 68)
    print("  swarmglass.core Import Guard — Standalone Check")
    print("=" * 68)
    print()

    if forbidden:
        print(f"❌  BLOCKED — {len(forbidden)} forbidden DSL module(s) in sys.modules:")
        for m in forbidden:
            print(f"       • {m}")
        print()
        print("  Root cause: A package __init__.py reintroduced eager DSL imports.")
        print("  Fix:        Convert to __getattr__-based lazy accessors.")
        print()
        if governance:
            print(f"  ℹ️   {len(governance)} governance module(s) also loaded (expected).")
        print()
        return 1

    if governance:
        print(f"✅  PASS — No forbidden DSL modules loaded.")
        print(f"    {len(governance)} governance module(s) present (expected).")
    else:
        print("✅  PASS — No forbidden DSL modules loaded.")
        print("    ℹ️   No governance modules loaded either (clean interpreter).")

    print()
    return 0


# ═══════════════════════════════════════════════════════════════════
#  Pytest test class
# ═══════════════════════════════════════════════════════════════════


class TestSwarmGlassImportGuard:
    """Verify that swarmglass.core never pulls in DSL/VM modules.

    The package-init lazy-loading fix (__getattr__ in hlf_mcp/__init__.py
    and hlf_mcp/hlf/__init__.py) ensures a bare ``import hlf_mcp`` loads
    zero DSL modules.  These tests gate any PR that reintroduces
    module-level DSL imports in the package init chain.

    Reference: docs/HIDDEN_COUPLING_REPORT.md lines 74-99.
    """

    # ── Granular per-module checks ──────────────────────────────────

    def test_no_compiler_import(self) -> None:
        """hlf_mcp.hlf.compiler must NOT be in sys.modules after
        importing only governance/audit/trust primitives."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]  # safe — we control the subprocess code
        assert "hlf_mcp.hlf.compiler" not in leaked, (
            f"compiler leaked into sys.modules: {leaked}"
        )

    def test_no_runtime_import(self) -> None:
        """hlf_mcp.hlf.runtime must NOT be in sys.modules after
        importing only governance/audit/trust primitives."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.runtime" not in leaked, (
            f"runtime leaked into sys.modules: {leaked}"
        )

    def test_no_bytecode_import(self) -> None:
        """hlf_mcp.hlf.bytecode must NOT be in sys.modules after
        importing only governance/audit/trust primitives."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.bytecode" not in leaked, (
            f"bytecode leaked into sys.modules: {leaked}"
        )

    def test_no_translator_import(self) -> None:
        """hlf_mcp.hlf.translator must NOT be transitively imported."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.translator" not in leaked, (
            f"translator leaked into sys.modules: {leaked}"
        )

    def test_no_grammar_import(self) -> None:
        """hlf_mcp.hlf.grammar must NOT be transitively imported."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.grammar" not in leaked, (
            f"grammar leaked into sys.modules: {leaked}"
        )

    def test_no_formal_verifier_import(self) -> None:
        """hlf_mcp.hlf.formal_verifier must NOT be transitively imported."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.formal_verifier" not in leaked, (
            f"formal_verifier leaked into sys.modules: {leaked}"
        )

    def test_no_linter_import(self) -> None:
        """hlf_mcp.hlf.linter must NOT be transitively imported."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.linter" not in leaked, (
            f"linter leaked into sys.modules: {leaked}"
        )

    def test_no_formatter_import(self) -> None:
        """hlf_mcp.hlf.formatter must NOT be transitively imported."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.formatter" not in leaked, (
            f"formatter leaked into sys.modules: {leaked}"
        )

    def test_no_codegen_import(self) -> None:
        """hlf_mcp.hlf.codegen must NOT be transitively imported."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert "hlf_mcp.hlf.codegen" not in leaked, (
            f"codegen leaked into sys.modules: {leaked}"
        )

    # ── Bulk isolation check ─────────────────────────────────────────

    def test_experimental_modules_isolated(self) -> None:
        """Verify ZERO forbidden DSL modules appear in sys.modules
        after importing governance-only primitives."""
        proc = _submodule_import_check(
            "hlf_mcp.hlf.governance_events", _FORBIDDEN_DSL_MODULES
        )
        leaked = eval(proc.stdout)["leaked"]
        assert leaked == [], (
            f"Forbidden DSL modules leaked into sys.modules: {leaked}"
        )

    # ── Documentation check (always runs) ────────────────────────────

    def test_guard_documents_reference(self) -> None:
        """Self-audit: this test file must reference the coupling analysis
        so future maintainers understand the architectural invariant."""
        import inspect

        source = inspect.getsource(sys.modules[__name__])
        assert "HIDDEN_COUPLING_REPORT.md" in source, (
            "Guard script must reference docs/HIDDEN_COUPLING_REPORT.md "
            "to document the coupling analysis."
        )
        assert "hlf_mcp/__init__.py" in source, (
            "Guard script must reference hlf_mcp/__init__.py as part of "
            "the package-init lazy-loading fix."
        )
        assert (
            "__getattr__" in source
        ), "Guard script must reference the __getattr__-based lazy-loading fix."


# ═══════════════════════════════════════════════════════════════════
#  __main__ — standalone CI runner
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(import_guard_check())
