#!/usr/bin/env python3
"""
single_prompt.py — Bridge between governed_pipeline.py and official inference_mas.py.

Wraps the stage functions to accept LoadedAgent objects (pre-loaded models + adapters)
instead of raw paths, enabling the SwarmGlass-governed pipeline to use official
RecursiveMAS inference with slot-based latent interleaving.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import torch
from tqdm import tqdm

THIS_DIR = Path(__file__).resolve().parent
# Official RecursiveMAS submodule is at HLF_MCP/recursivemas/
RECURSIVEMAS_SUBMODULE = THIS_DIR.parent.parent / "recursivemas"
if str(RECURSIVEMAS_SUBMODULE) not in sys.path:
    sys.path.insert(0, str(RECURSIVEMAS_SUBMODULE))

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
    pad_left_embeds,
    pad_left_ids,
    render_chat_prompt_ids,
    build_generation_kwargs,
    batch_iter_indices,
)


def run_planner_stage(
    agent,          # LoadedAgent
    outer_12,       # CrossModelAdapter (planner→critic)
    questions: List[str],
    latent_steps: int,
    device: torch.device,
) -> List[torch.Tensor]:
    """Planner latent stage: embed prompt → autoregressive latent rollout → inner adapter → outer_12."""
    model, tokenizer = agent.model, agent.tokenizer
    embed_layer = model.get_input_embeddings()
    embed_dtype = embed_layer.weight.dtype
    inner = agent.inner_adapter

    results = []
    for q in questions:
        user_prompt = build_math_planner_prompt_with_feedback_slot(q)
        seg_prefix, seg_suffix = split_prompt_ids_by_slots(
            tokenizer, user_prompt, [FEEDBACK_SLOT], enable_thinking=False
        )
        # For first round, feedback slot is empty — we just use prefix+suffix
        prefix_emb = token_ids_to_embeds(embed_layer, seg_prefix, device=device, dtype=embed_dtype)
        suffix_emb = token_ids_to_embeds(embed_layer, seg_suffix, device=device, dtype=embed_dtype)

        seq = torch.cat([prefix_emb, suffix_emb], dim=0)
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


def run_refiner_stage(
    agent,          # LoadedAgent (critic)
    outer_23,       # CrossModelAdapter (critic→solver)
    questions: List[str],
    planner_latents: List[torch.Tensor],
    latent_steps: int,
    device: torch.device,
) -> List[torch.Tensor]:
    """Critic/Refiner latent stage: consumes planner latents via PLANNER_SLOT, outputs via outer_23."""
    model, tokenizer = agent.model, agent.tokenizer
    embed_layer = model.get_input_embeddings()
    embed_dtype = embed_layer.weight.dtype
    inner = agent.inner_adapter

    results = []
    for idx, q in enumerate(questions):
        user_prompt = build_math_refiner_prompt_with_slot(q)
        seg_prefix, seg_suffix = split_prompt_ids_by_slots(
            tokenizer, user_prompt, [PLANNER_SLOT], enable_thinking=False
        )
        prefix_emb = token_ids_to_embeds(embed_layer, seg_prefix, device=device, dtype=embed_dtype)
        suffix_emb = token_ids_to_embeds(embed_layer, seg_suffix, device=device, dtype=embed_dtype)

        # Interleave planner latent into the PLANNER_SLOT position
        planner_emb = planner_latents[idx].to(device=device, dtype=embed_dtype)
        seq = torch.cat([prefix_emb, planner_emb, suffix_emb], dim=0)
        batch_emb, attn_mask = pad_left_embeds([seq], device=device)

        hidden = autoregressive_latent_rollout(
            model=model, rollout_inner_adapter=inner,
            input_embeds=batch_emb, attention_mask=attn_mask,
            latent_steps=latent_steps,
        )
        self_latent = run_inner_adapter(inner, hidden, output_dtype=embed_dtype)
        lat23 = run_outer_adapter(outer_23, self_latent, output_dtype=torch.float32)
        results.append(lat23[0].detach().cpu())

    return results


def run_solver_stage(
    agent,          # LoadedAgent (solver)
    questions: List[str],
    refiner_latents: List[torch.Tensor],
    max_new_tokens: int = 1000,
    temperature: float = 0.6,
    top_p: float = 0.95,
    device: torch.device = None,
) -> List[str]:
    """Solver text generation: consumes refiner latents via REFINED_SLOT, decodes to text."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model, tokenizer = agent.model, agent.tokenizer
    embed_layer = model.get_input_embeddings()
    embed_dtype = embed_layer.weight.dtype
    hidden_size = embed_layer.weight.size(-1)

    # Validate dim match
    if refiner_latents and refiner_latents[0].size(-1) != hidden_size:
        raise RuntimeError(
            f"Refiner latent dim {refiner_latents[0].size(-1)} != solver embedding dim {hidden_size}"
        )

    # Build prompt segments with REFINED_SLOT
    prompt_segments = []
    for q in questions:
        user_prompt = build_math_solver_prompt_with_slots(q, args=None, mas_shape="chain")
        seg = split_prompt_ids_by_slots(tokenizer, user_prompt, [REFINED_SLOT], enable_thinking=False)
        prompt_segments.append(seg)

    gen_kwargs = build_generation_kwargs(
        tokenizer,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=temperature,
        top_p=top_p,
    )

    outputs: List[str] = []
    for idx in range(len(questions)):
        seg_prefix, seg_suffix = prompt_segments[idx]
        prefix_embeds = token_ids_to_embeds(embed_layer, seg_prefix, device=device, dtype=embed_dtype)
        suffix_embeds = token_ids_to_embeds(embed_layer, seg_suffix, device=device, dtype=embed_dtype)
        refiner_embed = refiner_latents[idx].to(device=device, dtype=embed_dtype)

        seq = torch.cat([prefix_embeds, refiner_embed, suffix_embeds], dim=0)
        batch_emb, attn_mask = pad_left_embeds([seq], device=device)

        with torch.no_grad():
            generated = model.generate(
                inputs_embeds=batch_emb,
                attention_mask=attn_mask,
                **gen_kwargs,
            )
        # Decode only the new tokens (after input length)
        input_len = batch_emb.size(1)
        new_tokens = generated[0, input_len:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        outputs.append(text)

    return outputs
