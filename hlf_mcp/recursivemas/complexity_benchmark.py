"""Complexity-Scale Benchmark for FunctionGemma / RecursiveMAS local models.

Maps the capability boundary of local models by testing tool-call execution
across 5 escalating complexity tiers. Produces a capability score that agents
can use to decide local vs cloud routing.

Usage:
    # Test the fine-tuned FunctionGemma (default)
    python -m hlf_mcp.recursivemas.complexity_benchmark

    # Test a cloud model for comparison
    python -m hlf_mcp.recursivemas.complexity_benchmark --model deepseek-v4-pro:cloud

    # Test all available local models
    python -m hlf_mcp.recursivemas.complexity_benchmark --all-local
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# ── Paths ────────────────────────────────────────────────────────────────
HLF_MCP_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = Path(os.environ.get("FUNCTIONGEMMA_OUTPUT",
    str(HLF_MCP_ROOT.parent / "functiongemma_ft")))
RESULTS_PATH = OUTPUT_DIR / "complexity_benchmark_results.json"
RING_RESULTS_PATH = OUTPUT_DIR / "ring_benchmark_results.json"

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# ── System Resource Monitoring ────────────────────────────────────────────
import psutil
import subprocess


def get_gpu_memory_mb() -> tuple:
    """Returns (free_mb, total_mb) for first NVIDIA GPU, or (0, 0)."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        free, total = result.stdout.strip().split(", ")
        return int(free), int(total)
    except Exception:
        return 0, 0


def check_resources(verbose: bool = True) -> dict:
    """Check system resources and return status. Warns if thresholds breached."""
    ram = psutil.virtual_memory()
    free_ram_gb = ram.available / (1024**3)
    total_ram_gb = ram.total / (1024**3)
    ram_pct = ram.percent

    gpu_free, gpu_total = get_gpu_memory_mb()
    gpu_free_gb = gpu_free / 1024 if gpu_free else 0
    gpu_pct = (1 - gpu_free / gpu_total) * 100 if gpu_total else 0

    cpu_pct = psutil.cpu_percent(interval=0.5)

    status = {
        "free_ram_gb": round(free_ram_gb, 1),
        "total_ram_gb": round(total_ram_gb, 1),
        "ram_pct": ram_pct,
        "free_vram_gb": round(gpu_free_gb, 1),
        "total_vram_gb": round(gpu_total / 1024, 1) if gpu_total else 0,
        "gpu_pct": round(gpu_pct, 1),
        "cpu_pct": cpu_pct,
        "ok": True,
        "warnings": [],
    }

    if free_ram_gb < 4:
        status["ok"] = False
        status["warnings"].append(f"LOW RAM: {free_ram_gb:.1f} GB free")
    elif free_ram_gb < 8:
        status["warnings"].append(f"RAM getting low: {free_ram_gb:.1f} GB free")

    if gpu_total > 0 and gpu_free < 1024:
        status["ok"] = False
        status["warnings"].append(f"LOW VRAM: {gpu_free} MB free")
    elif gpu_total > 0 and gpu_free < 2048:
        status["warnings"].append(f"VRAM getting low: {gpu_free_gb:.1f} GB free")

    if verbose:
        print(f"  [RESOURCES] RAM: {free_ram_gb:.1f}/{total_ram_gb:.1f} GB free ({ram_pct:.0f}%) | "
              f"VRAM: {gpu_free_gb:.1f}/{gpu_total / 1024:.1f} GB free ({gpu_pct:.0f}%) | "
              f"CPU: {cpu_pct:.0f}%")
        for w in status["warnings"]:
            print(f"  [WARNING] {w}")

    return status


# ── Complexity Tiers ────────────────────────────────────────────────────
#
# Tier 0: Trivial — no tools needed, just factual response
# Tier 1: Single Action — one tool call, straightforward
# Tier 2: Compound — two related tool calls
# Tier 3: Multi-Step Composition — 3-5 tool calls in sequence
# Tier 4: Stateful Branching — depends on prior results, conditional logic
# Tier 5: Autonomous Agent — open-ended, requires planning + execution
#

