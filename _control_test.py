"""
Head-to-head: Single model vs RecursiveMAS on identical prompts.
Tests whether latent recursion produces better output than standalone models.
"""
import torch, time, sys
torch.cuda.empty_cache()
sys.path.insert(0, "C:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp")
from hlf.model_orchestrator import _resolve_checkpoint_base
from hlf.latent_model_interface import LatentRecursiveSession, RecursiveSessionConfig
from transformers import AutoModelForCausalLM, AutoTokenizer

cache_root = "C:/Users/gerry/.cache/huggingface/recursivemas"

PROMPTS = [
    ("MATH", "Find all real solutions to: sqrt(x+3) + sqrt(x) = 3. Show all steps including domain and verification."),
    ("PROB", "A bag has 4 red, 3 blue, 2 green marbles. Draw 3 without replacement. Probability at least 2 are same color? Show work."),
    ("MED", "Patient: 45F, fatigue, 15lb weight gain, constipation, cold intolerance, bradycardia 52bpm, TSH=150, free T4=0.3, visible goiter. Most likely diagnosis and why? Rule in/out: Hashimoto's, iodine deficiency, pituitary adenoma, subclinical hypothyroidism, postpartum thyroiditis."),
]

def make_rmas_config(task="math", rounds=2, tokens=300):
    return RecursiveSessionConfig(
        agent_models={
            "planner": _resolve_checkpoint_base(cache_root, "Sequential-Light-Planner-Qwen3-1.7B"),
            "critic":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Critic-Llama3.2-1B"),
            "solver":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B"),
        },
        recursion_rounds=rounds, max_new_tokens=tokens, temperature=0.0,
        device="cuda", adapter_task=task,
        inner_link_paths={
            "planner": _resolve_checkpoint_base(cache_root, "Sequential-Light-Planner-Qwen3-1.7B", adapter_file=f"adapter({task}).pt"),
            "critic":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Critic-Llama3.2-1B", adapter_file=f"adapter({task}).pt"),
            "solver":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B", adapter_file=f"adapter({task}).pt"),
        },
        outer_link_paths={
            "planner_critic": _resolve_checkpoint_base(cache_root, "Sequential-Light-Outerlinks", adapter_file=f"Planner-Critic-Outerlink({task}).pt"),
            "critic_solver":  _resolve_checkpoint_base(cache_root, "Sequential-Light-Outerlinks", adapter_file=f"Critic-Solver-Outerlink({task}).pt"),
            "solver_planner": _resolve_checkpoint_base(cache_root, "Sequential-Light-Outerlinks", adapter_file=f"Solver-Planner-Outerlink({task}).pt"),
        },
    )

def run_single_model(model_path, prompt, max_tokens=300):
    """Run a single model standalone (no latent recursion)."""
    model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16, device_map="cuda")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_tokens, temperature=0.0, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    elapsed = time.time() - t0
    text = tokenizer.decode(out[0], skip_special_tokens=True)
    # Remove prompt from output
    if text.startswith(prompt):
        text = text[len(prompt):].strip()
    vram = torch.cuda.memory_allocated() / 1e9
    del model; torch.cuda.empty_cache()
    return text, elapsed, vram

def run_recursive_mas(config, prompt):
    """Run full RecursiveMAS pipeline."""
    session = LatentRecursiveSession(config)
    session.load_all()
    t0 = time.time()
    result = session.recursive_infer(prompt)
    elapsed = time.time() - t0
    steps = len(result["steps"])
    chain = " -> ".join(f"{s['agent']}(R{s['round']})" for s in result["steps"])
    vram = torch.cuda.memory_allocated() / 1e9
    session.unload()
    torch.cuda.empty_cache()
    return result["final_text"].strip(), elapsed, steps, chain, vram

# ============================================================
print("=" * 75)
print("  CONTROL EXPERIMENT: Single Model vs RecursiveMAS")
print("  Solver (Qwen2.5-Math-1.5B) standalone vs Planner→Critic→Solver latent")
print("=" * 75)

for label, prompt in PROMPTS:
    print(f"\n{'─'*75}")
    print(f"  [{label}] {prompt[:100]}...")
    print(f"{'─'*75}")
    
    solver_path = _resolve_checkpoint_base(cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B")
    
    # Single model
    print(f"  ▶ SINGLE SOLVER (1.5B, text-only, no recursion)...")
    solo_text, solo_time, solo_vram = run_single_model(solver_path, prompt, max_tokens=300)
    print(f"    Time: {solo_time:.1f}s | VRAM: {solo_vram:.2f}GB | Output: {len(solo_text)} chars")
    print(f"    First 200 chars: {solo_text[:200]}")
    
    # RecursiveMAS
    print(f"  ▶ RECURSIVEMAS (3 models, 2-round latent recursion)...")
    rmas_config = make_rmas_config(task="math", rounds=2, tokens=300)
    rmas_text, rmas_time, rmas_steps, rmas_chain, rmas_vram = run_recursive_mas(rmas_config, prompt)
    print(f"    Time: {rmas_time:.1f}s | VRAM: {rmas_vram:.2f}GB | Steps: {rmas_steps} | Chain: {rmas_chain}")
    print(f"    First 200 chars: {rmas_text[:200]}")
    
    print(f"\n  COMPARISON: Solo={solo_time:.1f}s/{solo_vram:.1f}GB | RMAS={rmas_time:.1f}s/{rmas_vram:.1f}GB | Speedup={solo_time/rmas_time if rmas_time else 0:.1f}x")

print(f"\n{'='*75}")
print("  CONTROL EXPERIMENT COMPLETE")
print("=" * 75)
