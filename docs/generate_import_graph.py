#!/usr/bin/env python3
"""Generate a machine-checked import graph for the HLF_MCP codebase.

Walks all .py files, extracts hlf_mcp imports, classifies each file,
and writes import-graph.csv + import-summary.csv.
"""

import ast
import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\gerry\generic_workspace\HLF_MCP")
OUT_DIR = ROOT / "docs"
IMPORT_GRAPH_PATH = OUT_DIR / "import-graph.csv"
IMPORT_SUMMARY_PATH = OUT_DIR / "import-summary.csv"

# Regex for lazy/dynamic imports
LAZY_RE = re.compile(
    r'(?:importlib\.import_module|__import__)\s*\(\s*["\'](hlf_mcp(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)["\']'
)


def is_in_function(node: ast.AST, source_lines: list) -> bool:
    """Heuristic: check if an import node is inside a function body by
    walking back through source lines looking for 'def ' or 'async def '
    with less indentation than the import line."""
    if not hasattr(node, "lineno"):
        return False
    import_line = node.lineno - 1  # zero-indexed
    if import_line <= 0:
        return False

    # Get indentation of the import line
    import_indent = len(source_lines[import_line]) - len(
        source_lines[import_line].lstrip()
    )

    # Walk backwards looking for a 'def ' or 'async def ' at lower indentation
    for i in range(import_line - 1, -1, -1):
        line = source_lines[i].rstrip()
        stripped = line.lstrip()
        line_indent = len(line) - len(stripped)

        # If we hit a line with less indent, check if it's a function def
        if line_indent < import_indent:
            if stripped.startswith("def ") or stripped.startswith("async def "):
                return True
            # If it's a class def, the import is inside a class method
            if stripped.startswith("class "):
                continue
            # Any other lower-indent line means we're not inside a function
            return False

    return False


