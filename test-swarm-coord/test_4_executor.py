#!/usr/bin/env python3
"""Test 4 Executor — run 20-agent e-commerce swarm (NL or HLF).

Usage:
  python test_4_executor.py --mode nl --model deepseek-v4-pro:cloud --output-dir test-4-nl-results
  python test_4_executor.py --mode hlf --model deepseek-v4-pro:cloud --output-dir test-4-hlf-results

Discovers agents from the plan, dispatches them in dependency order,
collects metrics (time, tokens, files written), and writes RESULTS.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# Ensure HLF_MCP is on path
sys.path.insert(0, "C:\\Users\\gerry\\generic_workspace\\HLF_MCP")

from hlf_mcp.hlf.agent_spawner import AgentSpawner
from hlf_mcp.hlf.swarm_compiler import compile_swarm


MAX_CONCURRENT = 5
TIMEOUT_SEC = 300


def load_nl_plan(path: str) -> list[dict[str, Any]]:
    """Parse NL PLAN.md into agent task list.

    Heuristic: find ### Agent N: Name sections and extract role + output files.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    agents: list[dict[str, Any]] = []
    sections = re.split(r"\n###\s+Agent\s+\d+:\s+", text)
    for sec in sections[1:]:
        lines = sec.strip().splitlines()
        if not lines:
            continue
        name = lines[0].strip()
        role = ""
        output_files: list[str] = []
        in_output = False
        for line in lines[1:]:
            if line.startswith("**Role:**") or line.startswith("**Task:**"):
                role = line.split(":", 1)[1].strip().strip("*")
            elif line.startswith("**Output Files:**") or line.startswith("**Output:**"):
                in_output = True
            elif in_output and line.strip().startswith("- "):
                output_files.append(line.strip()[2:].strip())
            elif in_output and not line.strip().startswith("-"):
                in_output = False
        if not role:
            role = f"Implement {name}"
        agents.append({
            "agent_id": name.replace(" ", "").replace("-", ""),
            "role": name,
            "task": f"Agent: {name}\nRole: {role}\nOutput files: {', '.join(output_files)}\n\nRead the PLAN.md and implement your assigned files. Use CommonJS require/module.exports. Do NOT run npm install.",
            "constraints": ["COMMONJS", "NO-INSTALL"],
        })
    return agents


def load_hlf_plan(path: str) -> tuple[list[dict[str, Any]], list[list[str]]]:
    """Parse HLF swarm.hlf into agent task list + execution schedule."""
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    spec, graph, plan = compile_swarm(src)
    agents: list[dict[str, Any]] = []
    for name, decl in spec.agents.items():
        out_str = json.dumps(decl.output_spec) if isinstance(decl.output_spec, dict) else str(decl.output_spec)
        task = f"Agent: {name}\nRole: {decl.role}\nOutput: {out_str}\nConstraints: {', '.join(decl.constraints)}\n\nImplement the assigned files. Use CommonJS require/module.exports. Do NOT run npm install."
        agents.append({
            "agent_id": name,
            "role": decl.role,
            "task": task,
            "constraints": decl.constraints,
        })
    return agents, plan.schedule


def run_agent(agent: dict[str, Any], model: str, output_dir: str) -> dict[str, Any]:
    spawner = AgentSpawner(backend="asyncio", model=model)
    handle = spawner.spawn(
        agent_id=agent["agent_id"],
        role=agent["role"],
        task=agent["task"],
        model=model,
        constraints=agent.get("constraints", []),
    )
    result = spawner.wait(handle.agent_id, timeout=TIMEOUT_SEC)
    # asyncio backend returns immediately; no files to copy from work_dir
    copied: list[str] = []
    return {
        "agent_id": agent["agent_id"],
        "status": result.status,
        "elapsed_ms": result.elapsed_ms,
        "tokens_used": result.tokens_used,
        "files_written": copied or result.files_written,
        "stdout": result.stdout[:500],
        "stderr": result.stderr[:500],
        "error": result.error,
    }


