import torch, sys
from pathlib import Path
torch.cuda.empty_cache()
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR / "hlf_mcp"))
from hlf.model_orchestrator import _resolve_checkpoint_base
from hlf.latent_model_interface import LatentRecursiveSession, RecursiveSessionConfig

cache_root = str(Path.home() / ".cache/huggingface/recursivemas")
config = RecursiveSessionConfig(
    agent_models={
        "planner": _resolve_checkpoint_base(cache_root, "Sequential-Light-Planner-Qwen3-1.7B"),
        "critic":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Critic-Llama3.2-1B"),
        "solver":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B"),
    },
    recursion_rounds=2, max_new_tokens=100, temperature=0.0,
    device="cuda", adapter_task="math",
    inner_link_paths={
        "planner": _resolve_checkpoint_base(cache_root, "Sequential-Light-Planner-Qwen3-1.7B", adapter_file="adapter(math).pt"),
        "critic":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Critic-Llama3.2-1B", adapter_file="adapter(math).pt"),
        "solver":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B", adapter_file="adapter(math).pt"),
    },
    outer_link_paths={
        "planner_critic": _resolve_checkpoint_base(cache_root, "Sequential-Light-Outerlinks", adapter_file="Planner-Critic-Outerlink(math).pt"),
        "critic_solver":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Outerlinks", adapter_file="Critic-Solver-Outerlink(math).pt"),
        "solver_planner": _resolve_checkpoint_base(cache_root, "Sequential-Light-Outerlinks", adapter_file="Solver-Planner-Outerlink(math).pt"),
    },
)
session = LatentRecursiveSession(config)
session.load_all()
result = session.recursive_infer("What is 17 * 23? Show work.")
chain = " -> ".join(f"{s['agent']}(R{s['round']})" for s in result["steps"])
print(f"CHAIN: {chain}")
print(f"STEPS: {len(result['steps'])} (expected 6: planner+c+s x2 rounds)")
print(f"OUTPUT: {result['final_text'][:200]}")
session.unload()
