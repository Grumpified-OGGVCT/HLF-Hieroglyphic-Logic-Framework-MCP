# Session Handoff — RecursiveMAS → SwarmGlass Integration

**Date:** 2026-05-26  
**From:** Session with maxed context  
**To:** Fresh session — paste this entire message as your first user prompt

---

## START HERE — Paste into new session:

```
Continue from SESSION_HANDOFF.md at C:\Users\gerry\generic_workspace\HLF_MCP\SESSION_HANDOFF.md
```

---

## Current Objective

**Install missing packages then run FunctionGemma fine-tuning:**

```bash
# Step 1: Install packages (use SYSTEM Python 3.12 — venv Python 3.13 is blocked by firewall)
& "C:\Users\gerry\AppData\Local\Programs\Python\Python312\python.exe" -m pip install peft trl datasets bitsandbytes accelerate --target "C:\Users\gerry\generic_workspace\HLF_MCP\.venv\Lib\site-packages"

# Step 2: Run fine-tuning
cd C:\Users\gerry\generic_workspace\HLF_MCP
.venv\Scripts\python.exe -m hlf_mcp.recursivemas.functiongemma_ft
```

---

## CRITICAL: Network Issue (You'll Hit This)

**System Python 3.12** (`C:\Users\gerry\AppData\Local\Programs\Python\Python312\python.exe`) CAN reach PyPI.

**Venv Python 3.13** (`C:\Users\gerry\generic_workspace\HLF_MCP\.venv\Scripts\python.exe`) is BLOCKED — `[WinError 10013]` socket access forbidden. This is a uv-managed Python (cpython-3.13.11).

**Workaround:** Use system Python 3.12's pip with `--target` pointing to the venv's site-packages:
```
C:\Users\gerry\generic_workspace\HLF_MCP\.venv\Lib\site-packages
```

---

## What's Already Done (RecursiveMAS Integration)

The RecursiveMAS framework is fully integrated into HLF_MCP as `hlf_mcp.recursivemas`:

```
hlf_mcp/recursivemas/
├── __init__.py              # Package exports
├── inference.py             # 4-Model Ring inference
├── cli.py                   # CLI entrypoints (lazy imports)
├── official.py              # Official chain-trained topologies
├── functiongemma_ft.py      # FunctionGemma fine-tuning pipeline (READY)
├── governance_primitives.py # Stdlib governance (CircuitBreaker, MerkleAudit, etc)
├── governed_pipeline.py     # Governed multi-round pipeline
└── train.py                 # CrossModelAdapter training

recursivemas/                # Git submodule — official Stanford/MIT/Nvidia repo
```

### Files changed in this integration:
- `pyproject.toml` — Added `hlf_mcp.recursivemas` package, 4 CLI entrypoints, `recursivemas` optional deps
- `run.bat` — Added `recursivemas`, `rmas`, `recursivemas-train`, `rmas-train`, `recursivemas-governed`, `rmas-governed`
- `.gitmodules` — Added recursivemas submodule

### CLI Entrypoints:
| Command | Function |
|---------|----------|
| `hlf-recursivemas` | 4-Model Ring inference (Coder→Router→Critic→Solver) |
| `hlf-recursivemas-train` | Train CrossModelAdapters |
| `hlf-recursivemas-official` | Official chain-trained topologies |
| `hlf-recursivemas-governed` | Governed pipeline with SwarmGlass governance |

### Package Status:
| Component | Status | Blocker |
|-----------|--------|---------|
| 4-Model Ring inference | ✅ Ready | Needs trained adapters in `HLF_MCP/trained_adapters/` |
| CrossModelAdapter training | ✅ Ready | Nothing |
| FunctionGemma fine-tuning | ❌ Blocked | peft, trl, datasets, bitsandbytes, accelerate |
| Official topologies | ❌ Blocked | datasets + chain-trained checkpoints |
| Governed pipeline | ❌ Blocked | datasets + chain-trained checkpoints |

### Currently installed (venv):
```
torch==2.12.0
transformers==5.9.0
```

### Still needed:
```
peft trl datasets bitsandbytes accelerate
```

---

## FunctionGemma Fine-Tuning Details

Script: `hlf_mcp/recursivemas/functiongemma_ft.py` (~540 lines, complete and ready)

**What it does:**
1. Generate training dataset (~400 examples across 4 tool schemas: write_file, run_command, search_knowledge, no_action)
2. LoRA fine-tune `functiongemma:270m` to execute tool calls
3. Merge LoRA weights back into base model
4. Convert to GGUF for Ollama

**Training config:**
- Model: google/functiongemma-270m (or functiongemma:270m via Ollama)
- LoRA: rank=16, alpha=32
- Targets: q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj, down_proj
- Epochs: 3, batch_size=2, gradient_accumulation=4
- Precision: bf16
- Estimated time: ~2-3 hours on RTX 3060 12GB
- Output: `HLF_MCP/functiongemma_ft/` (adapter, merged model, GGUF)

**FunctionGemma format (discovered in prior work):**
- Uses `role: "developer"` (NOT "system")
- Special prompt: "You are a model that can do function calling with the following functions"
- Tool types: STRING, INTEGER, OBJECT (uppercase)
- Base model refuses code tasks — needs fine-tuning to override

---

## Long-Term Vision (After Fine-Tuning)

1. FunctionGemma fine-tuning complete → integrates as post-pipeline executor
2. Integrate ALL suitable local models MoE-style
3. Benchmark complexity scales to map local inference capability limits
4. Goal: agents can intelligently decide local vs cloud model usage

---

## Key Paths

| Item | Path |
|------|------|
| Repo root | `C:\Users\gerry\generic_workspace\HLF_MCP` |
| Venv Python (blocked) | `.venv\Scripts\python.exe` (3.13) |
| System Python (works) | `C:\Users\gerry\AppData\Local\Programs\Python\Python312\python.exe` |
| Venv site-packages | `.venv\Lib\site-packages` |
| RecursiveMAS submodule | `recursivemas/` (official repo) |
| FunctionGemma FT script | `hlf_mcp/recursivemas/functiongemma_ft.py` |
| Trained adapters dir | `trained_adapters/` (for CrossModelAdapters) |
| FT output dir | `functiongemma_ft/` |
