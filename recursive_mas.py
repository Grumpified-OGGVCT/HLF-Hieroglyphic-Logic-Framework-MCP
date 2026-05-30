"""RecursiveMAS — Latent-space multi-agent recursion with resource monitoring.

Architecture:
  Round 1: Agent A generates thinking tokens → capture last hidden state H
  Round 2: Project H through learned mapping → feed as inputs_embeds
  Final: Only the last hidden state is decoded to text via LM head.

Models: Any HuggingFace causal LM. Default: Qwen2.5-Coder-0.5B-Instruct (896-dim, ~1GB VRAM).
"""

import os
import sys
import time
import signal
import threading
import argparse
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import psutil

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# Resource Monitor
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResourceThresholds:
    """Kill thresholds — if ANY are exceeded, the process exits cleanly."""
    vram_max_gb: float = 11.0       # RTX 3060 has 12GB, leave 1GB buffer
    ram_max_gb: float = 60.0        # System has 64GB, leave 4GB for OS
    poll_interval_sec: float = 2.0

class ResourceMonitor:
    """Background thread that polls GPU/CPU memory and signals shutdown."""
    
    def __init__(self, thresholds: ResourceThresholds):
        self.thresholds = thresholds
        self._stop = threading.Event()
        self._killed = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._peak_vram = 0.0
        self._peak_ram = 0.0
        self._history: list[dict] = []
        
        # Initialize NVML
        self._has_gpu = False
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml = pynvml
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._has_gpu = True
        except Exception:
            print("[MONITOR] No GPU NVML access — VRAM monitoring disabled")
            self._nvml = None
    
    def _poll(self):
        """Single poll of resources. Returns (vram_gb, ram_gb, should_kill)."""
        vram_gb = 0.0
        ram_gb = 0.0
        
        if self._has_gpu and self._nvml:
            try:
                info = self._nvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                vram_gb = info.used / (1024**3)
            except Exception:
                pass
        
        mem = psutil.virtual_memory()
        ram_gb = mem.used / (1024**3)
        
        self._peak_vram = max(self._peak_vram, vram_gb)
        self._peak_ram = max(self._peak_ram, ram_gb)
        
        should_kill = (vram_gb > self.thresholds.vram_max_gb or 
                       ram_gb > self.thresholds.ram_max_gb)
        
        self._history.append({
            "time": time.time(),
            "vram_gb": vram_gb,
            "ram_gb": ram_gb,
        })
        
        return vram_gb, ram_gb, should_kill
    
    def _run(self):
        """Background polling loop."""
        while not self._stop.is_set():
            vram, ram, kill = self._poll()
            if kill:
                print(f"\n[MONITOR] ⚠️ RESOURCE LIMIT EXCEEDED!")
                print(f"  VRAM: {vram:.1f}GB / {self.thresholds.vram_max_gb}GB max")
                print(f"  RAM:  {ram:.1f}GB / {self.thresholds.ram_max_gb}GB max")
                print(f"  Peak VRAM: {self._peak_vram:.1f}GB, Peak RAM: {self._peak_ram:.1f}GB")
                self._killed.set()
                os._exit(1)
            self._stop.wait(self.thresholds.poll_interval_sec)
    
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[MONITOR] Started — VRAM limit: {self.thresholds.vram_max_gb}GB, "
              f"RAM limit: {self.thresholds.ram_max_gb}GB")
    
    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._has_gpu and self._nvml:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass
    
    def snapshot(self) -> dict:
        vram, ram, _ = self._poll()
        return {
            "vram_gb": vram,
            "ram_gb": ram,
            "peak_vram_gb": self._peak_vram,
            "peak_ram_gb": self._peak_ram,
        }
    
    def was_killed(self) -> bool:
        return self._killed.is_set()


# ─────────────────────────────────────────────────────────────────────────────
# Latent Projection (RecursiveMAS-style alignment)
# ─────────────────────────────────────────────────────────────────────────────

