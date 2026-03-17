"""Smoke test all 32 MCP tools."""
from pathlib import Path
from hlf.mcp_tools import HLFToolProvider
from hlf.mcp_resources import HLFResourceProvider
import base64

rp = HLFResourceProvider(Path('.'))
tp = HLFToolProvider(resource_provider=rp)

src = 'fn add(a: Int, b: Int): Int { a + b }'
failed = []
passed = []

def check(name, result):
    ok = result.get("success", False)
    status = "OK" if ok else "FAIL"
    print(f"  {name}: {status}")
    if not ok:
        err = result.get("error", "")
        if err:
            print(f"    error: {err}")
        failed.append(name)
    else:
        passed.append(name)
    return result

# Original 10 tools
print("=== Original Tools ===")
check("hlf_compile", tp.call_tool("hlf_compile", {"source": src}))
check("hlf_execute", tp.call_tool("hlf_execute", {
    "bytecode": tp.call_tool("hlf_compile", {"source": src})["bytecode"],
    "inputs": {"function": "add", "args": [3, 5]}
}))
check("hlf_validate", tp.call_tool("hlf_validate", {"source": src}))
check("hlf_friction_log", tp.call_tool("hlf_friction_log", {
    "source_snippet": "x ?? y", "failure_type": "parse"
}))
check("hlf_self_observe", tp.call_tool("hlf_self_observe", {
    "meta_intent": {"phase": "test", "gas_used": 0}
}))
check("hlf_get_version", tp.call_tool("hlf_get_version", {}))
check("hlf_compose", tp.call_tool("hlf_compose", {"programs": [src]}))
check("hlf_decompose", tp.call_tool("hlf_decompose", {"source": src}))
check("hlf_analyze", tp.call_tool("hlf_analyze", {"source": src}))
check("hlf_optimize", tp.call_tool("hlf_optimize", {"source": src}))

# New compiler/analysis tools
print("\n=== Compiler & Analysis ===")
check("hlf_format", tp.call_tool("hlf_format", {"source": src}))
check("hlf_lint", tp.call_tool("hlf_lint", {"source": src}))

r = tp.call_tool("hlf_run", {"source": src, "args": [3, 5]})
check("hlf_run", r)
if r.get("success"):
    print(f"    add(3,5) = {r['result']}")

compiled = tp.call_tool("hlf_compile", {"source": src})
hlb_hex = base64.b64decode(compiled["bytecode"]).hex()
check("hlf_disassemble", tp.call_tool("hlf_disassemble", {"bytecode_hex": hlb_hex}))

# Translation & decompilation
print("\n=== Translation & Decompilation ===")
r = tp.call_tool("hlf_translate_to_hlf", {"english": "create a file validator"})
check("hlf_translate_to_hlf", r)
if r.get("success"):
    print(f"    generated: {r['hlf_source'][:60]}")

r = tp.call_tool("hlf_translate_to_english", {"source": src})
check("hlf_translate_to_english", r)
if r.get("success"):
    print(f"    english: {r['english'][:80]}")

check("hlf_decompile_ast", tp.call_tool("hlf_decompile_ast", {"source": src}))
r = tp.call_tool("hlf_decompile_bytecode", {"source": src})
check("hlf_decompile_bytecode", r)
if r.get("success"):
    print(f"    .hlb size: {r['hlb_size']} bytes")

r = tp.call_tool("hlf_similarity_gate", {"source_a": src, "source_b": src})
check("hlf_similarity_gate", r)
if r.get("success"):
    print(f"    similarity: {r['similarity']} (equiv={r['equivalent']})")

# Capsule & security
print("\n=== Capsule & Security ===")
check("hlf_capsule_validate", tp.call_tool("hlf_capsule_validate", {
    "source": src, "capsule": "hearth"
}))
r = tp.call_tool("hlf_capsule_run", {
    "source": src, "capsule": "forge", "args": [2, 3]
})
check("hlf_capsule_run", r)
if r.get("success"):
    print(f"    capsule_run result: {r['result']}")

check("hlf_host_functions", tp.call_tool("hlf_host_functions", {"tier": "forge"}))
check("hlf_tool_list", tp.call_tool("hlf_tool_list", {}))

# Memory & instinct
print("\n=== Memory & Instinct ===")
check("hlf_memory_store", tp.call_tool("hlf_memory_store", {
    "key": "test_fact", "value": "HLF is a capability amplifier", "tags": ["vision"]
}))
check("hlf_memory_query", tp.call_tool("hlf_memory_query", {"query": "capability"}))
check("hlf_memory_stats", tp.call_tool("hlf_memory_stats", {}))

check("hlf_instinct_step", tp.call_tool("hlf_instinct_step", {"mission_id": "test-m1"}))
check("hlf_instinct_get", tp.call_tool("hlf_instinct_get", {"mission_id": "test-m1"}))

r = tp.call_tool("hlf_spec_lifecycle", {
    "spec_source": src, "mission_id": "lifecycle-1", "auto_advance": True
})
check("hlf_spec_lifecycle", r)
if r.get("success"):
    print(f"    final phase: {r['current_phase']}")

# Benchmarking
print("\n=== Benchmarking ===")
r = tp.call_tool("hlf_benchmark", {
    "hlf_source": src,
    "english_equivalent": "Define a function called add that takes two integer parameters a and b and returns their sum as an integer."
})
check("hlf_benchmark", r)
if r.get("success"):
    print(f"    compression: {r['token_compression_pct']}% tokens, {r['byte_compression_pct']}% bytes")

r = tp.call_tool("hlf_benchmark_suite", {})
check("hlf_benchmark_suite", r)
if r.get("success"):
    s = r["summary"]
    print(f"    {s['total_fixtures']} fixtures, avg compression: {s['average_compression_pct']}%")

# Summary
print(f"\n{'='*50}")
print(f"PASSED: {len(passed)}/{len(passed)+len(failed)}")
if failed:
    print(f"FAILED: {failed}")
else:
    print("ALL TOOLS OK")
