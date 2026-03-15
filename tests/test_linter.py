"""Tests for HLF linter."""

from hlf_mcp.hlf.linter import HLFLinter

LINTER = HLFLinter()


def test_lint_clean_program():
    src = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
    diags = LINTER.lint(src)
    errors = [d for d in diags if d["level"] == "error"]
    assert errors == []


def test_lint_missing_header():
    src = 'Δ [INTENT] goal="test"\nΩ\n'
    diags = LINTER.lint(src)
    errors = [d for d in diags if d["level"] == "error"]
    assert any("header" in d["message"].lower() for d in errors)


def test_lint_missing_terminator():
    src = '[HLF-v3]\nΔ [INTENT] goal="test"\n'
    diags = LINTER.lint(src)
    errors = [d for d in diags if d["level"] == "error"]
    assert any("terminator" in d["message"].lower() or "Ω" in d["message"] for d in errors)


def test_lint_gas_exceeded():
    # Create many statements to exceed gas limit
    stmts = "\n".join(f'MEMORY [key{i}] value="x"' for i in range(30))
    src = f"[HLF-v3]\n{stmts}\nΩ\n"
    diags = LINTER.lint(src, gas_limit=50)
    errors = [d for d in diags if d["level"] == "error"]
    assert any("gas" in d["message"].lower() or "budget" in d["message"].lower() for d in errors)


def test_lint_undefined_variable_warning():
    src = '[HLF-v3]\nΔ [INTENT] tier="$MY_TIER"\nΩ\n'
    diags = LINTER.lint(src)
    warnings = [d for d in diags if d["level"] == "warning"]
    assert any("MY_TIER" in d["message"] for d in warnings)


def test_lint_set_variable_no_warning():
    src = '[HLF-v3]\nSET MY_TIER = "hearth"\nΔ [INTENT] tier="$MY_TIER"\nΩ\n'
    diags = LINTER.lint(src)
    warnings = [d for d in diags if d["level"] == "warning"]
    # MY_TIER is set, so no "undefined variable" warning for it
    assert not any("MY_TIER" in d["message"] for d in warnings)


def test_lint_unused_memory_info():
    src = '[HLF-v3]\nMEMORY [my_key] value="data"\nΔ [INTENT] goal="test"\nΩ\n'
    diags = LINTER.lint(src)
    infos = [d for d in diags if d["level"] == "info"]
    assert any("my_key" in d["message"] for d in infos)


def test_lint_memory_recalled_no_info():
    src = '[HLF-v3]\nMEMORY [my_key] value="data"\nRECALL [my_key]\nΔ test\nΩ\n'
    diags = LINTER.lint(src)
    infos = [d for d in diags if d["level"] == "info"]
    assert not any("my_key" in d["message"] for d in infos)


def test_lint_token_budget_warning():
    # A very long line should trigger token budget warning
    long_line = "Δ " + " ".join(f'arg{i}="value{i}"' for i in range(40))
    src = f"[HLF-v3]\n{long_line}\nΩ\n"
    diags = LINTER.lint(src, token_limit=30)
    warnings = [d for d in diags if d["level"] == "warning"]
    assert any("token" in d["message"].lower() or "budget" in d["message"].lower() for d in warnings)


def test_lint_spec_seal_without_define():
    src = '[HLF-v3]\nSPEC_SEAL [MY_SPEC]\nΔ test\nΩ\n'
    diags = LINTER.lint(src)
    warns = [d for d in diags if d["level"] in ("warning", "error")]
    assert any("MY_SPEC" in d["message"] or "SPEC_SEAL" in d["message"] for d in warns)


def test_lint_passed_clean():
    src = '[HLF-v3]\nΔ [INTENT] goal="ok"\nΩ\n'
    diags = LINTER.lint(src)
    errors = [d for d in diags if d["level"] == "error"]
    assert len(errors) == 0


def test_lint_all_fixtures():
    """All fixture files should lint without errors."""
    import os
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "fixtures")
    for fname in os.listdir(fixtures_dir):
        if not fname.endswith(".hlf"):
            continue
        with open(os.path.join(fixtures_dir, fname)) as f:
            source = f.read()
        diags = LINTER.lint(source)
        errors = [d for d in diags if d["level"] == "error"]
        assert errors == [], f"Fixture {fname} has lint errors: {errors}"
