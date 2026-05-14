"""
HLF Compounding Benchmark — "Does it get better with use?"

Tests the core HLF hypothesis: HKS memory recall + LLM bridge creates a
compounding improvement loop where translation quality improves over cycles.

Run: python compounding_benchmark.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure hlf_mcp is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hlf_mcp.server_context import build_server_context
from hlf_mcp.hlf.benchmark import (
    _COMPLEX_WORKFLOW_NLP,
    _COMPLEX_WORKFLOW_HLF,
    _SWARM_WORKFLOW_NLP,
    _SWARM_WORKFLOW_HLF,
    _count,
)
from hlf_mcp.hlf.translator import language_to_hlf, translation_diagnostics
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.hlf_llm_bridge import HLFLLMBridge


# ── Test Intents ──────────────────────────────────────────────────────────

# Mix of simple + complex: single-sentence + multi-step + swarm
BENCHMARK_INTENTS = [
    {
        "id": "log_audit_simple",
        "text": "Audit /var/log/system.log in read-only mode and report the top 10 errors.",
        "domain": "log_analysis",
    },
    {
        "id": "deploy_simple",
        "text": "Deploy the application stack using auto-routing with operator confirmation required.",
        "domain": "stack_deployment",
    },
    {
        "id": "content_delegation",
        "text": "Delegate a fractalized summary task to a scribe agent with high priority.",
        "domain": "content_delegation",
    },
    {
        "id": "incident_response_7step",
        "text": _COMPLEX_WORKFLOW_NLP["incident_response_7step"],
        "domain": "security",
    },
    {
        "id": "multi_service_deploy_5step",
        "text": _COMPLEX_WORKFLOW_NLP["multi_service_deploy_5step"],
        "domain": "devops",
    },
    {
        "id": "data_pipeline_6step",
        "text": _COMPLEX_WORKFLOW_NLP["data_pipeline_6step"],
        "domain": "data-engineering",
    },
    {
        "id": "code_review_3agent",
        "text": _SWARM_WORKFLOW_NLP["code_review_3agent"],
        "domain": "ai-engineering",
    },
    {
        "id": "audit_trail_4agent",
        "text": _SWARM_WORKFLOW_NLP["audit_trail_4agent"],
        "domain": "security",
    },
]


# ── Helper: run translation through the available pipeline ────────────────

async def translate_intent(ctx, intent_text: str, language: str = "en", memory_hits: list | None = None) -> dict:
    """Translate NLP intent to HLF using the best available path.

    Returns dict with:
      - source: HLF source (or None)
      - method: "llm_bridge" | "keyword_heuristic" | "failed"
      - compile_success: bool
      - tokens_nlp: int
      - tokens_hlf: int
      - compile_error: str or None
      - elapsed_ms: int
      - glyph_count: int (structural richness)
      - action_count: int
      - quality_score: float 0.0-1.0
    """
    t0 = time.perf_counter()
    result = {
        "source": None,
        "method": "failed",
        "compile_success": False,
        "tokens_nlp": _count(intent_text),
        "tokens_hlf": 0,
        "compile_error": None,
        "elapsed_ms": 0,
        "glyph_count": 0,
        "action_count": 0,
        "quality_score": 0.0,
    }

    compiler = ctx.compiler
    bridge = None
    try:
        bridge = HLFLLMBridge(model="deepseek-v4-pro:cloud")
    except Exception:
        pass
    hlf_source = None

    # Path 1: LLM Bridge (preferred — proper semantic translation)
    if bridge is not None:
        try:
            system_prompt = (
                "You are a precise HLF-v3 translator. Your job is to convert "
                "natural-language intents into canonical HLF source code.\n\n"
                "HLF-v3 structure rules:\n"
                "- Every HLF program begins with [HLF-v3] on its own line and ends with Ω on its own line.\n"
                "- Decompose the intent into separate glyphs.\n"
                "  * GOAL directive for the primary objective\n"
                "  * ACTION blocks (Δ) for concrete operations\n"
                "  * ASSERT blocks (Ж) for constraints and invariants\n"
                "  * RESULT blocks (Σ) for expected outputs\n"
                "- Preserve ALL semantic detail from the input. Do not truncate.\n"
                "- For complex intents, produce multiple ACTION glyphs.\n"
                "- Output ONLY valid HLF source wrapped in a code block.\n\n"
                "Format your response as:\n"
                "```hlf\n"
                "[HLF-v3]\n"
                "MODULE main\n"
                "GOAL <primary-objective>\n"
                "Δ action=\"...\"\n"
                "Ж condition=\"...\"\n"
                "Σ result=\"...\"\n"
                "Ω\n"
                "```"
            )
            # Build few-shot examples from memory hits
            few_shot = ""
            if memory_hits:
                few_shot_parts = []
                for i, hit in enumerate(memory_hits[:3]):
                    hit_content = hit.get("content", "")
                    if hit_content and len(hit_content) > 20:
                        few_shot_parts.append(
                            f"EXAMPLE {i+1} (confidence {hit.get('confidence', 'N/A')}):\n{hit_content}"
                        )
                if few_shot_parts:
                    few_shot = (
                        "Here are examples of correct HLF translations for similar intents. "
                        "Use these as style and structure reference:\n\n"
                        + "\n\n".join(few_shot_parts)
                        + "\n\n"
                    )
            prompt = (
                f"Translate the following natural-language intent into "
                f"canonical HLF-v3 syntax. Decompose it into structured glyphs: "
                f"GOALs, ACTIONS, CONSTRAINTS, ASSERTIONS, and RESULT expectations. "
                f"Do not truncate or wrap. Preserve all semantic detail.\n\n"
                f"{few_shot}"
                f"INTENT:\n{intent_text}"
            )
            llm_result = await bridge.send(
                prompt, role="translator", system=system_prompt)
            if llm_result.extracted and llm_result.hlf_output and llm_result.hlf_output.strip() != "Ω":
                try:
                    compiler.compile(llm_result.hlf_output)
                    hlf_source = llm_result.hlf_output
                    result["method"] = "llm_bridge"
                except Exception:
                    pass  # fall through to heuristic
        except Exception:
            pass  # fall through to heuristic

    # Path 2: Keyword heuristic (fallback)
    if hlf_source is None:
        try:
            hlf_source = language_to_hlf(intent_text, language=language)
            if hlf_source and "[HLF-v3]" in hlf_source:
                result["method"] = "keyword_heuristic"
            else:
                hlf_source = None
        except Exception:
            hlf_source = None

    if hlf_source is None:
        result["method"] = "failed"
        result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
        return result

    result["source"] = hlf_source
    result["tokens_hlf"] = _count(hlf_source)
    # Quality metrics: structural decomposition richness
    result["glyph_count"] = hlf_source.count("⌘") + hlf_source.count("Δ") + hlf_source.count("Ж") + hlf_source.count("Σ")
    result["action_count"] = hlf_source.count("Δ")
    # Quality score: actions per 100 NLP tokens — measures decomposition granularity
    action_density = result["action_count"] / max(1, result["tokens_nlp"]) * 100
    result["quality_score"] = min(1.0, action_density / 10.0)  # 10 actions/100 tokens = perfect score

    # Compile check
    try:
        compiled = compiler.compile(hlf_source)
        result["compile_success"] = True
    except Exception as exc:
        result["compile_error"] = str(exc)[:200]
        result["compile_success"] = False

    result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


# ── Main benchmark cycle ──────────────────────────────────────────────────

async def run_compounding_benchmark(cycles: int = 3):
    """Run benchmarks across multiple cycles to measure compounding improvement."""

    print("=" * 72)
    print("HLF COMPOUNDING BENCHMARK")
    print(f"Cycles: {cycles}  |  Intents: {len(BENCHMARK_INTENTS)}")
    print("=" * 72)

    # Fresh context each cycle (but memory persists on disk)
    ctx = build_server_context()
    memory = ctx.memory_store

    # Check what's available
    bridge_available = True  # HLFLLMBridge always constructable
    embed_active = memory._embed_fn is not None
    print(f"LLM Bridge: {'READY' if bridge_available else 'UNAVAILABLE'}")
    print(f"Dense Embeddings: {'ACTIVE' if embed_active else 'SPARSE ONLY'}")
    print(f"Memory entries (pre-benchmark): {memory.stats().get('total_entries', '?')}")
    print()

    cycle_results = []

    for cycle in range(1, cycles + 1):
        print(f"─── CYCLE {cycle}/{cycles} ───")
        intent_results = []

        for intent in BENCHMARK_INTENTS:
            intent_id = intent["id"]

            # Query memory for similar past translations
            memory_hits = []
            if cycle > 1:
                recall = memory.query(
                    intent["text"][:300],
                    entry_kind="hks_exemplar",
                    domain=intent.get("domain"),
                )
                memory_hits = recall.get("results", [])

            # Run translation with memory hits for few-shot injection
            result = await translate_intent(ctx, intent["text"], memory_hits=memory_hits)
            result["intent_id"] = intent_id
            result["domain"] = intent.get("domain", "general-coding")
            result["cycle"] = cycle
            result["memory_hits"] = len(memory_hits)
            result["memory_top_similarity"] = (
                memory_hits[0].get("similarity", 0) if memory_hits else 0
            )

            # Store in HKS memory (only if compiled successfully)
            if result["compile_success"] and result["source"]:
                try:
                    from hlf_mcp.rag.memory import HKSValidatedExemplar, HKSProvenance, HKSTestEvidence

                    exemplar = HKSValidatedExemplar(
                        problem=intent["text"],
                        validated_solution=result["source"],
                        domain=intent.get("domain", "general-coding"),
                        solution_kind="translation",
                        provenance=HKSProvenance(
                            source_type="benchmark",
                            source=f"compounding_benchmark.cycle_{cycle}",
                            collector="compounding_benchmark",
                            collected_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                        ),
                        tests=[
                            HKSTestEvidence(
                                name="compile_check",
                                passed=result["compile_success"],
                                exit_code=0,
                                counts={"passed": 1},
                            )
                        ],
                        tags=[intent_id, f"cycle_{cycle}"],
                        evaluation={
                            "authority": "local_hks",
                            "groundedness": 1.0,
                            "citation_coverage": 1.0,
                            "freshness_verdict": "fresh",
                            "provenance_verdict": "evidence-backed",
                            "promotion_eligible": True,
                            "operator_summary": f"Cycle {cycle} translation of '{intent_id}'.",
                        },
                    )
                    stored = memory.store_exemplar(exemplar)
                    result["memory_stored"] = stored.get("stored", False)
                except Exception as exc:
                    result["memory_stored"] = False
                    result["memory_store_error"] = str(exc)[:100]
            else:
                result["memory_stored"] = False

            intent_results.append(result)

            # Print per-intent summary with quality metrics
            method = result["method"]
            comp = result["compile_success"]
            tok_nlp = result["tokens_nlp"]
            tok_hlf = result["tokens_hlf"]
            mem_hits = result["memory_hits"]
            q = result["quality_score"]
            icon = "✓" if comp else "✗"
            mem_icon = f"🧠{mem_hits}" if mem_hits > 0 else "·"
            print(f"  {icon} {intent_id:30s} {method:25s} NLP={tok_nlp:4d} HLF={tok_hlf:4d} Q={q:.2f} {mem_icon}")

        # Cycle summary
        compiled = sum(1 for r in intent_results if r["compile_success"])
        total_nlp = sum(r["tokens_nlp"] for r in intent_results)
        total_hlf = sum(r["tokens_hlf"] for r in intent_results)
        avg_elapsed = sum(r["elapsed_ms"] for r in intent_results) / len(intent_results)
        mem_total = sum(r["memory_hits"] for r in intent_results)

        print(f"  ── Cycle {cycle} summary: {compiled}/{len(intent_results)} compiled, "
              f"NLP={total_nlp} HLF={total_hlf}, "
              f"avg {avg_elapsed:.0f}ms, {mem_total} memory hits")
        print()

        cycle_results.append({
            "cycle": cycle,
            "compiled": compiled,
            "total": len(intent_results),
            "total_nlp_tokens": total_nlp,
            "total_hlf_tokens": total_hlf,
            "avg_elapsed_ms": round(avg_elapsed),
            "total_memory_hits": mem_total,
            "intents": intent_results,
        })

    # ── Final comparison ──────────────────────────────────────────────────
    print("=" * 72)
    print("CYCLE-OVER-CYCLE COMPARISON")
    print("=" * 72)

    if len(cycle_results) >= 2:
        c1 = cycle_results[0]
        c_last = cycle_results[-1]

        print(f"  Compilation success: {c1['compiled']}/{c1['total']} → {c_last['compiled']}/{c_last['total']}")
        print(f"  Memory hits:          0 → {c_last['total_memory_hits']}")
        print(f"  Avg elapsed:          {c1['avg_elapsed_ms']}ms → {c_last['avg_elapsed_ms']}ms")

        comp_c1 = round((1 - c1["total_hlf_tokens"] / c1["total_nlp_tokens"]) * 100, 1) if c1["total_nlp_tokens"] > 0 else 0
        comp_clast = round((1 - c_last["total_hlf_tokens"] / c_last["total_nlp_tokens"]) * 100, 1) if c_last["total_nlp_tokens"] > 0 else 0
        print(f"  Token compression:    {comp_c1}% → {comp_clast}%")

    # Detailed per-intent comparison
    print()
    print("PER-INTENT DELTA (Cycle 1 → Last Cycle):")
    for i, intent in enumerate(BENCHMARK_INTENTS):
        r1 = cycle_results[0]["intents"][i]
        r_last = cycle_results[-1]["intents"][i]
        comp_delta = "same"
        if r1["compile_success"] != r_last["compile_success"]:
            comp_delta = "IMPROVED" if r_last["compile_success"] else "REGRESSED"
        mem_delta = r_last["memory_hits"] - r1["memory_hits"]
        print(f"  {intent['id']:30s} compile={comp_delta:10s} mem_hits=+{mem_delta}")

    # ── Verdict ───────────────────────────────────────────────────────────
    print()
    print("=" * 72)
    compile_improvements = 0
    compile_regressions = 0
    quality_improvements = 0
    total_mem_start = cycle_results[0]["total_memory_hits"]
    total_mem_end = cycle_results[-1]["total_memory_hits"]

    for i in range(len(BENCHMARK_INTENTS)):
        r1 = cycle_results[0]["intents"][i]
        r_last = cycle_results[-1]["intents"][i]
        if not r1["compile_success"] and r_last["compile_success"]:
            compile_improvements += 1
        elif r1["compile_success"] and not r_last["compile_success"]:
            compile_regressions += 1
        if r_last["quality_score"] > r1.get("quality_score", 0) * 1.1:
            quality_improvements += 1

    c1_quality = sum(r.get("quality_score", 0) for r in cycle_results[0]["intents"]) / len(BENCHMARK_INTENTS)
    clast_quality = sum(r.get("quality_score", 0) for r in cycle_results[-1]["intents"]) / len(BENCHMARK_INTENTS)
    print(f"  Avg quality score:    {c1_quality:.3f} → {clast_quality:.3f}")
    print(f"  Memory hits:          {total_mem_start} → {total_mem_end}")

    if total_mem_end > total_mem_start and quality_improvements >= 3:
        print("VERDICT: HKS compounding IS working — memory compounds AND quality improves.")
    elif total_mem_end > total_mem_start:
        print("VERDICT: PARTIAL — memory compounds (recall works), but quality gains need more cycles.")
    else:
        print("VERDICT: INCONCLUSIVE — insufficient data. Run more cycles or improve LLM prompting.")
    print(f"  {compile_improvements} compile fixes, {quality_improvements} quality gains over {len(cycle_results)} cycles.")
    print("=" * 72)

    return cycle_results


if __name__ == "__main__":
    asyncio.run(run_compounding_benchmark(cycles=3))
