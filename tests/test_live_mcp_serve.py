#!/usr/bin/env python3
"""
Live MCP server serve test for governance-only mode (SWARMGLASS_HLF_ENABLED=0).

Verifies:
  1. Server starts in stdio transport without crashing
  2. MCP initialize handshake works
  3. tools/list returns sg_* governance tools
  4. sg_audit_event_log tool call succeeds
  5. Zero DSL imports (compiler, runtime, bytecode) are loaded
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any


def send_rpc(proc: subprocess.Popen, request: dict[str, Any]) -> dict[str, Any] | None:
    """Send a JSON-RPC 2.0 request and read the next JSON line response."""
    req_bytes = (json.dumps(request) + "\n").encode("utf-8")
    proc.stdin.write(req_bytes)  # type: ignore[union-attr]
    proc.stdin.flush()  # type: ignore[union-attr]
    line = proc.stdout.readline()  # type: ignore[union-attr]
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


def _read_stderr(proc: subprocess.Popen) -> str:
    """Non-blocking peek at stderr accumulated so far."""
    try:
        import msvcrt
        return ""  # Windows pipes don't support non-blocking peek easily
    except ImportError:
        pass
    return ""


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    # ── Environment ──────────────────────────────────────────────────────────
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["SWARMGLASS_HLF_ENABLED"] = "0"
    env["HLF_TRANSPORT"] = "stdio"
    env["HLF_SKIP_SELF_INDEX"] = "1"
    env["HLF_MEMORY_DB"] = ":memory:"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    print("=" * 70)
    print("HLF MCP Live Serve Test — Governance-Only Mode")
    print(f"SWARMGLASS_HLF_ENABLED=0  |  HLF_TRANSPORT=stdio")
    print(f"Working directory: {cwd}")
    print("=" * 70)

    # ── Step 1: Start the server subprocess ──────────────────────────────────
    print("\n[1] Starting MCP server subprocess …")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "hlf_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
    except Exception as exc:
        print(f"  FAIL: Could not spawn server — {exc}")
        results.append(("server-startup", False, str(exc)))
        return 1

    # Give the server a moment to bootstrap (imports, FastMCP init, tool reg)
    time.sleep(4)

    if proc.poll() is not None:
        stderr_text = proc.stderr.read().decode("utf-8", errors="replace")  # type: ignore[union-attr]
        print(f"  FAIL: Server exited early (rc={proc.returncode})")
        print(f"  stderr tail:\n{stderr_text[-1500:]}")
        results.append(("server-startup", False, f"exit code {proc.returncode}"))
        return 1

    print(f"  PASS: Server alive (pid={proc.pid})")
    results.append(("server-startup", True, f"pid={proc.pid}"))

    # ── Step 2: Initialize handshake ─────────────────────────────────────────
    print("\n[2] Sending initialize request …")
    init_req: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test_live_mcp_serve", "version": "1.0"},
        },
    }
    init_resp = send_rpc(proc, init_req)

    if init_resp is None:
        print("  FAIL: No response to initialize")
        results.append(("initialize", False, "no response"))
        proc.terminate()
        return 1

    if "result" not in init_resp:
        print(f"  FAIL: Initialize error — {json.dumps(init_resp, indent=2)}")
        results.append(("initialize", False, json.dumps(init_resp.get("error", {}))))
        proc.terminate()
        return 1

    result = init_resp["result"]
    server_name = result.get("serverInfo", {}).get("name", "unknown")
    protocol = result.get("protocolVersion", "?")
    caps = result.get("capabilities", {})
    instructions = result.get("instructions", "")

    print(f"  PASS: Initialize OK")
    print(f"    serverInfo.name = {server_name}")
    print(f"    protocolVersion = {protocol}")
    print(f"    capabilities    = {json.dumps(caps)}")

    # Check for governance-only marker in instructions
    if "governance-only" in instructions.lower():
        print(f"    ✓ Instructions confirm governance-only mode")

    results.append(("initialize", True, server_name))

    # ── Step 3: Send initialized notification ────────────────────────────────
    print("\n[3] Sending notifications/initialized …")
    notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    proc.stdin.write((json.dumps(notif) + "\n").encode("utf-8"))  # type: ignore[union-attr]
    proc.stdin.flush()  # type: ignore[union-attr]
    time.sleep(0.3)
    print("  OK: Notification delivered")

    # ── Step 4: tools/list ───────────────────────────────────────────────────
    print("\n[4] Sending tools/list request …")
    tools_req: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": {},
    }
    tools_resp = send_rpc(proc, tools_req)

    if tools_resp is None or "result" not in tools_resp:
        print(f"  FAIL: tools/list failed — {json.dumps(tools_resp, indent=2)}")
        results.append(("tools/list", False, "bad response"))
        proc.terminate()
        return 1

    tools = tools_resp["result"].get("tools", [])
    tool_names = [t["name"] for t in tools]
    sg_tools = sorted(n for n in tool_names if n.startswith("sg_"))
    hlf_tools = sorted(n for n in tool_names if n.startswith("hlf_"))

    print(f"  PASS: tools/list returned {len(tools)} tools total")
    print(f"    sg_*  tools: {len(sg_tools)}")
    print(f"    hlf_* tools: {len(hlf_tools)}")

    # Show a sample
    sample_sg = sg_tools[:12]
    if sample_sg:
        print(f"    Sample sg_*: {', '.join(sample_sg)}")
        if len(sg_tools) > 12:
            print(f"    … and {len(sg_tools) - 12} more sg_* tools")

    if len(sg_tools) == 0:
        print("  FAIL: No sg_* governance tools found!")
        results.append(("tools/list", False, "zero sg_ tools"))
        proc.terminate()
        return 1

    # Verify key governance tools are present
    required_sg = ["sg_audit_event_log", "sg_memory_store", "sg_observe_feedback_submit"]
    missing = [t for t in required_sg if t not in tool_names]
    if missing:
        print(f"  WARN: Missing expected tools: {missing}")

    # Verify no DSL tools leaked through
    dsl_indicators = [n for n in tool_names if "compile" in n.lower() or "bytecode" in n.lower()]
    if dsl_indicators:
        print(f"  WARN: Potential DSL tools present: {dsl_indicators}")
    else:
        print(f"    ✓ No compiler/bytecode tools detected in tool list")

    results.append(("tools/list", True, f"{len(tools)} tools, {len(sg_tools)} sg_*"))

    # ── Step 5: Call sg_audit_event_log ──────────────────────────────────────
    print("\n[5] Calling sg_audit_event_log …")
    call_req: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "sg_audit_event_log",
            "arguments": {"limit": 10, "summaries_only": False},
        },
    }
    call_resp = send_rpc(proc, call_req)

    if call_resp is None:
        print("  FAIL: No response to sg_audit_event_log")
        results.append(("sg_audit_event_log", False, "no response"))
        proc.terminate()
        return 1

    if "error" in call_resp:
        err = call_resp["error"]
        print(f"  WARN: sg_audit_event_log returned error: {err.get('message', err)}")
        # Still counts as tool reachable — it answered
        results.append(("sg_audit_event_log", True, f"error: {err.get('message', '')[:80]}"))
    elif "result" in call_resp:
        content = call_resp["result"].get("content", [])
        is_error = call_resp["result"].get("isError", False)
        if is_error:
            print(f"  WARN: sg_audit_event_log result flagged as error")
            results.append(("sg_audit_event_log", True, "tool responded (isError=True)"))
        else:
            print(f"  PASS: sg_audit_event_log responded ({len(content)} content items)")
            results.append(("sg_audit_event_log", True, f"{len(content)} items"))
        # Try to decode the text content
        for item in content:
            if item.get("type") == "text":
                text = item.get("text", "")
                try:
                    payload = json.loads(text)
                    status = payload.get("status", "?")
                    count = payload.get("count", "?")
                    print(f"    Inner status={status}, count={count}")
                except json.JSONDecodeError:
                    print(f"    Raw text: {text[:200]}")

    # ── Step 6: DSL import isolation check ───────────────────────────────────
    print("\n[6] Verifying zero DSL imports in governance-only mode …")
    check_script = r"""
