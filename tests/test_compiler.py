"""Tests for HLF compiler (parser + AST transformer)."""

import pytest
from hlf_mcp.hlf.compiler import HLFCompiler, CompileError

COMPILER = HLFCompiler()

# ── Fixtures ──────────────────────────────────────────────────────────────────

HELLO_WORLD = """\
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
Ω
"""

SECURITY_AUDIT = """\
[HLF-v3]
Δ analyze /security/seccomp.json
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] vulnerability_shorthand
  ⨝ [VOTE] consensus="strict"
Ω
"""

DELEGATION = """\
[HLF-v3]
⌘ [DELEGATE] agent="scribe" goal="fractal_summarize"
  ∇ [SOURCE] /data/raw_logs/matrix_sync_2026.txt
  ⩕ [PRIORITY] level="high"
  Ж [ASSERT] vram_limit="8GB"
Ω
"""

ROUTING = """\
[HLF-v3]
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  ∇ [PARAM] temperature=0.0
  Ж [VOTE] confirmation="required"
Ω
"""

SET_VAR = """\
[HLF-v3]
SET model_name = "llama3.2"
Δ [INTENT] model="llama3.2"
Ω
"""

WITH_SPEC = """\
[HLF-v3]
SPEC_DEFINE [MIGRATION] version="1.0" idempotent=true
Δ [INTENT] goal="migrate"
SPEC_GATE [MIGRATION] rollback_on_fail=true
Ω
"""

# ── Tests ─────────────────────────────────────────────────────────────────────


def test_compile_hello_world():
    result = COMPILER.compile(HELLO_WORLD)
    assert result["errors"] == []
    ast = result["ast"]
    assert ast["kind"] == "program"
    assert ast["version"] == "3"
    stmts = ast["statements"]
    assert len(stmts) >= 1
    assert stmts[0]["kind"] == "glyph_stmt"
    assert stmts[0]["glyph"] == "Δ"
    assert stmts[0]["tag"] == "INTENT"


def test_compile_security_audit():
    result = COMPILER.compile(SECURITY_AUDIT)
    assert result["errors"] == []
    ast = result["ast"]
    stmts = ast["statements"]
    # First stmt: Δ analyze with path arg
    assert stmts[0]["glyph"] == "Δ"
    # Check tags on other statements
    tags = [s.get("tag") for s in stmts]
    assert "CONSTRAINT" in tags
    assert "EXPECT" in tags
    assert "VOTE" in tags


def test_compile_delegation():
    result = COMPILER.compile(DELEGATION)
    assert result["errors"] == []
    ast = result["ast"]
    stmts = ast["statements"]
    assert stmts[0]["glyph"] == "⌘"
    assert stmts[0]["tag"] == "DELEGATE"
    # Check kv_arg parsing: agent="scribe"
    args = stmts[0]["arguments"]
    agent_arg = next((a for a in args if a.get("name") == "agent"), None)
    assert agent_arg is not None
    assert agent_arg["value"]["value"] == "scribe"


def test_compile_routing_with_var_ref():
    result = COMPILER.compile(ROUTING)
    assert result["errors"] == []
    ast = result["ast"]
    stmts = ast["statements"]
    first = stmts[0]
    assert first["tag"] == "ROUTE"
    # tier="$DEPLOYMENT_TIER" — quoted → type=string; Pass 2 expands $VAR inside strings
    args = first["arguments"]
    tier_arg = next((a for a in args if a.get("name") == "tier"), None)
    assert tier_arg is not None
    # Value is a quoted string whose content contains the variable reference
    assert tier_arg["value"]["type"] in ("string", "var_ref")
    assert "DEPLOYMENT_TIER" in str(tier_arg["value"]["value"])


def test_compile_set_statement():
    result = COMPILER.compile(SET_VAR)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    set_stmt = next(s for s in stmts if s["kind"] == "set_stmt")
    assert set_stmt["name"] == "model_name"
    assert set_stmt["value"]["value"] == "llama3.2"


def test_compile_spec_statements():
    result = COMPILER.compile(WITH_SPEC)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    kinds = [s["kind"] for s in stmts]
    assert "spec_define_stmt" in kinds
    assert "spec_gate_stmt" in kinds


def test_compile_float_value():
    src = '[HLF-v3]\n∇ [PARAM] temperature=0.0\nΩ\n'
    result = COMPILER.compile(src)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    args = stmts[0]["arguments"]
    temp_arg = next(a for a in args if a.get("name") == "temperature")
    assert temp_arg["value"]["type"] == "float"
    assert temp_arg["value"]["value"] == 0.0


def test_compile_version_extracted():
    result = COMPILER.compile(HELLO_WORLD)
    assert result["version"] == "3"


def test_compile_versioned_header():
    src = '[HLF-v3.1]\nΔ test\nΩ\n'
    result = COMPILER.compile(src)
    assert result["version"] == "3.1"


def test_compile_node_count():
    result = COMPILER.compile(SECURITY_AUDIT)
    assert result["node_count"] == 4  # Δ + 3 Ж/⨝ sub-statements


def test_compile_gas_estimate_positive():
    result = COMPILER.compile(HELLO_WORLD)
    assert result["gas_estimate"] > 0


def test_compile_human_readable_present():
    result = COMPILER.compile(HELLO_WORLD)
    ast = result["ast"]
    assert "human_readable" in ast
    assert len(ast["human_readable"]) > 0


def test_compile_sha256_present():
    result = COMPILER.compile(HELLO_WORLD)
    assert "sha256" in result["ast"]
    assert len(result["ast"]["sha256"]) == 64


def test_compile_invalid_source_raises():
    with pytest.raises(CompileError):
        COMPILER.compile("this is not hlf at all!!!")


def test_compile_missing_terminator_raises():
    with pytest.raises(CompileError):
        COMPILER.compile("[HLF-v3]\nΔ analyze /foo\n")  # no Ω


def test_compile_empty_raises():
    with pytest.raises(CompileError):
        COMPILER.compile("")


def test_validate_valid():
    result = COMPILER.validate(HELLO_WORLD)
    assert result["valid"] is True
    assert result["error"] is None
    assert result["has_terminator"] is True


def test_validate_invalid():
    result = COMPILER.validate("not valid hlf")
    assert result["valid"] is False
    assert result["error"] is not None


def test_compile_all_fixtures():
    """Compile all fixture files successfully."""
    import os
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures")
    hlf_files = [f for f in os.listdir(fixtures_dir) if f.endswith(".hlf")]
    assert len(hlf_files) > 0, "No fixture files found"
    for fname in hlf_files:
        with open(os.path.join(fixtures_dir, fname), encoding='utf-8') as f:
            source = f.read()
        result = COMPILER.compile(source)
        assert result["errors"] == [], f"Fixture {fname} failed: {result['errors']}"


def test_compile_with_integer_param():
    src = '[HLF-v3]\n∇ [PARAM] top_k=10\nΩ\n'
    result = COMPILER.compile(src)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    args = stmts[0]["arguments"]
    arg = next(a for a in args if a.get("name") == "top_k")
    assert arg["value"]["type"] == "int"
    assert arg["value"]["value"] == 10
