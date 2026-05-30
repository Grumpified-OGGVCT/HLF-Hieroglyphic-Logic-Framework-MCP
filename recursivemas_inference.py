"""RecursiveMAS Inference — 4-Model Complementary Ring with latent-space communication.

  Coder(Qwen0.5B,896d) → Router(functiongemma,640d) → Critic(Gemma3,1152d) → Solver(Qwen1.5B,1536d) → Coder

SwarmGlass governance shell: TelemetryCollector, CircuitBreaker, EvidenceSummaryRenderer.
ALL intermediate steps are pure latent-space — NO text between recursions. Only the FINAL step decodes.

Usage:  python recursivemas_inference.py "Your prompt" [--recursions N] [--max-tokens M]
"""

import sys, argparse, json, time, warnings
from pathlib import Path
from dataclasses import dataclass, field

import torch
import torch.nn as nn

warnings.filterwarnings("ignore")

# ═══ SwarmGlass Governance Primitives (stdlib only, zero DSL) ═══

@dataclass
class TelemetryCollector:
    """Tracks hidden state quality per bridge, per recursion round."""
    rounds: list = field(default_factory=list)
    def record(self, src, dst, in_norm, out_norm, loss_delta=None):
        self.rounds.append({"src": src, "dst": dst, "in_norm": in_norm,
                            "out_norm": out_norm, "loss_delta": loss_delta,
                            "ts": time.time()})
    def summary(self):
        print(f"\n{'=' * 60}\nSWARMGLASS TELEMETRY\n{'=' * 60}")
        for i, r in enumerate(self.rounds):
            flag = " ⚠" if r["out_norm"] > 100 else ""
            print(f"  [{i}] {r['src']}→{r['dst']}  "
                  f"in_norm={r['in_norm']:.4f}  out_norm={r['out_norm']:.4f}{flag}")
        norms = [r["out_norm"] for r in self.rounds]
        print(f"  mean_out_norm={sum(norms)/len(norms):.4f}  "
              f"min={min(norms):.4f}  max={max(norms):.4f}")

class CircuitBreaker:
    """Kill runaway recursion if hidden state norm explodes or goes NaN."""
    MAX_NORM = 500.0
    def __init__(self): self.tripped = False
    def check(self, hidden, label=""):
        n = hidden.norm().item()
        if torch.isnan(hidden).any():
            print(f"\n  ═══ CIRCUIT BREAKER TRIPPED ═══\n  NaN detected at: {label}")
            self.tripped = True
        elif n > self.MAX_NORM:
            print(f"\n  ═══ CIRCUIT BREAKER TRIPPED ═══\n  Norm {n:.1f} exceeds {self.MAX_NORM} at: {label}")
            self.tripped = True
        return self.tripped

class EvidenceSummaryRenderer:
    """Post-hoc governance report."""
    @staticmethod
    def render(telemetry, num_recursions, duration_s, circuit_breaker):
        print(f"\n{'═' * 60}\n  GOVERNANCE REPORT\n{'═' * 60}")
        print(f"  Recursions:     {num_recursions}")
        print(f"  Duration:       {duration_s:.1f}s")
        print(f"  Bridge events:  {len(telemetry.rounds)}")
        print(f"  Circuit OK:     {not circuit_breaker.tripped}")
        norms = [r["out_norm"] for r in telemetry.rounds]
        if norms:
            print(f"  Norm range:     [{min(norms):.2f}, {max(norms):.2f}]")
            print(f"  Norm trend:     {'stable' if max(norms) < 100 else '⚠ diverging'}")

# ═══ CrossModelAdapter — Published RecursiveMAS RecursiveLink (modeling.py:139-159) ═══

class CrossModelAdapter(nn.Module):
    """RecursiveLink: projects hidden states between models' dimensional spaces."""
    def __init__(self, in_dim, out_dim, adapter_type="outer_ln_res_adapter"):
        super().__init__()
        self.adapter_type = adapter_type
        self.in_dim, self.out_dim = in_dim, out_dim
        hdim = out_dim * 2
        self.proj1 = nn.Linear(in_dim, hdim)
        self.act = nn.GELU()
        self.proj2 = nn.Linear(hdim, out_dim)
        self.ln_source = nn.LayerNorm(in_dim)
        self.ln_target = nn.LayerNorm(out_dim)
        self.residual_proj = nn.Linear(in_dim, out_dim)

    def forward(self, x):
        h = self.ln_source(x)
        out = self.proj2(self.act(self.proj1(h)))
        out = out + self.residual_proj(x)
        return self.ln_target(out)