def run_version(mode: str, model: str, output_dir: str) -> dict[str, Any]:
    print(f"\n=== Test 4 {mode.upper()} ===")
    os.makedirs(output_dir, exist_ok=True)
    if mode == "nl":
        agents = load_nl_plan("test-swarm-coord/test-4-nl/PLAN.md")
        schedule: list[list[str]] = []
        # NL has no explicit schedule; run all in one batch (up to MAX_CONCURRENT)
        schedule = [[a["agent_id"] for a in agents]]
    else:
        agents, schedule = load_hlf_plan("test-swarm-coord/test-4-hlf/swarm.hlf")

    agent_map = {a["agent_id"]: a for a in agents}
    results: list[dict[str, Any]] = []
    overall_start = time.time()

    for layer_idx, layer in enumerate(schedule):
        print(f"\n-- Layer {layer_idx + 1}/{len(schedule)}: {layer} --")
        layer_agents = [agent_map[a] for a in layer if a in agent_map]
        if not layer_agents:
            continue
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
            futures = {
                executor.submit(run_agent, agent, model, output_dir): agent
                for agent in layer_agents
            }
            for future in as_completed(futures):
                agent = futures[future]
                try:
                    res = future.result()
                except Exception as exc:
                    res = {
                        "agent_id": agent["agent_id"],
                        "status": "error",
                        "error": str(exc),
                        "elapsed_ms": 0,
                        "tokens_used": 0,
                        "files_written": [],
                        "stdout": "",
                        "stderr": "",
                    }
                results.append(res)
                status_emoji = "✅" if res["status"] == "complete" else "❌"
                print(f"  {status_emoji} {res['agent_id']}: {res['status']} in {res['elapsed_ms']:.0f}ms, {res['tokens_used']} tokens, {len(res['files_written'])} files")

    overall_ms = (time.time() - overall_start) * 1000
    total_tokens = sum(r["tokens_used"] for r in results)
    complete = sum(1 for r in results if r["status"] == "complete")
    errors = sum(1 for r in results if r["status"] == "error")
    timeouts = sum(1 for r in results if r["status"] == "timeout")
    all_files = []
    for r in results:
        all_files.extend(r["files_written"])

    summary = {
        "mode": mode,
        "model": model,
        "total_agents": len(agents),
        "complete": complete,
        "errors": errors,
        "timeouts": timeouts,
        "total_ms": round(overall_ms, 2),
        "total_tokens": total_tokens,
        "files_produced": len(set(all_files)),
        "agent_results": results,
    }

    # Write RESULTS.md
    results_md = os.path.join(output_dir, "RESULTS.md")
    with open(results_md, "w", encoding="utf-8") as f:
        f.write(f"# Test 4 Results: {mode.upper()} 20-Agent E-Commerce Marketplace\n\n")
        f.write(f"**Model:** {model}\n\n")
        f.write(f"**Total Time:** {overall_ms / 1000:.2f}s\n\n")
        f.write(f"**Total Tokens:** {total_tokens}\n\n")
        f.write(f"**Agents Complete:** {complete}/{len(agents)}\n\n")
        f.write(f"**Errors:** {errors}\n\n")
        f.write(f"**Timeouts:** {timeouts}\n\n")
        f.write(f"**Files Produced:** {len(set(all_files))}\n\n")
        f.write("## Per-Agent Results\n\n")
        f.write("| Agent | Status | Time (ms) | Tokens | Files |\n")
        f.write("|-------|--------|-----------|--------|-------|\n")
        for r in results:
            f.write(f"| {r['agent_id']} | {r['status']} | {r['elapsed_ms']:.0f} | {r['tokens_used']} | {len(r['files_written'])} |\n")
        f.write("\n## Errors\n\n")
        for r in results:
            if r.get("error"):
                f.write(f"- **{r['agent_id']}**: {r['error']}\n")
        f.write("\n")

    print(f"\nSummary: {complete}/{len(agents)} complete, {errors} errors, {overall_ms/1000:.2f}s, {total_tokens} tokens")
    print(f"Results written to {results_md}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Test 4 Executor")
    parser.add_argument("--mode", choices=["nl", "hlf"], required=True)
    parser.add_argument("--model", default="deepseek-v4-pro:cloud")
    parser.add_argument("--output-dir", default="test-4-results")
    args = parser.parse_args()
    summary = run_version(args.mode, args.model, args.output_dir)
    print("\nJSON Summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
