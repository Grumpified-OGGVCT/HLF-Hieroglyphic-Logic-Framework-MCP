"""
MoE RecursiveMAS — Mixture-of-Experts multi-agent latent-space recursion.

Architecture:
  ┌---------------------------------------------------------┐
  │                    MoE RecursiveMAS                      │
  │                                                         │
  │  Task -> Expert A (text) -> hidden state -> [MoE Router]   │
  │     ┌------------------------------------------┐        │
  │     │  Router scores: [coder:0.6, critic:0.3,   │        │
  │     │                  diverse:0.1]              │        │
  │     │  -> Route to top expert -> bridge -> process │        │
  │     └------------------------------------------┘        │
  │  -> new hidden state -> Router -> ... -> Final Decode       │
  └---------------------------------------------------------┘

Experts (tiny, fit in 12GB VRAM collectively):
  - coder:     Qwen2.5-Coder-0.5B-Instruct (896-dim, ~1GB)
  - critic:    SmolLM2-360M-Instruct       (576-dim, ~0.7GB)
  - diverse:   gpt2                         (768-dim, ~0.5GB)

Total weight VRAM: ~2.2GB. With bridges + KV cache: ~4-5GB. Safe on 12GB.
"""

import os
import sys
import time
import threading
import argparse
import warnings
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from enum import Enum

import torch
import torch.nn as nn
import torch.nn.functional as F
import psutil

warnings.filterwarnings("ignore")

# ===============================================================================
# Context Augmenter — datetime, web search, web fetch for real-time awareness
# ===============================================================================

