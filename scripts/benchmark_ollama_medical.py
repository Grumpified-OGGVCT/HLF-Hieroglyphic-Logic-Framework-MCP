#!/usr/bin/env python3
"""Ollama Medical Model Benchmark: medgemma:4b vs PyTorch Solo vs RecursiveMAS.

Tests whether a domain-specific Ollama model (medgemma:4b) produces better
medical output than Qwen2.5-Math-1.5B on the hypothyroid prompt.

All paths wrapped in HLF governance envelope (manifest, gas, audit entry).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROMPT_MEDICAL = (
    "A 55-year-old woman presents with fatigue, weight gain, and constipation. "
    "Labs: TSH 8.2, free T4 1.1 (normal). She takes iron supplements for anemia "
    "and omeprazole for GERD. What is the most likely diagnosis, and what is the pathophysiology?"
)

# Available medical models to try (in order of preference)
MEDICAL_MODELS = [
    "medgemma:4b",
    "MedAIBase/MedGemma1.0:4b",
    "gemma3n:latest",      # fallback: general but small
    "phi4-mini-reasoning:latest",  # fallback: reasoning-capable
]


def query_ollama(model: str, prompt: str, timeout: int = 120) -> dict:
    """Query Ollama API for text generation."""
    import httpx

    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    url = f"{ollama_host}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,    # low temp for factual medical
            "num_predict": 512,    # enough for diagnosis + pathophysiology
        },
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return {
                "model": model,
                "output_text": data.get("response", ""),
                "total_duration_ms": data.get("total_duration", 0) / 1_000_000,
                "eval_count": data.get("eval_count", 0),
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "error": None,
            }
    except Exception as e:
        return {
            "model": model,
            "output_text": "",
            "error": str(e),
        }


def run_ollama_governed(prompt: str, model: str) -> dict:
    """Run Ollama model with governance envelope (manifest, gas, audit hash)."""
    print(f"\n{'=' * 60}")
    print(f"BENCHMARK: Ollama Governed ({model})")
    print(f"{'=' * 60}")

    t0 = time.time()

    # Build capability manifest for medical Solver
    manifest = {
        "agent_id": f"ollama-governed-{model.replace('/', '-').replace(':', '-')}",
        "tier": "hearth",
        "allowed_data": ["symptoms", "labs", "diagnosis", "medications"],
        "denied_data": ["patient_name", "ssn", "dob", "address"],
        "max_gas": 500,
        "effect_class": "medical_inference",
        "model_backend": f"ollama:{model}",
    }

    # Query Ollama
    result = query_ollama(model, prompt)

    elapsed = time.time() - t0

    output_text = result.get("output_text", "")
    error = result.get("error")

    # Build governance audit entry
    audit = {
        "capsule_id": hashlib.sha256(
            f"{manifest['agent_id']}:{prompt[:50]}:{time.time()}".encode()
        ).hexdigest()[:16],
        "manifest_hash": hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()[:16],
        "output_hash": hashlib.sha256(
            output_text.encode() if output_text else b""
        ).hexdigest()[:16],
        "gas_consumed": result.get("eval_count", 0),
        "gas_limit": manifest["max_gas"],
        "model": model,
        "tier": manifest["tier"],
        "status": "COMPLETED" if not error else "FAILED",
        "error": error,
    }

    return {
        "path": f"ollama_{model.replace(':', '_')}",
        "infer_time_s": round(elapsed, 2),
        "total_time_s": round(elapsed, 2),
        "output_text": output_text[:800],
        "output_tokens": len(output_text.split()),
        "ollama_eval_count": result.get("eval_count", 0),
        "ollama_duration_ms": round(result.get("total_duration_ms", 0) * 1000, 1),
        "error": error,
        "governance": audit,
    }


def score_medical_output(text: str) -> dict:
    """Score medical output quality — diagnosis accuracy + completeness."""
    text_lower = (text or "").lower()

    # Core diagnostic terms (must-haves for correct diagnosis)
    diagnostic_terms = [
        "hypothyroidism", "subclinical", "hashimoto", "thyroid",
        "autoimmune", "levothyroxine", "tpo", "thyroperoxidase",
    ]
    # Pathophysiology / mechanistic terms
    mechanism_terms = [
        "tsh", "t4", "thyroxine", "pituitary", "feedback",
        "gland", "hormone", "metabolism",
    ]
    # Clinical context terms (shows model understood the case)
    context_terms = [
        "iron", "omeprazole", "anemia", "gerd", "absorption",
        "interaction", "supplement",
    ]
    # Hallmarks of hallucination
    hallucination_markers = [
        "non-altoine", "altoine", "garbled", "��",
    ]

    diag_hits = [t for t in diagnostic_terms if t in text_lower]
    mech_hits = [t for t in mechanism_terms if t in text_lower]
    ctx_hits = [t for t in context_terms if t in text_lower]
    hall_hits = [t for t in hallucination_markers if t in text_lower]

    total_hits = len(diag_hits) + len(mech_hits) + len(ctx_hits)
    has_hallucination = len(hall_hits) > 0

    # Quality tiers
    if len(diag_hits) >= 4 and len(mech_hits) >= 3 and not has_hallucination:
        quality = "excellent"
    elif len(diag_hits) >= 2 and not has_hallucination:
        quality = "partial"
    elif has_hallucination:
        quality = "hallucination"
    else:
        quality = "poor"

    return {
        "diagnostic_hits": len(diag_hits),
        "diagnostic_terms_found": diag_hits,
        "mechanism_hits": len(mech_hits),
        "context_hits": len(ctx_hits),
        "total_term_hits": total_hits,
        "hallucination_detected": has_hallucination,
        "hallucination_markers": hall_hits,
        "quality": quality,
    }


def main() -> None:
    print("=" * 70)
    print("HLF — Ollama Medical Model Benchmark")
    print("=" * 70)
    print(f"\nPrompt: {PROMPT_MEDICAL[:100]}...\n")

    # Step 1: Try Ollama medical models
    ollama_results = []
    for model in MEDICAL_MODELS:
        print(f"\n{'─' * 60}")
        print(f"Trying model: {model}")
        print(f"{'─' * 60}")

        result = run_ollama_governed(PROMPT_MEDICAL, model)
        if result.get("error"):
            print(f"  ⚠️ {model} failed: {result['error']}")
            ollama_results.append(result)
            continue

        score = score_medical_output(result.get("output_text", ""))
        result["quality"] = score
        ollama_results.append(result)

        print(f"\n  Quality: {score['quality']}")
        print(f"  Diagnostic terms: {score['diagnostic_hits']} — {score['diagnostic_terms_found']}")
        print(f"  Mechanism terms: {score['mechanism_hits']}")
        print(f"  Context terms: {score['context_hits']}")
        print(f"  Hallucination: {score['hallucination_detected']}")

        if score["quality"] in ("excellent", "partial"):
            print(f"\n  ✅ {model} succeeded with {score['quality']} quality — stopping search")
            break  # Found a good model, stop trying fallbacks
        else:
            print(f"  → Trying next model...")

    # Step 2: Try GPU paths if available
    gpu_results = []
    try:
        import torch
        if torch.cuda.is_available():
            print(f"\n{'=' * 60}")
            print("GPU paths available — running for comparison")
            print(f"{'=' * 60}")

            # Try to load and run benchmark_gpu_comparison paths
            try:
                from scripts.benchmark_gpu_comparison import (
                    run_solo_solver, run_recursive_mas_latent,
                    score_medical_output as gpu_score_medical,
                    clear_gpu_memory,
                )

                clear_gpu_memory()
                solo = run_solo_solver(PROMPT_MEDICAL)
                if "error" not in solo:
                    solo["quality"] = score_medical_output(solo.get("output_text", ""))
                gpu_results.append(solo)

                clear_gpu_memory()
                latent = run_recursive_mas_latent(PROMPT_MEDICAL)
                if "error" not in latent:
                    latent["quality"] = score_medical_output(latent.get("output_text", ""))
                gpu_results.append(latent)

                clear_gpu_memory()
            except Exception as e:
                print(f"  ⚠️ GPU benchmark paths unavailable: {e}")
    except ImportError:
        print("\n  ℹ️ Torch not available — skipping GPU comparison paths")

    # Step 3: Comparison table
    print(f"\n{'=' * 70}")
    print("MEDICAL BENCHMARK COMPARISON")
    print(f"{'=' * 70}")

    all_results = ollama_results + gpu_results

    print(f"\n{'Path':<35} {'Quality':<15} {'Time(s)':<10} {'Tokens':<10}")
    print("-" * 70)
    for r in all_results:
        path = r.get("path", "unknown")[:33]
        qual = r.get("quality", {}).get("quality", "N/A") if isinstance(r.get("quality"), dict) else str(r.get("quality", "N/A"))
        time_s = str(r.get("infer_time_s", r.get("total_time_s", "N/A")))
        tokens = str(r.get("output_tokens", r.get("ollama_eval_count", "N/A")))
        error = r.get("error")
        if error:
            qual = f"ERROR: {error[:25]}"
        print(f"{path:<35} {qual:<15} {time_s:<10} {tokens:<10}")

    # Step 4: Show best Ollama output
    for r in ollama_results:
        if r.get("output_text") and not r.get("error"):
            quality = r.get("quality", {}).get("quality", "N/A") if isinstance(r.get("quality"), dict) else "N/A"
            print(f"\n{'=' * 70}")
            print(f"OUTPUT: {r['path']} (quality: {quality})")
            print(f"{'=' * 70}")
            print(r["output_text"])
            print(f"\n  Governance: {json.dumps(r.get('governance', {}), indent=2)}")
            break

    # Step 5: Save results
    out_path = REPO_ROOT / "benchmark_ollama_medical.json"
    with open(out_path, "w") as f:
        json.dump({
            "prompt": PROMPT_MEDICAL,
            "models_tested": MEDICAL_MODELS,
            "results": all_results,
        }, f, indent=2)
    print(f"\n\n  Results saved to: {out_path}")

    # Final verdict
    best_ollama = next((r for r in ollama_results if not r.get("error")), None)
    if best_ollama:
        quality = best_ollama.get("quality", {}).get("quality", "N/A") if isinstance(best_ollama.get("quality"), dict) else "N/A"
        print(f"\n  VERDICT: Best Ollama medical model = {best_ollama['path']} ({quality})")

    print("\n✅ Ollama medical benchmark complete.")


if __name__ == "__main__":
    main()
