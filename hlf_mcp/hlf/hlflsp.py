"""HLF Language Server Protocol surface for packaged HLF tooling."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import re
from pathlib import Path
from typing import Any

from lsprotocol import types as lsp

try:
    from pygls.lsp.server import LanguageServer
except ImportError:  # pragma: no cover - compatibility fallback
    from pygls.server import LanguageServer

from hlf_mcp.hlf.compiler import CompileError, HLFCompiler
from hlf_mcp.hlf.grammar import GLYPHS, TAGS
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.registry import HostFunctionRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAG_PATTERN = re.compile(r"\[([A-Z_][A-Z0-9_]*)\]")
VAR_PATTERN = re.compile(r"\$\{?(\w+)\}?")
LEGACY_SET_PATTERN = re.compile(r"^\s*\[SET\]\s+(\w+)\s*=?\s*(.*)$")
MODERN_SET_PATTERN = re.compile(r"^\s*SET\s+(\w+)\s*=\s*(.*)$")
IMPORT_PATTERN = re.compile(r"^\s*(?:\[IMPORT\]|IMPORT)\s+([\w\-./]+)")
CALL_PATTERN = re.compile(r"^\s*(?:\[CALL\]|CALL)\s+(\w+)")
FUNCTION_PATTERN = re.compile(r"^\s*(?:\[FUNCTION\]|FUNCTION)\s+(\w+)")
MODULE_PATTERN = re.compile(r"^\s*(?:\[MODULE\]|MODULE)\s+(\w+)")
HLF_HEADER_PATTERN = re.compile(r"\[HLF-v\d+(?:\.\d+)*\]")


def _load_dictionary() -> dict[str, Any]:
    path = PROJECT_ROOT / "governance" / "templates" / "dictionary.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"tags": [], "glyphs": {}}


def _load_stdlib_modules() -> list[dict[str, Any]]:
    import hlf_mcp.hlf.stdlib as stdlib_pkg

    modules: list[dict[str, Any]] = []
    for module_info in sorted(pkgutil.iter_modules(stdlib_pkg.__path__), key=lambda item: item.name):
        if module_info.name.startswith("__"):
            continue
        full_name = f"{stdlib_pkg.__name__}.{module_info.name}"
        module = importlib.import_module(full_name)
        exported = [
            name
            for name, value in inspect.getmembers(module, inspect.isfunction)
            if value.__module__ == full_name and not name.startswith("_")
        ]
        modules.append(
            {
                "name": module_info.name.removesuffix("_mod"),
                "python_module": module_info.name,
                "path": Path(module.__file__).resolve(),
                "functions": exported,
            }
        )
    return modules


def _looks_legacy_only(source: str) -> bool:
    lines = [line.strip() for line in source.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        return False
    if any(any(glyph in line for glyph in GLYPHS) for line in lines):
        return False
    legacy_markers = sum(1 for line in lines if line.startswith("["))
    return legacy_markers >= max(1, len(lines) - 2)


def _extract_set_bindings(source: str) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for line in source.splitlines():
        legacy = LEGACY_SET_PATTERN.match(line)
        modern = MODERN_SET_PATTERN.match(line)
        match = legacy or modern
        if match:
            bindings[match.group(1)] = match.group(2).strip() or "<unset>"
    return bindings


def _tag_description(tag_name: str, spec: dict[str, Any] | None) -> str:
    if spec:
        args = spec.get("args", [])
        pieces = []
        if args:
            pieces.append(
                "Args: " + ", ".join(
                    f"{arg['name']}:{arg.get('type', 'any')}{'[]' if arg.get('repeat') else ''}"
                    for arg in args
                )
            )
        for trait in ("pure", "immutable", "terminator", "macro"):
            if spec.get(trait):
                pieces.append(trait)
        return " | ".join(pieces) if pieces else "Canonical HLF tag"
    description = TAGS.get(tag_name)
    return description or "Canonical HLF tag"


class HLFLanguageServer(LanguageServer):
    """Language Server for packaged HLF editor support."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dictionary = _load_dictionary()
        self.tag_specs = {tag["name"]: tag for tag in self.dictionary.get("tags", [])}
        self.glyph_specs = self.dictionary.get("glyphs", {})
        self.host_functions = HostFunctionRegistry().list_all()
        self.stdlib_modules = _load_stdlib_modules()

    def _build_diagnostics(self, source: str, uri: str) -> list[lsp.Diagnostic]:
        diagnostics: list[lsp.Diagnostic] = []

        if not HLF_HEADER_PATTERN.search(source):
            diagnostics.append(_diag("Missing HLF header [HLF-vN]", severity=lsp.DiagnosticSeverity.Error))
        if "Ω" not in source and "Omega" not in source:
            diagnostics.append(_diag("Missing terminator Ω", severity=lsp.DiagnosticSeverity.Error))

        bindings = _extract_set_bindings(source)
        for var_name, value in bindings.items():
            if f"${{{var_name}}}" not in source and f"${var_name}" not in source:
                diagnostics.append(
                    _diag(
                        f"UNUSED_VAR {var_name}: binding is never referenced",
                        severity=lsp.DiagnosticSeverity.Hint,
                    )
                )

        if not _looks_legacy_only(source):
            try:
                issues = HLFLinter().lint(source)
                for issue in issues:
                    severity = {
                        "error": lsp.DiagnosticSeverity.Error,
                        "warning": lsp.DiagnosticSeverity.Warning,
                        "info": lsp.DiagnosticSeverity.Information,
                    }.get(issue["level"], lsp.DiagnosticSeverity.Information)
                    diagnostics.append(
                        _diag(
                            issue["message"],
                            line=max(issue["line"] - 1, 0) if issue["line"] else 0,
                            severity=severity,
                            source="hlflint",
                        )
                    )
            except Exception as exc:  # pragma: no cover - defensive
                diagnostics.append(_diag(f"Linter failed: {exc}", source="hlflint"))

            try:
                HLFCompiler().compile(source)
            except CompileError as exc:
                diagnostics.append(
                    _diag(
                        f"Syntax error: {exc}",
                        line=max(getattr(exc, "line", 1) - 1, 0),
                        severity=lsp.DiagnosticSeverity.Error,
                        source="hlfc",
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive
                diagnostics.append(_diag(f"Syntax error: {exc}", severity=lsp.DiagnosticSeverity.Error, source="hlfc"))

        return diagnostics

    def get_completions(self, source: str, position: lsp.Position) -> list[lsp.CompletionItem]:
        lines = source.splitlines() or [""]
        line_text = lines[position.line] if position.line < len(lines) else ""
        prefix = line_text[:position.character]
        items: list[lsp.CompletionItem] = []

        if prefix.endswith("[") or re.fullmatch(r"\[?[A-Z_]*", prefix.strip()):
            for tag_name, spec in sorted(self.tag_specs.items()):
                items.append(
                    lsp.CompletionItem(
                        label=f"[{tag_name}]",
                        kind=lsp.CompletionItemKind.Keyword,
                        detail=_tag_description(tag_name, spec),
                        documentation=lsp.MarkupContent(
                            kind=lsp.MarkupKind.Markdown,
                            value=f"**[{tag_name}]**\n\n{_tag_description(tag_name, spec)}",
                        ),
                        insert_text=f"[{tag_name}] ",
                    )
                )

        for glyph, info in GLYPHS.items():
            items.append(
                lsp.CompletionItem(
                    label=glyph,
                    kind=lsp.CompletionItemKind.Operator,
                    detail=info.get("name", glyph),
                    documentation=lsp.MarkupContent(
                        kind=lsp.MarkupKind.Markdown,
                        value=f"**{glyph} — {info.get('name', glyph)}**\n\nRole: {info.get('role', '')}",
                    ),
                )
            )

        if "IMPORT" in prefix or "[IMPORT]" in prefix:
            for module in self.stdlib_modules:
                items.append(
                    lsp.CompletionItem(
                        label=module["name"],
                        kind=lsp.CompletionItemKind.Module,
                        detail=f"stdlib module: {module['name']}",
                    )
                )

        if "TOOL" in prefix or "τ" in prefix or "[TOOL]" in prefix:
            for host_function in self.host_functions:
                args_text = ", ".join(
                    f"{arg['name']}:{arg.get('type', 'any')}" for arg in host_function.get("args", [])
                )
                items.append(
                    lsp.CompletionItem(
                        label=host_function["name"],
                        kind=lsp.CompletionItemKind.Function,
                        detail=f"({args_text}) -> {host_function.get('returns', 'any')} [gas: {host_function.get('gas', 1)}]",
                    )
                )

        variable_trigger_index = line_text.rfind("${", 0, max(position.character, 0) + 1)
        if "${" in prefix or prefix.endswith("$") or variable_trigger_index >= 0 or "${" in line_text:
            for var_name, value in _extract_set_bindings(source).items():
                items.append(
                    lsp.CompletionItem(
                        label=f"${{{var_name}}}",
                        kind=lsp.CompletionItemKind.Variable,
                        detail=f"= {value}",
                        insert_text=f"{var_name}}}",
                    )
                )

        return items

    def get_hover(self, source: str, position: lsp.Position) -> lsp.Hover | None:
        lines = source.splitlines()
        if position.line >= len(lines):
            return None
        line_text = lines[position.line]

        for match in TAG_PATTERN.finditer(line_text):
            if match.start() <= position.character <= match.end():
                tag_name = match.group(1)
                spec = self.tag_specs.get(tag_name)
                return lsp.Hover(
                    contents=lsp.MarkupContent(
                        kind=lsp.MarkupKind.Markdown,
                        value=f"### [{tag_name}]\n\n{_tag_description(tag_name, spec)}",
                    ),
                    range=_range(position.line, match.start(), match.end()),
                )

        for glyph, info in GLYPHS.items():
            idx = line_text.find(glyph)
            if idx >= 0 and idx <= position.character <= idx + len(glyph):
                return lsp.Hover(
                    contents=lsp.MarkupContent(
                        kind=lsp.MarkupKind.Markdown,
                        value=f"### {glyph} — {info.get('name', glyph)}\n\nRole: {info.get('role', '')}",
                    ),
                    range=_range(position.line, idx, idx + len(glyph)),
                )

        for match in re.finditer(r"\$\{(\w+)\}", line_text):
            if match.start() <= position.character <= match.end():
                var_name = match.group(1)
                bindings = _extract_set_bindings(source)
                if var_name in bindings:
                    return lsp.Hover(
                        contents=lsp.MarkupContent(
                            kind=lsp.MarkupKind.Markdown,
                            value=f"### ${{{var_name}}}\n\n**Value:** `{bindings[var_name]}`",
                        ),
                        range=_range(position.line, match.start(), match.end()),
                    )
        return None

    def get_definition(self, source: str, uri: str, position: lsp.Position) -> lsp.Location | None:
        lines = source.splitlines()
        if position.line >= len(lines):
            return None
        line_text = lines[position.line]

        for match in re.finditer(r"\$\{(\w+)\}", line_text):
            if match.start() <= position.character <= match.end():
                var_name = match.group(1)
                for line_number, source_line in enumerate(lines):
                    set_match = LEGACY_SET_PATTERN.match(source_line) or MODERN_SET_PATTERN.match(source_line)
                    if set_match and set_match.group(1) == var_name:
                        start = source_line.find(var_name)
                        return lsp.Location(uri=uri, range=_range(line_number, start, start + len(var_name)))

        import_match = IMPORT_PATTERN.match(line_text)
        if import_match:
            module_name = import_match.group(1)
            for module in self.stdlib_modules:
                if module["name"] == module_name:
                    return lsp.Location(uri=module["path"].as_uri(), range=_range(0, 0, 0))
            local_path = Path(uri.replace("file://", "")).parent / f"{module_name}.hlf"
            if local_path.exists():
                return lsp.Location(uri=local_path.as_uri(), range=_range(0, 0, 0))

        call_match = CALL_PATTERN.match(line_text)
        if call_match:
            function_name = call_match.group(1)
            for line_number, source_line in enumerate(lines):
                function_match = FUNCTION_PATTERN.match(source_line)
                if function_match and function_match.group(1) == function_name:
                    start = source_line.find(function_name)
                    return lsp.Location(uri=uri, range=_range(line_number, start, start + len(function_name)))
        return None

    def get_symbols(self, source: str) -> list[lsp.DocumentSymbol]:
        symbols: list[lsp.DocumentSymbol] = []
        for line_number, line_text in enumerate(source.splitlines()):
            set_match = LEGACY_SET_PATTERN.match(line_text) or MODERN_SET_PATTERN.match(line_text)
            if set_match:
                name = set_match.group(1)
                symbols.append(
                    lsp.DocumentSymbol(
                        name=name,
                        kind=lsp.SymbolKind.Variable,
                        detail=f"= {set_match.group(2).strip() or '?'}",
                        range=_range(line_number, 0, len(line_text)),
                        selection_range=_range(line_number, line_text.find(name), line_text.find(name) + len(name)),
                    )
                )

            function_match = FUNCTION_PATTERN.match(line_text)
            if function_match:
                name = function_match.group(1)
                start = line_text.find(name)
                symbols.append(
                    lsp.DocumentSymbol(
                        name=name,
                        kind=lsp.SymbolKind.Function,
                        range=_range(line_number, 0, len(line_text)),
                        selection_range=_range(line_number, start, start + len(name)),
                    )
                )

            import_match = IMPORT_PATTERN.match(line_text)
            if import_match:
                name = import_match.group(1)
                start = line_text.find(name)
                symbols.append(
                    lsp.DocumentSymbol(
                        name=name,
                        kind=lsp.SymbolKind.Package,
                        detail="module import",
                        range=_range(line_number, 0, len(line_text)),
                        selection_range=_range(line_number, start, start + len(name)),
                    )
                )

            module_match = MODULE_PATTERN.match(line_text)
            if module_match:
                name = module_match.group(1)
                start = line_text.find(name)
                symbols.append(
                    lsp.DocumentSymbol(
                        name=name,
                        kind=lsp.SymbolKind.Module,
                        range=_range(line_number, 0, len(line_text)),
                        selection_range=_range(line_number, start, start + len(name)),
                    )
                )
        return symbols


def _range(line: int, start: int, end: int) -> lsp.Range:
    return lsp.Range(
        start=lsp.Position(line=line, character=start),
        end=lsp.Position(line=line, character=end),
    )


def _diag(
    message: str,
    *,
    line: int = 0,
    severity: lsp.DiagnosticSeverity = lsp.DiagnosticSeverity.Information,
    source: str = "hlflsp",
) -> lsp.Diagnostic:
    return lsp.Diagnostic(
        range=_range(line, 0, 1000),
        message=message,
        severity=severity,
        source=source,
    )


_server = HLFLanguageServer("hlf-lsp", "v0.1.0")


@_server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
    doc = params.text_document
    _server.publish_diagnostics(doc.uri, _server._build_diagnostics(doc.text, doc.uri))


@_server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(params: lsp.DidChangeTextDocumentParams) -> None:
    doc = _server.workspace.get_text_document(params.text_document.uri)
    _server.publish_diagnostics(doc.uri, _server._build_diagnostics(doc.source, doc.uri))


@_server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    doc = _server.workspace.get_text_document(params.text_document.uri)
    _server.publish_diagnostics(doc.uri, _server._build_diagnostics(doc.source, doc.uri))


@_server.feature(lsp.TEXT_DOCUMENT_COMPLETION)
def completions(params: lsp.CompletionParams) -> lsp.CompletionList:
    doc = _server.workspace.get_text_document(params.text_document.uri)
    return lsp.CompletionList(is_incomplete=False, items=_server.get_completions(doc.source, params.position))


@_server.feature(lsp.TEXT_DOCUMENT_HOVER)
def hover(params: lsp.HoverParams) -> lsp.Hover | None:
    doc = _server.workspace.get_text_document(params.text_document.uri)
    return _server.get_hover(doc.source, params.position)


@_server.feature(lsp.TEXT_DOCUMENT_DEFINITION)
def definition(params: lsp.DefinitionParams) -> lsp.Location | None:
    doc = _server.workspace.get_text_document(params.text_document.uri)
    return _server.get_definition(doc.source, doc.uri, params.position)


@_server.feature(lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def document_symbol(params: lsp.DocumentSymbolParams) -> list[lsp.DocumentSymbol]:
    doc = _server.workspace.get_text_document(params.text_document.uri)
    return _server.get_symbols(doc.source)


def main() -> None:
    parser = argparse.ArgumentParser(description="HLF Language Server")
    parser.add_argument("--tcp", type=int, help="Run in TCP mode on the given port")
    parser.add_argument("--host", default="127.0.0.1", help="TCP host")
    args = parser.parse_args()

    if args.tcp:
        _server.start_tcp(args.host, args.tcp)
    else:
        _server.start_io()


__all__ = ["HLFLanguageServer", "_extract_set_bindings", "main"]