class ContextAugmenter:
    """Enriches prompts with real-time info before they reach experts.
    
    All augmentation happens in the prompt text — no model-level tool calling needed.
    Works with any model, including tiny ones.
    """
    
    def __init__(self, enable_search: bool = True, enable_fetch: bool = True):
        self.enable_search = enable_search
        self.enable_fetch = enable_fetch
    
    def enrich(self, task: str) -> str:
        """Build an enriched prompt from a raw task."""
        parts = []
        
        # 1. Current datetime — always injected
        parts.append(self._datetime_context())
        
        # 2. Web search if task seems to need current info
        if self.enable_search and self._needs_web_info(task):
            search_results = self._search(task)
            if search_results:
                parts.append(search_results)
        
        # 3. The actual task
        parts.append(f"## Task\n{task}")
        
        return "\n\n".join(parts)
    
    def _datetime_context(self) -> str:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        return (
            f"## Current Date & Time\n"
            f"- UTC: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"- Local: {local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"- Day: {now.strftime('%A')}\n"
            f"Use this to ensure your response is current and accurate."
        )
    
    def _needs_web_info(self, task: str) -> bool:
        """Heuristic: does this task need real-time web info?"""
        web_signals = [
            "latest", "current", "recent", "new", "2025", "2026", "today",
            "news", "update", "version", "release", "price", "stock",
            "weather", "event", "happening", "now", "just announced",
            "what is the", "who is", "tell me about", "explain",
        ]
        task_lower = task.lower()
        return any(signal in task_lower for signal in web_signals)
    
    def _search(self, query: str, max_results: int = 3) -> str:
        """Search the web via DuckDuckGo."""
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(r)
            
            if not results:
                return ""
            
            lines = ["## Web Search Results"]
            for i, r in enumerate(results, 1):
                title = r.get('title', 'No title')
                body = r.get('body', '')[:300]
                href = r.get('href', '')
                lines.append(f"{i}. **{title}**\n   {body}\n   Source: {href}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"<!-- Web search unavailable: {e} -->"
    
    def fetch_page(self, url: str, max_chars: int = 2000) -> str:
        """Fetch and extract text from a webpage."""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Remove scripts and styles
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            # Collapse whitespace
            import re
            text = re.sub(r'\s+', ' ', text)
            
            return f"## Fetched: {url}\n{text[:max_chars]}"
        except Exception as e:
            return f"<!-- Fetch failed for {url}: {e} -->"


# ===============================================================================
# Resource Monitor
# ===============================================================================

class ResourceMonitor:
    """Background thread. Kills process if VRAM/RAM exceeds limits."""

    def __init__(self, vram_limit_gb: float = 10.5, ram_limit_gb: float = 58.0):
        self.vram_limit_gb = vram_limit_gb
        self.ram_limit_gb = ram_limit_gb
        self.peak_vram = 0.0
        self.peak_ram = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[MONITOR] VRAM limit: {self.vram_limit_gb}GB | RAM limit: {self.ram_limit_gb}GB")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        print(f"[RESOURCE] Peak VRAM: {self.peak_vram:.1f}GB | Peak RAM: {self.peak_ram:.1f}GB")

    def _loop(self):
        while not self._stop.is_set():
            try:
                vram, ram = self._sample()
                self.peak_vram = max(self.peak_vram, vram)
                self.peak_ram = max(self.peak_ram, ram)
                if vram > self.vram_limit_gb:
                    print(f"\n[FATAL] VRAM {vram:.1f}GB > {self.vram_limit_gb}GB — KILLING")
                    os._exit(1)
                if ram > self.ram_limit_gb:
                    print(f"\n[FATAL] RAM {ram:.1f}GB > {self.ram_limit_gb}GB — KILLING")
                    os._exit(1)
            except Exception:
                pass
            self._stop.wait(2.0)

    def _sample(self) -> Tuple[float, float]:
        vram, ram = 0.0, 0.0
        try:
            ram = psutil.virtual_memory().used / (1024 ** 3)
        except Exception:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            vram = pynvml.nvmlDeviceGetMemoryInfo(h).used / (1024 ** 3)
        except Exception:
            pass
        return vram, ram

    def snapshot(self) -> Dict[str, float]:
        vram, ram = self._sample()
        return {"vram_gb": vram, "ram_gb": ram,
                "peak_vram_gb": self.peak_vram, "peak_ram_gb": self.peak_ram}


# ===============================================================================
# Expert Registry
# ===============================================================================

class ExpertRole(Enum):
    CODER = "coder"
    CRITIC = "critic"
    RESEARCHER = "researcher"
    DIVERSE = "diverse"
    TOOLS = "tools"

@dataclass
class ExpertProfile:
    role: ExpertRole
    model_name: str
    description: str
    system_prompt: str
    task_affinity: List[str]  # Tasks this expert is suited for
    priority: int
    use_4bit: bool = False   # Load with 4-bit quantization (for larger models)

EXPERT_REGISTRY: Dict[str, ExpertProfile] = {
    "coder": ExpertProfile(
        role=ExpertRole.CODER,
        model_name="Qwen/Qwen2.5-Coder-0.5B-Instruct",
        description="Code generation & refactoring specialist.",
        system_prompt="You are an expert programmer. Write clean, correct, well-documented code.",
        task_affinity=["code", "debug", "refactor", "implement", "build"],
        priority=3,
    ),
    "critic": ExpertProfile(
        role=ExpertRole.CRITIC,
        model_name="google/gemma-3-1b-it",
        description="Code reviewer. Catches bugs, security holes, edge cases.",
        system_prompt="You are a senior code reviewer. Find bugs, security issues, edge cases. Be specific and actionable.",
        task_affinity=["review", "audit", "analyze", "critique", "validate"],
        priority=3,
        use_4bit=True,
    ),
    "researcher": ExpertProfile(
        role=ExpertRole.RESEARCHER,
        model_name="google/gemma-3-1b-it",
        description="Research, context-gathering, knowledge synthesis.",
        system_prompt="You are a thorough researcher. Synthesize information, find patterns, explain clearly.",
        task_affinity=["research", "explain", "summarize", "analyze", "compare"],
        priority=2,
        use_4bit=True,
    ),
    "diverse": ExpertProfile(
        role=ExpertRole.DIVERSE,
        model_name="google/gemma-3-1b-it",
        description="Alternative perspective. Breaks groupthink with divergent prompts.",
        system_prompt="Think differently. Challenge every assumption. Propose approaches nobody considered.",
        task_affinity=["brainstorm", "alternative", "creative", "explore", "different"],
        priority=1,
        use_4bit=True,
    ),
    "tools": ExpertProfile(
        role=ExpertRole.TOOLS,
        model_name="google/gemma-4-E2B-it",
        description="Function calling + tool execution. Gemma 4 E2B for structured JSON output.",
        system_prompt=(
            "You are a tools specialist. Output a JSON function call.\n"
            "Available: web_search(query), web_fetch(url), file_read(path), "
            "file_write(path, content), run_command(cmd).\n"
            'Format: {"function": "name", "args": {...}}'
        ),
        task_affinity=["search", "fetch", "file", "command", "tool", "run", "execute", "read", "write", "download"],
        priority=2,
        use_4bit=True,
    ),
}


# ===============================================================================
# Expert Wrapper — loads a HF model, captures/accepts hidden states
# ===============================================================================

class ExpertAgent:
    """Wraps a HuggingFace causal LM for latent-space handoffs."""

    def __init__(self, profile: ExpertProfile, device: str = "cuda"):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.profile = profile
        self.role = profile.role
        self.device = device

        print(f"  [LOAD] {profile.role.value}: {profile.model_name}" + 
              (" (4-bit)" if profile.use_4bit else ""))

        self.tokenizer = AutoTokenizer.from_pretrained(profile.model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load with 4-bit quantization or FP16
        if profile.use_4bit:
            from transformers import BitsAndBytesConfig
            nf4_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                profile.model_name,
                quantization_config=nf4_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
            ).eval()
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                profile.model_name,
                torch_dtype=torch.float16,
                trust_remote_code=True,
            ).to(device).eval()

        cfg = self.model.config
        # Resolve hidden dim across model architectures
        if hasattr(cfg, 'text_config'):
            cfg = cfg.text_config  # Multi-modal models like Gemma 4
        if hasattr(cfg, 'hidden_size'):
            self.hidden_dim = cfg.hidden_size
        elif hasattr(cfg, 'n_embd'):
            self.hidden_dim = cfg.n_embd
        elif hasattr(cfg, 'd_model'):
            self.hidden_dim = cfg.d_model
        else:
            raise ValueError(f"Cannot determine hidden_dim from config: {cfg}")

        self.dtype = next(self.model.parameters()).dtype
        self.vram_gb = sum(p.numel() * self.dtype.itemsize for p in self.model.parameters()) / (1024**3)

        num_layers = getattr(cfg, 'num_hidden_layers', getattr(cfg, 'n_layer', '?'))
        print(f"    dim={self.hidden_dim}, vram={self.vram_gb:.2f}GB, "
              f"dtype={self.dtype}, layers={num_layers}")

    def process_text(self, prompt: str, max_tokens: int = 48, temperature: float = 0.7) -> dict:
        """Generate from text prompt AND capture final hidden state."""
        tokens = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        return self._generate(tokens.input_ids, None, max_tokens, temperature)

    def process_latent(self, hidden_state: torch.Tensor, max_tokens: int = 48,
                       temperature: float = 0.7) -> dict:
        """Generate from latent hidden state AND capture new hidden state."""
        # Convert to model's dtype
        hidden_state = hidden_state.to(dtype=self.dtype, device=self.device)
        return self._generate(None, hidden_state, max_tokens, temperature)

    def _generate(self, input_ids, inputs_embeds, max_tokens: int, temperature: float) -> dict:
        """Generate tokens and capture final hidden state using model.generate."""
        with torch.no_grad():
            if input_ids is not None:
                # Standard text generation
                outputs = self.model.generate(
                    input_ids,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    output_hidden_states=True,
                    return_dict_in_generate=True,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
                # Get all generated tokens (excluding prompt)
                prompt_len = input_ids.shape[1]
                generated_ids = outputs.sequences[0, prompt_len:].tolist()
                # Last hidden state from final step
                hidden_state = outputs.hidden_states[-1][-1][:, -1:, :].detach().clone()
            else:
                # Latent-space generation: start from embeddings
                generated_ids = []
                current_embeds = inputs_embeds
                hidden_state = None
                for step in range(max_tokens):
                    out = self.model(
                        inputs_embeds=current_embeds,
                        output_hidden_states=True,
                    )
                    hidden_state = out.hidden_states[-1][:, -1:, :].detach().clone()
                    del out.hidden_states
                    logits = out.logits[:, -1, :] / temperature
                    probs = torch.softmax(logits, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1)
                    generated_ids.append(next_token.item())
                    del out, logits, probs
                    if next_token.item() == self.tokenizer.eos_token_id:
                        break
                    current_embeds = self.model.get_input_embeddings()(next_token)
                    if step % 16 == 0:
                        torch.cuda.empty_cache()
                
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        return {"text": text, "hidden_state": hidden_state}

    def decode_final(self, hidden_state: torch.Tensor, max_tokens: int = 256,
                     temperature: float = 0.6) -> str:
        """Decode latent state to text. Used ONLY for final output."""
        current_embeds = hidden_state
        generated_ids = []

        with torch.no_grad():
            for step in range(max_tokens):
                outputs = self.model(
                    inputs_embeds=current_embeds,
                    output_hidden_states=False,
                )
                logits = outputs.logits[:, -1, :] / temperature
                probs = torch.softmax(logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                generated_ids.append(next_token.item())
                del outputs, logits, probs

                if next_token.item() == self.tokenizer.eos_token_id:
                    break

                current_embeds = self.model.get_input_embeddings()(next_token)
                if step % 16 == 0:
                    torch.cuda.empty_cache()

        return self.tokenizer.decode(generated_ids, skip_special_tokens=True)

    def unload(self):
        """Free VRAM by moving model to CPU and clearing."""
        self.model = self.model.to("cpu")
        torch.cuda.empty_cache()


# ===============================================================================
# Bridge Matrix — all-pairs linear projections between expert embedding spaces
# ===============================================================================

class BridgeMatrix:
    """Pre-computed bridges for all expert pairs."""

    def __init__(self, experts: Dict[str, ExpertAgent]):
        self.bridges: Dict[Tuple[str, str], nn.Module] = {}
        self.experts = experts

        for src_name, src in experts.items():
            for dst_name, dst in experts.items():
                if src_name == dst_name:
                    # Self-loop: identity bridge (pass-through)
                    key = (src_name, dst_name)
                    self.bridges[key] = self._build_self_bridge(src.hidden_dim)
                    continue
                key = (src_name, dst_name)
                bridge = self._build_bridge(src.hidden_dim, dst.hidden_dim)
                self.bridges[key] = bridge.cuda()
                print(f"  [BRIDGE] {src_name}({src.hidden_dim}) -> "
                      f"{dst_name}({dst.hidden_dim}): "
                      f"{sum(p.numel() for p in bridge.parameters()):,} params")

    def _build_self_bridge(self, dim: int) -> nn.Module:
        """Identity bridge for same-expert routing (pass-through)."""
        class IdentityBridge(nn.Module):
            def __init__(self, d):
                super().__init__()
            def forward(self, x):
                return x
        return IdentityBridge(dim)

    def _build_bridge(self, dim_from: int, dim_to: int) -> nn.Module:
        """Learned projection with residual refinement."""
        class Bridge(nn.Module):
            def __init__(self, d_in, d_out):
                super().__init__()
                self.proj = nn.Linear(d_in, d_out, bias=False)
                if d_in == d_out:
                    nn.init.eye_(self.proj.weight)
                else:
                    nn.init.orthogonal_(self.proj.weight)
                self.alpha = nn.Parameter(torch.tensor(0.1))
                mid = max(d_out, d_in) * 2
                self.refine = nn.Sequential(
                    nn.Linear(d_out, mid), nn.GELU(), nn.Linear(mid, d_out)
                )
                nn.init.normal_(self.refine[0].weight, std=0.02)
                nn.init.normal_(self.refine[2].weight, std=0.02)

            def forward(self, x):
                base = self.proj(x)
                return base + self.alpha * self.refine(base)

        return Bridge(dim_from, dim_to)

    def project(self, hidden: torch.Tensor, from_expert: str, to_expert: str) -> torch.Tensor:
        key = (from_expert, to_expert)
        bridge = self.bridges[key]
        # Identity bridges just pass through
        if isinstance(bridge, nn.Module) and not hasattr(bridge, 'proj'):
            return hidden
        return bridge(hidden.to(dtype=bridge.proj.weight.dtype))


# ===============================================================================
# MoE Router — gating network that routes hidden states to the best expert
# ===============================================================================

class MoERouter(nn.Module):
    """
    Tiny gating network that scores experts based on the current hidden state.
    
    Takes a hidden state vector -> predicts which expert should handle the next round.
    This is MoE-style gating at the AGENT level (not token level).
    """

    def __init__(self, input_dim: int, expert_names: List[str], 
                 expert_dims: Dict[str, int]):
        super().__init__()
        self.expert_names = expert_names
        self.num_experts = len(expert_names)
        self.expert_dims = expert_dims

        # Per-expert input projections (handles varying dims)
        self.input_projs = nn.ModuleDict({
            name: nn.Linear(dim, 256, bias=False)
            for name, dim in expert_dims.items()
        })

        # Gating network
        self.gate = nn.Sequential(
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, self.num_experts),
        )

        # Expert embeddings for context-aware routing
        self.expert_embeddings = nn.Parameter(torch.randn(self.num_experts, 64) * 0.02)
        self.expert_names = expert_names

        # Learnable temperature
        self.logit_scale = nn.Parameter(torch.tensor(0.0))

        # Routing history for analysis
        self.route_counts = {name: 0 for name in expert_names}

        print(f"  [ROUTER] {self.num_experts} experts, "
              f"{sum(p.numel() for p in self.parameters()):,} params")

    def forward(self, hidden_state: torch.Tensor, 
                return_scores: bool = False,
                source_expert: str = None) -> Tuple[str, torch.Tensor]:
        """
        Route a hidden state to the best expert.
        
        Args:
            hidden_state: (batch, 1, hidden_dim) — the current latent state
            return_scores: if True, also return routing scores
            
        Returns:
            expert_name: which expert to route to
            projected_hidden: if return_scores, the routing logits
        """
        # Project to shared space using source expert's projection
        x = hidden_state.squeeze(1)  # (batch, hidden_dim)
        dtype = x.dtype
        if source_expert and source_expert in self.input_projs:
            x = self.input_projs[source_expert].to(dtype)(x)  # (batch, 256)
        else:
            # Fallback: pad/truncate to 256
            if x.shape[-1] < 256:
                x = F.pad(x, (0, 256 - x.shape[-1]))
            x = x[:, :256]

        # Get routing logits (cast to float32 for the gate)
        logits = self.gate(x.float())  # (batch, num_experts)

        # Temperature-scaled softmax
        scale = torch.exp(self.logit_scale).clamp(0.1, 10.0)
        scores = F.softmax(logits * scale, dim=-1)

        # Pick top expert
        top_idx = scores.argmax(dim=-1).item()
        expert_name = self.expert_names[top_idx]
        self.route_counts[expert_name] += 1

        if return_scores:
            return expert_name, scores
        return expert_name

    def route_counts_summary(self) -> str:
        total = sum(self.route_counts.values()) or 1
        parts = [f"{name}:{count}" for name, count in self.route_counts.items()]
        return " | ".join(parts)


# ===============================================================================
# MoE RecursiveMAS Orchestrator
# ===============================================================================

@dataclass
class MoEConfig:
    max_rounds: int = 3
    tokens_per_round: int = 48
    final_tokens: int = 256
    temperature: float = 0.7
    initial_expert: str = "coder"  # Which expert handles round 1
    top_k_routing: int = 1         # Route to top-k experts (1 = standard MoE)
    vram_limit_gb: float = 10.5
    ram_limit_gb: float = 58.0


class MoERecursiveMAS:
    """
    MoE-gated multi-agent latent-space recursion.
    
    Each round:
      1. Current hidden state -> MoE Router -> select expert
      2. Bridge: project hidden state to selected expert's embedding space
      3. Expert processes in latent space (inputs_embeds, no text)
      4. Output hidden state -> next round
    
    Only the FINAL round's hidden state is decoded to text.
    """

    def __init__(self, config: MoEConfig, monitor: ResourceMonitor):
        self.config = config
        self.monitor = monitor

        # Context augmenter for real-time awareness
        self.augmenter = ContextAugmenter(enable_search=True, enable_fetch=True)

        # Load all experts (deduplicate: same model_name = shared instance)
        self.experts: Dict[str, ExpertAgent] = {}
        loaded_models: Dict[str, ExpertAgent] = {}  # model_name -> instance
        
        print("\n[EXPERTS]")
        for name, profile in EXPERT_REGISTRY.items():
            if profile.model_name in loaded_models:
                # Share model, but with different profile/system prompt
                self.experts[name] = loaded_models[profile.model_name]
                print(f"  [SHARE] {name} reuses {profile.model_name}")
            else:
                agent = ExpertAgent(profile)
                self.experts[name] = agent
                loaded_models[profile.model_name] = agent

        # Build bridge matrix
        print("\n[BRIDGES]")
        self.bridges = BridgeMatrix(self.experts)

        # Build MoE router (input dim = max expert dim for flexibility)
        max_dim = max(e.hidden_dim for e in self.experts.values())
        self.router = MoERouter(
            input_dim=max_dim,
            expert_names=list(self.experts.keys()),
            expert_dims={n: e.hidden_dim for n, e in self.experts.items()},
        ).to("cuda")

        total_vram = sum(e.vram_gb for e in self.experts.values())
        snap = monitor.snapshot()
        print(f"\n[READY] {len(self.experts)} experts loaded ({total_vram:.1f}GB weights)")
        print(f"[READY] VRAM: {snap['vram_gb']:.1f}GB | RAM: {snap['ram_gb']:.1f}GB")

    def solve(self, problem: str) -> str:
        """Run full MoE-gated recursive solution pipeline."""
        cfg = self.config

        # Enrich problem with datetime + web search
        enriched = self.augmenter.enrich(problem)
        
        print(f"\n{'-'*70}")
        print(f"TASK: {problem}")
        print(f"{'-'*70}")

        # Round 1: Initial expert processes from enriched text context
        initial_expert = self.experts[cfg.initial_expert]
        # Use model's chat template for proper prompt formatting
        messages = [
            {"role": "system", "content": initial_expert.profile.system_prompt},
            {"role": "user", "content": enriched},
        ]
        try:
            prompt = initial_expert.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            # Fallback: manual formatting
            prompt = (
                f"{initial_expert.profile.system_prompt}\n\n"
                f"{enriched}\n\nResponse:"
            )

        print(f"\n[ROUND 1] {cfg.initial_expert} (text -> latent)")
        result = initial_expert.process_text(prompt, cfg.tokens_per_round, cfg.temperature)
        hidden = result["hidden_state"]
        print(f"  Output: {result['text'][:150]}...")

        snap = self.monitor.snapshot()
        print(f"  VRAM: {snap['vram_gb']:.1f}GB | RAM: {snap['ram_gb']:.1f}GB")

        # Recursion rounds: MoE-routed latent processing
        current_expert_name = cfg.initial_expert
        
        # Track which models support latent input (some like Gemma4 require input_ids too)
        self._latent_compatible: Dict[str, bool] = {
            name: not ("gemma4" in exp.model.config.model_type.lower())
            for name, exp in self.experts.items()
        }

        for round_num in range(2, cfg.max_rounds + 1):
            # Router decides which expert handles this round (avoid self-routing)
            routed_name, scores = self.router(hidden, return_scores=True, source_expert=current_expert_name)
            if routed_name == current_expert_name and len(self.experts) > 1:
                # Pick second-best to avoid wasted self-loop round
                sorted_idx = scores.argsort(descending=True)[0]
                for idx in sorted_idx:
                    alt = list(self.experts.keys())[idx.item()]
                    if alt != current_expert_name:
                        routed_name = alt
                        break
            print(f"\n[ROUND {round_num}] Router -> {routed_name} " 
                  f"(from {current_expert_name})")

            # Bridge: project hidden state from current expert -> routed expert
            projected = self.bridges.project(
                hidden, current_expert_name, routed_name
            )

            # Routed expert processes the projected latent state
            routed_expert = self.experts[routed_name]
            
            # Fallback: if selected expert can't process latent (e.g., Gemma4),
            # use coder for latent processing, but still note the routing choice
            if not self._latent_compatible.get(routed_name, True):
                print(f"  (fallback: {routed_name} can't process latent, using coder)")
                routed_expert = self.experts["coder"]
                projected = self.bridges.project(hidden, current_expert_name, "coder")
                routed_name = "coder"  # Track dims correctly for next round
            
            result = routed_expert.process_latent(
                projected, cfg.tokens_per_round, cfg.temperature
            )
            hidden = result["hidden_state"]
            print(f"  Thinking: {result['text'][:100]}...")

            v, r = self.monitor.snapshot()["vram_gb"], self.monitor.snapshot()["ram_gb"]
            print(f"  VRAM: {v:.1f}GB | RAM: {r:.1f}GB")

            current_expert_name = routed_name

        # Final decode — use the coder expert for best output quality
        print(f"\n[FINAL] Decoding latent -> text (via coder)...")
        final_expert = self.experts["coder"]

        # Project to coder's space if needed
        if current_expert_name != "coder":
            final_hidden = self.bridges.project(hidden, current_expert_name, "coder")
        else:
            final_hidden = hidden
        
        # Ensure dtype matches the coder model
        final_hidden = final_hidden.to(dtype=final_expert.dtype, device=final_expert.device)

        final_text = final_expert.decode_final(
            final_hidden, cfg.final_tokens, cfg.temperature * 0.4  # Cooler for quality
        )

        snap = self.monitor.snapshot()
        print(f"\n{'='*70}")
        print(f"FINAL OUTPUT:")
        print(f"{'='*70}")
        print(final_text)
        print(f"{'='*70}")
        print(f"\n[DONE] Router: {self.router.route_counts_summary()}")
        print(f"[DONE] Peak VRAM: {snap['peak_vram_gb']:.1f}GB | "
              f"Peak RAM: {snap['peak_ram_gb']:.1f}GB")
        print(f"[DONE] Final output: {len(final_text)} chars")

        return final_text

    def shutdown(self):
        self.monitor.stop()
        for expert in self.experts.values():
            expert.unload()
        torch.cuda.empty_cache()
        print("[SHUTDOWN] All experts unloaded, VRAM freed")


# ===============================================================================
# Baseline: single-expert (no recursion, no MoE) for comparison
# ===============================================================================

def baseline_single(problem: str, expert_name: str = "coder",
                    max_tokens: int = 256, temperature: float = 0.6):
    """Run a single expert with no recursion for baseline comparison."""
    profile = EXPERT_REGISTRY[expert_name]
    expert = ExpertAgent(profile)
    prompt = f"{profile.system_prompt}\n\nTask: {problem}\n\nSolution:"
    result = expert.process_text(prompt, max_tokens, temperature)
    expert.unload()
    return result["text"]


# ===============================================================================
# CLI
# ===============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MoE RecursiveMAS — Gated multi-expert latent-space recursion")
    parser.add_argument("--problem", type=str,
                        default="Write a Python function that finds all prime numbers up to n using the Sieve of Eratosthenes",
                        help="Coding problem to solve")
    parser.add_argument("--rounds", type=int, default=3,
                        help="Recursion rounds (default: 3)")
    parser.add_argument("--tokens", type=int, default=48,
                        help="Tokens per round (default: 48)")
    parser.add_argument("--final-tokens", type=int, default=256,
                        help="Tokens for final output (default: 256)")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--initial-expert", type=str, default="coder",
                        choices=list(EXPERT_REGISTRY.keys()),
                        help="Expert for round 1 (default: coder)")
    parser.add_argument("--vram-limit", type=float, default=10.5,
                        help="VRAM limit GB (default: 10.5)")
    parser.add_argument("--ram-limit", type=float, default=58.0,
                        help="RAM limit GB (default: 58.0)")
    parser.add_argument("--baseline", action="store_true",
                        help="Run single-expert baseline for comparison")

    args = parser.parse_args()

    config = MoEConfig(
        max_rounds=args.rounds,
        tokens_per_round=args.tokens,
        final_tokens=args.final_tokens,
        temperature=args.temperature,
        initial_expert=args.initial_expert,
        vram_limit_gb=args.vram_limit,
        ram_limit_gb=args.ram_limit,
    )

    monitor = ResourceMonitor(vram_limit_gb=args.vram_limit, ram_limit_gb=args.ram_limit)
    monitor.start()

    try:
        if args.baseline:
            print("=" * 70)
            print("BASELINE (single expert, no recursion):")
            print("=" * 70)
            baseline_result = baseline_single(
                args.problem, args.initial_expert, args.final_tokens, args.temperature)
            print(baseline_result)
            print("=" * 70)
            print("\n" + "=" * 70)
            print("MoE RecursiveMAS (3 experts, gated routing):")
            print("=" * 70)

        mas = MoERecursiveMAS(config, monitor)
        final = mas.solve(args.problem)
        mas.shutdown()

        if args.baseline:
            print(f"\n[COMPARE] Baseline: {len(baseline_result)} chars")
            print(f"[COMPARE] MoE-RMAS: {len(final)} chars")

    except Exception as e:
        monitor.stop()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
