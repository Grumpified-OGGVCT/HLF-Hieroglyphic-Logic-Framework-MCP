"""End-to-end smoke test for the live MCP HTTP server using an explicit base URL."""
import urllib.request
import json
import os
import sys


def _resolve_base_url() -> str:
    base_url = os.environ.get("HLF_BASE_URL")
    if base_url:
        return base_url.rstrip("/")
    port = os.environ.get("HLF_PORT")
    if port:
        return f"http://127.0.0.1:{port}"
    raise RuntimeError("Set HLF_BASE_URL or HLF_PORT before running smoke_test_e2e.py")


BASE = _resolve_base_url()
PASSED = 0
FAILED = 0
SESSION_ID = None


def _decode_mcp_response(response) -> tuple[int, dict]:
    content_type = response.headers.get("Content-Type", "")
    session_id = response.headers.get("mcp-session-id")
    if session_id:
        global SESSION_ID
        SESSION_ID = session_id

    payload = response.read().decode("utf-8")
    if not payload.strip():
        return response.status, {}

    if "text/event-stream" in content_type:
        data_lines = []
        for line in payload.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if not data_lines:
            return response.status, {}
        payload = "\n".join(data_lines)

    return response.status, json.loads(payload)


def post(path, data):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if SESSION_ID:
        headers["Mcp-Session-Id"] = SESSION_ID
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return _decode_mcp_response(r)


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
check("status healthy", s == 200 and d["status"] == "ok")

# ---- 2. Initialize ----
print("=== 2. MCP Initialize (JSON-RPC) ===")
s, d = post(
    "/mcp",
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "clientInfo": {"name": "smoke", "version": "1.0.0"},
            "capabilities": {},
        },
    },
)
pv = d["result"]["protocolVersion"]
caps = list(d["result"]["capabilities"].keys())
print(f"  protocolVersion={pv}, capabilities={caps}")
check("protocol 2025-03-26", pv == "2025-03-26")
check("has resources+tools+prompts caps", all(k in caps for k in ["resources", "tools", "prompts"]))
check("session id established", SESSION_ID is not None and len(SESSION_ID) > 0)

# ---- 2b. Initialized notification ----
print("=== 2b. MCP Initialized Notification ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
print(f"  status={s}")
check("initialized notification accepted", s == 202)

# ---- 3. Resources List ----
print("=== 3. Resources List ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}})
uris = [r["uri"] for r in d["result"]["resources"]]
print(f"  {len(uris)} resources: {uris}")
check("grammar in resources", "hlf://grammar" in uris)
check("opcodes in resources", "hlf://opcodes" in uris)
check("formal verifier status in resources", "hlf://status/formal_verifier" in uris)
check("approval bypass status in resources", "hlf://status/approval_bypass" in uris)
check("daemon transparency status in resources", "hlf://status/daemon_transparency" in uris)
check("daemon transparency report in resources", "hlf://reports/daemon_transparency" in uris)

# ---- 4. Resource Read: grammar ----
print("=== 4. Resource Read (grammar) ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 3, "method": "resources/read", "params": {"uri": "hlf://grammar"}})
grammar_text = d["result"]["contents"][0]["text"]
print(f"  grammar_len={len(grammar_text)}")
check("grammar text returned", len(grammar_text) > 100)
check("grammar has start rule", "start" in grammar_text or "program" in grammar_text)

# ---- 5. Tools List ----
print("=== 5. Tools List ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}})
tools = [t["name"] for t in d["result"]["tools"]]
print(f"  {len(tools)} tools: {tools}")
check("20+ tools", len(tools) >= 20)
for t in [
    "hlf_compile",
    "hlf_run",
    "hlf_validate",
    "hlf_do",
    "hlf_verify_formal_ast",
    "hlf_verify_gas_budget",
    "hlf_route_governed_request",
    "hlf_capsule_run",
]:
    check(f"tool {t}", t in tools)

# ---- 6. Compile ----
print("=== 6. Tool: hlf_compile ===")
src = '[HLF-v3]\nΔ [INTENT] goal="sealed-run"\n∇ [RESULT] message="sealed"\nΩ\n'
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "hlf_compile", "arguments": {"source": src}}})
cr = d["result"].get("structuredContent") or json.loads(d["result"]["content"][0]["text"])
print(f"  status={cr['status']}, gas={cr['gas_estimate']}, bytecode_hex={cr['bytecode_hex'][:20]}...")
check("compile status ok", cr["status"] == "ok")
check("has bytecode hex", len(cr["bytecode_hex"]) > 0)

# ---- 7. Run ----
print("=== 7. Tool: hlf_run ===")
ingress_agent_id = "http-smoke-agent"
ingress_nonce = "http-smoke-nonce"
s, d = post(
    "/mcp",
    {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "hlf_run",
            "arguments": {
                "source": src,
                "gas_limit": 5000,
                "agent_id": ingress_agent_id,
                "ingress_nonce": ingress_nonce,
            },
        },
    },
)
er = d["result"].get("structuredContent") or json.loads(d["result"]["content"][0]["text"])
print(f"  status={er['status']}, gas_used={er['gas_used']}")
check("run status ok", er["status"] == "ok")
check("gas within limit", er["gas_used"] <= 5000)

