"""
HLF Native Agent Harness

A single agent that uses HLF as its native reasoning substrate.

Flow:
  1. Agent receives English intent
  2. Agent composes HLF source (CALL syntax for executable operations)
  3. Compiles → Bytecode → VM execute
  4. Produces real artifact (file, data, etc.)
  5. Returns audit trail in plain English

This is the first vertical slice: file I/O via HLF VM.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from hlf_mcp.server_context import build_server_context


def agent_do(intent: str, tier: str = "hearth") -> dict:
    """
    Execute an English intent through the HLF VM.

    For this vertical slice, the agent maps known intents to
    hand-crafted HLF programs. Future versions will use
    language_to_hlf for full natural-language translation.
    """
    ctx = build_server_context()

    # Map simple intents to HLF programs
    hlf_source = _intent_to_hlf(intent)
    if not hlf_source:
        return {"status": "unsupported_intent", "intent": intent}

    # Compile
    compile_result = ctx.compiler.compile(hlf_source)
    if not compile_result.get("ast"):
        return {
            "status": "compile_error",
            "intent": intent,
            "error": compile_result.get("error", "unknown"),
        }

    # Encode
    bc = ctx.bytecoder.encode(compile_result["ast"])

    # Execute
    run_result = ctx.runtime.run(
        bc,
        gas_limit=200,
        variables={"DEPLOYMENT_TIER": tier},
        ast=compile_result["ast"],
        source=hlf_source,
        tier=tier,
    )

    # Human-readable audit
    audit = {
        "intent": intent,
        "hlf_source": hlf_source.strip(),
        "compiled": compile_result.get("valid") is not False,
        "gas_estimate": compile_result.get("gas_estimate"),
        "execution_status": run_result.get("status"),
        "gas_used": run_result.get("gas_used"),
        "result": run_result.get("result"),
        "side_effects": run_result.get("side_effects", []),
        "trace_count": len(run_result.get("trace", [])),
    }

    return audit


def _intent_to_hlf(intent: str) -> str | None:
    """Map a simple English intent to an HLF program."""
    lowered = intent.lower().strip()

    if "write" in lowered or "create file" in lowered:
        # Extract filename and content heuristically
        # Default example for the slice
        return '''[HLF-v3]
CALL WRITE target="hlf/agent_output.txt" content="Hello from the HLF native agent!"
Ω
'''

    if "read" in lowered:
        return '''[HLF-v3]
CALL READ target="hlf/agent_output.txt"
Ω
'''

    if "hash" in lowered:
        return '''[HLF-v3]
CALL hash_sha256 data="Hello World"
Ω
'''

    if "timestamp" in lowered or "time" in lowered:
        return '''[HLF-v3]
CALL get_timestamp
Ω
'''

    return None


def main():
    print("=" * 60)
    print("HLF Native Agent Harness — Vertical Slice: File I/O")
    print("=" * 60)
    print()

    # Test 1: Write a file (requires operator tier)
    print("Test 1: 'Write a greeting file'")
    result = agent_do("Write a greeting file", tier="forge")
    print(json.dumps(result, indent=2, default=str))
    print()

    output = repo_root / "hlf" / "agent_output.txt"
    if output.exists():
        print(f"✅ Artifact verified: {output}")
        print(f"   Content: {output.read_text()}")
    else:
        print(f"❌ Artifact missing: {output}")
    print()

    # Test 2: Read it back
    print("Test 2: 'Read the greeting file'")
    result2 = agent_do("Read the greeting file", tier="hearth")
    print(json.dumps(result2, indent=2, default=str))
    print()

    # Test 3: Hash a string
    print("Test 3: 'Hash Hello World'")
    result3 = agent_do("Hash Hello World", tier="hearth")
    print(json.dumps(result3, indent=2, default=str))
    print()

    # Test 4: Get timestamp
    print("Test 4: 'Get current timestamp'")
    result4 = agent_do("Get current timestamp", tier="hearth")
    print(json.dumps(result4, indent=2, default=str))
    print()

    print("=" * 60)
    print("Harness complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