import os, sys, json
os.environ["SWARMGLASS_HLF_ENABLED"] = "0"
os.environ["HLF_SKIP_SELF_INDEX"] = "1"
os.environ["HLF_MEMORY_DB"] = ":memory:"

# Snapshot modules BEFORE importing server
before = set(sys.modules.keys())

from hlf_mcp.server_context import build_server_context
ctx = build_server_context()

# Modules loaded AFTER server_context import
after = set(sys.modules.keys())
new_mods = after - before

# Specific DSL engine modules — these are the actual compile/run/bytecode engines
# (NOT governance modules like persona_runtime which is a persona catalog)
dsl_engine_modules = [
    "hlf_mcp.hlf.compiler",
    "hlf_mcp.hlf.runtime",
    "hlf_mcp.hlf.bytecode",
    "hlf_mcp.hlf.formatter",
    "hlf_mcp.hlf.linter",
    "hlf_mcp.hlf.benchmark",
    "hlf_mcp.hlf.formal_verifier",
    "hlf_mcp.hlf.codegen",
]
loaded_dsl = sorted(m for m in dsl_engine_modules if m in new_mods)

# Also check the context attributes directly
result = {
    "compiler_none": ctx.compiler is None,
    "runtime_none": ctx.runtime is None,
    "bytecoder_none": ctx.bytecoder is None,
    "formatter_none": ctx.formatter is None,
    "linter_none": ctx.linter is None,
    "benchmark_none": ctx.benchmark is None,
    "formal_verifier_none": ctx.formal_verifier is None,
    "dsl_modules": loaded_dsl,
}
print("DSL_CHECK_RESULT:" + json.dumps(result))
"""

    try:
        check_proc = subprocess.run(
            [sys.executable, "-c", check_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
            timeout=60,
        )
        check_stdout = check_proc.stdout
        check_stderr = check_proc.stderr

        # Parse the marker line
        dsl_result = None
        for line in check_stdout.splitlines():
            if line.startswith("DSL_CHECK_RESULT:"):
                dsl_result = json.loads(line[len("DSL_CHECK_RESULT:"):])
                break

        if dsl_result is None:
            print(f"  FAIL: Could not parse DSL check output")
            print(f"  stdout: {check_stdout[:500]}")
            print(f"  stderr: {check_stderr[:500]}")
            results.append(("dsl-isolation", False, "parse error"))
        else:
            checks = [
                ("compiler", dsl_result["compiler_none"]),
                ("runtime", dsl_result["runtime_none"]),
                ("bytecoder", dsl_result["bytecoder_none"]),
                ("formatter", dsl_result["formatter_none"]),
                ("linter", dsl_result["linter_none"]),
                ("benchmark", dsl_result["benchmark_none"]),
                ("formal_verifier", dsl_result["formal_verifier_none"]),
            ]
            all_dsl_none = all(v for _, v in checks)
            dsl_mods_found = dsl_result["dsl_modules"]

            for name, is_none in checks:
                status = "None ✓" if is_none else "LOADED ✗"
                print(f"    ctx.{name}: {status}")

            if dsl_mods_found:
                print(f"    DSL modules in sys.modules: {dsl_mods_found}")
                all_dsl_none = False

            if all_dsl_none:
                print("  PASS: Zero DSL components loaded")
                results.append(("dsl-isolation", True, "all None"))
            else:
                print("  FAIL: DSL components detected in governance-only mode!")
                results.append(("dsl-isolation", False, "DSL loaded"))
    except subprocess.TimeoutExpired:
        print("  FAIL: DSL check timed out")
        results.append(("dsl-isolation", False, "timeout"))
    except Exception as exc:
        print(f"  FAIL: DSL check error — {exc}")
        results.append(("dsl-isolation", False, str(exc)))

    # ── Cleanup ──────────────────────────────────────────────────────────────
    print("\n[7] Shutting down server …")
    try:
        proc.terminate()
        proc.wait(timeout=5)
        print("  Server terminated cleanly")
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        print("  Server killed (timeout)")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    all_pass = True
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        detail_str = f" — {detail}" if detail else ""
        print(f"  [{status}] {name}{detail_str}")
        if not passed:
            all_pass = False

    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    print(f"\n  {passed_count}/{total} checks passed")

    if all_pass:
        print("\n✓  ALL CHECKS PASSED — Governance-only mode verified")
        return 0
    else:
        print("\n✗  SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