BENCHMARK_CASES = {
    # ── Tier 0: Trivial (no tool needed) ────────────────────────────────
    "t0_greeting": {
        "tier": 0,
        "prompt": "Hello, what can you help me with today?",
        "expected_tool": None,
        "expected_args_check": None,
        "description": "Basic greeting — no tool required",
    },
    "t0_fact": {
        "tier": 0,
        "prompt": "What is the capital of France?",
        "expected_tool": None,
        "expected_args_check": None,
        "description": "Simple factual question — no tool required",
    },
    "t0_explain": {
        "tier": 0,
        "prompt": "Explain what a Python decorator is in one sentence.",
        "expected_tool": None,
        "expected_args_check": None,
        "description": "Short explanation — no tool required",
    },

    # ── Tier 1: Single Action ───────────────────────────────────────────
    "t1_search_simple": {
        "tier": 1,
        "prompt": "Search for documentation about Python's asyncio.run() function.",
        "expected_tool": "search_knowledge",
        "expected_args_check": lambda a: "asyncio" in str(a).lower(),
        "description": "Single search_knowledge call",
    },
    "t1_command_simple": {
        "tier": 1,
        "prompt": "Run the command 'pip list' to show installed packages.",
        "expected_tool": "run_command",
        "expected_args_check": lambda a: "pip" in str(a).lower(),
        "description": "Single run_command call",
    },
    "t1_write_simple": {
        "tier": 1,
        "prompt": "Write a Python function that adds two numbers and save it to utils/add.py.",
        "expected_tool": "write_file",
        "expected_args_check": lambda a: "add" in str(a).lower(),
        "description": "Single write_file call",
    },

    # ── Tier 2: Compound (2-tool sequences) ─────────────────────────────
    "t2_search_then_write": {
        "tier": 2,
        "prompt": "Search for Python argparse best practices, then save the findings to docs/argparse_notes.md.",
        "expected_tool": "search_knowledge",
        "need_secondary": "write_file",
        "expected_args_check": lambda a: "argparse" in str(a).lower(),
        "description": "Search then write — 2-tool chain",
    },
    "t2_write_then_run": {
        "tier": 2,
        "prompt": "Create a Python script at scripts/hello.py that prints 'Hello World', then run it.",
        "expected_tool": "write_file",
        "need_secondary": "run_command",
        "expected_args_check": lambda a: "hello" in str(a).lower(),
        "description": "Write then execute — 2-tool chain",
    },
    "t2_investigate": {
        "tier": 2,
        "prompt": "Search for how to set up PostgreSQL on Ubuntu, then write the instructions to a file at docs/postgres_setup.md.",
        "expected_tool": "search_knowledge",
        "need_secondary": "write_file",
        "expected_args_check": lambda a: "postgres" in str(a).lower() or "PostgreSQL" in str(a),
        "description": "Research then document — 2-tool chain",
    },

    # ── Tier 3: Multi-Step Composition (3-5 tools) ──────────────────────
    "t3_scaffold_project": {
        "tier": 3,
        "prompt": (
            "Set up a new FastAPI project: "
            "1) Create app/main.py with a health endpoint, "
            "2) Create requirements.txt with fastapi and uvicorn, "
            "3) Run pip install -r requirements.txt to install dependencies."
        ),
        "expected_primary": ["write_file"],
        "min_tool_calls": 3,
        "expected_args_check": lambda results: len(results) >= 3,
        "description": "Multi-file project scaffold with dependency install",
    },
    "t3_data_pipeline": {
        "tier": 3,
        "prompt": (
            "Build a data processing pipeline: "
            "1) Create src/extract.py with a CSV extractor, "
            "2) Create src/transform.py with data cleaning, "
            "3) Create src/load.py that saves to JSON, "
            "4) Run the pipeline by calling 'python src/extract.py'."
        ),
        "expected_primary": ["write_file"],
        "min_tool_calls": 4,
        "expected_args_check": lambda results: len(results) >= 4,
        "description": "4-step data pipeline creation + execution",
    },
    "t3_bug_investigation": {
        "tier": 3,
        "prompt": (
            "Investigate a bug report: "
            "1) Search for common causes of 'ConnectionRefusedError' in Python, "
            "2) Create a diagnostic script at scripts/diagnose_connection.py, "
            "3) Run the diagnostic script."
        ),
        "expected_primary": ["search_knowledge"],
        "min_tool_calls": 3,
        "expected_args_check": lambda results: len(results) >= 3,
        "description": "Investigate → create diagnostic → run — 3-step chain",
    },

    # ── Tier 4: Stateful Branching ──────────────────────────────────────
    "t4_conditional_deploy": {
        "tier": 4,
        "prompt": (
            "Check if Docker is running by running 'docker ps'. "
            "If it succeeds, deploy the app with 'docker-compose up -d'. "
            "If it fails, write an error message to deploy_status.txt saying Docker is not available."
        ),
        "expected_primary": ["run_command"],
        "min_tool_calls": 2,
        "expected_args_check": lambda results: len(results) >= 2 and "docker" in str(results).lower(),
        "description": "Conditional branching based on command output",
    },
    "t4_self_healing": {
        "tier": 4,
        "prompt": (
            "Try running 'python -c \"import nonexistent_module\"'. "
            "If the import fails, search for how to install nonexistent-module, "
            "then create an install script and try again."
        ),
        "expected_primary": ["run_command"],
        "min_tool_calls": 2,
        "expected_args_check": lambda results: len(results) >= 2,
        "description": "Execute → handle failure → remediate",
    },

    # ── Tier 5: Autonomous Agent ────────────────────────────────────────
    "t5_fullstack_scaffold": {
        "tier": 5,
        "prompt": (
            "I need a complete microservice with tests: "
            "1) Create src/service.py with a Flask app that has /health and /api/data endpoints, "
            "2) Create tests/test_service.py with pytest tests for both endpoints, "
            "3) Create requirements.txt with flask and pytest, "
            "4) Install dependencies, "
            "5) Run the tests."
        ),
        "expected_primary": ["write_file"],
        "min_tool_calls": 5,
        "expected_args_check": lambda results: len(results) >= 5,
        "description": "Full autonomous microservice creation + test + verify",
    },
    "t5_system_diagnostic": {
        "tier": 5,
        "prompt": (
            "Diagnose this system issue: Users report the API is slow. "
            "1) Search for common causes of API latency, "
            "2) Create a performance testing script at scripts/perf_test.py, "
            "3) Run the performance script, "
            "4) Based on results, create a fix script, "
            "5) Apply the fix and verify."
        ),
        "expected_primary": ["search_knowledge"],
        "min_tool_calls": 4,
        "expected_args_check": lambda results: len(results) >= 4,
        "description": "Full diagnostic → implement → verify loop",
    },
}


