#!/usr/bin/env python3
"""
Governed RecursiveMAS Pipeline — SwarmGlass governance wrapping the official pipeline.

Uses governance_primitives.py (stdlib only) to wrap single_prompt.py stage functions
with circuit breaker, telemetry collection, Merkle-chained audit, and evidence reporting.

Usage: python governed_pipeline.py "Your question here"
"""
from __future__ import annotations

import argparse
import gc
import os
import statistics
import sys
import time
from pathlib import Path

import torch

THIS_DIR = Path(__file__).resolve().parent
PARENT_DIR = THIS_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from governance_primitives import (
    CircuitBreaker,
    TelemetryCollector,
    MerkleAuditChain,
    EvidenceSummaryRenderer,
)

try:
    from swarmglass_bridge import MicroSquadEventEmitter
except ImportError:
    MicroSquadEventEmitter = None

try:
    from cloud_dispatch import call_cloud_model, UsageTracker, CloudUsage
except ImportError:
    call_cloud_model = None
    UsageTracker = None
    CloudUsage = None

# Import the stage functions from the (now slot-based) single_prompt pipeline
from single_prompt import (
    run_planner_stage,
    run_refiner_stage,
    run_solver_stage,
)
# Import the Mixture/HIE pipeline bridge
from single_prompt_mixture import (
    run_hie_expert_stage,
    run_hie_summarizer_generate,
)
from system_loader import load_mas_system, LoadedAgent

# For multi-round feedback (official pipeline patterns)
from prompts import (
    PLANNER_SLOT, REFINED_SLOT, FEEDBACK_SLOT,
    build_math_planner_prompt_with_feedback_slot,
    build_math_refiner_prompt_with_slot,
    build_math_solver_prompt_with_slots,
)
from inference_utils.inference_mas import (
    autoregressive_latent_rollout,
    run_inner_adapter,
    run_outer_adapter,
    split_prompt_ids_by_slots,
    token_ids_to_embeds,
    pad_left_ids,
    pad_left_embeds,
    render_chat_prompt_ids,
    build_generation_kwargs,
)


def run_solver_feedback_stage(
    agent: LoadedAgent, outer_31,
    questions: list, refiner_latents: list,
    latent_steps: int, device: torch.device,
) -> list:
    """Solver feedback: latent-only pass producing feedback via outer_31 → planner dim."""
    model, tokenizer = agent.model, agent.tokenizer
    embed_layer = model.get_input_embeddings()
    embed_dtype = embed_layer.weight.dtype
    inner = agent.inner_adapter

    results = []
    for idx, q in enumerate(questions):
        user_prompt = build_math_solver_prompt_with_slots(q, args=None, mas_shape="chain")
        seg_prefix, seg_suffix = split_prompt_ids_by_slots(
            tokenizer, user_prompt, [REFINED_SLOT], enable_thinking=False
        )
        prefix_emb = token_ids_to_embeds(embed_layer, seg_prefix, device=device, dtype=embed_dtype)
        suffix_emb = token_ids_to_embeds(embed_layer, seg_suffix, device=device, dtype=embed_dtype)
        refiner_emb = refiner_latents[idx].to(device=device, dtype=embed_dtype)

        seq = torch.cat([prefix_emb, refiner_emb, suffix_emb], dim=0)
        batch_emb, attn_mask = pad_left_embeds([seq], device=device)

        hidden = autoregressive_latent_rollout(
            model=model, rollout_inner_adapter=inner,
            input_embeds=batch_emb, attention_mask=attn_mask,
            latent_steps=latent_steps,
        )
        self_latent = run_inner_adapter(inner, hidden, output_dtype=embed_dtype)
        feedback = run_outer_adapter(outer_31, self_latent, output_dtype=torch.float32)
        results.append(feedback[0].detach().cpu())

    return results


