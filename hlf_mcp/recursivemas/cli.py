"""CLI entry points for RecursiveMAS within SwarmGlass.

Usage:
    hlf-recursivemas <prompt> [--recursions N] [--max-tokens M]
    hlf-recursivemas-train [--epochs N] [--output-dir DIR]
    hlf-recursivemas-official --style <style> --dataset <dataset> [...]
"""


def main_inference():
    """SwarmGlass RecursiveMAS — 4-Model Complementary Ring inference."""
    from hlf_mcp.recursivemas.inference import main as inference_main
    return inference_main()


def main_train():
    """Train CrossModelAdapters for the 4-Model Ring."""
    from hlf_mcp.recursivemas.train import main as train_main
    return train_main()


def main_official():
    """Run official Stanford/MIT/Nvidia chain-trained topologies."""
    from hlf_mcp.recursivemas.official import main as official_main
    return official_main()


def main_governed():
    """Run governed RecursiveMAS pipeline with SwarmGlass governance."""
    from hlf_mcp.recursivemas.governed_pipeline import main as governed_main
    return governed_main()