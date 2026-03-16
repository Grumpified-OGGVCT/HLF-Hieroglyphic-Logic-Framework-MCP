#!/usr/bin/env python3
"""Generate lightweight reference docs from packaged HLF assets."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import pkgutil
from pathlib import Path
from typing import Any


def load_dictionary(dict_path: Path) -> dict[str, Any]:
    return json.loads(dict_path.read_text(encoding="utf-8"))


def collect_stdlib_symbols() -> list[dict[str, Any]]:
    import hlf_mcp.hlf.stdlib as stdlib_pkg

    modules: list[dict[str, Any]] = []
    for module_info in sorted(pkgutil.iter_modules(stdlib_pkg.__path__), key=lambda item: item.name):
        if module_info.name.startswith("__"):
            continue
        full_name = f"{stdlib_pkg.__name__}.{module_info.name}"
        module = importlib.import_module(full_name)
        functions = []
        for name, value in inspect.getmembers(module, inspect.isfunction):
            if value.__module__ != full_name or name.startswith("_"):
                continue
            signature = str(inspect.signature(value))
            functions.append({"name": name, "signature": signature})
        modules.append(
            {
                "module": module_info.name.removesuffix("_mod"),
                "python_module": module_info.name,
                "doc": inspect.getdoc(module) or "",
                "functions": functions,
            }
        )
    return modules


def render_tag_reference(dictionary: dict[str, Any]) -> str:
    lines = [
        "# HLF Tag Reference",
        "",
        f"Generated from `governance/templates/dictionary.json` (version {dictionary.get('version', 'unknown')}).",
        "",
        "| Tag | Arity | Arguments | Traits |",
        "| --- | --- | --- | --- |",
    ]
    for tag in dictionary.get("tags", []):
        args = tag.get("args", [])
        arity = str(len(args))
        if any(arg.get("repeat") for arg in args):
            arity += "+"
        arg_text = ", ".join(
            f"{arg['name']}:{arg['type']}{'[]' if arg.get('repeat') else ''}" for arg in args
        ) or "-"
        traits = []
        for trait in ("pure", "immutable", "terminator", "macro"):
            if tag.get(trait):
                traits.append(trait)
        lines.append(f"| `{tag['name']}` | {arity} | `{arg_text}` | {', '.join(traits) or '-'} |")
    return "\n".join(lines) + "\n"


def render_stdlib_reference(modules: list[dict[str, Any]]) -> str:
    lines = [
        "# HLF Stdlib Reference",
        "",
        "Generated from the packaged Python stdlib bindings in `hlf_mcp/hlf/stdlib/`.",
        "",
    ]
    for module in modules:
        lines.append(f"## {module['module']}")
        lines.append("")
        if module["doc"]:
            lines.append(module["doc"])
            lines.append("")
        if not module["functions"]:
            lines.append("No exported callables found.")
            lines.append("")
            continue
        lines.append("| Function | Signature |")
        lines.append("| --- | --- |")
        for function in module["functions"]:
            lines.append(f"| `{function['name']}` | `{function['signature']}` |")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_host_functions_reference(repo_root: Path) -> str:
    spec = importlib.util.spec_from_file_location(
        "hlf_docs_gen_from_spec",
        repo_root / "docs" / "gen_from_spec.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate_host_functions_reference(repo_root / "governance" / "host_functions.json")


def generate_docs(repo_root: Path) -> list[Path]:
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    dictionary = load_dictionary(repo_root / "governance" / "templates" / "dictionary.json")
    modules = collect_stdlib_symbols()

    outputs = {
        docs_dir / "HLF_TAG_REFERENCE.md": render_tag_reference(dictionary),
        docs_dir / "HLF_STDLIB_REFERENCE.md": render_stdlib_reference(modules),
        docs_dir / "HLF_HOST_FUNCTIONS_REFERENCE.md": render_host_functions_reference(repo_root),
    }
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
    return list(outputs)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for output in generate_docs(repo_root):
        print(f"Generated {output}")


if __name__ == "__main__":
    main()