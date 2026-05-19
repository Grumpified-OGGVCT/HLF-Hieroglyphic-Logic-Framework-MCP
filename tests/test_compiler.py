"""Tests for HLF compiler (parser + AST transformer)."""

import pytest

from hlf_mcp.hlf.compiler import CompileError, HLFCompiler

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
    src = "[HLF-v3]\n∇ [PARAM] temperature=0.0\nΩ\n"
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
    src = "[HLF-v3.1]\nΔ test\nΩ\n"
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
        with open(os.path.join(fixtures_dir, fname), encoding="utf-8") as f:
            source = f.read()
        result = COMPILER.compile(source)
        assert result["errors"] == [], f"Fixture {fname} failed: {result['errors']}"


def test_compile_with_integer_param():
    src = "[HLF-v3]\n∇ [PARAM] top_k=10\nΩ\n"
    result = COMPILER.compile(src)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    args = stmts[0]["arguments"]
    arg = next(a for a in args if a.get("name") == "top_k")
    assert arg["value"]["type"] == "int"
    assert arg["value"]["value"] == 10


def test_compile_restored_generic_memory_and_summary_glyphs():
    src = (
        '[HLF-v3]\n'
        '⌂ [MEMORY] entity="release" confidence=1.0\n'
        'Σ [PROVENANCE] source="weekly" confidence=1.0\n'
        "Ω\n"
    )
    result = COMPILER.compile(src)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert [stmt["glyph"] for stmt in stmts] == ["⌂", "Σ"]
    assert [stmt["tag"] for stmt in stmts] == ["MEMORY", "PROVENANCE"]


def test_memory_keyword_not_shadowed_by_memory_anchor_alias():
    src = '[HLF-v3]\nMEMORY [release] entity="release" confidence=1.0\nΩ\n'
    result = COMPILER.compile(src)
    assert result["errors"] == []
    assert result["ast"]["statements"][0]["kind"] == "memory_stmt"


def test_compile_module_with_function_block():
    src = (
        "[HLF-v3]\n"
        "MODULE demo tier=\"hearth\" {\n"
        "  FUNCTION main(input: text) {\n"
        "    RESULT 0 \"ok\"\n"
        "  }\n"
        "}\n"
        "Ω\n"
    )
    result = COMPILER.compile(src)
    module = result["ast"]["statements"][0]
    function = module["body"]["statements"][0]
    assert module["kind"] == "module_block_stmt"
    assert module["name"] == "demo"
    assert module["arguments"][0]["name"] == "tier"
    assert function["kind"] == "func_block_stmt"
    assert function["params"][0]["name"] == "input"


# ═══════════════════════════════════════════════════════════════════════════════
# Expansion 1: PIPE Operator (→)  —  sequential statement chaining
# ═══════════════════════════════════════════════════════════════════════════════

PIPE_2_STAGE = """\
[HLF-v3]
⌘ [ROUTE] agent="coder" priority="high" → ∇ [RESULT] bind="$output"
Ω
"""

PIPE_3_STAGE = """\
[HLF-v3]
⌘ [ROUTE] agent="coder" → ∇ [RESULT] bind="$output" → Ж [ENFORCE] gate="review"
Ω
"""

PIPE_MIXED = """\
[HLF-v3]
⌘ [ROUTE] agent="auditor" → Ж [ENFORCE] check="sql_injection" → Σ [RESULT] output="done"
Ω
"""

PIPE_NO_PIPE = """\
[HLF-v3]
⌘ [ROUTE] agent="solo"
Ω
"""


def test_pipe_2_stage_compiles():
    result = COMPILER.compile(PIPE_2_STAGE)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert len(stmts) == 2
    assert stmts[0]["kind"] == "glyph_stmt"
    assert stmts[0]["glyph"] == "⌘"
    assert stmts[0]["tag"] == "ROUTE"
    assert stmts[1]["kind"] == "glyph_stmt"
    assert stmts[1]["glyph"] == "∇"
    assert stmts[1]["tag"] == "RESULT"


def test_pipe_3_stage_chain():
    result = COMPILER.compile(PIPE_3_STAGE)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert len(stmts) == 3
    glyphs = [s["glyph"] for s in stmts]
    assert glyphs == ["⌘", "∇", "Ж"]


def test_pipe_mixed_types():
    result = COMPILER.compile(PIPE_MIXED)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert len(stmts) == 3
    assert stmts[0]["glyph"] == "⌘"
    assert stmts[1]["glyph"] == "Ж"
    assert stmts[2]["glyph"] == "Σ"


def test_pipe_no_pipe_still_valid():
    """Statements without pipes should still compile normally."""
    result = COMPILER.compile(PIPE_NO_PIPE)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert len(stmts) == 1
    assert stmts[0]["glyph"] == "⌘"


