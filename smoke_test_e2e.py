"""End-to-end smoke test for the live MCP HTTP server on port 8000."""
import urllib.request
import json
import sys

BASE = "http://127.0.0.1:8000"
PASSED = 0
FAILED = 0


def post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read())


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return r.status, json.loads(r.read())


def check(label, condition):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS: {label}")
    else:
        FAILED += 1
        print(f"  FAIL: {label}")


# ---- 1. Health ----
print("=== 1. Health ===")
s, d = get("/health")
print(f"  {s}: {d}")
check("status healthy", s == 200 and d["status"] == "healthy")

# ---- 2. Initialize ----
print("=== 2. MCP Initialize (JSON-RPC) ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "smoke"}}})
pv = d["result"]["protocolVersion"]
caps = list(d["result"]["capabilities"].keys())
print(f"  protocolVersion={pv}, capabilities={caps}")
check("protocol 2025-03-26", pv == "2025-03-26")
check("has resources+tools+prompts caps", all(k in caps for k in ["resources", "tools", "prompts"]))

# ---- 3. Resources List ----
print("=== 3. Resources List ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}})
uris = [r["uri"] for r in d["result"]["resources"]]
print(f"  {len(uris)} resources: {uris}")
check("grammar in resources", "hlf://grammar" in uris)
check("version in resources", "hlf://version" in uris)
check("ast-schema in resources", "hlf://ast-schema" in uris)

# ---- 4. Resource Read: version ----
print("=== 4. Resource Read (version) ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "hlf://version"}})
ver = json.loads(d["result"]["contents"][0]["text"])
print(f"  version={ver['version']}, sha256={ver['grammar_sha256'][:16]}...")
check("sha256 is 64 hex", len(ver["grammar_sha256"]) == 64)
check("has compatibility", isinstance(ver.get("compatibility"), list))

# ---- 5. Tools List ----
print("=== 5. Tools List ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}})
tools = [t["name"] for t in d["result"]["tools"]]
print(f"  {len(tools)} tools: {tools}")
check("10+ tools", len(tools) >= 10)
for t in ["hlf_compile", "hlf_execute", "hlf_validate", "hlf_friction_log", "hlf_self_observe",
          "hlf_get_version", "hlf_compose", "hlf_decompose", "hlf_analyze", "hlf_optimize"]:
    check(f"tool {t}", t in tools)

# ---- 6. Compile ----
print("=== 6. Tool: hlf_compile ===")
src = "module test v0.5 {\n  fn add(a: int, b: int): int {\n    ret a + b\n  }\n}"
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "hlf_compile", "arguments": {"source": src}}})
cr = json.loads(d["result"]["content"][0]["text"])
print(f"  success={cr['success']}, gas={cr['gas_estimate']}, bytecode={cr['bytecode'][:20]}...")
check("compile success", cr["success"] is True)
check("has bytecode", len(cr["bytecode"]) > 0)
bc = cr["bytecode"]

# ---- 7. Execute ----
print("=== 7. Tool: hlf_execute ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "hlf_execute", "arguments": {"bytecode": bc, "gas_limit": 50000}}})
er = json.loads(d["result"]["content"][0]["text"])
print(f"  success={er['success']}, gas_used={er['gas_used']}")
check("execute success", er["success"] is True)
check("gas within limit", er["gas_used"] <= 50000)

# ---- 8. Validate ----
print("=== 8. Tool: hlf_validate ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "hlf_validate", "arguments": {"source": src}}})
vr = json.loads(d["result"]["content"][0]["text"])
print(f"  success={vr['success']}, errors={vr['errors']}, ast_summary={vr.get('ast_summary')}")
check("validate has ast_summary", "ast_summary" in vr)
check("validate has errors list", isinstance(vr["errors"], list))

# ---- 9. Analyze ----
print("=== 9. Tool: hlf_analyze ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "hlf_analyze", "arguments": {"source": src, "metrics": ["complexity", "effects", "gas_estimate", "dependencies"]}}})
ar = json.loads(d["result"]["content"][0]["text"])
print(f"  success={ar['success']}, metrics={list(ar['metrics'].keys())}")
check("analyze success", ar["success"] is True)
check("4 metric groups", len(ar["metrics"]) == 4)

# ---- 10. Friction Log ----
print("=== 10. Tool: hlf_friction_log ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "hlf_friction_log", "arguments": {"source_snippet": "test -> unknown", "failure_type": "expression", "attempted_intent": "Map glyph"}}})
fr = json.loads(d["result"]["content"][0]["text"])
print(f"  success={fr['success']}, friction_id={fr['friction_id']}")
check("friction success", fr["success"] is True)
check("friction_id 16 hex", len(fr["friction_id"]) == 16)

# ---- 11. Get Version ----
print("=== 11. Tool: hlf_get_version ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "hlf_get_version", "arguments": {}}})
gv = json.loads(d["result"]["content"][0]["text"])
print(f"  success={gv['success']}, version={gv.get('version')}")
check("get_version success", gv["success"] is True)

# ---- 12. Prompts List ----
print("=== 12. Prompts List ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 11, "method": "prompts/list", "params": {}})
prompts = [p["name"] for p in d["result"]["prompts"]]
print(f"  {len(prompts)} prompts: {prompts}")
check("7+ prompts", len(prompts) >= 7)
check("init_agent prompt", "hlf_initialize_agent" in prompts)

# ---- 13. Prompt Get ----
print("=== 13. Prompt: hlf_initialize_agent ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 12, "method": "prompts/get", "params": {"name": "hlf_initialize_agent", "arguments": {"tier": "forge", "profile": "P0"}}})
msg = d["result"]["messages"][0]
text_len = len(msg["content"]["text"])
print(f"  role={msg['role']}, content_len={text_len}")
check("role is user", msg["role"] == "user")
check("prompt > 500 chars", text_len > 500)

# ---- 14. Self Observe (forge tier) ----
print("=== 14. Tool: hlf_self_observe (forge) ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {"name": "hlf_self_observe", "arguments": {"meta_intent": {"phase": "compile"}, "tier": "forge"}}})
so = json.loads(d["result"]["content"][0]["text"])
print(f"  success={so['success']}")
check("self_observe forge allowed", so["success"] is True)

# ---- 15. Self Observe (guest blocked) ----
print("=== 15. Tool: hlf_self_observe (guest -> blocked) ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 14, "method": "tools/call", "params": {"name": "hlf_self_observe", "arguments": {"meta_intent": {"phase": "test"}, "tier": "guest"}}})
so2 = json.loads(d["result"]["content"][0]["text"])
print(f"  success={so2['success']}, error={so2.get('error', 'n/a')}")
check("guest tier blocked", so2["success"] is False)

# ---- 16. Compose ----
print("=== 16. Tool: hlf_compose ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 15, "method": "tools/call", "params": {"name": "hlf_compose", "arguments": {"programs": ["module a {}", "module b {}"], "strategy": "sequential"}}})
co = json.loads(d["result"]["content"][0]["text"])
print(f"  success={co['success']}, program_count={co['program_count']}")
check("compose success", co["success"] is True)

# ---- 17. Unknown method -> -32601 ----
print("=== 17. Unknown method -> error ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 99, "method": "bogus/method", "params": {}})
print(f"  error_code={d['error']['code']}")
check("unknown method -32601", d["error"]["code"] == -32601)

# ---- Summary ----
print()
print(f"{'='*50}")
print(f"  PASSED: {PASSED}  |  FAILED: {FAILED}  |  TOTAL: {PASSED + FAILED}")
print(f"{'='*50}")

if FAILED > 0:
    print("  SOME CHECKS FAILED!")
    sys.exit(1)
else:
    print("  ALL END-TO-END CHECKS PASSED")
    sys.exit(0)
