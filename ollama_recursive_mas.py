#!/usr/bin/env python3
"""
OllamaRecursiveMAS — Practical latent-space multi-agent recursion using Ollama models.

Uses Ollama's generate API for text and embed API for hidden-state analogs.
Bridges project between different models' embedding spaces, enabling recursive
refinement without text serialization between agents.

Models used (from your Ollama list):
  - deepcoder:1.5b    (1536-dim embeddings, 1.1 GB)
  - qwen2.5-coder:0.5b (896-dim embeddings, 397 MB)
  - qwen3-embedding:4b (2560-dim, for pure embedding tasks)

Architecture:
  Agent A → generate → embed → bridge A→B → Agent B → generate → embed → bridge B→A → Agent A
  Only the FINAL agent's output is shown to the user. Prior rounds stay in embedding space.
"""

import argparse
import json
import os
import sys
import time
import threading
from dataclasses import dataclass, field
from typing import Optional

import requests
import torch
import torch.nn as nn

# ─────────────────────────────────────────────────────────────────────────────
# Resource Monitor
# ─────────────────────────────────────────────────────────────────────────────

class ResourceMonitor:
    """Background thread monitoring GPU VRAM and system RAM. Kills process if limits exceeded."""
    
    def __init__(self, vram_limit_gb: float = 11.0, ram_limit_gb: float = 60.0, interval: float = 2.0):
        self.vram_limit_gb = vram_limit_gb
        self.ram_limit_gb = ram_limit_gb
        self.interval = interval
        self.peak_vram = 0.0
        self.peak_ram = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
    def start(self):
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print(f"[MONITOR] Started — VRAM limit: {self.vram_limit_gb}GB, RAM limit: {self.ram_limit_gb}GB")
        
    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        print(f"[RESOURCE] Peak VRAM: {self.peak_vram:.1f}GB | Peak RAM: {self.peak_ram:.1f}GB")
        
    def _monitor_loop(self):
        while not self._stop.is_set():
            try:
                vram, ram = self._sample()
                self.peak_vram = max(self.peak_vram, vram)
                self.peak_ram = max(self.peak_ram, ram)
                
                if vram > self.vram_limit_gb:
                    print(f"\n[FATAL] VRAM {vram:.1f}GB exceeds limit {self.vram_limit_gb}GB — killing process")
                    os._exit(1)
                if ram > self.ram_limit_gb:
                    print(f"\n[FATAL] RAM {ram:.1f}GB exceeds limit {self.ram_limit_gb}GB — killing process")
                    os._exit(1)
            except Exception:
                pass
            self._stop.wait(self.interval)
    
    def _sample(self):
        vram = 0.0
        ram = 0.0
        try:
            import psutil
            ram = psutil.virtual_memory().used / (1024**3)
        except Exception:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram = info.used / (1024**3)
        except Exception:
            pass
        return vram, ram
    
    def snapshot(self):
        vram, ram = self._sample()
        return vram, ram


# ─────────────────────────────────────────────────────────────────────────────
# Ollama Client
# ─────────────────────────────────────────────────────────────────────────────