# ═══════════════════════════════════════════════════════════════════════════════
# Expansion 2: @validate Inline Annotations
# ═══════════════════════════════════════════════════════════════════════════════

VALIDATE_SINGLE = """\
[HLF-v3]
Δ [ACTION] exec="deploy" @validate(schema="deploy.json")
Ω
"""

VALIDATE_MULTI = """\
[HLF-v3]
⌘ [ROUTE] agent="coder" @validate(gate="prod_approval", severity="critical")
Ω
"""

VALIDATE_TOOL = """\
[HLF-v3]
TOOL scanner target="app" @validate(timeout="30")
Ω
"""

VALIDATE_NONE = """\
[HLF-v3]
Ж [ENFORCE] check="injection"
Ω
"""


def test_validate_single_annotation():
    result = COMPILER.compile(VALIDATE_SINGLE)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    # First: original glyph stmt (without validate node), then ENFORCE stmt
    assert stmts[0]["kind"] == "glyph_stmt"
    assert stmts[0]["glyph"] == "Δ"
    assert "validations" not in stmts[0]
    # The validate arg becomes an ENFORCE check
    enforce_stmts = [s for s in stmts if s.get("glyph") == "Ж" and s.get("tag") == "ENFORCE"]
    assert len(enforce_stmts) == 1
    enf_args = enforce_stmts[0]["arguments"]
    check_arg = next(a for a in enf_args if a.get("name") == "check")
    assert check_arg["value"]["value"] == "schema"
    val_arg = next(a for a in enf_args if a.get("name") == "value")
    assert val_arg["value"]["value"] == "deploy.json"


def test_validate_multiple_annotations():
    result = COMPILER.compile(VALIDATE_MULTI)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    # Original glyph + 2 ENFORCE checks
    assert stmts[0]["glyph"] == "⌘"
    enforce_stmts = [s for s in stmts if s.get("glyph") == "Ж" and s.get("tag") == "ENFORCE"]
    assert len(enforce_stmts) == 2
    check_names = []
    for s in enforce_stmts:
        check_names.append(
            next(a["value"]["value"] for a in s["arguments"] if a.get("name") == "check")
        )
    assert "gate" in check_names
    assert "severity" in check_names


def test_validate_on_tool_stmt():
    result = COMPILER.compile(VALIDATE_TOOL)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert stmts[0]["kind"] == "tool_stmt"
    assert stmts[0]["name"] == "scanner"
    enforce_stmts = [s for s in stmts if s.get("glyph") == "Ж" and s.get("tag") == "ENFORCE"]
    assert len(enforce_stmts) == 1


