"""
Test harness: can we instantiate ServerContext and run hlf_do end-to-end?
This is the first gate for the vertical slice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repo root is on path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from hlf_mcp.server_context import build_server_context
from hlf_mcp.server_translation import run_hlf_do


def main():
    print("Building ServerContext...")
    ctx = build_server_context()
    print(f"  Compiler: {type(ctx.compiler).__name__}")
    print(f"  Runtime: {type(ctx.runtime).__name__}")
    print(f"  Bytecoder: {type(ctx.bytecoder).__name__}")
    print(f"  Memory: {type(ctx.memory_store).__name__}")
    print(f"  Host Registry: {len(ctx.host_registry._functions)} functions")
    print()

    # Test 1: Simple arithmetic intent
    intent1 = "Calculate 2 plus 3 and return the result"
    print(f"Intent: {intent1}")
    result1 = run_hlf_do(ctx, intent=intent1, tier="hearth", dry_run=True, show_hlf=True)
    print(json.dumps(result1, indent=2, default=str))
    print()

    # Test 2: File write intent
    intent2 = "Write a greeting message to hello.txt"
    print(f"Intent: {intent2}")
    result2 = run_hlf_do(ctx, intent=intent2, tier="hearth", dry_run=True, show_hlf=True)
    print(json.dumps(result2, indent=2, default=str))
    print()

    # Test 3: If dry_run passes, try actual execution for a safe task
    if result1.get("success"):
        print("Attempting LIVE execution of arithmetic intent...")
        result3 = run_hlf_do(ctx, intent=intent1, tier="hearth", dry_run=False, show_hlf=True)
        print(json.dumps(result3, indent=2, default=str))
    else:
        print("Dry run failed; skipping live execution.")


if __name__ == "__main__":
    main()