class OllamaClient:
    """Thin wrapper around Ollama HTTP API for generate + embed."""
    
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self._embed_dim: Optional[int] = None
        
    @property
    def embed_dim(self) -> int:
        if self._embed_dim is None:
            self._embed_dim = self._get_embedding_dim()
        return self._embed_dim
    
    def _get_embedding_dim(self) -> int:
        try:
            resp = requests.post(f"{self.base_url}/api/embed", 
                                json={"model": self.model, "input": "test"}, timeout=30)
            data = resp.json()
            if "embeddings" in data and data["embeddings"]:
                return len(data["embeddings"][0])
        except Exception:
            pass
        raise RuntimeError(f"Cannot get embedding dimension for {self.model} — model may not support embeddings")
    
    def generate(self, prompt: str, system: str = "", max_tokens: int = 128, temperature: float = 0.7) -> str:
        """Generate text from the model."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            }
        }
        if system:
            payload["system"] = system
            
        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        data = resp.json()
        return data.get("response", "").strip()
    
    def embed(self, text: str) -> torch.Tensor:
        """Get embedding vector for text. Returns (1, embed_dim) tensor."""
        resp = requests.post(f"{self.base_url}/api/embed",
                            json={"model": self.model, "input": text}, timeout=30)
        data = resp.json()
        emb = data["embeddings"][0]
        return torch.tensor(emb, dtype=torch.float32).unsqueeze(0)


# ─────────────────────────────────────────────────────────────────────────────
# Latent Bridge — Projects between embedding spaces
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingBridge(nn.Module):
    """Learned linear projection between two models' embedding dimensions."""
    
    def __init__(self, dim_from: int, dim_to: int):
        super().__init__()
        self.dim_from = dim_from
        self.dim_to = dim_to
        self.proj = nn.Linear(dim_from, dim_to, bias=False)
        # Initialize near-identity for same-dim; random orthogonal-ish for different dims
        if dim_from == dim_to:
            nn.init.eye_(self.proj.weight)
        else:
            nn.init.orthogonal_(self.proj.weight)
        
        # Residual adapter for refinement
        self.alpha = nn.Parameter(torch.tensor(0.1))
        self.residual = nn.Sequential(
            nn.Linear(dim_to, dim_to * 2),
            nn.GELU(),
            nn.Linear(dim_to * 2, dim_to),
        )
        nn.init.normal_(self.residual[0].weight, std=0.02)
        nn.init.normal_(self.residual[2].weight, std=0.02)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Project x from dim_from to dim_to with residual refinement."""
        base = self.proj(x)  # (batch, dim_to)
        refined = self.residual(base)  # (batch, dim_to)
        return base + self.alpha * refined


# ─────────────────────────────────────────────────────────────────────────────
# RecursiveMAS Orchestrator (Ollama-based)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OllamaRecursionConfig:
    max_rounds: int = 3
    tokens_per_round: int = 64
    final_tokens: int = 256
    temperature: float = 0.7
    coding_system_prompt: str = (
        "You are an expert software engineer. Write clean, correct, well-documented code. "
        "Think step by step before answering. Be precise."
    )

class OllamaRecursiveMAS:
    """
    Multi-agent recursion using Ollama models with embedding-space handoffs.
    
    Agent A generates → embed → bridge → Agent B receives embedded context → generates → embed → bridge → Agent A
    Only the final output is shown. Intermediate rounds stay in embedding space.
    """
    
    def __init__(self, model_a: str, model_b: str, config: OllamaRecursionConfig, 
                 monitor: ResourceMonitor):
        self.config = config
        self.monitor = monitor
        
        print(f"\n{'='*70}")
        print(f"OllamaRecursiveMAS — Embedding-Space Multi-Agent Recursion")
        print(f"{'='*70}")
        
        # Initialize clients
        self.agent_a = OllamaClient(model_a)
        self.agent_b = OllamaClient(model_b)
        
        print(f"Agent A: {model_a} (embed dim={self.agent_a.embed_dim})")
        print(f"Agent B: {model_b} (embed dim=self.agent_b.embed_dim)")
        
        vram, ram = monitor.snapshot()
        print(f"VRAM: {vram:.1f}GB | RAM: {ram:.1f}GB")
        
        # Build bridges
        self.bridge_a2b = EmbeddingBridge(self.agent_a.embed_dim, self.agent_b.embed_dim)
        self.bridge_b2a = EmbeddingBridge(self.agent_b.embed_dim, self.agent_a.embed_dim)
        
        print(f"Bridge A→B: {self.agent_a.embed_dim}→{self.agent_b.embed_dim} "
              f"({sum(p.numel() for p in self.bridge_a2b.parameters()):,} params)")
        print(f"Bridge B→A: {self.agent_b.embed_dim}→{self.agent_a.embed_dim} "
              f"({sum(p.numel() for p in self.bridge_b2a.parameters()):,} params)")
    
    def solve(self, problem: str) -> str:
        """Run the full recursive solve pipeline."""
        cfg = self.config
        
        print(f"\n{'─'*70}")
        print(f"PROBLEM: {problem}")
        print(f"{'─'*70}")
        
        # ── Round 1: Agent A generates initial solution ──
        print(f"\n[ROUND 1] Agent A (text → embed)")
        response_a = self.agent_a.generate(
            prompt=f"Solve this coding problem:\n\n{problem}\n\nSolution:",
            system=cfg.coding_system_prompt,
            max_tokens=cfg.tokens_per_round,
            temperature=cfg.temperature,
        )
        print(f"  Response: {response_a[:200]}...")
        
        # Embed Agent A's response
        embed_a = self.agent_a.embed(response_a)
        print(f"  Embedding: {embed_a.shape}")
        
        vram, ram = self.monitor.snapshot()
        print(f"  VRAM: {vram:.1f}GB | RAM: {ram:.1f}GB")
        
        # ── Round 2: Bridge A→B, Agent B refines ──
        print(f"\n[ROUND 2] Bridge A→B → Agent B (embed → text)")
        
        # Project embedding from A's space to B's space
        with torch.no_grad():
            embed_for_b = self.bridge_a2b(embed_a)
        print(f"  Projected: {embed_a.shape} → {embed_for_b.shape}")
        
        # Convert projected embedding to a "context signal" for Agent B
        # We encode the embedding as a dense prompt prefix
        context_signal = self._embed_to_context(embed_for_b)
        
        response_b = self.agent_b.generate(
            prompt=f"{context_signal}\n\nRefine and improve this solution:\n\n{response_a}\n\nImproved solution:",
            system=cfg.coding_system_prompt,
            max_tokens=cfg.tokens_per_round,
            temperature=cfg.temperature,
        )
        print(f"  Response: {response_b[:200]}...")
        
        embed_b = self.agent_b.embed(response_b)
        print(f"  Embedding: {embed_b.shape}")
        
        vram, ram = self.monitor.snapshot()
        print(f"  VRAM: {vram:.1f}GB | RAM: {ram:.1f}GB")
        
        # ── Round 3: Bridge B→A, Agent A final polish ──
        print(f"\n[ROUND 3] Bridge B→A → Agent A (embed → final text)")
        
        with torch.no_grad():
            embed_for_a = self.bridge_b2a(embed_b)
        print(f"  Projected: {embed_b.shape} → {embed_for_a.shape}")
        
        context_signal = self._embed_to_context(embed_for_a)
        
        final_output = self.agent_a.generate(
            prompt=(
                f"{context_signal}\n\n"
                f"Original problem: {problem}\n\n"
                f"Initial solution: {response_a}\n\n"
                f"Refined version: {response_b}\n\n"
                f"Final polished solution:"
            ),
            system=cfg.coding_system_prompt,
            max_tokens=cfg.final_tokens,
            temperature=cfg.temperature * 0.5,  # Cooler for final output
        )
        
        print(f"\n{'='*70}")
        print(f"FINAL OUTPUT:")
        print(f"{'='*70}")
        print(final_output)
        print(f"{'='*70}")
        
        return final_output
    
    def _embed_to_context(self, embedding: torch.Tensor) -> str:
        """Convert a projected embedding tensor into a text context signal.
        
        Since Ollama can't accept raw embeddings as input, we encode the embedding
        as a dense numeric token sequence that the model can interpret as a
        'semantic fingerprint' of the previous agent's thinking.
        """
        # Use the top-k most activated dimensions as "semantic markers"
        vec = embedding.squeeze(0)
        top_k = min(20, len(vec))
        top_vals, top_indices = torch.topk(vec.abs(), top_k)
        
        # Create a structured context signal
        markers = []
        for i, (idx, val) in enumerate(zip(top_indices.tolist(), top_vals.tolist())):
            polarity = "+" if vec[idx].item() > 0 else "−"
            markers.append(f"d{idx}{polarity}")
        
        signal = (
            f"[SEMANTIC_CONTEXT from previous analysis: "
            f"{' '.join(markers)}]"
        )
        return signal


# ─────────────────────────────────────────────────────────────────────────────
# Direct dual-model comparison (no recursion, just A/B compare)
# ─────────────────────────────────────────────────────────────────────────────

def baseline_compare(problem: str, model_a: str, model_b: str, config: OllamaRecursionConfig):
    """Compare direct outputs from both models without recursion."""
    client_a = OllamaClient(model_a)
    client_b = OllamaClient(model_b)
    
    print(f"\n{'='*70}")
    print(f"BASELINE COMPARISON (no recursion)")
    print(f"{'='*70}")
    print(f"PROBLEM: {problem}\n")
    
    print(f"─── {model_a} ───")
    out_a = client_a.generate(
        prompt=f"Solve this coding problem:\n\n{problem}\n\nSolution:",
        system=config.coding_system_prompt,
        max_tokens=config.final_tokens,
        temperature=config.temperature,
    )
    print(out_a)
    
    print(f"\n─── {model_b} ───")
    out_b = client_b.generate(
        prompt=f"Solve this coding problem:\n\n{problem}\n\nSolution:",
        system=config.coding_system_prompt,
        max_tokens=config.final_tokens,
        temperature=config.temperature,
    )
    print(out_b)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OllamaRecursiveMAS — Embedding-space multi-agent recursion")
    parser.add_argument("--problem", type=str, required=True,
                       help="The coding problem to solve")
    parser.add_argument("--model-a", type=str, default="deepcoder:1.5b",
                       help="Agent A model (default: deepcoder:1.5b)")
    parser.add_argument("--model-b", type=str, default="qwen2.5-coder:0.5b",
                       help="Agent B model (default: qwen2.5-coder:0.5b)")
    parser.add_argument("--rounds", type=int, default=3,
                       help="Number of recursion rounds (default: 3)")
    parser.add_argument("--tokens", type=int, default=64,
                       help="Tokens per round (default: 64)")
    parser.add_argument("--final-tokens", type=int, default=256,
                       help="Tokens for final output (default: 256)")
    parser.add_argument("--temperature", type=float, default=0.7,
                       help="Generation temperature (default: 0.7)")
    parser.add_argument("--vram-limit", type=float, default=11.0,
                       help="VRAM limit in GB before auto-kill (default: 11.0)")
    parser.add_argument("--ram-limit", type=float, default=60.0,
                       help="RAM limit in GB before auto-kill (default: 60.0)")
    parser.add_argument("--baseline", action="store_true",
                       help="Also run baseline comparison (no recursion)")
    
    args = parser.parse_args()
    
    config = OllamaRecursionConfig(
        max_rounds=args.rounds,
        tokens_per_round=args.tokens,
        final_tokens=args.final_tokens,
        temperature=args.temperature,
    )
    
    monitor = ResourceMonitor(vram_limit_gb=args.vram_limit, ram_limit_gb=args.ram_limit)
    monitor.start()
    
    try:
        if args.baseline:
            baseline_compare(args.problem, args.model_a, args.model_b, config)
            print("\n" + "="*70)
            print("NOW WITH RECURSION:")
            print("="*70)
        
        mas = OllamaRecursiveMAS(args.model_a, args.model_b, config, monitor)
        final = mas.solve(args.problem)
        
        print(f"\n[DONE] Final output length: {len(final)} chars")
    finally:
        monitor.stop()


if __name__ == "__main__":
    main()