def run_planner_feedback_stage(
    agent: LoadedAgent, outer_12,
    questions: list, feedback_latents: list,
    latent_steps: int, device: torch.device,
) -> list:
    """Planner feedback: consumes feedback latents via FEEDBACK_SLOT interleaving."""
    model, tokenizer = agent.model, agent.tokenizer
    embed_layer = model.get_input_embeddings()
    embed_dtype = embed_layer.weight.dtype
    inner = agent.inner_adapter

    results = []
    for idx, q in enumerate(questions):
        user_prompt = build_math_planner_prompt_with_feedback_slot(q)
        seg_prefix, seg_suffix = split_prompt_ids_by_slots(
            tokenizer, user_prompt, [FEEDBACK_SLOT], enable_thinking=False
        )
        prefix_emb = token_ids_to_embeds(embed_layer, seg_prefix, device=device, dtype=embed_dtype)
        suffix_emb = token_ids_to_embeds(embed_layer, seg_suffix, device=device, dtype=embed_dtype)
        feedback_emb = feedback_latents[idx].to(device=device, dtype=embed_dtype)

        seq = torch.cat([prefix_emb, feedback_emb, suffix_emb], dim=0)
        batch_emb, attn_mask = pad_left_embeds([seq], device=device)

        hidden = autoregressive_latent_rollout(
            model=model, rollout_inner_adapter=inner,
            input_embeds=batch_emb, attention_mask=attn_mask,
            latent_steps=latent_steps,
        )
        self_latent = run_inner_adapter(inner, hidden, output_dtype=embed_dtype)
        lat12 = run_outer_adapter(outer_12, self_latent, output_dtype=torch.float32)
        results.append(lat12[0].detach().cpu())

    return results


def _compute_confidence(breaker, telemetry) -> float:
    """Compute local pipeline confidence from breaker state and telemetry.

    Returns 0.0-1.0 where 1.0 = high confidence, 0.0 = low.
    Factors: breaker warnings, norm stability, stage completion.
    """
    warnings = sum(1 for h in breaker.history if not h.get("ok", True))
    stages = len(telemetry.stages)
    if stages == 0:
        return 0.0
    completed = sum(1 for s in telemetry.stages if s.success)
    completion_rate = completed / stages if stages > 0 else 0

    # Breaker warnings reduce confidence
    breaker_penalty = min(warnings * 0.15, 0.5)

    # Norm stability (low variance = high confidence)
    norms = [s.output_norm for s in telemetry.stages if s.output_norm > 0]
    norm_stability = 0.5
    if len(norms) >= 2:
        try:
            cv = statistics.stdev(norms) / (abs(statistics.mean(norms)) + 1e-8)
            norm_stability = max(0.0, 1.0 - min(cv, 1.0))
        except Exception:
            norm_stability = 0.5

    confidence = (completion_rate * 0.4 + norm_stability * 0.4 + (1.0 - breaker_penalty) * 0.2)
    return max(0.0, min(1.0, confidence))


