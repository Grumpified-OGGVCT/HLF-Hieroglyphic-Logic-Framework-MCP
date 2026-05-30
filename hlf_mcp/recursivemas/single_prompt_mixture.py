#!/usr/bin/env python3
"""
single_prompt_mixture.py — Bridge between governed_pipeline.py and official inference_mas_mixture.py.

For the Mixture (HIE) style: 3 domain expert agents (math, code, science) run in parallel
through latent-space processing, then a summarizer agent synthesizes the final text answer.
Uses pre-loaded LoadedAgent objects instead of raw paths, enabling the SwarmGlass-governed
pipeline to use official RecursiveMAS inference with slot-based latent interleaving.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Sequence

import torch
from tqdm import tqdm

THIS_DIR = Path(__file__).resolve().parent
RECURSIVEMAS_SUBMODULE = THIS_DIR.parent.parent / "recursivemas"
if str(RECURSIVEMAS_SUBMODULE) not in sys.path:
    sys.path.insert(0, str(RECURSIVEMAS_SUBMODULE))

from prompts import (
    HIE_CODE_EXPERT_SLOT,
    HIE_FEEDBACK_SLOT,
    HIE_MATH_EXPERT_SLOT,
    HIE_SCIENCE_EXPERT_SLOT,
    build_hie_expert_prompt_with_feedback_slot,
    build_hie_summarizer_prompt_with_slots,
    build_hie_expert_prompt,
)
from inference_utils.inference_mas import (
    autoregressive_latent_rollout,
    run_inner_adapter,
    run_outer_adapter,
    pad_left_embeds,
    token_ids_to_embeds,
    render_chat_prompt_ids,
    build_generation_kwargs,
    batch_iter_indices,
    split_prompt_ids_by_slots,
)

# Slot definitions must match HIE_SLOT_TEXTS from inference_mas_mixture.py
HIE_SLOT_TEXTS = (HIE_MATH_EXPERT_SLOT, HIE_CODE_EXPERT_SLOT, HIE_SCIENCE_EXPERT_SLOT)
HIE_EXPERT_ROLES = ("hie_math_expert", "hie_code_expert", "hie_science_expert")


def split_prompt_ids_by_hie_slots(
    tokenizer,
    user_prompt_with_slots: str,
    enable_thinking: bool = False,
) -> List[List[int]]:
    """Split a HIE summarizer prompt into segments per expert slot."""
    return split_prompt_ids_by_slots(
        tokenizer,
        user_prompt_with_slots,
        list(HIE_SLOT_TEXTS),
        enable_thinking,
    )


def run_hie_expert_stage(
    agent,              # LoadedAgent
    outer_adapter,      # CrossModelAdapter (expert→summarizer)
    questions: List[str],
    role: str,          # "hie_math_expert", "hie_code_expert", "hie_science_expert"
    latent_steps: int,
    device: torch.device,
    mas_task: str = "code",
    feedback_latents: Optional[List[torch.Tensor]] = None,
) -> List[torch.Tensor]:
    """Run a single HIE expert through latent processing → outer adapter → summarizer input."""
    model, tokenizer = agent.model, agent.tokenizer
    embed_layer = model.get_input_embeddings()
    embed_dtype = embed_layer.weight.dtype
    inner = agent.inner_adapter

    use_feedback = feedback_latents is not None
    if use_feedback and len(feedback_latents) != len(questions):
        raise ValueError(f"{role}: feedback_latents size mismatch")

    results: List[torch.Tensor] = []
    for idx, question in enumerate(questions):
        if use_feedback:
            user_prompt = build_hie_expert_prompt_with_feedback_slot(
                question, role, mas_task=mas_task,
            )
            seg_prefix, seg_suffix = split_prompt_ids_by_slots(
                tokenizer, user_prompt, [HIE_FEEDBACK_SLOT], enable_thinking=False,
            )
            prefix_emb = token_ids_to_embeds(embed_layer, seg_prefix, device=device, dtype=embed_dtype)
            suffix_emb = token_ids_to_embeds(embed_layer, seg_suffix, device=device, dtype=embed_dtype)
            feedback_emb = feedback_latents[idx].to(device=device, dtype=embed_dtype)
            seq = torch.cat([prefix_emb, feedback_emb, suffix_emb], dim=0)
        else:
            # First round: no feedback, use simple expert prompt
            user_prompt = build_hie_expert_prompt(question, role, mas_task=mas_task)
            prompt_ids = render_chat_prompt_ids(tokenizer, user_prompt, enable_thinking=False)
            seq = embed_layer(torch.tensor(prompt_ids, dtype=torch.long, device=device).unsqueeze(0))[0]
            if seq.dtype != embed_dtype:
                seq = seq.to(embed_dtype)

        batch_emb, attn_mask = pad_left_embeds([seq], device=device)

        hidden = autoregressive_latent_rollout(
            model=model, rollout_inner_adapter=inner,
            input_embeds=batch_emb, attention_mask=attn_mask,
            latent_steps=latent_steps,
        )
        self_latent = run_inner_adapter(inner, hidden, output_dtype=embed_dtype)
        mapped = run_outer_adapter(outer_adapter, self_latent, output_dtype=torch.float32)
        results.append(mapped[0].detach().cpu())

    return results


def run_hie_summarizer_generate(
    agent,              # LoadedAgent (summarizer)
    questions: List[str],
    expert_latents_list: List[List[torch.Tensor]],  # [math_latents, code_latents, science_latents]
    max_new_tokens: int = 1000,
    temperature: float = 0.6,
    top_p: float = 0.95,
    device: torch.device = None,
    mas_task: str = "code",
) -> List[str]:
    """Run the HIE summarizer: consumes 3 expert latent vectors, generates final text."""
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model, tokenizer = agent.model, agent.tokenizer
    embed_layer = model.get_input_embeddings()
    embed_dtype = embed_layer.weight.dtype
    hidden_size = embed_layer.weight.size(-1)

    # Validate all expert latents match summarizer hidden size
    for name, latents in zip(("math", "code", "science"), expert_latents_list):
        if latents and latents[0].size(-1) != hidden_size:
            raise RuntimeError(
                f"{name} expert → summarizer latent dim mismatch: {latents[0].size(-1)} vs {hidden_size}"
            )

    # Build prompt segments for each question with 3 expert slots
    prompt_segments = []
    for question in questions:
        summarizer_prompt = build_hie_summarizer_prompt_with_slots(
            question, mas_task=mas_task,
        )
        seg = split_prompt_ids_by_hie_slots(
            tokenizer, summarizer_prompt, enable_thinking=False,
        )
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
        # seg = [prefix, math_slot, code_slot, science_slot, suffix]
        seg = prompt_segments[idx]
        if len(seg) != 5:
            raise RuntimeError(f"Expected 5 prompt segments for HIE, got {len(seg)}")

        seg_prefix = seg[0]       # before MATH slot
        seg_after_math = seg[1]   # between MATH and CODE slots
        seg_after_code = seg[2]   # between CODE and SCIENCE slots
        seg_after_science = seg[3]  # between SCIENCE and end
        seg_suffix = seg[4] if len(seg) > 4 else []

        prefix_emb = token_ids_to_embeds(embed_layer, seg_prefix, device=device, dtype=embed_dtype)
        math_emb = expert_latents_list[0][idx].to(device=device, dtype=embed_dtype)
        between_mc_emb = token_ids_to_embeds(embed_layer, seg_after_math, device=device, dtype=embed_dtype)
        code_emb = expert_latents_list[1][idx].to(device=device, dtype=embed_dtype)
        between_cs_emb = token_ids_to_embeds(embed_layer, seg_after_code, device=device, dtype=embed_dtype)
        science_emb = expert_latents_list[2][idx].to(device=device, dtype=embed_dtype)
        suffix_emb = token_ids_to_embeds(embed_layer, seg_after_science, device=device, dtype=embed_dtype)

        seq = torch.cat([
            prefix_emb, math_emb, between_mc_emb, code_emb,
            between_cs_emb, science_emb, suffix_emb,
        ], dim=0)

        batch_emb, attn_mask = pad_left_embeds([seq], device=device)

        with torch.no_grad():
            generated = model.generate(
                inputs_embeds=batch_emb,
                attention_mask=attn_mask,
                **gen_kwargs,
            )
        input_len = batch_emb.size(1)
        new_tokens = generated[0, input_len:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        outputs.append(text)

    return outputs
