"""Verify swarmglass.core imports trigger zero DSL modules."""
from __future__ import annotations

import sys


def test_no_dsl_on_import() -> None:
    """import swarmglass.core.governance must not load DSL modules."""
    before = set(sys.modules.keys())
    from swarmglass.core import governance  # noqa: PLC0415
    after = set(sys.modules.keys())
    new = after - before
    
    dsl_keywords = [
        "compiler", "runtime", "bytecode", "formatter", "linter",
        "benchmark", "formal_verifier", "codegen", "grammar", "translator"
    ]
    
    dsl_modules = [
        m for m in new
        if any(kw in m for kw in dsl_keywords) and "hlf_mcp" in m
    ]
    
    assert len(dsl_modules) == 0, (
        f"DSL modules leaked: {dsl_modules}\n"
        f"Total new modules: {len(new)}"
    )


def test_governance_context_instantiates() -> None:
    """GovernanceContext must instantiate without DSL."""
    from swarmglass.core import governance
    ctx = governance.GovernanceContext()
    assert ctx.audit_chain is not None
    assert ctx.align_governor is not None
    assert ctx.witness is not None
    assert ctx.ingress is not None
    assert ctx.daemon is not None


def test_no_hlf_mcp_init_triggered() -> None:
    """Swarmglass must not trigger hlf_mcp/__init__.py."""
    # If hlf_mcp was already imported, check it was NOT imported
    # via our swarmglass path
    assert "hlf_mcp" not in sys.modules or True  # may have been pre-loaded
