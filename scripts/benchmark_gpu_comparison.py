#!/usr/bin/env python3
"""Live GPU benchmark: Solo Solver vs RecursiveMAS Governed Latent Inference.

Compares the same medical diagnosis prompt through both paths.
Captures wall-clock time, VRAM, token counts, and output quality.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# The "killshot" hypothyroid prompt from the stress-test suite
PROMPT_MEDICAL = (
    "A 55-year-old woman presents with fatigue, weight gain, and constipation. "
    "Labs: TSH 8.2, free T4 1.1 (normal). She takes iron supplements for anemia "
    "and omeprazole for GERD. What is the most likely diagnosis, and what is the pathophysiology?"
)

# In-distribution math prompt (where RecursiveMAS should excel)
PROMPT_MATH = (
    "Evaluate the indefinite integral: ∫ x·sin(x) dx. "
    "Show your work step by step."
)

# Simple baseline prompt
PROMPT_SIMPLE = "What is 2+2?"

# Test matrix: run all three prompts
PROMPT_MATRIX = [
    ("math", PROMPT_MATH),
    ("medical", PROMPT_MEDICAL),
    ("simple", PROMPT_SIMPLE),
]


def get_vram_usage() -> dict:
    """Get GPU VRAM usage in MB."""
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / (1024 ** 2)
            reserved = torch.cuda.memory_reserved() / (1024 ** 2)
            return {
                "allocated_mb": round(allocated, 1),
                "reserved_mb": round(reserved, 1),
                "device": torch.cuda.get_device_name(0),
            }
    except ImportError:
        pass
    return {"error": "torch not available"}


def clear_gpu_memory() -> None:
    """Aggressively clear CUDA memory between benchmark runs."""
    try:
        import torch
        import gc
        # Force sync before cleanup
        torch.cuda.synchronize()
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        # Verify cleanup and report
        alloc_mb = torch.cuda.memory_allocated() / (1024 ** 2)
        reserved_mb = torch.cuda.memory_reserved() / (1024 ** 2)
        if alloc_mb > 100:
            print(f"  ⚠️ VRAM not fully freed: allocated={alloc_mb:.1f} MB, reserved={reserved_mb:.1f} MB")
        else:
            print(f"  ✅ GPU memory cleared: allocated={alloc_mb:.1f} MB, reserved={reserved_mb:.1f} MB")
    except Exception:
        pass


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken if available, else approximate."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except (ImportError, Exception):
        # Rough approximation: ~4 chars per token
        return len(text) // 4


def run_solo_solver(prompt: str) -> dict:
    """Run solo Qwen2.5-Math-1.5B solver."""
    print("\n" + "=" * 60)
    print("BENCHMARK: Solo Solver (Qwen2.5-Math-1.5B)")
    print("=" * 60)

    vram_before = get_vram_usage()
    print(f"  VRAM before: {vram_before}")

    try:
        from hlf_mcp.hlf.latent_model_interface import (
            LatentRecursiveSession, RecursiveSessionConfig,
        )
        from hlf_mcp.hlf.model_orchestrator import _resolve_checkpoint_base

        cache_root = str(Path.home() / ".cache" / "huggingface" / "recursivemas")
        solver_path = _resolve_checkpoint_base(
            cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B",
            fallback_hf_id="RecursiveMAS/Sequential-Light-Solver-Qwen2.5-Math-1.5B"
        )
        print(f"  Solver path: {solver_path}")

        config = RecursiveSessionConfig(
            agent_models={"solver": str(solver_path)},
            recursion_rounds=1,
            adapter_task="math",
        )
        session = LatentRecursiveSession(config)

        t0 = time.time()
        session.load_all()
        load_time = time.time() - t0

        vram_after_load = get_vram_usage()

        t0 = time.time()
        result = session.recursive_infer(prompt)
        infer_time = time.time() - t0

        vram_after_infer = get_vram_usage()
        output_text = result.output_text if hasattr(result, 'output_text') else str(result)
        output_tokens = count_tokens(output_text)

        session.unload()
        import torch
        import gc
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        gc.collect()

        return {
            "path": "solo_solver",
            "load_time_s": round(load_time, 2),
            "infer_time_s": round(infer_time, 2),
            "total_time_s": round(load_time + infer_time, 2),
            "output_text": output_text[:500],
            "output_tokens": output_tokens,
            "vram_before_mb": vram_before.get("allocated_mb", 0),
            "vram_after_load_mb": vram_after_load.get("allocated_mb", 0),
            "vram_peak_mb": vram_after_infer.get("allocated_mb", 0),
        }
    except Exception as e:
        return {"path": "solo_solver", "error": str(e)}


def run_recursive_mas_latent(prompt: str) -> dict:
    """Run RecursiveMAS governed latent inference (2 rounds)."""
    print("\n" + "=" * 60)
    print("BENCHMARK: RecursiveMAS Governed Latent (3 models, 2 rounds)")
    print("=" * 60)

    vram_before = get_vram_usage()
    print(f"  VRAM before: {vram_before}")

    try:
        from hlf_mcp.hlf.latent_capsule import governed_latent_infer

        t0 = time.time()
        result = governed_latent_infer(
            prompt,
            agent_id="benchmark-capsule",
            max_rounds=2,
        )
        total_time = time.time() - t0

        vram_after = get_vram_usage()

        result_dict = result if isinstance(result, dict) else result.to_dict()

        output_text = result_dict.get("final_text", "")
        output_tokens = count_tokens(output_text)
        rounds = result_dict.get("rounds_completed", 0)
        gas = result_dict.get("total_gas", 0)
        prov_hashes = result_dict.get("provenance_chain", [])
        capsule_id = result_dict.get("capsule_id", "N/A")
        status = result_dict.get("status", "unknown")
        # Use peak VRAM captured during inference (before session.unload)
        peak_vram = result_dict.get("peak_vram_mb", vram_after.get("allocated_mb", 0))

        return {
            "path": "recursive_mas_governed",
            "load_time_s": "inline",  # governed_latent_infer loads internally
            "infer_time_s": round(total_time, 2),
            "total_time_s": round(total_time, 2),
            "output_text": output_text[:500],
            "output_tokens": output_tokens,
            "vram_before_mb": vram_before.get("allocated_mb", 0),
            "vram_peak_mb": peak_vram,
            "gas_consumed": gas,
            "rounds": rounds,
            "provenance_hashes": len(prov_hashes),
            "capsule_id": capsule_id,
            "status": status,
        }
    except Exception as e:
        import traceback
        return {
            "path": "recursive_mas_governed",
            "error": str(e),
            "traceback": traceback.format_exc()[-500:],
        }


def score_math_output(text: str) -> dict:
    """Score math output quality. Checks for correct integral of x*sin(x)."""
    text_lower = (text or "").lower()
    result = {
        "has_antiderivative": False,
        "has_correct_result": False,
        "has_work_shown": False,
        "quality": "poor",
    }

    # Check for correct antiderivative: -x*cos(x) + sin(x) + C
    correct_variants = [
        "-x*cos(x) + sin(x) + c",
        "-x*cos(x)+sin(x)+c",
        "-x cos(x) + sin(x) + c",
        "-xcos(x)+sin(x)+c",
        "sin(x) - x*cos(x) + c",
        "sin(x)-x*cos(x)+c",
        "sin(x) - x cos(x) + c",
    ]
    for variant in correct_variants:
        if variant in text_lower:
            result["has_antiderivative"] = True
            result["has_correct_result"] = True
            break

    # Partial credit: mentions integration by parts
    if "integration by parts" in text_lower or "∫" in text_lower or "integral" in text_lower:
        result["has_work_shown"] = True

    if result["has_correct_result"]:
        result["quality"] = "excellent"
    elif result["has_work_shown"]:
        result["quality"] = "partial"
    else:
        result["quality"] = "poor"

    return result


def score_medical_output(text: str) -> dict:
    """Score medical output quality."""
    text_lower = (text or "").lower()
    key_terms = ["hypothyroidism", "tsh", "subclinical", "hashimoto", "thyroid",
                 "iron", "omeprazole", "t4", "levothyroxine", "autoimmune"]
    hits = [t for t in key_terms if t in text_lower]
    quality = "poor"
    if len(hits) >= 6:
        quality = "excellent"
    elif len(hits) >= 3:
        quality = "partial"
    return {
        "term_hits": len(hits),
        "hits": hits,
        "total_terms": len(key_terms),
        "quality": quality,
    }


def main() -> None:
    print("=" * 70)
    print("HLF Governed Latent Inference — GPU Benchmark (3-prompt matrix)")
    print("=" * 70)

    all_results = {}

    for prompt_label, prompt_text in PROMPT_MATRIX:
        print(f"\n{'#' * 70}")
        print(f"# PROMPT: {prompt_label} — {prompt_text[:80]}...")
        print(f"{'#' * 70}")

        results = []

        # Clear GPU before starting
        clear_gpu_memory()

        # Run solo solver
        solo = run_solo_solver(prompt_text)
        results.append(solo)
        if "error" in solo:
            print(f"\n  ⚠️ Solo solver error: {solo['error']}")

        # Aggressively clear VRAM between runs
        clear_gpu_memory()

        # Run RecursiveMAS governed latent
        latent = run_recursive_mas_latent(prompt_text)
        results.append(latent)
        if "error" in latent:
            print(f"\n  ⚠️ RecursiveMAS error: {latent['error']}")

        # Print comparison
        print("\n" + "=" * 70)
        print(f"COMPARISON TABLE — {prompt_label}")
        print("=" * 70)

        print(f"\n{'Metric':<30} {'Solo Solver':>15} {'RecursiveMAS':>15}")
        print("-" * 60)

        for label, skey in [
            ("Load time (s)", "load_time_s"),
            ("Inference time (s)", "infer_time_s"),
            ("Total time (s)", "total_time_s"),
            ("Output tokens", "output_tokens"),
            ("VRAM peak (MB)", "vram_peak_mb"),
        ]:
            sv = "N/A" if "error" in solo else str(solo.get(skey, "N/A"))
            lv = "N/A" if "error" in latent else str(latent.get(skey, "N/A"))
            print(f"{label:<30} {sv:>15} {lv:>15}")

        if "gas_consumed" in latent:
            print(f"{'Gas consumed':<30} {'N/A':>15} {str(latent['gas_consumed']):>15}")

        # Quality scoring
        print("\n" + "=" * 70)
        print(f"QUALITY ASSESSMENT — {prompt_label}")
        print("=" * 70)

        if prompt_label == "math":
            solo_score = score_math_output(solo.get("output_text", ""))
            latent_score = score_math_output(latent.get("output_text", ""))
            print(f"\n  Solo Solver quality: {solo_score['quality']}")
            print(f"  RecursiveMAS quality: {latent_score['quality']}")
            results[0]["quality"] = solo_score
            results[1]["quality"] = latent_score
        elif prompt_label == "medical":
            solo_score = score_medical_output(solo.get("output_text", ""))
            latent_score = score_medical_output(latent.get("output_text", ""))
            print(f"\n  Solo Solver: {solo_score['term_hits']}/{solo_score['total_terms']} terms — {solo_score['quality']}")
            print(f"  RecursiveMAS: {latent_score['term_hits']}/{latent_score['total_terms']} terms — {latent_score['quality']}")
            results[0]["quality"] = solo_score
            results[1]["quality"] = latent_score
        else:
            print(f"\n  (quality scoring not applicable for simple prompt)")

        # Show outputs
        print("\n" + "=" * 70)
        print(f"OUTPUT COMPARISON — {prompt_label}")
        print("=" * 70)
        if "output_text" in solo:
            print(f"\n--- Solo Solver Output ---\n{solo['output_text']}")
        if "output_text" in latent:
            print(f"\n--- RecursiveMAS Governed Output ---\n{latent['output_text']}")

        all_results[prompt_label] = results

    # Save all results
    out_path = REPO_ROOT / "benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump({"prompts": list(PROMPT_MATRIX), "results": all_results}, f, indent=2)
    print(f"\n\n  Results saved to: {out_path}")

    print("\n✅ Benchmark complete (all 3 prompts).")


if __name__ == "__main__":
    main()
