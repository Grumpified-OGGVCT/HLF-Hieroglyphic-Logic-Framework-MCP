"""Latent Model Interface — RecursiveMAS-compatible inference path.

Provides direct PyTorch model access for latent-space multi-agent recursion
(arXiv:2604.25917), bypassing Ollama's text-in/text-out REST API to intercept
last-layer hidden states.

Architecture:
  - RecursiveLinkInner:  maps h_id → emb_id  (same-model recursion)
  - RecursiveLinkOuter:  maps h_id → emb_jd (cross-model alignment)
  - LatentModelInterface: loads HF model, captures hidden states before LM head
  - LatentRecursiveSession: orchestrates multi-round latent recursion

All PyTorch/transformers imports are lazy — the module degrades gracefully
when those packages aren't installed.  Use is_latent_available() to check.

Usage:
    from hlf_mcp.hlf.latent_model_interface import LatentRecursiveSession

    if LatentRecursiveSession.is_available():
        session = LatentRecursiveSession(
            agent_models={"primary": "Qwen/Qwen2.5-1.5B-Instruct",
                          "critic":  "meta-llama/Llama-3.2-1B-Instruct"},
            recursion_rounds=2,
        )
        result = session.recursive_infer("Prove: ∀x ∈ ℤ, x + 0 = x")
        print(result["final_text"])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports — module is importable even without PyTorch
_HAS_TORCH = False
_HAS_TRANSFORMERS = False


def is_latent_available() -> bool:
    """Check whether the latent inference path is usable."""
    global _HAS_TORCH, _HAS_TRANSFORMERS
    if not _HAS_TORCH:
        try:
            import torch  # noqa: F401
            _HAS_TORCH = True
        except ImportError:
            return False
    if not _HAS_TRANSFORMERS:
        try:
            import transformers  # noqa: F401
            _HAS_TRANSFORMERS = True
        except ImportError:
            return False
    return True


# ------------------------------------------------------------------ #
# RecursiveLink Modules (arXiv:2604.25917, Section 3.1)
# ------------------------------------------------------------------ #

class RecursiveLinkInner:
    """Inner Link: same-model latent recursion (arXiv:2604.25917, Section 3.1).

    R_in(h) = post_ln(h + W₂·GELU(W₁·pre_ln(h)))

    Maps a model's last-layer hidden state back into its own embedding
    space with LayerNorm pre/post and a residual connection.

    Architecture matches the official RecursiveMAS modeling.py Adapter class.
    """

    @staticmethod
    def build(d_model: int) -> Any:
        """Construct the inner RecursiveLink module.

        Args:
            d_model: Hidden dimension of the model.

        Returns:
            torch.nn.Module or None if PyTorch unavailable.
        """
        try:
            import torch.nn as nn
        except ImportError:
            return None

        class _InnerAdapter(nn.Module):
            def __init__(self, hidden_size: int):
                super().__init__()
                self.proj1 = nn.Linear(hidden_size, hidden_size)
                self.act = nn.GELU()
                self.proj2 = nn.Linear(hidden_size, hidden_size)
                self.pre_ln = nn.LayerNorm(hidden_size)
                self.post_ln = nn.LayerNorm(hidden_size)

            def forward(self, x):  # x: [*, hidden_size]
                h = self.pre_ln(x)
                out = self.proj2(self.act(self.proj1(h)))
                out = x + out  # residual
                return self.post_ln(out)

        return _InnerAdapter(d_model)


class RecursiveLinkOuter:
    """Outer Link: cross-model latent alignment (arXiv:2604.25917, Section 3.1).

    R_out(h) = ln_target(W₂·GELU(W₁·ln_source(h)) + W₃·h)

    Maps between different hidden dimensions with LayerNorm on both
    source and target, a learned residual projection (W₃), and an
    expanded hidden_dim = out_dim * 2 bottleneck.

    Architecture matches the official RecursiveMAS modeling.py CrossModelAdapter.
    """

    @staticmethod
    def build(in_dim: int, out_dim: int) -> Any:
        """Construct the outer RecursiveLink module.

        Args:
            in_dim:  Hidden dimension of the source model.
            out_dim: Hidden dimension of the destination model.

        Returns:
            torch.nn.Module or None if PyTorch unavailable.
        """
        try:
            import torch.nn as nn
        except ImportError:
            return None

        class _OuterAdapter(nn.Module):
            def __init__(self, in_dim: int, out_dim: int):
                super().__init__()
                hidden_dim = out_dim * 2  # paper's bottleneck expansion
                self.proj1 = nn.Linear(in_dim, hidden_dim)
                self.act = nn.GELU()
                self.proj2 = nn.Linear(hidden_dim, out_dim)
                self.ln_source = nn.LayerNorm(in_dim)
                self.ln_target = nn.LayerNorm(out_dim)
                self.residual_proj = nn.Linear(in_dim, out_dim)  # W₃

            def forward(self, x):  # x: [*, in_dim]
                h = self.ln_source(x)
                out = self.proj2(self.act(self.proj1(h)))
                out = out + self.residual_proj(x)  # learned residual projection
                return self.ln_target(out)

        return _OuterAdapter(in_dim, out_dim)


# ------------------------------------------------------------------ #
# Latent Model Interface
# ------------------------------------------------------------------ #

@dataclass
class LatentStepResult:
    """Result from a single latent forward pass."""

    agent_name: str
    hidden_state: Any  # torch.Tensor, shape [1, seq_len, d_model]
    last_hidden: Any  # torch.Tensor, shape [1, d_model] — final token hidden state
    logits: Any | None = None  # Only populated for final (decoding) step


@dataclass
class RecursiveSessionConfig:
    """Configuration for a latent recursive inference session."""

    agent_models: dict[str, str] = field(default_factory=dict)
    recursion_rounds: int = 2
    max_new_tokens: int = 512
    temperature: float = 0.0
    device: str = "auto"  # "auto" | "cpu" | "cuda"
    # RecursiveLink checkpoint paths (optional — uses random init if None)
    inner_link_paths: dict[str, str | None] = field(default_factory=dict)
    outer_link_paths: dict[str, str | None] = field(default_factory=dict)
    # Task scope for adapter selection ("math" | "code" — default "math")
    adapter_task: str = "math"


# ------------------------------------------------------------------ #
# Latent Recursive Session
# ------------------------------------------------------------------ #

class LatentRecursiveSession:
    """Orchestrates multi-agent latent-space recursive inference.

    Follows the RecursiveMAS architecture (arXiv:2604.25917):
      1. Load all agent models frozen (no weight updates).
      2. For each recursion round, each agent runs one forward pass.
      3. Intermediate rounds: capture last-layer hidden state, pipe through
         RecursiveLink, inject into next agent's embedding space.
      4. Final round / final agent: decode to text tokens.

    Minimal resource footprint: only RecursiveLink params are trainable
    (~13M params, <0.31% of full system).  Inference uses standard
    HuggingFace generate() for text output or manual forward() for
    hidden-state extraction.
    """

    def __init__(
        self,
        config: RecursiveSessionConfig | None = None,
        *,
        agent_models: dict[str, str] | None = None,
        recursion_rounds: int = 2,
        max_new_tokens: int = 512,
        device: str = "auto",
    ):
        if config is None:
            config = RecursiveSessionConfig(
                agent_models=agent_models or {},
                recursion_rounds=recursion_rounds,
                max_new_tokens=max_new_tokens,
                device=device,
            )
        self.config = config
        self._models: dict[str, Any] = {}
        self._tokenizers: dict[str, Any] = {}
        self._inner_links: dict[str, Any] = {}
        self._outer_links: dict[tuple[str, str], Any] = {}
        self._loaded = False
        self._monitor_record_id: str | None = None  # ResourceMonitor tracking

    # ── Availability ──────────────────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        return is_latent_available()

    # ── Model Loading ─────────────────────────────────────────────────────

    def load_all(self) -> bool:
        """Load all agent models and tokenizers into memory.

        Returns True if all models loaded successfully, False otherwise.
        """
        if not is_latent_available():
            logger.warning("Latent path unavailable: install torch + transformers")
            return False

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        for agent_name, model_id in self.config.agent_models.items():
            try:
                logger.info(f"Loading {agent_name}: {model_id}")
                tokenizer = AutoTokenizer.from_pretrained(
                    model_id,
                    trust_remote_code=True,
                    padding_side="left",
                )
                # Ensure pad_token is set (some models don't have one)
                if tokenizer.pad_token is None:
                    tokenizer.pad_token = tokenizer.eos_token
                model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if self._use_fp16() else torch.float32,
                    device_map=self._resolve_device(),
                    trust_remote_code=True,
                )
                model.eval()
                for param in model.parameters():
                    param.requires_grad = False  # Frozen base weights

                self._models[agent_name] = model
                self._tokenizers[agent_name] = tokenizer
            except Exception as exc:
                logger.error(f"Failed to load {agent_name} ({model_id}): {exc}")
                return False

        self._build_links()
        self._loaded = True

        # ── Notify ResourceMonitor ───────────────────────────────────────
        self._notify_monitor_load()
        return True

    def _notify_monitor_load(self) -> None:
        """Register this session with the global ResourceMonitor."""
        try:
            from hlf_mcp.hlf.resource_monitor import (
                ResourceMonitor,
                estimate_model_vram,
            )
            monitor = ResourceMonitor.get_instance()
            agent_ids = list(self.config.agent_models.values())
            device = self._resolve_device()
            fp16 = self._use_fp16()
            total_vram = sum(
                estimate_model_vram(mid, fp16=fp16) for mid in agent_ids
            )
            adapter_count = len(self._inner_links) + len(self._outer_links)
            record = monitor.register_session_load(
                session_type="latent_recursive",
                agent_models=agent_ids,
                adapter_count=adapter_count,
                recursion_rounds=self.config.recursion_rounds,
                vram_allocated_mb=total_vram,
                device=device,
            )
            self._monitor_record_id = record.record_id
        except Exception:
            pass  # ResourceMonitor is optional; never block inference

    def _notify_monitor_unload(self) -> None:
        """Notify the global ResourceMonitor that models are being freed."""
        try:
            from hlf_mcp.hlf.resource_monitor import ResourceMonitor
            monitor = ResourceMonitor.get_instance()
            monitor.register_session_unload(
                record_id=self._monitor_record_id,
                agent_models=list(self.config.agent_models.values()),
            )
        except Exception:
            pass

    def _build_links(self) -> None:
        """Construct RecursiveLink modules matching official architecture.

        Inner links use LayerNorm pre/post + residual (Adapter class).
        Outer links use learned residual projection + LayerNorm (CrossModelAdapter).

        If checkpoint paths are provided, loads trained weights from .pt files.
        Otherwise uses random initialization (useful for architecture verification).
        """
        for name, model in self._models.items():
            cfg = model.config
            d_model = getattr(cfg, "hidden_size", getattr(cfg, "d_model", 768))
            inner = RecursiveLinkInner.build(d_model)
            if inner is not None:
                # Load trained weights if available
                inner_path = self.config.inner_link_paths.get(name)
                if inner_path:
                    self._load_adapter_weights(inner, inner_path)
                    logger.info(f"Loaded trained inner link weights for {name}: {inner_path}")
                # Move adapter to model device and match dtype
                inner = inner.to(device=model.device, dtype=model.dtype)
                self._inner_links[name] = inner

        agent_names = list(self._models.keys())
        for src_name in agent_names:
            for dst_name in agent_names:
                if src_name == dst_name:
                    continue
                src_cfg = self._models[src_name].config
                dst_cfg = self._models[dst_name].config
                d_src = getattr(src_cfg, "hidden_size", getattr(src_cfg, "d_model", 768))
                d_dst = getattr(dst_cfg, "hidden_size", getattr(dst_cfg, "d_model", 768))
                outer = RecursiveLinkOuter.build(d_src, d_dst)
                if outer is not None:
                    # Load trained outer link weights if available
                    outer_key = f"{src_name}_{dst_name}"
                    outer_path = self.config.outer_link_paths.get(outer_key)
                    if outer_path:
                        self._load_adapter_weights(outer, outer_path)
                        logger.info(f"Loaded trained outer link weights for {outer_key}: {outer_path}")
                    # Move adapter to destination model device and match dtype
                    outer = outer.to(device=self._models[dst_name].device, dtype=self._models[dst_name].dtype)
                    self._outer_links[(src_name, dst_name)] = outer

    @staticmethod
    def _load_adapter_weights(module: Any, path: str) -> None:
        """Load trained RecursiveLink weights from a .pt checkpoint file."""
        import torch
        state_dict = torch.load(path, map_location="cpu", weights_only=True)
        # Handle wrapped state dicts (some checkpoints store under 'adapter' key)
        if "adapter" in state_dict:
            state_dict = state_dict["adapter"]
        module.load_state_dict(state_dict, strict=True)

    # ── Inference ─────────────────────────────────────────────────────────

    def recursive_infer(self, prompt: str) -> dict[str, Any]:
        """Run multi-agent latent recursive inference.

        Args:
            prompt: Input text to process.

        Returns:
            dict with 'final_text', 'steps', 'rounds', 'status'.
        """
        if not self._loaded and not self.load_all():
            return {
                "status": "error",
                "error": "Failed to load models. Ensure torch + transformers are installed.",
                "final_text": "",
                "steps": [],
                "rounds": 0,
            }

        import torch

        agent_names = list(self._models.keys())
        if not agent_names:
            return {
                "status": "error",
                "error": "No agent models configured.",
                "final_text": "",
                "steps": [],
                "rounds": 0,
            }

        steps: list[dict[str, Any]] = []

        # ── Round 1: All agents process initial prompt ──────────────────
        first_agent = agent_names[0]
        hidden_state = self._forward_latent(
            first_agent, prompt=prompt, steps=steps, round_idx=1
        )

        for round_idx in range(1, self.config.recursion_rounds + 1):
            for agent_name in agent_names:
                # Skip first agent on first round (already processed)
                if round_idx == 1 and agent_name == first_agent:
                    continue

                # Project hidden state through RecursiveLink
                if agent_name != self._last_agent(steps):
                    prev_agent = self._last_agent(steps)
                    link_key = (prev_agent, agent_name)
                    if link_key in self._outer_links:
                        hidden_state = self._apply_link(
                            hidden_state, self._outer_links[link_key], "outer"
                        )

                hidden_state = self._forward_latent(
                    agent_name,
                    hidden_state=hidden_state,
                    steps=steps,
                    round_idx=round_idx,
                )

        # ── Final agent decodes to text ─────────────────────────────────
        final_agent = agent_names[-1]
        final_text = self._decode_text(final_agent, hidden_state, prompt)

        return {
            "status": "ok",
            "final_text": final_text,
            "steps": steps,
            "rounds": self.config.recursion_rounds,
            "agent_count": len(agent_names),
        }

    def _forward_latent(
        self,
        agent_name: str,
        prompt: str | None = None,
        hidden_state: Any | None = None,
        steps: list[dict[str, Any]] | None = None,
        round_idx: int = 0,
    ) -> Any:
        """Run one forward pass, capturing last-layer hidden state.

        Returns the last-token hidden state tensor [1, d_model].
        """
        import torch

        model = self._models[agent_name]
        tokenizer = self._tokenizers[agent_name]

        if prompt is not None:
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            with torch.no_grad():
                outputs = model(**inputs, output_hidden_states=True)
            last_hidden = outputs.hidden_states[-1][:, -1, :]
        elif hidden_state is not None:
            # Inject latent state through embedding layer
            embed = model.get_input_embeddings()
            if hasattr(embed, "weight"):
                d_embed = embed.weight.shape[1]
            else:
                d_embed = getattr(model.config, "hidden_size", 768)

            # Project hidden to embedding dimension if needed
            h = hidden_state
            if isinstance(h, torch.Tensor):
                # Cross-model dimension alignment: outer link should already
                # project to target hidden dim. Inner link is for intra-model
                # recursion (same-dim residual refinement), NOT cross-dim
                # projection. If dimensions still don't match, the outer
                # link wasn't applied — use the inner link as a fallback
                # only if it matches, otherwise truncate.
                if h.shape[-1] != d_embed:
                    inner_link = self._inner_links.get(agent_name)
                    inner_dim = getattr(inner_link, "pre_ln", None)
                    inner_dim = inner_dim.normalized_shape[0] if inner_dim is not None else None
                    if inner_link is not None and h.shape[-1] == inner_dim:
                        h = inner_link(h)
                    elif inner_link is not None:
                        logger.warning(
                            f"Inner link for {agent_name} expects dim {inner_dim} "
                            f"but got {h.shape[-1]}. Outer link may have failed. "
                            f"Truncating to {d_embed}."
                        )
                        h = h[..., :d_embed]
                    else:
                        h = h[..., :d_embed]

                # Normalize to inputs_embeds shape: [batch, seq_len, hidden]
                if h.dim() == 2:
                    h = h.unsqueeze(1)  # [1, d] → [1, 1, d]
                elif h.dim() > 3:
                    h = h.reshape(1, 1, h.shape[-1])  # Flatten higher dims

                inputs_embeds = h  # [1, 1, d_embed]
                with torch.no_grad():
                    outputs = model(
                        inputs_embeds=inputs_embeds,
                        output_hidden_states=True,
                    )
            else:
                raise TypeError(f"hidden_state must be a Tensor, got {type(hidden_state)}")

            last_hidden = outputs.hidden_states[-1][:, -1, :]
        else:
            raise ValueError("Must provide either prompt or hidden_state")

        if steps is not None:
            steps.append({
                "agent": agent_name,
                "round": round_idx,
                "hidden_shape": list(last_hidden.shape),
            })

        return last_hidden

    def _decode_text(
        self,
        agent_name: str,
        hidden_state: Any,
        original_prompt: str,
    ) -> str:
        """Decode final hidden state to text via the designated agent."""
        import torch

        model = self._models[agent_name]
        tokenizer = self._tokenizers[agent_name]

        embed = model.get_input_embeddings()
        d_embed = embed.weight.shape[1]

        h = hidden_state
        if h.shape[-1] != d_embed:
            inner_link = self._inner_links.get(agent_name)
            inner_dim = getattr(inner_link, "pre_ln", None)
            inner_dim = inner_dim.normalized_shape[0] if inner_dim is not None else None
            if inner_link is not None and h.shape[-1] == inner_dim:
                h = inner_link(h)
            elif inner_link is not None:
                logger.warning(
                    f"Decode: inner link for {agent_name} expects dim {inner_dim} "
                    f"but got {h.shape[-1]}. Truncating to {d_embed}."
                )
                h = h[..., :d_embed]
            else:
                h = h[..., :d_embed]

        # Normalize to [1, 1, d_embed] for concatenation with prompt embeds
        if h.dim() == 2:
            h = h.unsqueeze(1)  # [1, d] → [1, 1, d]
        elif h.dim() > 3:
            h = h.reshape(1, 1, h.shape[-1])

        # Embed the prompt to provide generation context
        prompt_inputs = tokenizer(original_prompt, return_tensors="pt").to(model.device)
        prompt_embeds = embed(prompt_inputs.input_ids)

        # Concatenate prompt embeds with latent representation
        latent_embed = h  # Already normalized to [1, 1, d_embed] above
        combined_embeds = torch.cat([prompt_embeds, latent_embed], dim=1)

        # Build attention_mask for combined embeds (1 for all tokens)
        attention_mask = torch.ones(
            combined_embeds.shape[:2], dtype=torch.long, device=combined_embeds.device
        )

        with torch.no_grad():
            generated = model.generate(
                inputs_embeds=combined_embeds,
                attention_mask=attention_mask,
                max_new_tokens=self.config.max_new_tokens,
                temperature=self.config.temperature,
                do_sample=self.config.temperature > 0,
                pad_token_id=tokenizer.eos_token_id,
            )

        return tokenizer.decode(generated[0], skip_special_tokens=True)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _apply_link(
        self,
        hidden_state: Any,
        link_module: Any,
        link_type: str,
    ) -> Any:
        """Apply a RecursiveLink module.

        The official architecture (Adapter/CrossModelAdapter) includes
        its own residual connection internally — we do NOT add another.
        """
        if link_module is None:
            return hidden_state
        try:
            return link_module(hidden_state)
        except Exception as exc:
            logger.warning(
                f"RecursiveLink {link_type} failed: {exc}. "
                f"Input shape: {getattr(hidden_state, 'shape', 'N/A')}. "
                f"Returning unprojected hidden state — downstream may fail."
            )
            return hidden_state

    def _last_agent(self, steps: list[dict[str, Any]]) -> str:
        if not steps:
            return ""
        return steps[-1]["agent"]

    def _resolve_device(self) -> str:
        dev = self.config.device
        if dev == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return dev

    def _use_fp16(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    # ── Cleanup ───────────────────────────────────────────────────────────

    def unload(self) -> None:
        """Release all model references to free GPU/CPU memory."""
        import gc as _gc
        import torch

        # Notify ResourceMonitor before releasing
        self._notify_monitor_unload()

        # Move models to CPU and delete explicitly
        for name in list(self._models.keys()):
            try:
                model = self._models.pop(name)
                model.cpu()
                del model
            except Exception:
                pass

        self._tokenizers.clear()
        self._inner_links.clear()
        self._outer_links.clear()
        self._loaded = False

        # Aggressively free CUDA memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        _gc.collect()

        logger.info("LatentRecursiveSession unloaded all models.")

    def __del__(self) -> None:
        try:
            self.unload()
        except Exception:
            pass


# ------------------------------------------------------------------ #
# Convenience — session builder
# ------------------------------------------------------------------ #

def build_latent_session(
    agent_models: dict[str, str],
    *,
    recursion_rounds: int = 2,
    device: str = "auto",
) -> LatentRecursiveSession | None:
    """Factory: build a LatentRecursiveSession if PyTorch is available.

    Returns None if the latent path is not usable, so callers can
    fall back to Ollama/OpenRouter text-based inference.
    """
    if not is_latent_available():
        return None

    config = RecursiveSessionConfig(
        agent_models=agent_models,
        recursion_rounds=recursion_rounds,
        device=device,
    )
    return LatentRecursiveSession(config)
