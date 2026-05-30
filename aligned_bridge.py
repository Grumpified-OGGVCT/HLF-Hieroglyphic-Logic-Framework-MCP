"""
Embedding-Aligned Bridge Initializer for RecursiveMAS

PROBLEM: Random bridge weights destroy semantic content during cross-model
latent transfer. Hidden states from Model A's deep layers are projected into
Model B's embedding space through random matrices, producing noise.

SOLUTION: Use the embedding layers of both models to find a least-squares
projection that maps semantically equivalent vectors between spaces.

1. Find common tokens (same text) in both vocabularies
2. Get embedding vectors from both models for those tokens
3. Solve: emb_src @ W^T = emb_dst  (least squares)
4. Initialize bridge with W
5. Hidden states from Model A live near its embedding space, so W preserves
   semantic relationships when projecting to Model B's space.

This gives us INITIALIZED bridges that produce non-garbage output immediately,
without requiring training.
"""

import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Dict, Set, Tuple, Optional
import warnings
warnings.filterwarnings("ignore")


def get_embedding_matrix(model) -> torch.Tensor:
    """Get the token embedding matrix from a model."""
    return model.get_input_embeddings().weight.detach()  # (vocab_size, dim)


def find_common_tokens(tokenizer_a, tokenizer_b, max_tokens: int = 5000) -> Dict[int, int]:
    """
    Find tokens that decode to the same text in both tokenizers.
    Returns: {token_id_a: token_id_b} mapping.
    """
    vocab_a = tokenizer_a.get_vocab()
    vocab_b = tokenizer_b.get_vocab()
    
    # Build reverse mapping: text -> token_id for B
    text_to_id_b = {}
    for token_str, token_id in vocab_b.items():
        if token_id < len(vocab_b):
            text_to_id_b[token_str] = token_id
    
    # Find overlapping tokens
    mapping = {}
    for token_str, token_id_a in vocab_a.items():
        if token_id_a >= min(max_tokens, len(vocab_a)):
            continue
        if token_str in text_to_id_b:
            token_id_b = text_to_id_b[token_str]
            if token_id_b < max_tokens:
                mapping[token_id_a] = token_id_b
        if len(mapping) >= max_tokens:
            break
    
    return mapping


def compute_aligned_projection(
    model_a, model_b,
    tokenizer_a, tokenizer_b,
    num_tokens: int = 3000,
    device: str = "cuda"
) -> torch.Tensor:
    """
    Compute a least-squares projection from Model A's embedding space to
    Model B's embedding space using common vocabulary tokens.
    
    Returns: weight matrix W of shape (dim_b, dim_a) such that emb_b = emb_a @ W^T
    """
    emb_a = get_embedding_matrix(model_a)  # (vocab_a, dim_a)
    emb_b = get_embedding_matrix(model_b)  # (vocab_b, dim_b)
    
    dim_a = emb_a.shape[1]
    dim_b = emb_b.shape[1]
    
    mapping = find_common_tokens(tokenizer_a, tokenizer_b, max_tokens=num_tokens * 2)
    
    if len(mapping) < 100:
        print(f"  WARNING: Only {len(mapping)} common tokens found! Projection will be poor.")
    
    ids_a = list(mapping.keys())[:num_tokens]
    ids_b = [mapping[i] for i in ids_a]
    
    # Build aligned embedding matrices
    X = emb_a[ids_a].to(device)  # (N, dim_a)
    Y = emb_b[ids_b].to(device)  # (N, dim_b)
    
    print(f"  Using {len(ids_a)} aligned token pairs")
    print(f"  X shape: {tuple(X.shape)}, Y shape: {tuple(Y.shape)}")
    
    # Solve: Y = X @ W^T  =>  W = lstsq(X, Y)^T
    # lstsq requires float32
    X_f32 = X.float()
    Y_f32 = Y.float()
    solution = torch.linalg.lstsq(X_f32, Y_f32)
    W = solution.solution.T  # (dim_b, dim_a)
    
    # Check reconstruction quality
    Y_pred = X_f32 @ W.float().T
    cos_sim = nn.functional.cosine_similarity(Y_pred, Y_f32, dim=-1).mean().item()
    mse = nn.functional.mse_loss(Y_pred, Y_f32).item()
    print(f"  Reconstruction: cosine_sim={cos_sim:.4f}, MSE={mse:.6f}")
    
    return W.cpu()


class AlignedBridge(nn.Module):
    """
    Bridge initialized from embedding alignment, with a small trainable
    refinement layer for adapting hidden states (which differ from embeddings).
    """
    def __init__(self, dim_from: int, dim_to: int, aligned_weight: Optional[torch.Tensor] = None):
        super().__init__()
        self.proj = nn.Linear(dim_from, dim_to, bias=False)
        
        if aligned_weight is not None:
            # Initialize with embedding-aligned projection
            self.proj.weight.data = aligned_weight.to(dtype=self.proj.weight.dtype)
        else:
            nn.init.orthogonal_(self.proj.weight)
        
        # Small refinement — hidden states aren't exactly embeddings,
        # but they live in a nearby subspace
        self.alpha = nn.Parameter(torch.tensor(0.05))  # Start small — trust the alignment
        
        refine_dim = max(dim_from, dim_to) // 2
        self.refine = nn.Sequential(
            nn.Linear(dim_to, refine_dim),
            nn.LayerNorm(refine_dim),
            nn.GELU(),
            nn.Linear(refine_dim, dim_to),
            nn.LayerNorm(dim_to),
        )
        # Initialize refinement near identity
        nn.init.normal_(self.refine[0].weight, std=0.01)
        nn.init.zeros_(self.refine[0].bias)
        nn.init.normal_(self.refine[3].weight, std=0.01)
        nn.init.zeros_(self.refine[3].bias)
    
    def forward(self, x):
        base = self.proj(x)
        refinement = self.refine(base)
        return base + self.alpha * refinement