def governed_pipeline(
    question: str,
    style: str = "sequential_light",
    latent_steps: int = 32,
    max_tokens: int = 1000,
    temperature: float = 0.6,
    top_p: float = 0.95,
    rounds: int = 1,
    device: torch.device = None,
    load_in_4bit: bool = False,
    mode: str = "hybrid",                       # local, cloud, hybrid
    cloud_model: str = "gpt-4o-mini",           # cloud model for hybrid/cloud modes
    cloud_confidence_threshold: float = 0.5,    # min local confidence to skip cloud in hybrid
    use_hks: bool = True,                       # query HKS memory for knowledge augmentation
) -> dict:
    """Run the full RecursiveMAS pipeline with SwarmGlass governance wrapping.

    Returns dict with: output_text, telemetry, audit, breaker, evidence_report
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ── HKS Knowledge Augmentation ──
    original_question = question
    if use_hks:
        try:
            from hlf_mcp.recursivemas.hks_bridge import augment_prompt
            t_hks = time.time()
            question = augment_prompt(question)
            hks_time = time.time() - t_hks
            if question != original_question:
                added = len(question) - len(original_question)
                print(f"[GOVERN] HKS augmentation: +{added} chars in {hks_time:.1f}s")
            else:
                print(f"[GOVERN] HKS empty (no matches in {hks_time:.1f}s)")
        except Exception as e:
            print(f"[GOVERN] HKS bridge unavailable: {e}")
            question = original_question

    # ── Governance layer ──
    breaker = CircuitBreaker()
    telemetry = TelemetryCollector()
    audit = MerkleAuditChain()

    telemetry.start_run(
        style=style, latent_steps=latent_steps, temperature=temperature,
        top_p=top_p, max_tokens=max_tokens, question=original_question[:100],
    )

    pipeline_info = {
        "style": style,
        "latent_steps": latent_steps,
        "temperature": temperature,
        "top_p": top_p,
        "rounds": rounds,
        "device": str(device),
        "quantization": "4bit" if load_in_4bit else "none",
        "use_hks": use_hks,
    }

    # ── SwarmGlass bridge ──
    emitter = None
    if MicroSquadEventEmitter is not None:
        try:
            emitter = MicroSquadEventEmitter()
            emitter.emit_stage_start("pipeline", {"style": style, "question": original_question[:200]})
        except Exception as e:
            print(f"[GOVERN] SwarmGlass bridge unavailable: {e}")

    try:
        # ── Load system (skip for pure cloud mode) ──
        output_text = ""
        cloud_result = None
        usage_tracker = UsageTracker() if UsageTracker else None
        dispatch_prompt = ""
        local_confidence = 0.0
        questions = [question]
        if mode != "cloud":
            print("[GOVERN] Loading MAS system...")
            t0 = time.time()
            system = load_mas_system(
                style=style, dataset="math500", device=device, trust_remote_code=True,
                load_in_4bit=load_in_4bit,
            )
            load_time = time.time() - t0
            telemetry.metadata["load_time_s"] = load_time
            audit.append("system_load", question[:100], f"loaded_{style}", load_time_s=load_time)
            print(f"[GOVERN] System loaded in {load_time:.1f}s")
            if emitter:
                emitter.emit_stage_end("pipeline", "load", {"load_time_s": load_time, "style": style})

            # ── Dispatch by family ──
            family = getattr(system, "family", "sequential")

            if family == "mixture":
                # ========= Mixture/HIE Pipeline =========
                p_latents = None
                r_latents = None
                mas_task = "code"

                print(f"[GOVERN] Mixture experts ({latent_steps} latent steps each)...")
                t_exp = time.time()
                math_latents = run_hie_expert_stage(
                    system.agents["math"], system.outer_adapters["outer_1s"],
                    questions, "hie_math_expert", latent_steps, device, mas_task=mas_task,
                )
                code_latents = run_hie_expert_stage(
                    system.agents["code"], system.outer_adapters["outer_2s"],
                    questions, "hie_code_expert", latent_steps, device, mas_task=mas_task,
                )
                science_latents = run_hie_expert_stage(
                    system.agents["science"], system.outer_adapters["outer_3s"],
                    questions, "hie_science_expert", latent_steps, device, mas_task=mas_task,
                )
                expert_time = time.time() - t_exp
                print(f"[GOVERN]   experts completed in {expert_time:.1f}s")
                gc.collect(); torch.cuda.empty_cache()

                print(f"[GOVERN] Summarizer stage (text generation)...")
                st = telemetry.start_stage("summarizer", latent_steps=0)
                outputs = run_hie_summarizer_generate(
                    system.agents["summarizer"], questions,
                    [math_latents, code_latents, science_latents],
                    max_new_tokens=max_tokens, temperature=temperature,
                    top_p=top_p, device=device, mas_task=mas_task,
                )
                output_text = outputs[0]
                telemetry.end_stage(st, output_shape=None, output_norm=len(output_text))
                audit.append("summarizer", question[:100], output_text[:200], token_count=len(output_text.split()))
                print(f"[GOVERN]   output: {len(output_text)} chars, ~{len(output_text.split())} tokens")

            else:
                # ========= Sequential Pipeline =========
                # Stage 1: Planner
                print(f"[GOVERN] Planner stage ({latent_steps} latent steps)...")
                pid = None
                if emitter:
                    pid = emitter.emit_stage_start("planner", {"latent_steps": latent_steps})
                st = telemetry.start_stage("planner", latent_steps=latent_steps)
                planner_ok = breaker.check_norm("planner_pre", 0.0)
                if not planner_ok:
                    raise RuntimeError("Circuit breaker OPEN - planner stage rejected")

                p_latents = run_planner_stage(
                    system.agents["planner"], system.outer_adapters["outer_12"],
                    questions, latent_steps, device,
                )
                p_norm = p_latents[0].norm().item()
                telemetry.end_stage(st, output_shape=tuple(p_latents[0].shape), output_norm=p_norm)
                breaker.record_baseline("planner", p_norm)
                breaker.check_norm("planner", p_norm)
                audit.append("planner", question[:100], f"latent[{list(p_latents[0].shape)}]", norm=p_norm)
                print(f"[GOVERN]   norm={p_norm:.1f}  shape={list(p_latents[0].shape)}")
                if emitter and pid:
                    emitter.emit_stage_end("planner", pid, {"norm": p_norm, "shape": list(p_latents[0].shape)})
                gc.collect(); torch.cuda.empty_cache()

                # Stage 2: Critic
                print(f"[GOVERN] Critic stage ({latent_steps} latent steps)...")
                cid = None
                if emitter:
                    cid = emitter.emit_stage_start("critic", {"latent_steps": latent_steps})
                st = telemetry.start_stage("critic", latent_steps=latent_steps)
                critic_ok = breaker.check_norm("critic_pre", p_norm)
                if not critic_ok:
                    raise RuntimeError("Circuit breaker OPEN - critic stage rejected")

                r_latents = run_refiner_stage(
                    system.agents["critic"], system.outer_adapters["outer_23"],
                    questions, p_latents, latent_steps, device,
                )
                r_norm = r_latents[0].norm().item()
                telemetry.end_stage(st, output_shape=tuple(r_latents[0].shape), output_norm=r_norm)
                breaker.record_baseline("critic", r_norm)
                breaker.check_norm("critic", r_norm)
                audit.append("critic", f"norm={p_norm:.1f}", f"latent[{list(r_latents[0].shape)}]", norm=r_norm)
                print(f"[GOVERN]   norm={r_norm:.1f}  shape={list(r_latents[0].shape)}")
                if emitter and cid:
                    emitter.emit_stage_end("critic", cid, {"norm": r_norm, "shape": list(r_latents[0].shape)})
                gc.collect(); torch.cuda.empty_cache()

                # Stage 3: Solver
                print(f"[GOVERN] Solver stage (text generation)...")
                sid = None
                if emitter:
                    sid = emitter.emit_stage_start("solver", {"max_tokens": max_tokens})
                st = telemetry.start_stage("solver", latent_steps=0)
                solver_ok = breaker.check_norm("solver_pre", r_norm)
                if not solver_ok:
                    raise RuntimeError("Circuit breaker OPEN - solver stage rejected")

                outputs = run_solver_stage(
                    system.agents["solver"], questions, r_latents,
                    max_new_tokens=max_tokens, temperature=temperature,
                    top_p=top_p, device=device,
                )
                output_text = outputs[0]
                telemetry.end_stage(st, output_shape=None, output_norm=len(output_text))
                audit.append("solver", f"norm={r_norm:.1f}", output_text[:200], token_count=len(output_text.split()))
                print(f"[GOVERN]   output: {len(output_text)} chars, ~{len(output_text.split())} tokens")
                if emitter and sid:
                    emitter.emit_stage_end("solver", sid, {"output_length": len(output_text), "token_count": len(output_text.split())})

            # ── Multi-round recursion (rounds 2+) ──
            for round_num in range(2, rounds + 1):
                print(f"\n[GOVERN] --- Round {round_num}/{rounds} ---")

                # Solver feedback: latent-only pass → outer_31 → planner dim
                print(f"[GOVERN] Solver feedback (latent → outer_31)...")
                st = telemetry.start_stage(f"solver_feedback_r{round_num}", latent_steps=latent_steps)
                fb_ok = breaker.check_norm(f"solver_fb_r{round_num}_pre", r_norm)
                if not fb_ok:
                    raise RuntimeError(f"Circuit breaker OPEN — solver feedback round {round_num} rejected")

                feedback_latents = run_solver_feedback_stage(
                    system.agents["solver"], system.outer_adapters["outer_31"],
                    questions, r_latents, latent_steps, device,
                )
                fb_norm = feedback_latents[0].norm().item()
                telemetry.end_stage(st, output_shape=tuple(feedback_latents[0].shape), output_norm=fb_norm)
                breaker.check_norm(f"solver_fb_r{round_num}", fb_norm)
                audit.append(f"solver_fb_r{round_num}", f"refiner_norm={r_norm:.1f}", f"feedback[{list(feedback_latents[0].shape)}]", norm=fb_norm)
                print(f"[GOVERN]   ✓ feedback norm={fb_norm:.1f}  shape={list(feedback_latents[0].shape)}")

                # Planner feedback: consumes feedback → new planner latents
                print(f"[GOVERN] Planner feedback (FEEDBACK_SLOT interleaving)...")
                st = telemetry.start_stage(f"planner_feedback_r{round_num}", latent_steps=latent_steps)
                planner_fb_ok = breaker.check_norm(f"planner_fb_r{round_num}_pre", fb_norm)
                if not planner_fb_ok:
                    raise RuntimeError(f"Circuit breaker OPEN — planner feedback round {round_num} rejected")

                p_latents = run_planner_feedback_stage(
                    system.agents["planner"], system.outer_adapters["outer_12"],
                    questions, feedback_latents, latent_steps, device,
                )
                p_norm = p_latents[0].norm().item()
                telemetry.end_stage(st, output_shape=tuple(p_latents[0].shape), output_norm=p_norm)
                breaker.record_baseline(f"planner_r{round_num}", p_norm)
                breaker.check_norm(f"planner_r{round_num}", p_norm)
                audit.append(f"planner_r{round_num}", f"feedback_norm={fb_norm:.1f}", f"latent[{list(p_latents[0].shape)}]", norm=p_norm)
                print(f"[GOVERN]   ✓ planner norm={p_norm:.1f}")
                gc.collect(); torch.cuda.empty_cache()

                # Critic: normal pass
                print(f"[GOVERN] Critic stage (round {round_num})...")
                st = telemetry.start_stage(f"critic_r{round_num}", latent_steps=latent_steps)
                critic_ok = breaker.check_norm(f"critic_r{round_num}_pre", p_norm)
                if not critic_ok:
                    raise RuntimeError(f"Circuit breaker OPEN — critic round {round_num} rejected")

                r_latents = run_refiner_stage(
                    system.agents["critic"], system.outer_adapters["outer_23"],
                    questions, p_latents, latent_steps, device,
                )
                r_norm = r_latents[0].norm().item()
                telemetry.end_stage(st, output_shape=tuple(r_latents[0].shape), output_norm=r_norm)
                breaker.record_baseline(f"critic_r{round_num}", r_norm)
                breaker.check_norm(f"critic_r{round_num}", r_norm)
                audit.append(f"critic_r{round_num}", f"planner_norm={p_norm:.1f}", f"latent[{list(r_latents[0].shape)}]", norm=r_norm)
                print(f"[GOVERN]   ✓ critic norm={r_norm:.1f}")
                gc.collect(); torch.cuda.empty_cache()

                # Solver: final text generation for this round
                print(f"[GOVERN] Solver stage (round {round_num})...")
                st = telemetry.start_stage(f"solver_r{round_num}", latent_steps=0)
                solver_ok = breaker.check_norm(f"solver_r{round_num}_pre", r_norm)
                if not solver_ok:
                    raise RuntimeError(f"Circuit breaker OPEN — solver round {round_num} rejected")

                outputs = run_solver_stage(
                    system.agents["solver"], questions, r_latents,
                    max_new_tokens=max_tokens, temperature=temperature,
                    top_p=top_p, device=device,
                )
                output_text = outputs[0]
                telemetry.end_stage(st, output_shape=None, output_norm=len(output_text))
                audit.append(f"solver_r{round_num}", f"refiner_norm={r_norm:.1f}", output_text[:200], token_count=len(output_text.split()))
                print(f"[GOVERN]   ✓ output: {len(output_text)} chars, ~{len(output_text.split())} tokens")
        else:
            # Pure cloud mode — skip local pipeline entirely
            print("[GOVERN] Cloud-only mode — skipping local pipeline")

        # ── Cloud dispatch (hybrid/cloud modes) ──
        if mode in ("cloud", "hybrid") and call_cloud_model is not None:
            if mode == "cloud":
                dispatch_prompt = question
            else:  # hybrid
                local_confidence = _compute_confidence(breaker, telemetry)
                if local_confidence >= cloud_confidence_threshold:
                    print(f"[GOVERN] Local confidence {local_confidence:.2f} >= threshold {cloud_confidence_threshold}, skipping cloud")
                else:
                    dispatch_prompt = (
                        f"Original question: {question}\n"
                        f"Local answer: {output_text[:500]}\n"
                        f"Verify this answer and provide the correct result if different."
                    )
                    print(f"[GOVERN] Local confidence {local_confidence:.2f} < threshold {cloud_confidence_threshold}, dispatching to cloud")

            if dispatch_prompt and (mode == "cloud" or local_confidence < cloud_confidence_threshold):
                print(f"[GOVERN] Dispatching to cloud model: {cloud_model}")
                t0 = time.time()
                cloud_text, cloud_usage = call_cloud_model(
                    prompt=dispatch_prompt,
                    model=cloud_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    tracker=usage_tracker,
                )
                cloud_duration = time.time() - t0

                if cloud_text:
                    cloud_result = {
                        "text": cloud_text,
                        "usage": {
                            "prompt_tokens": cloud_usage.prompt_tokens,
                            "completion_tokens": cloud_usage.completion_tokens,
                            "total_tokens": cloud_usage.total_tokens,
                            "cost_usd": cloud_usage.cost_usd,
                            "duration_s": cloud_duration,
                        },
                    }
                    # For hybrid, cloud answer becomes final
                    if mode == "hybrid" and not output_text.strip():
                        output_text = cloud_text
                    audit.append("cloud_dispatch", dispatch_prompt[:100], cloud_text[:200],
                                cost_usd=cloud_usage.cost_usd, tokens=cloud_usage.total_tokens)
                    print(f"[GOVERN]   ✓ cloud: {cloud_usage.total_tokens} tokens, ${cloud_usage.cost_usd:.5f}")
                    if emitter and cloud_usage.total_tokens > 0:
                        try:
                            emitter.track_cloud_usage(
                                model=cloud_model,
                                prompt_tokens=cloud_usage.prompt_tokens,
                                completion_tokens=cloud_usage.completion_tokens,
                                total_tokens=cloud_usage.total_tokens,
                                cost_usd=cloud_usage.cost_usd,
                                duration_s=cloud_duration,
                            )
                        except Exception:
                            pass  # SwarmGlass tracking is best-effort
                elif cloud_usage.error:
                    print(f"[GOVERN]   ✗ cloud error: {cloud_usage.error}")

        # ── Hybrid: cloud result supersedes local ──
        if mode == "hybrid" and cloud_result:
            output_text = cloud_result["text"]

        telemetry.end_run()

    except Exception as e:
        telemetry.end_run()
        print(f"[GOVERN] Pipeline failed: {e}")
        return {
            "output_text": "",
            "telemetry": telemetry,
            "audit": audit,
            "breaker": breaker,
            "evidence_report": f"PIPELINE FAILED: {e}",
            "success": False,
            "error": str(e),
            "mode": mode,
            "cloud_usage": None,
            "cloud_result": None,
        }

    # ── Evidence report ──
    pipeline_info["mode"] = mode
    pipeline_info["cloud_model"] = cloud_model if mode in ("cloud", "hybrid") else "none"
    evidence = EvidenceSummaryRenderer(
        telemetry=telemetry, audit=audit, breaker=breaker,
    )
    report = evidence.render(output_text, pipeline_info)

    # Append cloud usage to evidence report if present
    if cloud_result:
        cu = cloud_result["usage"]
        report += (
            f"\n  Cloud: {cloud_model} — "
            f"{cu['total_tokens']} tokens, ${cu['cost_usd']:.5f}, {cu['duration_s']:.1f}s"
        )
    elif usage_tracker and usage_tracker.calls:
        report += f"\n  Cloud: {usage_tracker.summary()} (all errors)"
    elif mode in ("cloud", "hybrid") and call_cloud_model is None:
        report += "\n  Cloud: UNAVAILABLE (cloud_dispatch module not loaded)"

    if emitter:
        emitter.emit_solution(question, output_text, {"evidence_report": report})

    return {
        "output_text": output_text,
        "telemetry": telemetry,
        "audit": audit,
        "breaker": breaker,
        "evidence_report": report,
        "success": True,
        "error": None,
        "mode": mode,
        "cloud_usage": usage_tracker.to_dict() if usage_tracker else None,
        "cloud_result": cloud_result,
    }


def main():
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("MAS_FORCE_DISABLE_TORCHVISION", "1")

    p = argparse.ArgumentParser(description="Governed RecursiveMAS inference")
    p.add_argument("prompt", type=str)
    p.add_argument("--style", default="sequential_light")
    p.add_argument("--latent-steps", type=int, default=32)
    p.add_argument("--max-tokens", type=int, default=1000)
    p.add_argument("--temperature", type=float, default=0.6)
    p.add_argument("--top-p", type=float, default=0.95)
    p.add_argument("--device", default="cuda")
    p.add_argument("--rounds", type=int, default=1, help="Number of recursive rounds (2+ enables outer_31 feedback loop)")
    p.add_argument("--4bit", action="store_true", help="Load models in 4-bit quantization for VRAM-constrained GPUs")
    p.add_argument("--mode", default="hybrid", choices=["local", "cloud", "hybrid"],
                   help="Execution mode: local (MicroSquad only), cloud (API only), hybrid (local first, cloud if needed)")
    p.add_argument("--cloud-model", default="gpt-4o-mini",
                   help="Cloud model for hybrid/cloud modes (default: gpt-4o-mini)")
    p.add_argument("--use-hks", dest="use_hks", default=True, action="store_true",
                   help="Augment prompts with HKS knowledge (default: True)")
    p.add_argument("--no-hks", dest="use_hks", action="store_false",
                   help="Disable HKS knowledge augmentation")
    args = p.parse_args()

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")

    print("=" * 60)
    print("SWARMGLASS-GOVERNED RECURSIVEMAS PIPELINE")
    print("=" * 60)
    print(f"  Prompt: {args.prompt[:100]}{'...' if len(args.prompt) > 100 else ''}")
    print(f"  Mode: {args.mode} (local={args.style}, cloud={args.cloud_model})")
    if args.__dict__.get("4bit"):
        print("  Quantization: 4-bit NF4 (bitsandbytes)")
    print()

    result = governed_pipeline(
        question=args.prompt,
        style=args.style,
        latent_steps=args.latent_steps,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        rounds=args.rounds,
        device=device,
        load_in_4bit=args.__dict__.get("4bit", False),
        mode=args.mode,
        cloud_model=args.cloud_model,
        use_hks=getattr(args, "use_hks", True),
    )

    if result["success"]:
        print(f"\n{'='*60}")
        print("PIPELINE OUTPUT")
        print("=" * 60)
        print(result["output_text"])

    print(f"\n{result['evidence_report']}")

    # Verify audit chain
    valid, msg = result["audit"].verify()
    print(f"\n  Audit integrity: {'✓ ' + msg if valid else '✗ ' + msg}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