# ── Ollama Client ───────────────────────────────────────────────────────

def ollama_chat(model: str, prompt: str, tools: list | None = None,
                temperature: float = 0.1) -> dict:
    """Send a chat request to Ollama with optional tools."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if tools:
        payload["tools"] = tools

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# ── Tool Schemas (same as FunctionGemma learns) ─────────────────────────

BENCHMARK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write code or text content to a file on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the file to write."},
                    "content": {"type": "string", "description": "Content to write to the file."},
                    "language": {"type": "string", "description": "Programming language of the content."},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."},
                    "cwd": {"type": "string", "description": "Working directory for the command."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search a knowledge base for relevant information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "max_results": {"type": "integer", "description": "Maximum number of results."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "no_action",
            "description": "No tool action is needed — the response is complete as-is.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Why no action is needed."},
                },
                "required": ["summary"],
            },
        },
    },
]


# ── RecursiveMAS Ring Benchmark ─────────────────────────────────────────
#
# Tests the FULL 4-model ring (Coder→Router→Critic→Solver) as a system.
# This is NOT the same as testing individual Ollama models — the ring uses
# latent-space communication via trained CrossModelAdapters, with ONLY the
# final step decoded to text.
#
# Ring: Coder(Qwen0.5B,896d) → Router(funcG,640d) → Critic(Gemma3,1152d)
#       → Solver(Qwen1.5B,1536d) → Coder

def benchmark_recursivemas_ring(cases: list = None, recursions: int = 3,
                                 verbose: bool = True) -> dict:
    """Benchmark the RecursiveMAS 4-model ring across complexity tiers.

    The ring processes prompts through pure latent-space reasoning.
    Output quality is evaluated by the Coder's final decoded text.
    """
    import warnings
    warnings.filterwarnings("ignore")

    if verbose:
        print("=" * 72)
        print(f"MICROSQUAD 4-MODEL RING BENCHMARK")
        print(f"Ring: Coder(896d)→Router(640d)→Critic(1152d)→Solver(1536d)")
        print(f"Recursions: {recursions} | Latent-only (no text between steps)")
        print("=" * 72)
        res_status = check_resources(verbose=True)
        if not res_status["ok"]:
            print("  [ABORT] System resources too low for ring benchmark.")
            return {"error": "Resources too low", "resource_status": res_status, "results": []}

    # Load ring models and adapters
    try:
        from hlf_mcp.recursivemas.inference import (
            load_models, load_adapters, run_recursive_inference
        )
    except ImportError as e:
        return {"error": f"Import failed: {e}", "results": []}

    try:
        if verbose:
            print("  Loading MicroSquad ring models (this is the heavy part)...")
            print("  Models: Qwen2.5-0.5B + FunctionGemma-270M + Gemma3n + Qwen1.5B")
        models = load_models()
        coder, coder_tok, router, router_tok, critic, critic_tok, solver, solver_tok = models
        adapter_dir = str(HLF_MCP_ROOT / "trained_adapters")
        q2f, f2g, g2q15, q152q05 = load_adapters(
            adapter_dir, next(coder.parameters()).device
        )
    except Exception as e:
        print(f"  ERROR loading ring: {e}")
        return {"error": str(e), "results": []}

    case_ids = cases or list(BENCHMARK_CASES.keys())
    results = []
    tier_scores = {0: [], 1: [], 2: [], 3: [], 4: [], 5: []}

    for case_id in case_ids:
        case_def = BENCHMARK_CASES[case_id]
        tier = case_def["tier"]

        if verbose:
            print(f"\n  [{case_id}] Tier {tier}: {case_def['description']}")

        t0 = time.time()

        try:
            # Run through the full RecursiveMAS ring
            output_text, telemetry = run_recursive_inference(
                case_def["prompt"],
                coder, coder_tok, router, router_tok,
                critic, critic_tok, solver, solver_tok,
                q2f, f2g, g2q15, q152q05,
                num_recursions=recursions,
                max_new_tokens=128,
            )
            elapsed_ms = (time.time() - t0) * 1000

            # Evaluate ring output quality
            eval_result = evaluate_ring_output(case_id, case_def, output_text, telemetry)
            eval_result["elapsed_ms"] = round(elapsed_ms)
            eval_result["ring_model"] = "RecursiveMAS-4Model-Ring"

        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            eval_result = {
                "case_id": case_id,
                "tier": tier,
                "description": case_def["description"],
                "passed": False,
                "error": str(e)[:200],
                "elapsed_ms": round(elapsed_ms),
                "score": 0.0,
                "output_text": f"ERROR: {e}",
                "ring_model": "RecursiveMAS-4Model-Ring",
            }

        results.append(eval_result)
        tier_scores[tier].append(eval_result["score"])

        if verbose:
            status = "✅" if eval_result["passed"] else "❌"
            output_preview = eval_result.get("output_text", "")[:80]
            print(f"    {status} score={eval_result['score']:.2f} "
                  f"({elapsed_ms:.0f}ms) → \"{output_preview}...\"")

    # ── Ring tier summaries ─────────────────────────────────────────────
    tier_summaries = {}
    for tier in range(6):
        scores = tier_scores[tier]
        if scores:
            avg = sum(scores) / len(scores)
            passed = sum(1 for s in scores if s >= 0.60)
            tier_summaries[f"tier_{tier}"] = {
                "avg_score": round(avg, 3),
                "pass_rate": f"{passed}/{len(scores)}",
                "verdict": "CAPABLE" if avg >= 0.60 else "PARTIAL" if avg >= 0.30 else "NOT_CAPABLE",
            }

    # ── Capability boundary ─────────────────────────────────────────────
    capability_boundary = -1
    for tier in range(6):
        scores = tier_scores[tier]
        if scores:
            avg = sum(scores) / len(scores)
            if avg >= 0.60:
                capability_boundary = tier

    all_scores = [r["score"] for r in results]
    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
    overall_passed = sum(1 for s in all_scores if s >= 0.60)

    summary = {
        "model": "RecursiveMAS-4Model-Ring",
        "recursions": recursions,
        "total_cases": len(results),
        "passed": overall_passed,
        "failed": len(results) - overall_passed,
        "overall_avg_score": round(overall_avg, 3),
        "capability_boundary_tier": capability_boundary,
        "capability_boundary_label": {
            -1: "NONE", 0: "TRIVIAL_ONLY", 1: "SINGLE_ACTION",
            2: "COMPOUND", 3: "MULTI_STEP", 4: "STATEFUL", 5: "AUTONOMOUS",
        }.get(capability_boundary, "UNKNOWN"),
        "tier_summaries": tier_summaries,
        "total_elapsed_ms": sum(r.get("elapsed_ms", 0) for r in results),
        "results": results,
    }

    if verbose:
        print("\n" + "=" * 72)
        print("RING CAPABILITY MAP")
        print("=" * 72)
        for tier in range(6):
            ts = tier_summaries.get(f"tier_{tier}")
            if ts:
                labels = {0: "TRIVIAL", 1: "SINGLE", 2: "COMPOUND",
                          3: "MULTI-STEP", 4: "STATEFUL", 5: "AUTONOMOUS"}
                print(f"  Tier {tier} ({labels.get(tier, '?')}): "
                      f"{ts['avg_score']:.2f} avg | {ts['pass_rate']} pass | {ts['verdict']}")
        print(f"\n  📍 Ring capability boundary: Tier {capability_boundary} "
              f"({summary['capability_boundary_label']})")
        print(f"  📊 Ring overall: {overall_passed}/{len(results)} passed "
              f"({overall_avg:.2f} avg)")

    # Save ring results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(RING_RESULTS_PATH, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def evaluate_ring_output(case_id: str, case_def: dict, output_text: str,
                          telemetry) -> dict:
    """Evaluate RecursiveMAS ring output quality.

    The ring produces TEXT (not tool calls), so we evaluate:
    1. Did it produce meaningful text? (not empty, not pure gibberish)
    2. Did the ring stay stable? (no circuit breaker trips)
    3. For tool-call tiers: does output mention relevant concepts?
    4. Is the hidden state norm stable? (not exploding)
    """
    result = {
        "case_id": case_id,
        "tier": case_def["tier"],
        "description": case_def["description"],
        "passed": False,
        "output_text": output_text[:300] if output_text else "",
        "score": 0.0,
        "circuit_ok": True,
        "norm_stable": True,
        "has_output": False,
        "relevant_concepts": False,
    }

    # 1. Did it produce output?
    if not output_text or len(output_text.strip()) < 3:
        return result
    result["has_output"] = True
    result["score"] += 0.25

    # 2. Circuit breaker status
    norms = [r["out_norm"] for r in telemetry.rounds] if telemetry.rounds else []
    if norms:
        max_norm = max(norms)
        if max_norm > 500:
            result["circuit_ok"] = False
        else:
            result["score"] += 0.25
    else:
        result["score"] += 0.25  # No norms = no circuit issues

    # 3. Norm stability (not exploding)
    if len(norms) >= 2:
        avg_norm = sum(norms) / len(norms)
        # Check if norms are within reasonable bounds
        if avg_norm < 300:
            result["norm_stable"] = True
            result["score"] += 0.25
        else:
            result["norm_stable"] = False
    else:
        result["score"] += 0.25

    # 4. For Tier 1+: does output touch on expected concepts?
    if case_def["tier"] > 0:
        prompt = case_def["prompt"].lower()
        output_lower = output_text.lower()
        # Extract key terms from prompt
        key_terms = set()
        for word in prompt.split():
            cleaned = word.strip(".,!?()\":;")
            if len(cleaned) > 3 and cleaned not in {
                "that", "this", "with", "from", "your", "have", "what",
                "when", "where", "which", "would", "could", "should",
                "their", "there", "about", "please", "need",
            }:
                key_terms.add(cleaned)

        matching = sum(1 for term in key_terms if term in output_lower)
        if len(key_terms) > 0 and matching / len(key_terms) > 0.15:
            result["relevant_concepts"] = True
            result["score"] += 0.25
    else:
        # Tier 0: any coherent response is fine
        result["score"] += 0.25

    result["passed"] = result["score"] >= 0.60
    return result

def evaluate_case(case_id: str, case_def: dict, response: dict) -> dict:
    """Evaluate a single benchmark case against model response."""
    result = {
        "case_id": case_id,
        "tier": case_def["tier"],
        "description": case_def["description"],
        "prompt_tokens": len(case_def["prompt"].split()),
        "passed": False,
        "tool_calls_count": 0,
        "tool_names_called": [],
        "expected_tool_matched": False,
        "secondary_matched": False,
        "min_tool_count_met": False,
        "error": None,
        "response_text": None,
        "score": 0.0,
    }

    if "error" in response:
        result["error"] = response["error"]
        return result

    # Check message response
    message = response.get("message", {})
    result["response_text"] = message.get("content", "")[:200]

    # Check tool calls
    tool_calls = message.get("tool_calls", [])
    result["tool_calls_count"] = len(tool_calls)
    result["tool_names_called"] = [
        tc.get("function", {}).get("name", "unknown") for tc in tool_calls
    ]

    if not tool_calls:
        # Tier 0 expects no tool calls
        if case_def["tier"] == 0 and case_def.get("expected_tool") is None:
            result["passed"] = True
            result["score"] = 1.0
        return result

    # Extract tool call arguments for inspection
    all_args = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        all_args.append(fn.get("arguments", {}))

    # Check expected primary tool
    expected = case_def.get("expected_tool")
    expected_primary = case_def.get("expected_primary", [])

    if expected:
        result["expected_tool_matched"] = any(
            expected in tc.get("function", {}).get("name", "")
            for tc in tool_calls
        )
    elif expected_primary:
        result["expected_tool_matched"] = any(
            ep in result["tool_names_called"] for ep in expected_primary
        )

    # Check secondary tool requirement (Tier 2+)
    need_secondary = case_def.get("need_secondary")
    if need_secondary:
        result["secondary_matched"] = need_secondary in result["tool_names_called"]

    # Check minimum tool call count (Tier 3+)
    min_calls = case_def.get("min_tool_calls", 0)
    if min_calls > 0:
        result["min_tool_count_met"] = result["tool_calls_count"] >= min_calls

    # Check argument quality
    args_check = case_def.get("expected_args_check")
    args_ok = True
    if args_check:
        try:
            if callable(args_check):
                # Pass the arguments dict/list
                if len(all_args) == 1:
                    args_ok = args_check(all_args[0])
                else:
                    args_ok = args_check(all_args)
            else:
                args_ok = str(all_args).find(args_check) >= 0
        except Exception:
            args_ok = False

    # ── Score calculation ──────────────────────────────────────────────
    score = 0.0
    if result["tool_calls_count"] > 0:
        # Tool selection accuracy (40%)
        if result["expected_tool_matched"]:
            score += 0.40
        # Secondary tool presence (20%)
        if need_secondary:
            if result["secondary_matched"]:
                score += 0.20
        else:
            score += 0.20  # No secondary needed = free points
        # Min count met (20%)
        if min_calls > 0:
            if result["min_tool_count_met"]:
                score += 0.20
            else:
                ratio = min(result["tool_calls_count"] / max(1, min_calls), 1.0)
                score += 0.20 * ratio
        else:
            score += 0.20
        # Argument quality (20%)
        score += 0.20 if args_ok else 0.0

    result["score"] = score
    result["passed"] = score >= 0.60  # 60% threshold for "capable"

    return result


# ── Main Benchmark Runner ───────────────────────────────────────────────

def run_benchmark(model: str = "functiongemma:270m", cases: list | None = None,
                  verbose: bool = True) -> dict:
    """Run the complexity benchmark against a model.

    Args:
        model: Ollama model name.
        cases: List of case IDs to run. None = all cases.
        verbose: Print progress.

    Returns:
        Dict with per-case results, tier summaries, and capability map.
    """
    if verbose:
        print("=" * 72)
        print(f"COMPLEXITY-SCALE BENCHMARK: {model}")
        print("=" * 72)
        check_resources(verbose=True)

    case_ids = cases or list(BENCHMARK_CASES.keys())
    results = []
    tier_scores = {0: [], 1: [], 2: [], 3: [], 4: [], 5: []}

    for case_id in case_ids:
        case_def = BENCHMARK_CASES[case_id]
        tier = case_def["tier"]

        if verbose:
            print(f"\n  [{case_id}] Tier {tier}: {case_def['description']}")

        t0 = time.time()
        response = ollama_chat(
            model=model,
            prompt=case_def["prompt"],
            tools=BENCHMARK_TOOLS if tier > 0 else None,
        )
        elapsed_ms = (time.time() - t0) * 1000

        eval_result = evaluate_case(case_id, case_def, response)
        eval_result["elapsed_ms"] = round(elapsed_ms)
        eval_result["model"] = model

        results.append(eval_result)
        tier_scores[tier].append(eval_result["score"])

        if verbose:
            tool_names = eval_result["tool_names_called"]
            tools_str = ", ".join(tool_names) if tool_names else "none"
            status = "✅" if eval_result["passed"] else "❌"
            print(f"    {status} score={eval_result['score']:.2f} "
                  f"tools=[{tools_str}] ({elapsed_ms:.0f}ms)")

    # ── Tier summaries ──────────────────────────────────────────────────
    tier_summaries = {}
    for tier in range(6):
        scores = tier_scores[tier]
        if scores:
            avg = sum(scores) / len(scores)
            passed = sum(1 for s in scores if s >= 0.60)
            tier_summaries[f"tier_{tier}"] = {
                "avg_score": round(avg, 3),
                "pass_rate": f"{passed}/{len(scores)}",
                "verdict": "CAPABLE" if avg >= 0.60 else "PARTIAL" if avg >= 0.30 else "NOT_CAPABLE",
            }

    # ── Capability boundary ─────────────────────────────────────────────
    # Find the highest tier where avg_score >= 0.60
    capability_boundary = -1
    for tier in range(6):
        scores = tier_scores[tier]
        if scores:
            avg = sum(scores) / len(scores)
            if avg >= 0.60:
                capability_boundary = tier

    # ── Overall metrics ─────────────────────────────────────────────────
    all_scores = [r["score"] for r in results]
    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
    overall_passed = sum(1 for s in all_scores if s >= 0.60)

    summary = {
        "model": model,
        "total_cases": len(results),
        "passed": overall_passed,
        "failed": len(results) - overall_passed,
        "overall_avg_score": round(overall_avg, 3),
        "capability_boundary_tier": capability_boundary,
        "capability_boundary_label": {
            -1: "NONE",
            0: "TRIVIAL_ONLY",
            1: "SINGLE_ACTION",
            2: "COMPOUND",
            3: "MULTI_STEP",
            4: "STATEFUL",
            5: "AUTONOMOUS",
        }.get(capability_boundary, "UNKNOWN"),
        "tier_summaries": tier_summaries,
        "total_elapsed_ms": sum(r.get("elapsed_ms", 0) for r in results),
        "results": results,
    }

    if verbose:
        print("\n" + "=" * 72)
        print("CAPABILITY MAP")
        print("=" * 72)
        for tier in range(6):
            ts = tier_summaries.get(f"tier_{tier}")
            if ts:
                labels = {0: "TRIVIAL", 1: "SINGLE", 2: "COMPOUND",
                          3: "MULTI-STEP", 4: "STATEFUL", 5: "AUTONOMOUS"}
                print(f"  Tier {tier} ({labels.get(tier, '?')}): "
                      f"{ts['avg_score']:.2f} avg | {ts['pass_rate']} pass | {ts['verdict']}")
        print(f"\n  📍 Capability boundary: Tier {capability_boundary} "
              f"({summary['capability_boundary_label']})")
        print(f"  📊 Overall: {overall_passed}/{len(results)} passed "
              f"({overall_avg:.2f} avg)")
        print("=" * 72)

    return summary


def compare_models(models: list[str]):
    """Run benchmark across multiple models and compare."""
    all_summaries = []
    for model in models:
        print(f"\n{'#' * 72}")
        print(f"# TESTING: {model}")
        print(f"{'#' * 72}")
        summary = run_benchmark(model=model)
        all_summaries.append(summary)

    print("\n\n" + "=" * 72)
    print("MODEL COMPARISON")
    print("=" * 72)
    print(f"{'Model':<35} {'Score':>6} {'Boundary':>12} {'Passed':>8}")
    print("-" * 72)
    for s in all_summaries:
        print(f"{s['model']:<35} {s['overall_avg_score']:>6.3f} "
              f"{s['capability_boundary_label']:>12} "
              f"{s['passed']}/{s['total_cases']:>7}")

    # Save comparison
    OUTPUT_DIR.mkdir(exist_ok=True)
    compare_path = OUTPUT_DIR / "model_comparison.json"
    with open(compare_path, "w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"\nComparison saved to {compare_path}")

    return all_summaries


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Complexity-scale benchmark for FunctionGemma / RecursiveMAS"
    )
    parser.add_argument(
        "--model", "-m",
        default="functiongemma:270m",
        help="Ollama model to benchmark (default: functiongemma:270m)",
    )
    parser.add_argument(
        "--all-local",
        action="store_true",
        help="Benchmark all available local models",
    )
    parser.add_argument(
        "--compare",
        nargs="+",
        help="Compare multiple models (space-separated)",
    )
    parser.add_argument(
        "--tiers",
        nargs="+",
        type=int,
        help="Only run specific tiers (e.g., --tiers 0 1 2)",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(RESULTS_PATH),
        help="Output path for results JSON",
    )
    parser.add_argument(
        "--ring",
        action="store_true",
        help="Benchmark the RecursiveMAS 4-model ring (Coder→Router→Critic→Solver)",
    )
    parser.add_argument(
        "--full-suite",
        action="store_true",
        help="Run full suite: individual model test + RecursiveMAS ring test",
    )
    parser.add_argument(
        "--recursions", "-r",
        type=int, default=3,
        help="Number of ring recursions (default: 3)",
    )

    args = parser.parse_args()

    # Filter by tiers if specified
    cases = None
    if args.tiers:
        cases = [
            cid for cid, cdef in BENCHMARK_CASES.items()
            if cdef["tier"] in args.tiers
        ]

    if args.full_suite:
        # Run individual model benchmark + ring benchmark
        print("#" * 72)
        print("# FULL SUITE: Individual Model + RecursiveMAS Ring")
        print("#" * 72)

        # Part 1: Individual model
        summary = run_benchmark(model=args.model, cases=cases)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)

        # Part 2: RecursiveMAS ring
        print("\n")
        ring_summary = benchmark_recursivemas_ring(
            cases=cases, recursions=args.recursions
        )

        # Combined comparison
        print("\n\n" + "=" * 72)
        print("FULL SUITE COMPARISON")
        print("=" * 72)
        print(f"  Individual ({args.model}):  "
              f"score={summary['overall_avg_score']:.3f}  "
              f"boundary={summary['capability_boundary_label']}  "
              f"passed={summary['passed']}/{summary['total_cases']}")
        print(f"  RecursiveMAS Ring:        "
              f"score={ring_summary['overall_avg_score']:.3f}  "
              f"boundary={ring_summary['capability_boundary_label']}  "
              f"passed={ring_summary['passed']}/{ring_summary['total_cases']}")

        # Save combined
        combined = {
            "individual_model": summary,
            "recursivemas_ring": ring_summary,
        }
        combined_path = OUTPUT_DIR / "full_suite_results.json"
        with open(combined_path, "w") as f:
            json.dump(combined, f, indent=2)
        print(f"\nFull suite results saved to {combined_path}")

        return 0

    if args.ring:
        benchmark_recursivemas_ring(cases=cases, recursions=args.recursions)
        return 0

    if args.all_local:
        # Discover local models from Ollama
        try:
            resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            models_data = resp.json()
            local_models = [
                m["name"] for m in models_data.get("models", [])
                if ":" in m.get("name", "")
            ]
            if not local_models:
                print("No local models found in Ollama.")
                return 1
            print(f"Found {len(local_models)} local models: {', '.join(local_models[:10])}...")
            compare_models(local_models)
        except Exception as e:
            print(f"Error discovering models: {e}")
            return 1
        return 0

    if args.compare:
        compare_models(args.compare)
        return 0

    # Filter by tiers if specified
    cases = None
    if args.tiers:
        cases = [
            cid for cid, cdef in BENCHMARK_CASES.items()
            if cdef["tier"] in args.tiers
        ]

    summary = run_benchmark(model=args.model, cases=cases)

    # Save results
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved to {args.output}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