def build_aligned_bridges(
    experts: Dict[str, "ExpertAgent"],
    num_tokens: int = 3000,
    device: str = "cuda"
) -> Dict[Tuple[str, str], AlignedBridge]:
    """
    Build all-pairs bridges between experts, initialized from embedding alignment.
    Only creates non-identity bridges (src != dst).
    """
    bridges = {}
    
    expert_names = list(experts.keys())
    for i, src_name in enumerate(expert_names):
        src = experts[src_name]
        for j, dst_name in enumerate(expert_names):
            if src_name == dst_name:
                continue  # Self-loops are identity
            
            # Check if we already have this bridge (shared model case)
            key = (src_name, dst_name)
            
            print(f"\n  [ALIGN] {src_name}({src.hidden_dim}) -> {dst_name}({dst.hidden_dim})")
            
            # Only compute alignment if model instances differ
            if src.model is dst.model:
                # Same model instance — use identity-like initialization
                print(f"    Same model instance, using orthogonal init")
                bridge = AlignedBridge(src.hidden_dim, dst.hidden_dim, aligned_weight=None)
                if src.hidden_dim == dst.hidden_dim:
                    bridge.proj.weight.data = torch.eye(dst.hidden_dim)
            else:
                # Different models — compute embedding alignment
                aligned_w = compute_aligned_projection(
                    src.model, dst.model,
                    src.tokenizer, dst.tokenizer,
                    num_tokens=num_tokens, device=device
                )
                bridge = AlignedBridge(src.hidden_dim, dst.hidden_dim, aligned_weight=aligned_w)
            
            bridge = bridge.to(device)
            bridges[key] = bridge
            print(f"    Bridge: {sum(p.numel() for p in bridge.parameters()):,} params")
    
    return bridges


# ===============================================================================
# Test harness
# ===============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 70)
    print("Embedding-Aligned Bridge Initializer — Proof of Concept")
    print("=" * 70)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Load two models for testing
    model_names = [
        "Qwen/Qwen2.5-Coder-0.5B-Instruct",
        "google/gemma-3-1b-it"
    ]
    
    models = {}
    tokenizers = {}
    
    for name in model_names:
        short = name.split("/")[-1]
        print(f"\n[LOAD] {short}")
        
        load_kwargs = {"trust_remote_code": True, "torch_dtype": torch.float16}
        if "gemma" in name.lower():
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
        
        model = AutoModelForCausalLM.from_pretrained(name, **load_kwargs)
        tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        models[name] = model
        tokenizers[name] = tokenizer
        
        dim = model.config.hidden_size
        if hasattr(model.config, 'text_config'):
            dim = model.config.text_config.hidden_size
        print(f"  dim={dim}, vocab={len(tokenizer)}")
    
    # Compute alignment
    print(f"\n{'=' * 70}")
    print("COMPUTING EMBEDDING ALIGNMENT")
    print(f"{'=' * 70}")
    
    aligned_w = compute_aligned_projection(
        models[model_names[0]], models[model_names[1]],
        tokenizers[model_names[0]], tokenizers[model_names[1]],
        num_tokens=3000, device=device
    )
    
    # Test: encode text with Model A, project to Model B, decode
    print(f"\n{'=' * 70}")
    print("TEST: Cross-model latent transfer")
    print(f"{'=' * 70}")
    
    test_text = "def fibonacci(n):"
    
    # Model A (Qwen Coder) encode
    tok_a = tokenizers[model_names[0]]
    model_a = models[model_names[0]]
    
    # Get device for model A
    try:
        a_device = next(model_a.parameters()).device
    except StopIteration:
        a_device = torch.device("cuda:0")
    
    # Model B and its tokenizer
    model_b = models[model_names[1]]
    tok_b = tokenizers[model_names[1]]
    try:
        b_device = next(model_b.parameters()).device
    except StopIteration:
        b_device = torch.device("cuda:0")
    
    inputs_a = tok_a(test_text, return_tensors="pt").to(a_device)
    
    with torch.no_grad():
        outputs_a = model_a(**inputs_a, output_hidden_states=True)
        num_layers = len(outputs_a.hidden_states)
        print(f"  Model has {num_layers} hidden state layers (0..{num_layers-1})")
        
        test_layers = [(0, "embeddings"), (1, "layer_1"), (2, "layer_2"), 
                       (num_layers//4, f"layer_{num_layers//4}"),
                       (num_layers//2, f"layer_{num_layers//2}"),
                       (-1, "last_layer")]
        
        for layer_idx, layer_name in test_layers:
            hidden_a = outputs_a.hidden_states[layer_idx][:, -1:, :]  # Last token
            dim_a = hidden_a.shape[-1]
            
            # Project to Model B's space  
            proj_weight = aligned_w.to(device=a_device, dtype=hidden_a.dtype)
            projected = torch.matmul(hidden_a, proj_weight.T)
            
            projected_b = projected.to(dtype=model_b.dtype, device=b_device)
            
            with torch.no_grad():
                outputs_b = model_b.generate(
                    inputs_embeds=projected_b,
                    max_new_tokens=24,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=tok_b.eos_token_id,
                    eos_token_id=tok_b.eos_token_id,
                )
            
            text_b = tok_b.decode(outputs_b[0], skip_special_tokens=True)
            print(f"  {layer_name:12s} -> B output: {text_b[:120]}")
    
    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")
