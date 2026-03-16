"""Quick test of MCP tools with real pipeline."""
from hlf.mcp_tools import HLFToolProvider, HAS_PARSER, HAS_COMPILER, HAS_VM

print(f"HAS_PARSER={HAS_PARSER}")
print(f"HAS_COMPILER={HAS_COMPILER}")
print(f"HAS_VM={HAS_VM}")

class MockResources:
    def _get_version_info(self):
        return {"version": "0.5.0", "grammar_sha256": "test"}

tp = HLFToolProvider(MockResources())

# Test compile
r1 = tp.call_tool("hlf_compile", {"source": "fn add(a: Int, b: Int): Int { a + b }"})
print(f"Compile: success={r1['success']}, funcs={r1.get('functions')}, errors={r1.get('errors', [])}")

# Test validate
r2 = tp.call_tool("hlf_validate", {"source": "fn mul(x: Int, y: Int): Int { x * y }"})
print(f"Validate: success={r2['success']}, summary={r2.get('ast_summary')}")

# Test execute with source passthrough
r3 = tp.call_tool("hlf_execute", {
    "bytecode": r1["bytecode"],
    "inputs": {"_source": "fn add(a: Int, b: Int): Int { a + b }", "_function": "add", "_args": [3, 5]}
})
print(f"Execute: success={r3['success']}, result={r3.get('result')}, gas={r3.get('gas_used')}")
if not r3["success"]:
    print(f"  ERROR: {r3.get('error')}")
    tb = r3.get('traceback')
    if tb:
        print(f"  TB:\n{tb}")

print("\nALL MCP TOOLS OK" if all(r["success"] for r in [r1, r2, r3]) else "\nSOME TOOLS FAILED")