def extract_imports(file_path: Path, rel_path: str) -> dict:
    """Extract all hlf_mcp imports from a .py file.

    Returns a dict with keys: file_path, total_hlf_imports, imported_modules,
    classification_hint, lazy_imports.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as e:
        print(f"  WARNING: Could not read {file_path}: {e}", file=sys.stderr)
        return None

    source_lines = source.splitlines()
    hlf_imports = set()
    lazy_imports = set()
    has_inline_lazy = False

    # --- Phase 1: AST-based parsing for regular imports ---
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        print(f"  WARNING: Syntax error in {file_path}: {e}", file=sys.stderr)
        # Fall through to lazy-only detection
        tree = None

    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("hlf_mcp.") or alias.name == "hlf_mcp":
                        in_fn = is_in_function(node, source_lines)
                        label = f"{alias.name} [lazy]" if in_fn else alias.name
                        if in_fn:
                            lazy_imports.add(alias.name)
                            has_inline_lazy = True
                        hlf_imports.add(label)

            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module.startswith("hlf_mcp.") or node.module == "hlf_mcp"
                ):
                    in_fn = is_in_function(node, source_lines)
                    if node.level == 0:  # absolute import, not relative
                        for alias in node.names:
                            full = f"{node.module}.{alias.name}" if alias.name != "*" else f"{node.module}.*"
                            label = f"{full} [lazy]" if in_fn else full
                            if in_fn:
                                lazy_imports.add(full)
                                has_inline_lazy = True
                            hlf_imports.add(label)

    # --- Phase 2: Regex for lazy/dynamic imports ---
    for match in LAZY_RE.finditer(source):
        module_name = match.group(1)
        lazy_imports.add(module_name)
        hlf_imports.add(f"{module_name} [lazy]")
        has_inline_lazy = True

    # --- Phase 3: Also catch plain regex for any hlf_mcp mention in import context ---
    # This catches edge cases the AST might miss (e.g., inside try/except)
    for match in re.finditer(
        r'^\s*(?:from|import)\s+(hlf_mcp(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)',
        source,
        re.MULTILINE,
    ):
        module_name = match.group(1)
        # Check if already captured by AST
        already = any(module_name in imp for imp in hlf_imports)
        if not already:
            stripped = source_lines[match.string[:match.start()].count("\n")].strip()
            if not stripped.startswith("#"):
                hlf_imports.add(module_name)

    if not hlf_imports:
        return None

    # Classification
    total = len(hlf_imports)
    is_test = "tests" in rel_path.replace("\\", "/").split("/") or file_path.stem.startswith("test_")
    is_init = file_path.name == "__init__.py"

    if is_test:
        classification = "TEST"
    elif is_init and total >= 5:
        classification = "INIT_REEXPORT"
    elif total == 0:
        classification = "KEEP"
    elif 1 <= total <= 3:
        classification = "KEEP_WITH_WORK"
    else:
        classification = "LEAVE"

    return {
        "file_path": rel_path,
        "total_hlf_imports": total,
        "imported_modules": ", ".join(sorted(hlf_imports)),
        "classification_hint": classification,
    }


def main():
    print(f"Scanning: {ROOT}")
    if not ROOT.exists():
        print(f"ERROR: {ROOT} does not exist!", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all .py files
    all_py_files = list(ROOT.rglob("*.py"))
    print(f"Found {len(all_py_files)} .py files total")

    # Filter: only process files that could have hlf_mcp imports
    # First, quick grep pre-filter for performance (optional)
    results = []
    files_scanned = 0
    files_with_imports = 0
    all_imported_modules = Counter()

    for py_file in all_py_files:
        try:
            rel = py_file.relative_to(ROOT)
        except ValueError:
            rel = py_file
        rel_str = str(rel).replace("\\", "/")
        files_scanned += 1

        result = extract_imports(py_file, rel_str)
        if result is not None:
            results.append(result)
            files_with_imports += 1
            # Count individual modules (strip [lazy] suffix for counting)
            for mod in result["imported_modules"].split(", "):
                clean_mod = mod.replace(" [lazy]", "")
                all_imported_modules[clean_mod] += 1

        if files_scanned % 2000 == 0:
            print(f"  Processed {files_scanned}/{len(all_py_files)} files...")

    print(f"Done. Scanned {files_scanned} files, {files_with_imports} have hlf_mcp imports.")

    # Sort results: higher import counts first, then alphabetically
    results.sort(key=lambda r: (-r["total_hlf_imports"], r["file_path"]))

    # --- Write import-graph.csv ---
    fieldnames = ["file_path", "total_hlf_imports", "imported_modules", "classification_hint"]
    with open(IMPORT_GRAPH_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\nWrote {len(results)} rows to {IMPORT_GRAPH_PATH}")

    # Also write files with ZERO imports as KEEP entries
    files_without_imports = files_scanned - files_with_imports
    print(f"Files with zero hlf_mcp imports (classified KEEP): {files_without_imports}")

    # --- Compute summary ---
    classification_counts = Counter(r["classification_hint"] for r in results)
    # Add KEEP for zero-import files
    classification_counts["KEEP"] = classification_counts.get("KEEP", 0) + files_without_imports

    top_imported = all_imported_modules.most_common(20)
    top_files = [(r["file_path"], r["total_hlf_imports"]) for r in results[:20]]

    # --- Write import-summary.csv ---
    with open(IMPORT_SUMMARY_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total files scanned", files_scanned])
        writer.writerow(["Files with hlf_mcp imports", files_with_imports])
        writer.writerow(["Files without hlf_mcp imports (KEEP)", files_without_imports])
        writer.writerow([])

        writer.writerow(["Classification", "Count"])
        for cls in ["KEEP", "KEEP_WITH_WORK", "LEAVE", "TEST", "INIT_REEXPORT"]:
            writer.writerow([cls, classification_counts.get(cls, 0)])
        writer.writerow([])

        writer.writerow(["Rank", "Module", "Import Count"])
        for rank, (mod, count) in enumerate(top_imported, 1):
            writer.writerow([rank, mod, count])
        writer.writerow([])

        writer.writerow(["Rank", "File", "Import Count"])
        for rank, (fp, count) in enumerate(top_files, 1):
            writer.writerow([rank, fp, count])

    print(f"Wrote summary to {IMPORT_SUMMARY_PATH}")

    # --- Print summary to console ---
    print(f"\n=== Classification Breakdown ===")
    for cls in ["KEEP", "KEEP_WITH_WORK", "LEAVE", "TEST", "INIT_REEXPORT"]:
        print(f"  {cls}: {classification_counts.get(cls, 0)}")

    print(f"\n=== Top 10 Most-Imported Modules ===")
    for rank, (mod, count) in enumerate(top_imported[:10], 1):
        print(f"  {rank}. {mod} ({count} imports)")

    print(f"\n=== Top 10 Files by Import Count ===")
    for rank, (fp, count) in enumerate(top_files[:10], 1):
        print(f"  {rank}. {fp} ({count} imports)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
