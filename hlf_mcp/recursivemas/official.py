"""
Official RecursiveMAS chain-trained checkpoints inference.

Runs the Stanford/MIT/Nvidia published topologies using pre-trained
RecursiveLink adapters from the RecursiveMAS HuggingFace organization.

Topologies:
    - sequential (Planner → Critic → Solver chain)
    - mixture (Math, Code, Science experts → Summarizer)
    - distillation (Expert → Learner)
    - deliberation (Reflector ↔ ToolCaller loop)

Usage:
    python -m hlf_mcp.recursivemas.official sequential math500 --num_recursive_rounds 3
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
RECURSIVEMAS_SUBMODULE = THIS_DIR.parent.parent.parent / "recursivemas"

if str(RECURSIVEMAS_SUBMODULE) not in sys.path:
    sys.path.insert(0, str(RECURSIVEMAS_SUBMODULE))

from recursivemas.run import main as official_main


def main():
    """Entry point for official RecursiveMAS inference."""
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("MAS_FORCE_DISABLE_TORCHVISION", "1")
    return official_main()


if __name__ == "__main__":
    raise SystemExit(main())