# ═══ 4-Model Constants ═══

QWEN_MODEL   = "Qwen/Qwen2.5-Coder-0.5B-Instruct"
FUNCG_MODEL  = "google/functiongemma-270m-it"
GEMMA_MODEL  = "google/gemma-3-1b-it"
QWEN15_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"

QWEN_DIM    = 896
FUNCG_DIM   = 640
GEMMA_DIM   = 1152
QWEN15_DIM  = 1536

ADAPTER_DIR = str(Path(__file__).resolve().parent / "trained_adapters")

# ═══ Model helpers ═══

def _freeze(m):
    m.eval()
    for p in m.parameters(): p.requires_grad = False


def _hidden_size(m):
    return m.config.hidden_size


def load_models():
    """Load all 4 models. FP16 for Qwen0.5B, FP32 for funcG (FP16 unstable), 4-bit for Gemma/Qwen1.5B."""
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    print("=" * 60 + "\nLOADING 4-MODEL RECURSIVEMAS RING\n" + "=" * 60)
    free, total = torch.cuda.mem_get_info()
    print(f"  VRAM free: {free / 1024**3:.1f} GB / {total / 1024**3:.1f} GB")

    print(f"\n[1/4] Coder:     Qwen2.5-Coder-0.5B (FP16, ~1.0GB)")
    coder = AutoModelForCausalLM.from_pretrained(
        QWEN_MODEL, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
    coder_tok = AutoTokenizer.from_pretrained(QWEN_MODEL, trust_remote_code=True)
    if coder_tok.pad_token is None: coder_tok.pad_token = coder_tok.eos_token
    _freeze(coder)
    print(f"    dim={coder.config.hidden_size}  device={coder.device}")

    print(f"\n[2/4] Router:    functiongemma-270m-it (FP32, ~1.1GB)")
    router = AutoModelForCausalLM.from_pretrained(
        FUNCG_MODEL, torch_dtype=torch.float32, device_map="auto", trust_remote_code=True)
    router_tok = AutoTokenizer.from_pretrained(FUNCG_MODEL, trust_remote_code=True)
    if router_tok.pad_token is None: router_tok.pad_token = router_tok.eos_token
    _freeze(router)
    print(f"    dim={router.config.hidden_size}  device={router.device}")

    print(f"\n[3/4] Critic:    Gemma-3-1B-it (4-bit NF4, ~1.2GB)")
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                              bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4")
    critic = AutoModelForCausalLM.from_pretrained(
        GEMMA_MODEL, quantization_config=bnb, device_map="auto", trust_remote_code=True)
    critic_tok = AutoTokenizer.from_pretrained(GEMMA_MODEL, trust_remote_code=True)
    if critic_tok.pad_token is None: critic_tok.pad_token = critic_tok.eos_token
    _freeze(critic)
    gdim = critic.config.hidden_size
    if hasattr(critic.config, 'text_config'): gdim = critic.config.text_config.hidden_size
    print(f"    dim={gdim}  device={critic.device}")

    print(f"\n[4/4] Solver:    Qwen2.5-Coder-1.5B (4-bit NF4, ~1.5GB)")
    bnb2 = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4")
    solver = AutoModelForCausalLM.from_pretrained(
        QWEN15_MODEL, quantization_config=bnb2, device_map="auto", trust_remote_code=True)
    solver_tok = AutoTokenizer.from_pretrained(QWEN15_MODEL, trust_remote_code=True)
    if solver_tok.pad_token is None: solver_tok.pad_token = solver_tok.eos_token
    _freeze(solver)
    print(f"    dim={solver.config.hidden_size}  device={solver.device}")
    torch.cuda.empty_cache()

    return coder, coder_tok, router, router_tok, critic, critic_tok, solver, solver_tok


def load_adapters(adapter_dir, device):
    """Load 4 ring adapters: qwen→funcG, funcG→gemma, gemma→qwen15, qwen15→qwen."""
    adir = Path(adapter_dir)

    def _load(name):
        cfg_path = adir / f"{name}_config.json"
        pt_path  = adir / f"{name}.pt"
        with open(cfg_path) as f: cfg = json.load(f)
        adapter = CrossModelAdapter(cfg['in_dim'], cfg['out_dim'])
        adapter.load_state_dict(torch.load(pt_path, map_location="cpu", weights_only=True))
        return adapter.to(device).eval(), cfg

    print(f"\n{'=' * 60}\nLOADING RECURSIVELINK ADAPTERS\n{'=' * 60}")
    q2f, q2f_cfg = _load("qwen_to_funcg")
    f2g, f2g_cfg = _load("funcg_to_gemma")
    g2q15, g2q15_cfg = _load("gemma_to_qwen15")
    q152q05, q152q05_cfg = _load("qwen15_to_qwen05")

    for name, cfg in [("qwen→funcG", q2f_cfg), ("funcG→gemma", f2g_cfg),
                       ("gemma→qwen1.5B", g2q15_cfg), ("qwen1.5B→qwen", q152q05_cfg)]:
        print(f"  {name:20s}  {cfg['in_dim']}→{cfg['out_dim']}  "
              f"loss={cfg['final_loss']:.4f}  ({cfg['training_steps']} steps)")

    return q2f, f2g, g2q15, q152q05


# ═══ Core RecursiveMAS Inference ═══

@torch.no_grad()
def _manual_generate(model, inputs_embeds, eos_id, max_new, temp=0.7, top_p=0.9):
    """Autoregressive generation from embeddings."""
    gen = []
    cur = inputs_embeds
    for _ in range(max_new):
        out = model(inputs_embeds=cur)
        logits = out.logits[:, -1, :] / temp
        if top_p < 1.0:
            sl, si = torch.sort(logits, descending=True)
            cp = torch.cumsum(torch.softmax(sl, dim=-1), dim=-1)
            mask = cp > top_p; mask[..., 1:] = mask[..., :-1].clone(); mask[..., 0] = False
            logits = logits.masked_fill(mask.scatter(1, si, mask), float('-inf'))
        nxt = torch.multinomial(torch.softmax(logits, dim=-1), 1)
        tid = nxt.item(); gen.append(tid)
        del out, logits
        if tid == eos_id: break
        cur = model.get_input_embeddings()(nxt)
    return torch.tensor([gen], device=inputs_embeds.device)


def run_recursive_inference(prompt, coder, coder_tok, router, router_tok,
                            critic, critic_tok, solver, solver_tok,
                            q2f, f2g, g2q15, q152q05,
                            num_recursions=3, max_new_tokens=128):
    """4-model RecursiveMAS latent-space ring.

    Flow per recursion:
      Coder(Qwen0.5B) →[q2f]→ Router(funcG) →[f2g]→ Critic(Gemma) →[g2q15]→ Solver(Qwen1.5B) →[q152q05]→ Coder
    """
    telemetry = TelemetryCollector()
    cb = CircuitBreaker()
    start_time = time.time()
    cdev = next(coder.parameters()).device

    print(f"\n{'=' * 60}\nRECURSIVE INFERENCE (4-Model Ring)\n{'=' * 60}")
    print(f"  Prompt:      {prompt[:120]}{'...' if len(prompt) > 120 else ''}")
    print(f"  Recursions:  {num_recursions} complete ring cycles")
    print(f"  Ring:        Coder(896d) → Router(640d) → Critic(1152d) → Solver(1536d) → Coder")

    # ── Step 1: Encode prompt → Coder hidden state (mean-pool full sequence) ──
    tok = coder_tok(prompt, return_tensors="pt")
    ids = tok["input_ids"].to(cdev); am = tok["attention_mask"].to(cdev)

    with torch.no_grad():
        emb = coder.get_input_embeddings()(ids)
        out = coder(inputs_embeds=emb, attention_mask=am, output_hidden_states=True)
        # Mean-pool across sequence for richer semantic representation
        hs = out.hidden_states[-1]  # [1, seq, 896]
        mask = am.unsqueeze(-1).float()
        hidden = (hs * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)  # [1, 896]
        prompt_emb_coder = emb.detach().clone()  # save for anchoring
        del out, hs, mask

    print(f"\n[Init]  Coder hidden  | shape={list(hidden.shape)}  norm={hidden.norm().item():.4f}")
    torch.cuda.empty_cache()

    # ── Step 2: Recursive latent-space ring ──
    REPEAT_TOKENS = 8  # expand pooled hidden into short sequence for richer model processing
    # Cache original prompt embeddings for each model (semantic anchor)
    prompt_anchors = {}
    with torch.no_grad():
        prompt_anchors["router"] = router.get_input_embeddings()(
            router_tok(prompt, return_tensors="pt", truncation=True, max_length=32)
            ["input_ids"].to(cdev))
        prompt_anchors["critic"] = critic.get_input_embeddings()(
            critic_tok(prompt, return_tensors="pt", truncation=True, max_length=32)
            ["input_ids"].to(cdev))
        prompt_anchors["solver"] = solver.get_input_embeddings()(
            solver_tok(prompt, return_tensors="pt", truncation=True, max_length=32)
            ["input_ids"].to(cdev))
        prompt_anchors["coder"] = prompt_emb_coder  # already have it from init

    for r in range(num_recursions):
        print(f"\n── Ring Cycle {r + 1}/{num_recursions} " + "─" * 30)

        # Coder → Router: Qwen0.5B(FP16) →[q2f]→ funcG(FP32)
        r_in = hidden.unsqueeze(0).float()                          # [1, 896]
        router_emb = q2f(r_in).squeeze(0).to(router.dtype)          # [640]
        # Anchor: concat projected emb + prompt embeds
        anchor = prompt_anchors["router"].squeeze(0).to(router.dtype)[:REPEAT_TOKENS]
        router_seq = router_emb.unsqueeze(0).repeat(1, REPEAT_TOKENS, 1)  # [1, 8, 640]
        # Interleave or prepend anchor? Let's do: [projected_tokens | anchor_tokens]
        eR = torch.cat([router_seq, anchor.unsqueeze(0)], dim=1)     # [1, 8+N, 640]
        in_norm = hidden.norm().item()
        with torch.no_grad():
            oR = router(inputs_embeds=eR, output_hidden_states=True)
            hs_r = oR.hidden_states[-1]                              # [1, 8+N, 640]
            hidden = hs_r.mean(dim=1)                                # [1, 640]
            del oR, eR, hs_r
        out_norm = hidden.norm().item()
        telemetry.record("coder", "router", in_norm, out_norm)
        print(f"  Coder→Router  | 896→640   in_norm={in_norm:.4f}  out_norm={out_norm:.4f}")
        if cb.check(hidden, "Coder→Router"): break

        # Router → Critic: funcG(FP32) →[f2g]→ Gemma(BF16)
        r_in = hidden.unsqueeze(0).float()
        critic_emb = f2g(r_in).squeeze(0).to(critic.dtype)          # [1152]
        anchor = prompt_anchors["critic"].squeeze(0).to(critic.dtype)[:REPEAT_TOKENS]
        critic_seq = critic_emb.unsqueeze(0).repeat(1, REPEAT_TOKENS, 1)
        eC = torch.cat([critic_seq, anchor.unsqueeze(0)], dim=1)
        in_norm = hidden.norm().item()
        with torch.no_grad():
            oC = critic(inputs_embeds=eC, output_hidden_states=True)
            hs_c = oC.hidden_states[-1]
            hidden = hs_c.mean(dim=1)
            del oC, eC, hs_c
        out_norm = hidden.norm().item()
        telemetry.record("router", "critic", in_norm, out_norm)
        print(f"  Router→Critic | 640→1152  in_norm={in_norm:.4f}  out_norm={out_norm:.4f}")
        if cb.check(hidden, "Router→Critic"): break

        # Critic → Solver: Gemma(BF16) →[g2q15]→ Qwen1.5B(BF16)
        r_in = hidden.unsqueeze(0).float()
        solver_emb = g2q15(r_in).squeeze(0).to(solver.dtype)        # [1536]
        anchor = prompt_anchors["solver"].squeeze(0).to(solver.dtype)[:REPEAT_TOKENS]
        solver_seq = solver_emb.unsqueeze(0).repeat(1, REPEAT_TOKENS, 1)
        eS = torch.cat([solver_seq, anchor.unsqueeze(0)], dim=1)
        in_norm = hidden.norm().item()
        with torch.no_grad():
            oS = solver(inputs_embeds=eS, output_hidden_states=True)
            hs_s = oS.hidden_states[-1]
            hidden = hs_s.mean(dim=1)
            del oS, eS, hs_s
        out_norm = hidden.norm().item()
        telemetry.record("critic", "solver", in_norm, out_norm)
        print(f"  Critic→Solver | 1152→1536 in_norm={in_norm:.4f}  out_norm={out_norm:.4f}")
        if cb.check(hidden, "Critic→Solver"): break

        # Solver → Coder: Qwen1.5B(BF16) →[q152q05]→ Qwen0.5B(FP16)
        r_in = hidden.unsqueeze(0).float()
        coder_emb = q152q05(r_in).squeeze(0).to(coder.dtype)        # [896]
        anchor = prompt_anchors["coder"].squeeze(0).to(coder.dtype)[:REPEAT_TOKENS]
        coder_seq = coder_emb.unsqueeze(0).repeat(1, REPEAT_TOKENS, 1)
        eCo = torch.cat([coder_seq, anchor.unsqueeze(0)], dim=1)
        in_norm = hidden.norm().item()
        with torch.no_grad():
            oCo = coder(inputs_embeds=eCo, output_hidden_states=True)
            hs_co = oCo.hidden_states[-1]
            hidden = hs_co.mean(dim=1)
            del oCo, eCo, hs_co
        out_norm = hidden.norm().item()
        telemetry.record("solver", "coder", in_norm, out_norm)
        print(f"  Solver→Coder  | 1536→896  in_norm={in_norm:.4f}  out_norm={out_norm:.4f}")
        if cb.check(hidden, "Solver→Coder"): break

        torch.cuda.empty_cache()

    # ── Step 3: Decode final hidden state → text (via Coder) ──
    print(f"\n{'=' * 60}\nDECODING (final step — first text output)\n{'=' * 60}")
    print(f"  Final hidden: shape={list(hidden.shape)}  norm={hidden.norm().item():.4f}  dtype={hidden.dtype}")

    fin = hidden.unsqueeze(1).to(coder.dtype)  # [1, 1, 896]
    with torch.no_grad():
        try:
            out_ids = coder.generate(inputs_embeds=fin, max_new_tokens=max_new_tokens,
                                      do_sample=True, temperature=0.7, top_p=0.9,
                                      pad_token_id=coder_tok.eos_token_id,
                                      eos_token_id=coder_tok.eos_token_id)
            print("  Method: model.generate() ✓")
        except Exception as e:
            print(f"  generate() failed ({type(e).__name__}), falling back to manual decode")
            out_ids = _manual_generate(coder, fin, coder_tok.eos_token_id,
                                        max_new_tokens, temp=0.7, top_p=0.9)
            print("  Method: manual autoregressive ✓")

    result = coder_tok.decode(out_ids[0], skip_special_tokens=True)
    duration_s = time.time() - start_time

    # ── SwarmGlass governance reports ──
    telemetry.summary()
    EvidenceSummaryRenderer.render(telemetry, num_recursions, duration_s, cb)

    print(f"\n{'=' * 60}\nRESULT\n{'=' * 60}\n{result}")

    if cb.tripped:
        print(f"\n{'!' * 60}\n  WARNING: Circuit breaker tripped — result may be degraded\n{'!' * 60}")

    return result, telemetry


# ═══ CLI ═══

def main():
    p = argparse.ArgumentParser(description="RecursiveMAS 4-Model Inference with SwarmGlass governance")
    p.add_argument("prompt", type=str, help="Input prompt")
    p.add_argument("--recursions", "-r", type=int, default=3,
                   help="Ring cycles (default: 3, each cycle = 4 bridge crossings)")
    p.add_argument("--max-tokens", "-m", type=int, default=128,
                   help="Max new tokens to generate (default: 128)")
    p.add_argument("--adapter-dir", type=str, default=ADAPTER_DIR,
                   help="Directory containing trained adapter .pt files")
    args = p.parse_args()

    print("=" * 60 + "\nRecursiveMAS 4-Model Inference\n" + "=" * 60)
    print(f"  CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU:  {torch.cuda.get_device_name(0)}")

    models = load_models()
    coder, coder_tok, router, router_tok, critic, critic_tok, solver, solver_tok = models
    q2f, f2g, g2q15, q152q05 = load_adapters(args.adapter_dir, next(coder.parameters()).device)

    result, telemetry = run_recursive_inference(
        args.prompt, coder, coder_tok, router, router_tok,
        critic, critic_tok, solver, solver_tok,
        q2f, f2g, g2q15, q152q05,
        args.recursions, args.max_tokens)

    print(f"\n{'=' * 60}\nPIPELINE COMPLETE\n{'=' * 60}")


if __name__ == "__main__":
    main()
