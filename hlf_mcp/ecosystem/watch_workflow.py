"""
Watch Workflow — file watcher that regenerates ecosystem SDKs.

Watches ``hlf_mcp/ecosystem/schema_translator.py`` and related schema
source files.  When changes are detected, regenerates all SDK outputs
to ``hlf_mcp/ecosystem/generated/``.

Supports:
    --once   : One-shot regeneration, exits immediately.
    --watch  : Continuous watching (polling-based, cross-platform).

Uses ``os.path.getmtime`` polling (not inotify) for Windows/macOS/Linux
compatibility.  Default poll interval is 2 seconds.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

# Paths relative to the HLF_MCP project root
_DEFAULT_WATCH_PATHS: list[str] = [
    "hlf_mcp/ecosystem/schema_translator.py",
    "hlf_mcp/hlf/typed_contracts.py",
]

_DEFAULT_OUTPUT_DIR: str = "hlf_mcp/ecosystem/generated"

# Map of (contract_name) → output filenames per language
# In a full implementation this would use the actual manifest/contract registry;
# here we generate stub SDKs for all languages from known contract definitions.
_GENERATED_LANGUAGES: list[str] = ["python", "typescript", "go", "java", "rust"]


def _find_project_root(start_dir: Optional[str] = None) -> str:
    """Locate the HLF_MCP project root by searching for pyproject.toml or setup.py."""
    current = start_dir or os.getcwd()
    # Walk up to find project root marker
    markers = ["pyproject.toml", "setup.py", "setup.cfg", "uv.lock"]
    for _ in range(10):
        for marker in markers:
            if os.path.isfile(os.path.join(current, marker)):
                return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    # Fallback: use cwd
    return os.getcwd()


def _resolve_path(project_root: str, relative: str) -> str:
    """Resolve a path relative to the project root."""
    return os.path.normpath(os.path.join(project_root, relative))


def _get_file_mtime(filepath: str) -> float:
    """Return the mtime of a file, or 0 if it does not exist."""
    try:
        return os.path.getmtime(filepath)
    except OSError:
        return 0.0


def _generate_all(project_root: str) -> dict[str, object]:
    """Regenerate all SDK outputs.

    Imports SchemaTranslator, generates SDK snippets for a set of known
    contract shapes, and writes them to the output directory.

    Returns:
        Dict with status and generated file count.
    """
    # Ensure the output directory exists
    output_dir = _resolve_path(project_root, _DEFAULT_OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    # Build minimal contracts for SDK generation demonstration
    try:
        # Add project root to path so imports work from any cwd
        sys.path.insert(0, project_root)

        from hlf_mcp.hlf.typed_contracts import (
            HlfType,
            InputContract,
            OutputContract,
            TypeContract,
        )
        from hlf_mcp.ecosystem.schema_translator import SchemaTranslator
    except ImportError as exc:
        return {
            "status": "error",
            "error": f"Import failed: {exc}",
            "hint": "Run from the HLF_MCP project root or set PYTHONPATH.",
            "generated": 0,
        }

    translator = SchemaTranslator(name="watch-workflow", strict_mode=False)

    # Define sample contracts for each category
    contracts: list[tuple[str, object]] = [
        (
            "read_file",
            InputContract(
                function_name="read_file",
                parameters=[
                    TypeContract(
                        name="path",
                        hlf_type=HlfType.STRING,
                        json_schema_type="string",
                        required=True,
                        constraints={"description": "File path to read"},
                    ),
                ],
            ),
        ),
        (
            "read_file_output",
            OutputContract(
                function_name="read_file",
                return_type=HlfType.STRING,
            ),
        ),
        (
            "search_query",
            InputContract(
                function_name="search_query",
                parameters=[
                    TypeContract(
                        name="query",
                        hlf_type=HlfType.STRING,
                        json_schema_type="string",
                        required=True,
                        constraints={"description": "Search query string"},
                    ),
                    TypeContract(
                        name="max_results",
                        hlf_type=HlfType.INTEGER,
                        json_schema_type="integer",
                        required=False,
                        constraints={"description": "Maximum results", "default": 10},
                    ),
                ],
            ),
        ),
        (
            "search_query_output",
            OutputContract(
                function_name="search_query",
                return_type=HlfType.LIST,
            ),
        ),
    ]

    generated_count = 0

    for contract_name, contract in contracts:
        # Generate for each target language
        for lang in _GENERATED_LANGUAGES:
            try:
                code = translator.generate_client_sdk(contract, language=lang)
                # Determine file extension
                ext_map = {
                    "python": ".py",
                    "typescript": ".ts",
                    "go": ".go",
                    "java": ".java",
                    "rust": ".rs",
                }
                ext = ext_map.get(lang, ".txt")
                filename = f"{contract_name}_{lang}{ext}"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(code)
                generated_count += 1
            except Exception as exc:
                print(
                    f"  [WARN] Failed to generate {lang} SDK for {contract_name}: {exc}",
                    file=sys.stderr,
                )

    return {
        "status": "ok",
        "generated": generated_count,
        "output_dir": output_dir,
        "languages": _GENERATED_LANGUAGES,
    }


def run_once(project_root: Optional[str] = None) -> int:
    """Execute a one-shot regeneration of all SDKs.

    Returns:
        Exit code (0 on success, 1 on failure).
    """
    root = project_root or _find_project_root()
    print(f"[watch_workflow] Project root: {root}")
    print("[watch_workflow] Regenerating SDKs (--once)...")

    result = _generate_all(root)

    if result.get("status") == "error":
        print(f"[watch_workflow] ERROR: {result.get('error')}", file=sys.stderr)
        hint = result.get("hint")
        if hint:
            print(f"[watch_workflow] HINT: {hint}", file=sys.stderr)
        return 1

    generated = result.get("generated", 0)
    output_dir = result.get("output_dir", "unknown")
    print(f"[watch_workflow] Generated {generated} SDK files → {output_dir}")
    return 0


def run_watch(
    project_root: Optional[str] = None,
    poll_interval: float = 2.0,
) -> int:
    """Continuously watch schema files and regenerate on change.

    Uses polling (os.path.getmtime) for cross-platform compatibility.
    Press Ctrl+C to stop.

    Args:
        project_root: Project root directory. Auto-detected if None.
        poll_interval: Seconds between checks.

    Returns:
        Exit code (0 on normal exit, 1 on startup failure).
    """
    root = project_root or _find_project_root()
    print(f"[watch_workflow] Project root: {root}")
    print(f"[watch_workflow] Poll interval: {poll_interval}s")
    print("[watch_workflow] Watching for changes (Ctrl+C to stop)...")

    # Build watch file list
    watch_files: list[str] = [
        _resolve_path(root, p) for p in _DEFAULT_WATCH_PATHS
    ]

    # Verify at least one watch file exists
    existing = [f for f in watch_files if os.path.isfile(f)]
    if not existing:
        print(
            "[watch_workflow] ERROR: No watch files found. "
            f"Checked: {watch_files}",
            file=sys.stderr,
        )
        return 1

    print("[watch_workflow] Watching:")
    for fpath in existing:
        print(f"  - {fpath}")

    # Initial generation
    print("[watch_workflow] Initial generation...")
    _generate_all(root)

    # Track mtimes
    last_mtimes: dict[str, float] = {}
    for fpath in existing:
        last_mtimes[fpath] = _get_file_mtime(fpath)

    try:
        while True:
            time.sleep(poll_interval)
            changed = False

            for fpath in existing:
                current_mtime = _get_file_mtime(fpath)
                if current_mtime > last_mtimes.get(fpath, 0.0):
                    changed = True
                    print(
                        f"[watch_workflow] Change detected: {os.path.basename(fpath)}"
                    )
                last_mtimes[fpath] = current_mtime

            if changed:
                result = _generate_all(root)
                generated = result.get("generated", 0)
                print(f"[watch_workflow] Regenerated {generated} SDK files.")

    except KeyboardInterrupt:
        print("\n[watch_workflow] Stopped.")
        return 0

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for the watch workflow CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code.
    """
    parser = argparse.ArgumentParser(
        prog="watch_workflow",
        description="Watch HLF schema files and regenerate SDKs on change.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="One-shot regeneration (exit after generation).",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuous watching mode (polling-based).",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Path to the HLF_MCP project root (auto-detected if omitted).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Poll interval in seconds for --watch mode (default: 2.0).",
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.once and not args.watch:
        parser.print_help()
        print(
            "\n[watch_workflow] Specify --once or --watch. "
            "Example: python -m hlf_mcp.ecosystem.watch_workflow --once",
            file=sys.stderr,
        )
        return 1

    root = args.project_root or _find_project_root()

    if args.once:
        return run_once(project_root=root)

    if args.watch:
        return run_watch(project_root=root, poll_interval=args.poll_interval)

    return 0


if __name__ == "__main__":
    sys.exit(main())
