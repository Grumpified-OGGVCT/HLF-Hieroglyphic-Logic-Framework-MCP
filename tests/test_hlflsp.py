from __future__ import annotations

from lsprotocol import types as lsp

from hlf_mcp.hlf.hlflsp import HLFLanguageServer, _extract_set_bindings


def _prog(body: str) -> str:
    return f"[HLF-v3]\n{body}\nΩ\n"


def test_clean_modern_source_has_no_error_diagnostic() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    source = _prog('Δ [INTENT] goal="deploy" target="/app"')
    diags = server._build_diagnostics(source, "file:///test.hlf")
    errors = [diag for diag in diags if diag.severity == lsp.DiagnosticSeverity.Error]
    assert errors == []


def test_invalid_source_produces_error_diagnostic() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    diags = server._build_diagnostics("not valid hlf", "file:///test.hlf")
    assert any(diag.severity == lsp.DiagnosticSeverity.Error for diag in diags)


def test_legacy_set_binding_gets_hint_when_unused() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    source = _prog('[SET] unused_var = "hello"')
    diags = server._build_diagnostics(source, "file:///test.hlf")
    assert any(
        diag.severity == lsp.DiagnosticSeverity.Hint and "unused_var" in diag.message
        for diag in diags
    )


def test_tag_completions_include_intent() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    items = server.get_completions("[", lsp.Position(line=0, character=1))
    labels = [item.label for item in items]
    assert "[INTENT]" in labels


def test_import_completion_lists_stdlib_modules() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    items = server.get_completions("IMPORT ", lsp.Position(line=0, character=7))
    modules = [item for item in items if item.kind == lsp.CompletionItemKind.Module]
    assert any(item.label == "math" for item in modules)


def test_variable_completion_uses_set_bindings() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    source = 'SET name = "world"\nΔ [INTENT] goal="greet" target="${'
    items = server.get_completions(source, lsp.Position(line=1, character=31))
    assert any(
        item.kind == lsp.CompletionItemKind.Variable and "name" in item.label for item in items
    )


def test_hover_on_tag_returns_markdown() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    hover = server.get_hover('Δ [INTENT] goal="deploy"', lsp.Position(line=0, character=4))
    assert hover is not None
    assert hover.contents.kind == lsp.MarkupKind.Markdown
    assert "INTENT" in hover.contents.value


def test_hover_on_var_ref_shows_bound_value() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    source = 'SET greeting = "hello"\nΔ [INTENT] goal="greet" target="${greeting}"'
    hover = server.get_hover(source, lsp.Position(line=1, character=36))
    assert hover is not None
    assert "hello" in hover.contents.value


def test_definition_jumps_to_set_binding() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    source = 'SET target = "/deploy"\nΔ [INTENT] goal="go" target="${target}"'
    location = server.get_definition(source, "file:///test.hlf", lsp.Position(line=1, character=33))
    assert location is not None
    assert location.range.start.line == 0


def test_definition_jumps_to_function_binding() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    source = "FUNCTION deploy {}\nCALL deploy"
    location = server.get_definition(source, "file:///test.hlf", lsp.Position(line=1, character=7))
    assert location is not None
    assert location.range.start.line == 0


def test_document_symbols_include_variables_and_functions() -> None:
    server = HLFLanguageServer("test-hlf-lsp", "v0.0.1-test")
    symbols = server.get_symbols("SET port = 8080\nFUNCTION deploy {}\nIMPORT math")
    assert any(
        symbol.kind == lsp.SymbolKind.Variable and symbol.name == "port" for symbol in symbols
    )
    assert any(
        symbol.kind == lsp.SymbolKind.Function and symbol.name == "deploy" for symbol in symbols
    )
    assert any(
        symbol.kind == lsp.SymbolKind.Package and symbol.name == "math" for symbol in symbols
    )


def test_extract_set_bindings_supports_legacy_and_modern_syntax() -> None:
    bindings = _extract_set_bindings('[SET] a = 1\nSET b = "hello"\nΔ [INTENT] goal="noop"')
    assert bindings == {"a": "1", "b": '"hello"'}