class LatentBridge(nn.Module):
    """
    Projects hidden state from model A's dimension to model B's embedding dimension.
    
    Simplified version of RecursiveMAS OuterRecursiveLink:
    - Linear projection + LayerNorm + GELU + residual
    - ~(d_in * d_out + d_out) params
    """
    
    def __init__(self, dim_in: int, dim_out: int, hidden_mult: int = 4):
        super().__init__()
        self.dim_in = dim_in
        self.dim_out = dim_out
        hidden_dim = max(dim_in, dim_out) * hidden_mult
        
        self.project = nn.Sequential(
            nn.Linear(dim_in, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, dim_out),
            nn.LayerNorm(dim_out),
        )
        
        # Residual adapter if dimensions differ
        if dim_in != dim_out:
            self.residual = nn.Linear(dim_in, dim_out, bias=False)
        else:
            self.residual = nn.Identity()
        
        # Learnable scale for residual blend
        self.alpha = nn.Parameter(torch.tensor(0.5))
    
    def forward(self, hidden_state: torch.Tensor) -> torch.Tensor:
        """
        Args:
            hidden_state: (batch, seq_len, dim_in) — last hidden state
        Returns:
            projected: (batch, seq_len, dim_out) — aligned for target model's inputs_embeds
        """
        projected = self.project(hidden_state)
        residual = self.residual(hidden_state)
        return self.alpha * projected + (1 - self.alpha) * residual
    
    @property
    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


# ─────────────────────────────────────────────────────────────────────────────
# Agent Wrapper — loads model, captures hidden states, supports latent input
# ─────────────────────────────────────────────────────────────────────────────