# ---- 7b. Resource Read: ingress ----
print("=== 7b. Resource Read (ingress) ===")
s, d = post(
    "/mcp",
    {
        "jsonrpc": "2.0",
        "id": 61,
        "method": "resources/read",
        "params": {"uri": f"hlf://status/ingress/{ingress_agent_id}"},
    },
)
ingress_resource = json.loads(d["result"]["contents"][0]["text"])
print(
    "  "
    f"status={ingress_resource['status']}, "
    f"source={(ingress_resource.get('ingress_status') or {}).get('source')}, "
    f"decision={(ingress_resource.get('ingress_status') or {}).get('decision')}"
)
check("ingress resource status ok", ingress_resource["status"] == "ok")
check(
    "ingress resource uses execution admission fallback",
    (ingress_resource.get("ingress_status") or {}).get("source") == "execution_admission",
)
check(
    "ingress resource decision allow",
    (ingress_resource.get("ingress_status") or {}).get("decision") == "allow",
)
check(
    "ingress replay protection accepted",
    ((ingress_resource.get("ingress_status") or {}).get("stage_status") or {})
    .get("replay_protection", {})
    .get("status")
    == "accepted",
)

# ---- 8. Validate ----
print("=== 8. Tool: hlf_validate ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "hlf_validate", "arguments": {"source": src}}})
vr = d["result"].get("structuredContent") or json.loads(d["result"]["content"][0]["text"])
print(f"  valid={vr['valid']}, statement_count={vr['statement_count']}, error={vr.get('error')}")
check("validate success", vr["valid"] is True)
check("validate no error", vr.get("error") is None)

# ---- 9. Formal Verifier ----
print("=== 9. Tool: hlf_verify_formal_ast ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "hlf_verify_formal_ast", "arguments": {"source": src, "gas_budget": 5000}}})
fv = d["result"].get("structuredContent") or json.loads(d["result"]["content"][0]["text"])
print(f"  status={fv['status']}, proven={fv['report']['proven']}, total={fv['report']['total']}")
check("formal verifier status ok", fv["status"] == "ok")
check("formal verifier emitted report", fv["report"]["total"] >= 1)

# ---- 10. Prompts List ----
print("=== 10. Prompts List ===")
s, d = post("/mcp", {"jsonrpc": "2.0", "id": 11, "method": "prompts/list", "params": {}})
prompts = [p["name"] for p in d["result"]["prompts"]]
print(f"  {len(prompts)} prompts: {prompts}")
check("prompts list returned", isinstance(prompts, list))

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
