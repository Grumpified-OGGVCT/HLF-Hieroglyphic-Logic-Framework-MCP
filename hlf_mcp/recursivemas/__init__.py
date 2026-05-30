"""
RecursiveMAS — Multi-Agent Latent-Space Orchestration for SwarmGlass.

This package provides two inference modes:

1.  **Custom 4-Model Ring** (`inference.py`) — A latent-space ring using raw HuggingFace
    models (Qwen0.5B → FunctionGemma → Gemma3 → Qwen1.5B) with locally-trained
    CrossModelAdapters. SwarmGlass governance wraps every bridge crossing.

2.  **Official Chain-Trained Checkpoints** (`official.py`) — Inference using the
    Stanford/MIT/Nvidia published RecursiveLinks from the RecursiveMAS submodule.
    Four topologies: sequential (chain), mixture, distillation, deliberation.

Also contains tools for training custom adapters (`train.py`) and the
governed multi-round pipeline (`governed_pipeline.py`).

Install once:
    pip install hlf-mcp[full]    # includes torch, transformers, peft for inference

Usage:
    hlf-recursivemas "Explain the P vs NP problem" --recursions 5
    hlf-recursivemas-official sequential math500 --recursive-rounds 3
"""

from pathlib import Path

# Reference to official RecursiveMAS submodule (chain-trained checkpoints + reference impl)
OFFICIAL_RECURSIVEMAS_PATH = Path(__file__).resolve().parent.parent.parent / "recursivemas"

# Re-export inference
from hlf_mcp.recursivemas.inference import (
    run_recursive_inference,
    load_models,
    load_adapters,
    CrossModelAdapter,
    TelemetryCollector,
    CircuitBreaker,
    EvidenceSummaryRenderer,
)

__all__ = [
    "run_recursive_inference",
    "load_models",
    "load_adapters",
    "CrossModelAdapter",
    "TelemetryCollector",
    "CircuitBreaker",
    "EvidenceSummaryRenderer",
    "OFFICIAL_RECURSIVEMAS_PATH",
]