class LatentAgent:
    """
    Wraps a HuggingFace causal LM for latent-space recursion.
    
    Key capability: generate with `output_hidden_states=True` to capture
    the last hidden state BEFORE the LM head, and accept `inputs_embeds`
    directly (bypassing token embedding) for receiving latent handoffs.
    """
    
    def __init__(self, model_name: str, device: str = "cuda", 
                 load_in_8bit: bool = False, load_in_4bit: bool = False):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        self.name = model_name
        self.device = device
        
        print(f"[AGENT] Loading {model_name}...")
        
        load_kwargs = {
            "dtype": torch.float16 if device == "cuda" else torch.float32,
            "trust_remote_code": True,
        }
        
        if load_in_4bit:
            load_kwargs["load_in_4bit"] = True
            load_kwargs["bnb_4bit_compute_dtype"] = torch.float16
        elif load_in_8bit:
            load_kwargs["load_in_8bit"] = True
        
        self.model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        if device == "cuda" and not load_in_4bit and not load_in_8bit:
            self.model = self.model.to(device)
        
        self.model.eval()
        
        cfg = self.model.config
        self.hidden_dim = cfg.n_embd if hasattr(cfg, 'n_embd') else cfg.hidden_size
        self.vocab_size = cfg.vocab_size
        self.dtype = self.model.dtype  # Store the model's dtype for consistency
        
        print(f"  hidden_dim={self.hidden_dim}, vocab={self.vocab_size}, "
              f"device={self.model.device}, dtype={self.dtype}")
    
    def encode_text(self, text: str) -> torch.Tensor:
        """Tokenize text for initial input only (not used during recursion)."""
        tokens = self.tokenizer(text, return_tensors="pt")
        return tokens["input_ids"].to(self.device)
    
    def generate_latent(self, input_ids: Optional[torch.Tensor] = None,
                        inputs_embeds: Optional[torch.Tensor] = None,
                        max_new_tokens: int = 32,
                        temperature: float = 0.7,
                        return_hidden: bool = True) -> dict:
        """
        Generate tokens AND capture the final hidden state.
        
        Uses manual autoregressive generation to ensure hidden states are captured.
        """
        if input_ids is None and inputs_embeds is None:
            raise ValueError("Must provide either input_ids or inputs_embeds")
        
        generated_ids = []
        hidden_state = None
        
        # Prepare initial input
        if input_ids is not None:
            current_ids = input_ids
            current_embeds = None
        else:
            current_ids = None
            current_embeds = inputs_embeds
        
        with torch.no_grad():
            for step in range(max_new_tokens):
                # Forward pass with hidden states
                outputs = self.model(
                    input_ids=current_ids,
                    inputs_embeds=current_embeds,
                    output_hidden_states=True,
                )
                
                # Capture last hidden state from final layer (ONLY what we need)
                hidden_state = outputs.hidden_states[-1][:, -1:, :].detach().clone()
                
                # Clean up full hidden state tuple immediately to free VRAM
                del outputs.hidden_states
                
                # Get logits for next token prediction
                logits = outputs.logits[:, -1, :] / temperature
                probs = torch.softmax(logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                generated_ids.append(next_token.item())
                
                # Clean up outputs
                del outputs, logits, probs
                
                # Stop on EOS
                if next_token.item() == self.tokenizer.eos_token_id:
                    break
                
                # Prepare for next iteration — use embedding of generated token
                current_embeds = self.model.get_input_embeddings()(next_token)
                current_ids = None  # Switch to embeds-only mode
                
                # Periodic cache cleanup for long generations
                if step % 16 == 0:
                    torch.cuda.empty_cache()
        
        result = {
            'generated_ids': torch.tensor([generated_ids]) if generated_ids else None,
            'generated_text': self.tokenizer.decode(generated_ids, skip_special_tokens=True) if generated_ids else "",
            'hidden_state': hidden_state,
        }
        
        return result
    
    def decode_from_latent(self, hidden_state: torch.Tensor, 
                           max_new_tokens: int = 64,
                           temperature: float = 0.7) -> str:
        """
        Decode a hidden state to text through the LM head.
        Uses autoregressive generation from the latent representation.
        Used ONLY at the final recursion round.
        """
        with torch.no_grad():
            # Start autoregressive generation from the latent hidden state
            # Feed hidden state as inputs_embeds + generate one token at a time
            current_embeds = hidden_state  # (batch, 1, hidden_dim)
            
            generated_ids = []
            for step in range(max_new_tokens):
                outputs = self.model(
                    inputs_embeds=current_embeds,
                    output_hidden_states=False,  # Don't need hidden states for decode
                )
                
                logits = outputs.logits[:, -1, :] / temperature
                probs = torch.softmax(logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                generated_ids.append(next_token.item())
                
                del outputs, logits, probs
                
                if next_token.item() == self.tokenizer.eos_token_id:
                    break
                
                # Get embedding of generated token for next iteration
                current_embeds = self.model.get_input_embeddings()(next_token)
                
                if step % 16 == 0:
                    torch.cuda.empty_cache()
            
            return self.tokenizer.decode(generated_ids, skip_special_tokens=True)


# ─────────────────────────────────────────────────────────────────────────────
# RecursiveMAS Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecursionConfig:
    max_rounds: int = 3
    tokens_per_round: int = 32
    final_tokens: int = 128
    temperature: float = 0.7
    seed_prompt: str = "The solution to this problem involves"
    
    # Resource limits
    vram_limit_gb: float = 11.0
    ram_limit_gb: float = 60.0


class RecursiveMASOrchestrator:
    """
    Orchestrates latent-space multi-agent recursion.
    
    Flow:
      1. Agent A receives seed prompt → generates thinking tokens
      2. Capture A's last hidden state
      3. Project through LatentBridge → Agent B's embedding space
      4. Agent B generates from projected latent state
      5. (Optional) Project B's hidden state back to A for recursion
      6. Repeat for max_rounds
      7. Final round: decode hidden state to human-readable text
    """
    
    def __init__(self, agent_a_model: str, agent_b_model: str,
                 config: RecursionConfig):
        self.config = config
        self.monitor = ResourceMonitor(ResourceThresholds(
            vram_max_gb=config.vram_limit_gb,
            ram_max_gb=config.ram_limit_gb,
        ))
        
        print("=" * 70)
        print("RecursiveMAS — Latent Multi-Agent Recursion")
        print("=" * 70)
        print(f"Agent A: {agent_a_model}")
        print(f"Agent B: {agent_b_model}")
        print(f"Max rounds: {config.max_rounds}")
        print(f"Tokens/round: {config.tokens_per_round}")
        print(f"VRAM limit: {config.vram_limit_gb}GB")
        print(f"RAM limit: {config.ram_limit_gb}GB")
        print("=" * 70)
        
        # Start resource monitoring
        self.monitor.start()
        
        # Load agents
        self.agent_a = LatentAgent(agent_a_model, device="cuda")
        self.agent_b = LatentAgent(agent_b_model, device="cuda")
        
        snap = self.monitor.snapshot()
        print(f"[RESOURCE] After model load: VRAM={snap['vram_gb']:.1f}GB, "
              f"RAM={snap['ram_gb']:.1f}GB")
        
        # Build projection bridges (match model dtype)
        self.bridge_a_to_b = LatentBridge(
            self.agent_a.hidden_dim, self.agent_b.hidden_dim
        ).to(device="cuda", dtype=self.agent_a.dtype)
        self.bridge_b_to_a = LatentBridge(
            self.agent_b.hidden_dim, self.agent_a.hidden_dim
        ).to(device="cuda", dtype=self.agent_a.dtype)
        
        print(f"[BRIDGE] A→B: {self.agent_a.hidden_dim}→{self.agent_b.hidden_dim} "
              f"({self.bridge_a_to_b.param_count:,} params)")
        print(f"[BRIDGE] B→A: {self.agent_b.hidden_dim}→{self.agent_a.hidden_dim} "
              f"({self.bridge_b_to_a.param_count:,} params)")
    
    def run(self, problem: str) -> dict:
        """Execute the full recursive multi-agent loop."""
        rounds = []
        print(f"\n{'─' * 70}")
        print(f"PROBLEM: {problem}")
        print(f"{'─' * 70}\n")
        
        # ── Round 1: Agent A (text input) ──
        print("[ROUND 1] Agent A (text → latent)")
        prompt = f"{self.config.seed_prompt} {problem}"
        input_ids = self.agent_a.encode_text(prompt)
        
        result_a = self.agent_a.generate_latent(
            input_ids=input_ids,
            max_new_tokens=self.config.tokens_per_round,
            temperature=self.config.temperature,
            return_hidden=True,
        )
        
        hidden_a = result_a['hidden_state']
        thinking_a = result_a['generated_text']
        
        rounds.append({
            "round": 1,
            "agent": "A",
            "thinking": thinking_a,
            "input_type": "text",
        })
        
        snap = self.monitor.snapshot()
        print(f"  Thinking: {thinking_a[:100]}...")
        print(f"  Hidden state shape: {hidden_a.shape if hidden_a is not None else 'N/A'}")
        print(f"  VRAM: {snap['vram_gb']:.1f}GB | RAM: {snap['ram_gb']:.1f}GB")
        
        if hidden_a is None:
            print("[ERROR] Failed to capture hidden state from Agent A")
            return {"rounds": rounds, "error": "No hidden state from Agent A"}
        
        # ── Round 2: Agent B (latent input) ──
        print(f"\n[ROUND 2] Agent B (latent → thinking)")
        
        # Project A's hidden state to B's embedding space
        inputs_embeds_b = self.bridge_a_to_b(hidden_a)
        print(f"  Projected: {hidden_a.shape} → {inputs_embeds_b.shape}")
        
        result_b = self.agent_b.generate_latent(
            inputs_embeds=inputs_embeds_b,
            max_new_tokens=self.config.tokens_per_round,
            temperature=self.config.temperature,
            return_hidden=True,
        )
        
        hidden_b = result_b['hidden_state']
        thinking_b = result_b['generated_text']
        
        rounds.append({
            "round": 2,
            "agent": "B",
            "thinking": thinking_b,
            "input_type": "latent",
        })
        
        snap = self.monitor.snapshot()
        print(f"  Thinking: {thinking_b[:100]}...")
        print(f"  Hidden state shape: {hidden_b.shape if hidden_b is not None else 'N/A'}")
        print(f"  VRAM: {snap['vram_gb']:.1f}GB | RAM: {snap['ram_gb']:.1f}GB")
        
        if hidden_b is None:
            print("[ERROR] Failed to capture hidden state from Agent B")
            return {"rounds": rounds, "error": "No hidden state from Agent B"}
        
        # ── Round 3+: Latent recursion ──
        current_hidden = hidden_b
        current_agent = "B"
        
        for r in range(3, self.config.max_rounds + 1):
            if current_agent == "B":
                # Project B→A, Agent A generates
                inputs_embeds = self.bridge_b_to_a(current_hidden)
                agent = self.agent_a
                next_agent = "A"
            else:
                # Project A→B, Agent B generates
                inputs_embeds = self.bridge_a_to_b(current_hidden)
                agent = self.agent_b
                next_agent = "B"
            
            print(f"\n[ROUND {r}] Agent {next_agent} (latent → latent recursion)")
            print(f"  Projected: {current_hidden.shape} → {inputs_embeds.shape}")
            
            result = agent.generate_latent(
                inputs_embeds=inputs_embeds,
                max_new_tokens=self.config.tokens_per_round,
                temperature=self.config.temperature,
                return_hidden=True,
            )
            
            current_hidden = result['hidden_state']
            thinking = result['generated_text']
            current_agent = next_agent
            
            rounds.append({
                "round": r,
                "agent": next_agent,
                "thinking": thinking,
                "input_type": "latent",
            })
            
            snap = self.monitor.snapshot()
            print(f"  Thinking: {thinking[:100]}...")
            print(f"  VRAM: {snap['vram_gb']:.1f}GB | RAM: {snap['ram_gb']:.1f}GB")
        
        # ── Final Decode: ONE text output at termination ──
        print(f"\n{'─' * 70}")
        print("[FINAL] Decoding latent state to text...")
        print(f"{'─' * 70}")
        
        final_text = self.agent_a.decode_from_latent(
            current_hidden,
            max_new_tokens=self.config.final_tokens,
            temperature=self.config.temperature,
        )
        
        snap = self.monitor.snapshot()
        print(f"\n{'=' * 70}")
        print(f"FINAL OUTPUT:")
        print(f"{'=' * 70}")
        print(final_text)
        print(f"{'=' * 70}")
        
        print(f"\n[RESOURCE] Peak VRAM: {snap['peak_vram_gb']:.1f}GB")
        print(f"[RESOURCE] Peak RAM: {snap['peak_ram_gb']:.1f}GB")
        print(f"[RESOURCE] Final VRAM: {snap['vram_gb']:.1f}GB")
        print(f"[RESOURCE] Final RAM: {snap['ram_gb']:.1f}GB")
        
        return {
            "rounds": rounds,
            "final_output": final_text,
            "resources": snap,
        }
    
    def shutdown(self):
        self.monitor.stop()
        # Free VRAM
        del self.agent_a
        del self.agent_b
        del self.bridge_a_to_b
        del self.bridge_b_to_a
        torch.cuda.empty_cache()
        print("[SHUTDOWN] VRAM freed")


# ─────────────────────────────────────────────────────────────────────────────
# Single-Agent Self-Recursion Mode (for tiny models)
# ─────────────────────────────────────────────────────────────────────────────

class SelfRecursiveAgent:
    """
    Recursion with a single model — hidden state loops back through a projection.
    Useful for proof-of-concept with one small model when VRAM is tight.
    """
    
    def __init__(self, model_name: str, config: RecursionConfig):
        self.config = config
        self.monitor = ResourceMonitor(ResourceThresholds(
            vram_max_gb=config.vram_limit_gb,
            ram_max_gb=config.ram_limit_gb,
        ))
        self.monitor.start()
        
        self.agent = LatentAgent(model_name, device="cuda")
        self.bridge = LatentBridge(
            self.agent.hidden_dim, self.agent.hidden_dim
        ).to(device="cuda", dtype=self.agent.dtype)
        
        print(f"\n[Self-Recursive] Model: {model_name}")
        print(f"[Self-Recursive] Hidden dim: {self.agent.hidden_dim}")
        print(f"[Self-Recursive] Bridge params: {self.bridge.param_count:,}")
    
    def run(self, problem: str) -> dict:
        rounds = []
        
        # Round 1: text input
        print(f"\n[ROUND 1] Text → latent")
        prompt = f"{self.config.seed_prompt} {problem}"
        input_ids = self.agent.encode_text(prompt)
        
        result = self.agent.generate_latent(
            input_ids=input_ids,
            max_new_tokens=self.config.tokens_per_round,
            temperature=self.config.temperature,
            return_hidden=True,
        )
        
        hidden = result['hidden_state']
        rounds.append({
            "round": 1, "thinking": result['generated_text'], "input_type": "text"
        })
        print(f"  Thinking: {result['generated_text'][:100]}...")
        
        # Recursion rounds
        for r in range(2, self.config.max_rounds + 1):
            inputs_embeds = self.bridge(hidden)
            result = self.agent.generate_latent(
                inputs_embeds=inputs_embeds,
                max_new_tokens=self.config.tokens_per_round,
                temperature=self.config.temperature,
                return_hidden=True,
            )
            hidden = result['hidden_state']
            rounds.append({
                "round": r, "thinking": result['generated_text'], "input_type": "latent"
            })
            snap = self.monitor.snapshot()
            print(f"[ROUND {r}] VRAM={snap['vram_gb']:.1f}GB | {result['generated_text'][:80]}...")
        
        # Final decode
        print(f"\n[FINAL] Decoding latent → text...")
        final_text = self.agent.decode_from_latent(
            hidden,
            max_new_tokens=self.config.final_tokens,
            temperature=self.config.temperature,
        )
        
        snap = self.monitor.snapshot()
        print(f"\n{'=' * 70}")
        print(f"FINAL OUTPUT:")
        print(final_text)
        print(f"{'=' * 70}")
        print(f"Peak VRAM: {snap['peak_vram_gb']:.1f}GB | Peak RAM: {snap['peak_ram_gb']:.1f}GB")
        
        return {"rounds": rounds, "final_output": final_text, "resources": snap}
    
    def shutdown(self):
        self.monitor.stop()
        del self.agent
        del self.bridge
        torch.cuda.empty_cache()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RecursiveMAS — Latent-space multi-agent recursion")
    parser.add_argument("--problem", type=str, default="designing a memory-efficient caching system",
                        help="Problem statement for the agents")
    parser.add_argument("--rounds", type=int, default=3, help="Number of recursion rounds")
    parser.add_argument("--tokens", type=int, default=32, help="Tokens per recursion round")
    parser.add_argument("--final-tokens", type=int, default=128, help="Tokens for final decode")
    parser.add_argument("--mode", choices=["self", "dual"], default="self",
                        help="Self-recursion (1 model) or dual-agent (2 models)")
    parser.add_argument("--model-a", type=str, default="Qwen/Qwen2.5-Coder-0.5B-Instruct",
                        help="Model for Agent A (default: Qwen2.5-Coder-0.5B-Instruct)")
    parser.add_argument("--model-b", type=str, default="Qwen/Qwen2.5-Coder-0.5B-Instruct",
                        help="Model for Agent B (dual mode only)")
    parser.add_argument("--vram-limit", type=float, default=11.0,
                        help="VRAM limit in GB (kill if exceeded)")
    parser.add_argument("--ram-limit", type=float, default=60.0,
                        help="RAM limit in GB (kill if exceeded)")
    
    args = parser.parse_args()
    
    config = RecursionConfig(
        max_rounds=args.rounds,
        tokens_per_round=args.tokens,
        final_tokens=args.final_tokens,
        vram_limit_gb=args.vram_limit,
        ram_limit_gb=args.ram_limit,
    )
    
    try:
        if args.mode == "self":
            orchestrator = SelfRecursiveAgent(args.model_a, config)
        else:
            orchestrator = RecursiveMASOrchestrator(args.model_a, args.model_b, config)
        
        result = orchestrator.run(args.problem)
        orchestrator.shutdown()
        
        print(f"\n[DONE] {len(result['rounds'])} rounds completed")
        if result.get('final_output'):
            print(f"[DONE] Final output length: {len(result['final_output'])} chars")
        
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Shutting down...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
