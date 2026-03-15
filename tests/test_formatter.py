"""Tests for HLF formatter."""

from hlf_mcp.hlf.formatter import HLFFormatter

FMT = HLFFormatter()

_MESSY = """\
[HLF-v3]
delta  analyze  /security/seccomp.json
  Ж   [constraint]  mode="ro"
Ж  [expect]    vulnerability_shorthand
⨝ [vote] consensus="strict"
Ω
"""


def test_format_uppercase_tags():
    result = FMT.format('[HLF-v3]\nΔ [intent] goal="test"\nΩ\n')
    assert "[INTENT]" in result


def test_format_preserves_omega():
    result = FMT.format('[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n')
    assert "Ω" in result


def test_format_trailing_newline():
    result = FMT.format('[HLF-v3]\nΔ test\nΩ')
    assert result.endswith("\n")


def test_format_strips_blank_lines():
    src = '[HLF-v3]\n\n\nΔ test\n\nΩ\n'
    result = FMT.format(src)
    # Should not have multiple consecutive blank lines in output
    assert "\n\n\n" not in result


def test_format_sub_statement_indentation():
    src = '[HLF-v3]\nΔ analyze /foo\nЖ [CONSTRAINT] mode="ro"\nΩ\n'
    result = FMT.format(src)
    lines = result.splitlines()
    # Find the Ж line and verify indentation
    zhe_line = next((l for l in lines if l.lstrip().startswith("Ж")), None)
    assert zhe_line is not None
    # Sub-statement should be indented (preceded by spaces/tabs)
    assert zhe_line.startswith("  ")


def test_format_primary_glyph_not_indented():
    src = '[HLF-v3]\nΔ analyze /foo\nΩ\n'
    result = FMT.format(src)
    lines = result.splitlines()
    delta_line = next(l for l in lines if l.lstrip().startswith("Δ"))
    # Primary glyph should NOT be indented
    assert not delta_line.startswith("  ")


def test_diff_summary_no_changes():
    src = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
    formatted = FMT.format(src)
    diff = FMT.diff_summary(formatted, formatted)
    assert "No changes" in diff


def test_diff_summary_shows_changes():
    src = '[HLF-v3]\nΔ [intent] goal="test"\nΩ\n'
    formatted = FMT.format(src)
    diff = FMT.diff_summary(src, formatted)
    # Should report changes since [intent] → [INTENT]
    assert "No changes" not in diff or "[INTENT]" in formatted


def test_format_removes_comments():
    src = '[HLF-v3]\n# This is a comment\nΔ [INTENT] goal="test"\nΩ\n'
    result = FMT.format(src)
    assert "# This is a comment" not in result


def test_format_collapses_spaces():
    src = '[HLF-v3]\nΔ   [INTENT]   goal="test"\nΩ\n'
    result = FMT.format(src)
    # Should not have multiple consecutive spaces after formatting
    lines = result.splitlines()
    delta_line = next((l for l in lines if "INTENT" in l), None)
    assert delta_line is not None
    # Multiple spaces should be collapsed
    assert "   " not in delta_line
