"""Multi-Model Validation Script for HLF Swarm Coordination

Re-runs a scaled-down swarm test across multiple Ollama models to verify
the HLF pipeline is model-agnostic.

Usage:
    python scripts/multi_model_validation.py [--models MODEL1 MODEL2 ...]

Defaults to a curated set spanning tiers:
    - Top-tier cloud: kimi-k2.6:cloud, deepseek-v4-pro:cloud
    - Mid-tier: qwen3.5:9b, deepseek-r1:14b
    - Lightweight: llama3.2:latest, gemma3:12b-cloud
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# Ensure repo is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hlf_mcp.hlf.agent_spawner import AgentSpawner


MAX_CONCURRENT = 3
TIMEOUT_SEC = 120

AGENTS = [
    {"agent_id": "SchemaDesigner", "role": "designer", "task": "Design DB schema"},
    {"agent_id": "AuthService", "role": "backend", "task": "Implement auth"},
    {"agent_id": "ApiRoutes", "role": "backend", "task": "Write REST routes"},
]

LAYERS = [["SchemaDesigner"], ["AuthService", "ApiRoutes"]]


def run_agent(agent: dict[str, str], model: str) -> dict[str, object]:
    spawner = AgentSpawner(backend="asyncio")
    handle = spawner.spawn(
        agent_id=agent["agent_id"],
        role=agent["role"],
        task=agent["task"],
        model=model,
    )
    result = spawner.wait(handle.agent_id, timeout=TIMEOUT_SEC)
    return {
        "agent_id": agent["agent_id"],
        "model": model,
        "status": result.status,
        "elapsed_ms": result.elapsed_ms,
        "tokens_used": result.tokens_used,
        "stdout": result.stdout[:200],
        "stderr": result.stderr[:200],
        "error": result.error,
    }


def run_for_model(model: str) -> dict[str, object]:
    print(f"\n=== Model: {model} ===")
    agent_map = {a["agent_id"]: a for a in AGENTS}
    results: list[dict[str, object]] = []

    t0 = time.time()
    for layer in LAYERS:
        print(f"  Layer: {layer}")
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
            futures = {
                ex.submit(run_agent, agent_map[aid], model): aid
                for aid in layer
            }
            for fut in futures:
                res = fut.result()
                results.append(res)
                icon = "✅" if res["status"] == "complete" else "❌"
                print(
                    f"    {icon} {res['agent_id']}: {res['status']} "
                    f"in {res['elapsed_ms']}ms, {res['tokens_used']} tokens"
                )
    total_ms = (time.time() - t0) * 1000

    complete = sum(1 for r in results if r["status"] == "complete")
    errors = sum(1 for r in results if r["status"] == "error")

    print(
        f"  Summary: {complete}/{len(AGENTS)} complete, "
        f"{errors} errors, {total_ms:.0f}ms"
    )

    return {
        "model": model,
        "total_agents": len(AGENTS),
        "complete": complete,
        "errors": errors,
        "total_ms": total_ms,
        "agent_results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-model HLF validation")
    parser.add_argument(
        "--models",
        nargs="+",
        default=[
            "kimi-k2.6:cloud",
            "deepseek-v4-pro:cloud",
            "qwen3.5:9b",
            "deepseek-r1:14b",
            "llama3.2:latest",
        ],
        help="Ollama models to validate",
    )
    parser.add_argument(
        "--output",
        default="multi-model-results.json",
        help="Output JSON file",
    )
    args = parser.parse_args()

    all_results: list[dict[str, object]] = []
    for model in args.models:
        all_results.append(run_for_model(model))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n📝 Results written to {args.output}")

    # Summary table
    print("\n=== Multi-Model Validation Summary ===")
    print(f"{'Model':<30} {'Complete':>10} {'Errors':>8} {'Time (ms)':>12}")
    print("-" * 62)
    for r in all_results:
        print(
            f"{r['model']:<30} "
            f"{r['complete']:>10}/{r['total_agents']} "
            f"{r['errors']:>8} "
            f"{r['total_ms']:>12.0f}"
        )

    total_errors = sum(r["errors"] for r in all_results)
    if total_errors == 0:
        print("\n✅ All models passed validation.")
        return 0
    else:
        print(f"\n❌ {total_errors} errors across {len(all_results)} models.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