def test_validate_not_present_still_works():
    """Statements without @validate should compile unchanged."""
    result = COMPILER.compile(VALIDATE_NONE)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert len(stmts) == 1
    assert stmts[0]["glyph"] == "Ж"
    assert "validations" not in stmts[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Expansion 3: TEMPLATE Blocks for Reusable Patterns
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATE_DEFINE = """\
[HLF-v3]
TEMPLATE security_review {
    Ж [ENFORCE] check="sql_injection"
    Ж [ENFORCE] check="xss"
}
Ω
"""

TEMPLATE_REF = """\
[HLF-v3]
TEMPLATE security_review {
    Ж [ENFORCE] check="sql_injection"
    Ж [ENFORCE] check="xss"
}
⌘ [ROUTE] agent="auditor" ref="security_review"
Ω
"""

TEMPLATE_UNDEFINED = """\
[HLF-v3]
⌘ [ROUTE] agent="auditor" ref="nonexistent"
Ω
"""

TEMPLATE_MULTI_REF = """\
[HLF-v3]
TEMPLATE checks {
    Ж [ENFORCE] check="auth_bypass"
}
⌘ [ROUTE] agent="scanner" ref="checks"
Δ [ACTION] exec="scan" ref="checks"
Ω
"""

TEMPLATE_AFTER_REF = """\
[HLF-v3]
⌘ [ROUTE] agent="auditor" ref="security_review"
TEMPLATE security_review {
    Ж [ENFORCE] check="sql_injection"
}
Ω
"""


def test_template_definition_compiles():
    """Template definition should compile and be extracted from statements."""
    result = COMPILER.compile(TEMPLATE_DEFINE)
    assert result["errors"] == []
    # Template is extracted from statement list
    stmts = result["ast"]["statements"]
    template_stmts = [s for s in stmts if s.get("kind") == "template_stmt"]
    assert len(template_stmts) == 0  # extracted by compiler pass
    # The template registry should contain it (accessible via _template_registry)
    assert "security_review" in COMPILER._template_registry


def test_template_reference_expands():
    """ref='template_name' should inline the template body."""
    result = COMPILER.compile(TEMPLATE_REF)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    # Should have: glyph_stmt (the referencing statement) + 2 ENFORCE from template
    assert len(stmts) >= 3
    # First stmt is the referencing glyph
    assert stmts[0]["kind"] == "glyph_stmt"
    assert stmts[0]["glyph"] == "⌘"
    # Template body inlined after
    enforce_stmts = [s for s in stmts if s.get("glyph") == "Ж"]
    assert len(enforce_stmts) == 2


def test_template_undefined_raises():
    """Reference to undefined template should produce clear error."""
    with pytest.raises(CompileError, match="Undefined template reference"):
        COMPILER.compile(TEMPLATE_UNDEFINED)


def test_template_multiple_references():
    """Multiple statements can reference the same template."""
    result = COMPILER.compile(TEMPLATE_MULTI_REF)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    # 2 referencing glyphs + 2 inlined ENFORCE blocks
    enforce_stmts = [s for s in stmts if s.get("glyph") == "Ж"]
    assert len(enforce_stmts) == 2  # one per reference


def test_template_after_reference_still_works():
    """Two-pass compilation: template defined after reference should still expand."""
    result = COMPILER.compile(TEMPLATE_AFTER_REF)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    enforce_stmts = [s for s in stmts if s.get("glyph") == "Ж"]
    assert len(enforce_stmts) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: Prose Bridge (§), Aesthetic Modulation (~), Negative Constraint (⊖)
#          Exponentiation, Bitwise, List Literals, Pattern Matching
# ═══════════════════════════════════════════════════════════════════════════════

PROSE_BRIDGE = """\
[HLF-v3]
"some expression" § "verify output matches expected schema"
Ω
"""

PROSE_BRIDGE_EXPR = """\
[HLF-v3]
my_var § "the answer to everything"
Ω
"""

AESTHETIC_STMT = """\
[HLF-v3]
output_data ~ pretty
Ω
"""

AESTHETIC_STRING = """\
[HLF-v3]
output_data ~ "compressed"
Ω
"""

NEGATE_CONSTRAINT = """\
[HLF-v3]
⊖ Ж [CONSTRAINT] mode="write"
Ω
"""

EXPONENTIATION = """\
[HLF-v3]
ASSIGN result = 2 ^ 3
Ω
"""

EXPONENT_RIGHT_ASSOC = """\
[HLF-v3]
ASSIGN result = 2 ^ 3 ^ 2
Ω
"""

BITWISE_AND = """\
[HLF-v3]
ASSIGN mask = flags & 255
Ω
"""

BITWISE_OR = """\
[HLF-v3]
ASSIGN combined = a | b
Ω
"""

BITWISE_XOR = """\
[HLF-v3]
ASSIGN xored = x ⊕ y
Ω
"""

BITWISE_MIXED = """\
[HLF-v3]
ASSIGN result = a & b | c ⊕ d
Ω
"""

LIST_LITERAL_SRC = """\
[HLF-v3]
ASSIGN items = ⟨1, 2, 3⟩
Ω
"""

LIST_LITERAL_SINGLE = """\
[HLF-v3]
ASSIGN item = ⟨42⟩
Ω
"""

LIST_LITERAL_MIXED = """\
[HLF-v3]
ASSIGN mixed = ⟨1, "hello", true⟩
Ω
"""

PATTERN_MATCH = """\
[HLF-v3]
ASSIGN result = MATCH status {
  "ok" => 0,
  "error" => 1
}
Ω
"""

PATTERN_MATCH_INT = """\
[HLF-v3]
ASSIGN result = MATCH code {
  200 => "success",
  404 => "not_found",
  500 => "server_error"
}
Ω
"""

PATTERN_MATCH_IDENT = """\
[HLF-v3]
ASSIGN result = MATCH value {
  something => "found",
  other => "fallback"
}
Ω
"""


# ── Prose Bridge (§) ──────────────────────────────────────────────────────────

def test_prose_bridge_parse():
    result = COMPILER.compile(PROSE_BRIDGE)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert stmts[0]["kind"] == "prose_stmt"
    assert stmts[0]["prose"] == "verify output matches expected schema"
    assert "human_readable" in stmts[0]


def test_prose_bridge_expr_form():
    result = COMPILER.compile(PROSE_BRIDGE_EXPR)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert stmts[0]["kind"] == "prose_stmt"
    assert "the answer to everything" in stmts[0]["prose"]


# ── Aesthetic Modulation (~) ──────────────────────────────────────────────────

def test_aesthetic_ident_qualifier():
    result = COMPILER.compile(AESTHETIC_STMT)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert stmts[0]["kind"] == "aesthetic_stmt"
    modifier = stmts[0]["modifier"]
    assert modifier["kind"] == "qualifier"
    assert modifier["type"] == "ident"
    assert modifier["value"] == "pretty"


def test_aesthetic_string_qualifier():
    result = COMPILER.compile(AESTHETIC_STRING)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert stmts[0]["kind"] == "aesthetic_stmt"
    modifier = stmts[0]["modifier"]
    assert modifier["kind"] == "qualifier"
    assert modifier["type"] == "string"
    assert modifier["value"] == "compressed"


# ── Negative Constraint (⊖) ───────────────────────────────────────────────────

def test_negate_constraint_parse():
    result = COMPILER.compile(NEGATE_CONSTRAINT)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    assert stmts[0]["kind"] == "negate_stmt"
    body = stmts[0]["body"]
    assert body["kind"] == "glyph_stmt"
    assert body["glyph"] == "Ж"
    assert body["tag"] == "CONSTRAINT"


# ── Exponentiation (^) ────────────────────────────────────────────────────────

def test_exponentiation():
    result = COMPILER.compile(EXPONENTIATION)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "binop"
    assert expr["op"] == "^"
    assert expr["left"]["value"] == 2
    assert expr["right"]["value"] == 3


def test_exponentiation_right_associative():
    result = COMPILER.compile(EXPONENT_RIGHT_ASSOC)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "binop"
    assert expr["op"] == "^"
    assert expr["left"]["value"] == 2
    # Right-assoc: 2 ^ (3 ^ 2) → right is (3 ^ 2)
    assert expr["right"]["kind"] == "binop"
    assert expr["right"]["op"] == "^"
    assert expr["right"]["left"]["value"] == 3
    assert expr["right"]["right"]["value"] == 2


# ── Bitwise Operations (&, |, ^) ──────────────────────────────────────────────

def test_bitwise_and():
    result = COMPILER.compile(BITWISE_AND)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "binop"
    assert expr["op"] == "&"


def test_bitwise_or():
    result = COMPILER.compile(BITWISE_OR)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "binop"
    assert expr["op"] == "|"


def test_bitwise_xor():
    result = COMPILER.compile(BITWISE_XOR)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "binop"
    assert expr["op"] == "⊕"


def test_bitwise_mixed_operators():
    result = COMPILER.compile(BITWISE_MIXED)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    # a & b | c ⊕ d  → left-assoc: ((a & b) | c) ⊕ d
    assert expr["kind"] == "binop"
    assert expr["op"] == "⊕"


# ── List Literals ⟨…⟩ ────────────────────────────────────────────────────────

def test_list_literal_multi():
    result = COMPILER.compile(LIST_LITERAL_SRC)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "list_literal"
    elements = expr["elements"]
    assert len(elements) == 3
    assert elements[0]["value"] == 1
    assert elements[1]["value"] == 2
    assert elements[2]["value"] == 3


def test_list_literal_single():
    result = COMPILER.compile(LIST_LITERAL_SINGLE)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "list_literal"
    assert len(expr["elements"]) == 1
    assert expr["elements"][0]["value"] == 42


def test_list_literal_mixed_types():
    result = COMPILER.compile(LIST_LITERAL_MIXED)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "list_literal"
    elements = expr["elements"]
    assert len(elements) == 3
    assert elements[0]["type"] == "int"
    assert elements[1]["type"] == "string"
    assert elements[2]["type"] == "ident"


# ── Pattern Matching ──────────────────────────────────────────────────────────

def test_pattern_match_string():
    result = COMPILER.compile(PATTERN_MATCH)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    expr = stmts[0]["expr"]
    assert expr["kind"] == "match_expr"
    assert expr["subject"]["kind"] == "value"
    arms = expr["arms"]
    assert len(arms) == 2
    assert arms[0]["kind"] == "match_arm"
    assert arms[0]["pattern"]["type"] == "string"
    assert arms[0]["pattern"]["value"] == "ok"
    assert arms[0]["body"]["value"] == 0
    assert arms[1]["pattern"]["value"] == "error"
    assert arms[1]["body"]["value"] == 1


def test_pattern_match_int():
    result = COMPILER.compile(PATTERN_MATCH_INT)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    arms = stmts[0]["expr"]["arms"]
    assert len(arms) == 3
    assert arms[0]["pattern"]["type"] == "int"
    assert arms[0]["pattern"]["value"] == 200
    assert arms[1]["pattern"]["value"] == 404
    assert arms[2]["pattern"]["value"] == 500


def test_pattern_match_ident():
    result = COMPILER.compile(PATTERN_MATCH_IDENT)
    assert result["errors"] == []
    stmts = result["ast"]["statements"]
    arms = stmts[0]["expr"]["arms"]
    assert len(arms) == 2
    assert arms[0]["pattern"]["type"] == "ident"
    assert arms[0]["pattern"]["value"] == "something"
    assert arms[1]["pattern"]["value"] == "other"
