#!/usr/bin/env python3
"""
RecursiveMAS v2 -- Text-based recursive multi-agent collaboration with specialized models.

ARCHITECTURE:
    Problem -> ContextAugmenter(datetime + web) ->
      [Round 1] Router picks expert -> expert generates with specialized system prompt -> text output
      [Round 2] Router picks expert (different, due to diversity) -> sees ALL prior outputs -> generates
      [Round 3] Router picks expert -> sees ALL prior outputs -> generates
      ...
      [Final] Coder (or best-fit expert) synthesizes everything into final solution

NO latent-space transfer. NO bridges. Just text-based recursive collaboration.

MODELS:
    - Qwen/Qwen2.5-Coder-0.5B-Instruct  (FP16,  ~1.0 GB) -- coder
    - google/gemma-3-1b-it              (4-bit, ~1.2 GB) -- critic, researcher, diverse (SHARED)
    - google/gemma-4-E2B-it             (4-bit, ~7.3 GB) -- tools (optional, skipped if VRAM tight)

VRAM BUDGET:
    Qwen (FP16):       ~1.0 GB
    Gemma-3-1B (4bit): ~1.2 GB (shared across 3 experts)
    Gemma-4-E2B (4bit):~7.3 GB
    KV cache + overhead:~2.0 GB
    Total target:      ~11.5 GB  -> 10.5 GB limit (may skip Gemma-4)
"""

import os
import sys
import re
import json
import time
import signal
import threading
import argparse
import warnings
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any, Callable
from enum import Enum
from datetime import datetime, timezone

import psutil
import torch

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_VRAM_LIMIT_GB = 10.5
DEFAULT_RAM_LIMIT_GB = 58.0
DEFAULT_MAX_ROUNDS = 3
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_NEW_TOKENS = 256
POLL_INTERVAL_SEC = 2.0


# =============================================================================
# Context Augmenter -- datetime + web search enrichment
# =============================================================================

class ContextAugmenter:
    """Enriches prompts with real-time info before they reach experts.

    All augmentation happens in the prompt text -- no model-level tool calling needed.
    Works with any model, including tiny ones.
    """

    def __init__(self, enable_search: bool = True, enable_fetch: bool = True):
        self.enable_search = enable_search
        self.enable_fetch = enable_fetch

    def enrich(self, task: str) -> str:
        """Build an enriched prompt from a raw task."""
        parts = []

        # 1. Current datetime -- always injected
        parts.append(self._datetime_context())

        # 2. Web search if task seems to need current info
        if self.enable_search and self._needs_web_info(task):
            search_results = self._search(task)
            if search_results:
                parts.append(search_results)

        # 3. The actual task
        parts.append(f"## Task\n{task}")

        return "\n\n".join(parts)

    def _datetime_context(self) -> str:
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        return (
            f"## Current Date & Time\n"
            f"- UTC: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"- Local: {local.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"- Day: {now.strftime('%A')}\n"
            f"Use this to ensure your response is current and accurate."
        )

    def _needs_web_info(self, task: str) -> bool:
        """Heuristic: does this task need real-time web info?"""
        web_signals = [
            "latest", "current", "recent", "new", "2025", "2026", "today",
            "news", "update", "version", "release", "price", "stock",
            "weather", "event", "happening", "now", "just announced",
            "what is the", "who is", "tell me about", "explain",
        ]
        task_lower = task.lower()
        return any(signal in task_lower for signal in web_signals)

    def _search(self, query: str, max_results: int = 3) -> str:
        """Search the web via DuckDuckGo."""
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append(r)

            if not results:
                return ""

            lines = ["## Web Search Results"]
            for i, r in enumerate(results, 1):
                title = r.get('title', 'No title')
                body = r.get('body', '')[:300]
                href = r.get('href', '')
                lines.append(f"{i}. **{title}**\n   {body}\n   Source: {href}")

            return "\n".join(lines)
        except ImportError:
            return "<!-- duckduckgo_search not installed; web search unavailable -->"
        except Exception as e:
            return f"<!-- Web search unavailable: {e} -->"

    def fetch_page(self, url: str, max_chars: int = 2000) -> str:
        """Fetch and extract text from a webpage."""
        if not self.enable_fetch:
            return f"<!-- Fetch disabled for {url} -->"
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get(url, timeout=10, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                )
            })
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()

            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)

            return f"## Fetched: {url}\n{text[:max_chars]}"
        except ImportError as e:
            return f"<!-- Fetch requires requests+bs4: {e} -->"
        except Exception as e:
            return f"<!-- Fetch failed for {url}: {e} -->"


# =============================================================================
# Resource Monitor -- background VRAM/RAM watchdog
# =============================================================================

class ResourceMonitor:
    """Background thread. Kills process if VRAM/RAM exceeds limits.

    Polls GPU memory via pynvml and system RAM via psutil every 2 seconds.
    Tracks peak usage. Exits process cleanly with os._exit(1) on limit breach.
    """

    def __init__(self, vram_limit_gb: float = DEFAULT_VRAM_LIMIT_GB,
                 ram_limit_gb: float = DEFAULT_RAM_LIMIT_GB):
        self.vram_limit_gb = vram_limit_gb
        self.ram_limit_gb = ram_limit_gb
        self.peak_vram = 0.0
        self.peak_ram = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Initialize NVML
        self._has_gpu = False
        self._nvml = None
        self._gpu_handle = None
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml = pynvml
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._has_gpu = True
        except Exception:
            pass

    def start(self):
        """Launch the background monitoring thread."""
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        gpu_status = "NVML" if self._has_gpu else "No GPU NVML"
        print(f"[MONITOR] {gpu_status} | VRAM limit: {self.vram_limit_gb}GB | "
              f"RAM limit: {self.ram_limit_gb}GB")

    def stop(self):
        """Stop monitoring and print peak usage."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._has_gpu and self._nvml:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass
        print(f"[RESOURCE] Peak VRAM: {self.peak_vram:.1f}GB | "
              f"Peak RAM: {self.peak_ram:.1f}GB")

    def _loop(self):
        """Background polling loop."""
        while not self._stop.is_set():
            try:
                vram, ram = self._sample()
                self.peak_vram = max(self.peak_vram, vram)
                self.peak_ram = max(self.peak_ram, ram)

                if vram > self.vram_limit_gb:
                    print(f"\n[FATAL] VRAM {vram:.1f}GB > {self.vram_limit_gb}GB "
                          f"limit -- KILLING PROCESS")
                    os._exit(1)
                if ram > self.ram_limit_gb:
                    print(f"\n[FATAL] RAM {ram:.1f}GB > {self.ram_limit_gb}GB "
                          f"limit -- KILLING PROCESS")
                    os._exit(1)
            except Exception:
                pass
            self._stop.wait(POLL_INTERVAL_SEC)

    def _sample(self) -> Tuple[float, float]:
        """Single resource sample. Returns (vram_gb, ram_gb)."""
        vram, ram = 0.0, 0.0
        try:
            ram = psutil.virtual_memory().used / (1024 ** 3)
        except Exception:
            pass
        if self._has_gpu and self._nvml and self._gpu_handle:
            try:
                info = self._nvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                vram = info.used / (1024 ** 3)
            except Exception:
                pass
        return vram, ram

    def snapshot(self) -> Dict[str, float]:
        """Return current and peak resource usage."""
        vram, ram = self._sample()
        return {
            "vram_gb": vram,
            "ram_gb": ram,
            "peak_vram_gb": self.peak_vram,
            "peak_ram_gb": self.peak_ram,
        }


# =============================================================================
# Expert Profiles -- role definitions with system prompts
# =============================================================================

class ExpertRole(Enum):
    CODER = "coder"
    CRITIC = "critic"
    RESEARCHER = "researcher"
    DIVERSE = "diverse"
    TOOLS = "tools"


@dataclass
class ExpertProfile:
    """Metadata for an expert role, including model and system prompt."""
    role: ExpertRole
    model_name: str
    description: str
    system_prompt: str
    task_affinity: List[str]  # keywords that indicate this expert is suited
    priority: int             # base priority (higher = preferred when scores tie)
    use_4bit: bool = False    # load with 4-bit quantization
    shared_model_key: Optional[str] = None  # if set, reuse model from this key


# Expert registry: all 5 roles, 3 model instances
EXPERT_REGISTRY: Dict[str, ExpertProfile] = {
    "coder": ExpertProfile(
        role=ExpertRole.CODER,
        model_name="Qwen/Qwen2.5-Coder-0.5B-Instruct",
        description="Code generation & implementation specialist.",
        system_prompt=(
            "You are an expert programmer. Write clean, correct, well-documented code. "
            "Consider edge cases, performance, and readability. "
            "Provide complete, working solutions."
        ),
        task_affinity=[
            "code", "write", "function", "bug", "fix", "implement", "build",
            "program", "script", "class", "method", "api", "refactor",
            "debug", "error", "compile", "test", "deploy",
        ],
        priority=3,
        use_4bit=False,
        shared_model_key=None,  # unique model
    ),
    "critic": ExpertProfile(
        role=ExpertRole.CRITIC,
        model_name="google/gemma-3-1b-it",
        description="Code reviewer. Finds bugs, security issues, edge cases.",
        system_prompt=(
            "You are a senior code reviewer. Find bugs, security issues, and edge cases. "
            "Be specific and actionable. Point out exactly what's wrong and how to fix it. "
            "Consider: correctness, security, performance, readability, error handling."
        ),
        task_affinity=[
            "review", "check", "audit", "find bugs", "critique", "validate",
            "verify", "inspect", "test", "quality", "security", "vulnerability",
        ],
        priority=3,
        use_4bit=True,
        shared_model_key="gemma-3-1b",  # shared
    ),
    "researcher": ExpertProfile(
        role=ExpertRole.RESEARCHER,
        model_name="google/gemma-3-1b-it",
        description="Research, context-gathering, knowledge synthesis.",
        system_prompt=(
            "You are a thorough researcher. Gather facts, analyze trade-offs, "
            "and provide evidence-based answers. Synthesize information from "
            "multiple angles. Be comprehensive and cite reasoning clearly."
        ),
        task_affinity=[
            "research", "compare", "analyze", "latest", "pros and cons",
            "explain", "summarize", "background", "history", "survey",
            "what is", "how does", "why", "difference between",
        ],
        priority=2,
        use_4bit=True,
        shared_model_key="gemma-3-1b",  # shared
    ),
    "diverse": ExpertProfile(
        role=ExpertRole.DIVERSE,
        model_name="google/gemma-3-1b-it",
        description="Alternative perspective. Challenges assumptions.",
        system_prompt=(
            "You are a creative thinker. Consider alternative approaches, "
            "unusual edge cases, and different perspectives. Challenge every "
            "assumption. Propose approaches nobody has considered. Think outside the box."
        ),
        task_affinity=[
            "brainstorm", "alternative", "creative", "explore", "different",
            "perspective", "innovation", "novel", "outside the box",
            "challenge", "rethink", "imagine",
        ],
        priority=1,
        use_4bit=True,
        shared_model_key="gemma-3-1b",  # shared
    ),
    "tools": ExpertProfile(
        role=ExpertRole.TOOLS,
        model_name="google/gemma-4-E2B-it",
        description="Tool use specialist. Executes web searches and commands.",
        system_prompt=(
            "You are a tool-use specialist. When you need to search the web, "
            "fetch a URL, run a command, or read a file, output a function call "
            "in JSON format. Available functions:\n"
            '- web_search: {{"function": "web_search", "query": "..."}}\n'
            '- web_fetch: {{"function": "web_fetch", "url": "..."}}\n'
            '- run_command: {{"function": "run_command", "command": "..."}}\n'
            '- read_file: {{"function": "read_file", "path": "..."}}\n'
            "Output ONLY the JSON object on a single line when making a call. "
            "After receiving tool results, incorporate them into your response."
        ),
        task_affinity=[
            "search", "fetch", "tool", "run", "execute", "web", "url",
            "command", "file", "read", "download", "look up", "find online",
        ],
        priority=2,
        use_4bit=True,
        shared_model_key=None,  # unique model
    ),
}

# Which experts share which model instance
SHARED_MODEL_GROUPS = {
    "gemma-3-1b": ["critic", "researcher", "diverse"],
}


# =============================================================================
# Model Wrapper -- loads and wraps a HuggingFace model for text generation
# =============================================================================

class ModelWrapper:
    """Wraps a HuggingFace causal LM for chat-template-based text generation.

    Handles:
    - 4-bit quantization (device_map="auto") vs FP16 (explicit .to(device))
    - Multi-modal model config resolution (Gemma 4 has text_config)
    - Chat template application
    - Device placement for tokenized inputs
    """

    def __init__(self, model_name: str, use_4bit: bool = False, device: str = "cuda"):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_name = model_name
        self.use_4bit = use_4bit
        self.device_str = device

        print(f"  [LOAD] {model_name}" + (" (4-bit)" if use_4bit else " (FP16)"))

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model
        if use_4bit:
            from transformers import BitsAndBytesConfig
            nf4_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=nf4_config,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
            ).eval()
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                torch_dtype=torch.float16,
                trust_remote_code=True,
            ).to(device).eval()

        # Resolve config (handle multi-modal models like Gemma 4)
        cfg = self.model.config
        if hasattr(cfg, 'text_config'):
            cfg = cfg.text_config

        if hasattr(cfg, 'hidden_size'):
            self.hidden_dim = cfg.hidden_size
        elif hasattr(cfg, 'n_embd'):
            self.hidden_dim = cfg.n_embd
        elif hasattr(cfg, 'd_model'):
            self.hidden_dim = cfg.d_model
        else:
            self.hidden_dim = None  # not critical for text-only generation

        self.dtype = next(self.model.parameters()).dtype

        # Estimate VRAM
        total_params = sum(p.numel() for p in self.model.parameters())
        bytes_per_param = 1 if use_4bit else self.dtype.itemsize
        self.vram_est_gb = total_params * bytes_per_param / (1024 ** 3)

        num_layers = getattr(cfg, 'num_hidden_layers',
                             getattr(cfg, 'n_layer', '?'))
        print(f"    dim={self.hidden_dim}, vram~{self.vram_est_gb:.2f}GB, "
              f"dtype={self.dtype}, layers={num_layers}")

    def _get_device(self) -> torch.device:
        """Get the device the model's parameters are on."""
        return next(self.model.parameters()).device

    def generate(self, messages: List[Dict[str, str]],
                 max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
                 temperature: float = DEFAULT_TEMPERATURE) -> str:
        """Generate text from chat messages using the model's chat template.

        Args:
            messages: List of {"role": "system"|"user"|"assistant", "content": str}
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text string
        """
        # Apply chat template
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt")

        # Move to correct device
        device = self._get_device()
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        # Decode only the new tokens (skip the prompt)
        prompt_len = inputs["input_ids"].shape[1]
        generated_ids = outputs[0, prompt_len:]
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        # Clean up
        del inputs, outputs
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return text.strip()


# =============================================================================
# Router -- keyword-based expert selection with diversity enforcement
# =============================================================================

class Router:
    """Selects which expert handles each round.

    Uses keyword-based affinity scoring with compounding diversity penalties.
    Each time an expert is selected, their score for future rounds is multiplied
    by a penalty factor (0.4x), compounding to force different experts to contribute.
    """

    # Base keyword -> expert score mapping
    KEYWORD_SCORES: Dict[str, Dict[str, float]] = {
        # Coder keywords
        "code": {"coder": 1.0},
        "write": {"coder": 0.8, "diverse": 0.2},
        "function": {"coder": 1.0},
        "bug": {"coder": 0.6, "critic": 0.5},
        "fix": {"coder": 0.9, "critic": 0.3},
        "implement": {"coder": 1.0},
        "build": {"coder": 0.9},
        "program": {"coder": 0.9},
        "script": {"coder": 0.8},
        "class": {"coder": 0.9},
        "method": {"coder": 0.8},
        "api": {"coder": 0.8},
        "refactor": {"coder": 0.7, "critic": 0.5},
        "debug": {"coder": 0.6, "critic": 0.6},
        "error": {"coder": 0.5, "critic": 0.6},
        "compile": {"coder": 0.7},
        "test": {"coder": 0.5, "critic": 0.5},
        "deploy": {"coder": 0.6},

        # Critic keywords
        "review": {"critic": 1.0},
        "check": {"critic": 0.7},
        "audit": {"critic": 1.0},
        "find bugs": {"critic": 1.0},
        "critique": {"critic": 1.0},
        "validate": {"critic": 0.8},
        "verify": {"critic": 0.7},
        "inspect": {"critic": 0.7},
        "quality": {"critic": 0.8},
        "security": {"critic": 0.8, "researcher": 0.4},
        "vulnerability": {"critic": 0.9, "researcher": 0.3},

        # Researcher keywords
        "research": {"researcher": 1.0},
        "compare": {"researcher": 0.9},
        "analyze": {"researcher": 0.8, "critic": 0.4},
        "latest": {"researcher": 0.9, "tools": 0.5},
        "pros and cons": {"researcher": 0.9, "diverse": 0.4},
        "explain": {"researcher": 0.8},
        "summarize": {"researcher": 0.8},
        "background": {"researcher": 0.7},
        "history": {"researcher": 0.7},
        "survey": {"researcher": 0.9},
        "what is": {"researcher": 0.7},
        "how does": {"researcher": 0.7},
        "why": {"researcher": 0.6, "diverse": 0.3},
        "difference between": {"researcher": 0.8},

        # Diverse keywords
        "brainstorm": {"diverse": 1.0},
        "alternative": {"diverse": 1.0},
        "creative": {"diverse": 1.0},
        "explore": {"diverse": 0.8},
        "different": {"diverse": 0.8},
        "perspective": {"diverse": 1.0},
        "innovation": {"diverse": 0.9},
        "novel": {"diverse": 0.9},
        "outside the box": {"diverse": 1.0},
        "challenge": {"diverse": 0.8, "critic": 0.5},
        "rethink": {"diverse": 0.9},
        "imagine": {"diverse": 0.9},

        # Tools keywords
        "search": {"tools": 0.9, "researcher": 0.4},
        "fetch": {"tools": 1.0},
        "tool": {"tools": 0.8},
        "run": {"tools": 0.7},
        "execute": {"tools": 0.8},
        "web": {"tools": 0.7, "researcher": 0.4},
        "url": {"tools": 0.8},
        "command": {"tools": 0.8},
        "file": {"tools": 0.6},
        "read": {"tools": 0.5},
        "download": {"tools": 0.8},
        "look up": {"tools": 0.8, "researcher": 0.5},
        "find online": {"tools": 0.9},
    }

    def __init__(self, diversity_penalty: float = 0.4):
        self.diversity_penalty = diversity_penalty
        self.selection_count: Dict[str, int] = {}  # times each expert was picked

    def score(self, problem: str, experts: List[str]) -> Dict[str, float]:
        """Score all available experts for the given problem.

        Returns dict of expert_name -> score (higher is better).
        Applies diversity penalty based on prior selections.
        """
        problem_lower = problem.lower()
        scores: Dict[str, float] = {e: 0.0 for e in experts}

        # 1. Keyword affinity scoring
        for keyword, expert_scores in self.KEYWORD_SCORES.items():
            if keyword in problem_lower:
                for expert, boost in expert_scores.items():
                    if expert in scores:
                        # Count occurrences to boost repeated keywords
                        count = problem_lower.count(keyword)
                        scores[expert] += boost * count

        # 2. If no keywords matched, give uniform base score
        if all(s < 0.01 for s in scores.values()):
            for e in experts:
                scores[e] = 0.5

        # 3. Apply diversity penalty (compounding)
        for expert, count in self.selection_count.items():
            if expert in scores and count > 0:
                penalty = self.diversity_penalty ** count
                scores[expert] *= penalty

        # 4. Small random jitter to break ties (deterministic based on problem hash)
        import hashlib
        seed = int(hashlib.md5(problem.encode()).hexdigest()[:8], 16)
        rng_state = seed + sum(self.selection_count.values()) * 7
        for e in scores:
            jitter = ((rng_state * 13 + hash(e) * 31) % 100) / 1000.0
            scores[e] += jitter

        return scores

    def select(self, problem: str, experts: List[str]) -> str:
        """Select the best expert for this round. Records the selection."""
        scores = self.score(problem, experts)
        best = max(scores, key=scores.get)
        self.selection_count[best] = self.selection_count.get(best, 0) + 1
        return best, scores

    def reset(self):
        """Reset selection history."""
        self.selection_count.clear()


# =============================================================================
# Tool Executor -- parses and executes function calls from tools expert
# =============================================================================

class ToolExecutor:
    """Parses JSON function calls and executes them.

    Supported functions:
    - web_search(query) -- DuckDuckGo text search
    - web_fetch(url) -- fetch webpage content
    - run_command(command) -- execute system command (restricted)
    - read_file(path) -- read file content
    """

    # Dangerous command patterns to block
    BLOCKED_COMMAND_PATTERNS = [
        r'rm\s+-rf', r'del\s+/[fsq]', r'format\s', r'mkfs',
        r'shutdown', r'reboot', r'chmod\s+777', r'>\s*/dev/',
        r'dd\s+if=', r'wget\s.*\|\s*sh', r'curl\s.*\|\s*bash',
    ]

    def __init__(self, augmenter: Optional[ContextAugmenter] = None):
        self.augmenter = augmenter or ContextAugmenter()

    def try_extract_and_execute(self, text: str) -> Tuple[bool, Optional[str]]:
        """Try to find and execute a JSON function call in the text.

        Returns (was_executed, result_text).
        """
        # Try to find a JSON function call
        call = self._extract_call(text)
        if call is None:
            return False, None

        func = call.get("function", "")
        result = self._execute(func, call)
        return True, result

    def _extract_call(self, text: str) -> Optional[Dict]:
        """Extract a JSON function call from text."""
        # Try multiple patterns: standalone JSON line, JSON in code block, inline JSON
        patterns = [
            r'^\s*(\{[^}]+\})\s*$',           # single-line JSON
            r'```(?:json)?\s*\n?(\{[^}]+\})\s*```',  # fenced JSON
            r'(\{"function"\s*:\s*"[^"]+"\s*,\s*"[^"]+"\s*:\s*"[^"]*"\})',  # inline
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
            if match:
                try:
                    obj = json.loads(match.group(1))
                    if "function" in obj:
                        return obj
                except json.JSONDecodeError:
                    continue
        return None

    def _execute(self, func: str, call: Dict) -> str:
        """Execute a function call and return the result."""
        try:
            if func == "web_search":
                query = call.get("query", "")
                if not query:
                    return "<!-- web_search: missing query -->"
                return self.augmenter._search(query)

            elif func == "web_fetch":
                url = call.get("url", "")
                if not url:
                    return "<!-- web_fetch: missing url -->"
                return self.augmenter.fetch_page(url)

            elif func == "run_command":
                command = call.get("command", "")
                if not command:
                    return "<!-- run_command: missing command -->"
                return self._run_command_safe(command)

            elif func == "read_file":
                path = call.get("path", "")
                if not path:
                    return "<!-- read_file: missing path -->"
                return self._read_file_safe(path)

            else:
                return f"<!-- Unknown function: {func} -->"

        except Exception as e:
            return f"<!-- Tool execution error ({func}): {e} -->"

    def _run_command_safe(self, command: str) -> str:
        """Execute a system command with safety checks."""
        # Check against blocked patterns
        for pattern in self.BLOCKED_COMMAND_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"<!-- BLOCKED command (matches dangerous pattern): {command} -->"

        # Restrict to safe commands
        allowed_prefixes = [
            'dir', 'ls', 'echo', 'type', 'cat', 'head', 'tail',
            'python', 'py', 'node', 'pip', 'npm', 'git',
            'find', 'grep', 'wc', 'sort', 'uniq',
        ]
        cmd_lower = command.strip().lower()
        if not any(cmd_lower.startswith(p) for p in allowed_prefixes):
            return f"<!-- BLOCKED command (not in allowed list): {command[:80]} -->"

        try:
            import subprocess
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=30, cwd=os.getcwd()
            )
            output = result.stdout[:2000] if result.stdout else ""
            if result.stderr:
                output += f"\n[stderr]: {result.stderr[:500]}"
            return f"## Command: {command}\n```\n{output}\n```\nReturn code: {result.returncode}"
        except subprocess.TimeoutExpired:
            return f"<!-- Command timed out: {command[:80]} -->"
        except Exception as e:
            return f"<!-- Command failed: {e} -->"

    def _read_file_safe(self, path: str) -> str:
        """Read a file with path traversal protection."""
        # Resolve and check path
        try:
            real_path = os.path.realpath(os.path.expanduser(path))
        except Exception:
            return f"<!-- Cannot resolve path: {path} -->"

        # Only allow reads within current workspace or common safe dirs
        allowed_roots = [
            os.path.realpath(os.getcwd()),
            os.path.realpath(os.path.expanduser("~/.cache")),
        ]
        if not any(real_path.startswith(root) for root in allowed_roots):
            return f"<!-- BLOCKED: path outside allowed directories: {path} -->"

        try:
            with open(real_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(5000)
            return f"## File: {path}\n```\n{content}\n```"
        except FileNotFoundError:
            return f"<!-- File not found: {path} -->"
        except Exception as e:
            return f"<!-- File read error: {e} -->"


# =============================================================================
# RecursiveMAS -- main orchestrator
# =============================================================================

class RecursiveMAS:
    """Text-based recursive multi-agent system.

    Loads specialized models, runs iterative refinement rounds with
    different experts, and synthesizes a final answer.

    Architecture:
        1. ContextAugmenter enriches the problem
        2. Router selects an expert for each round
        3. Expert generates text output (system prompt + full context)
        4. Output is appended to context for next round
        5. Final round: coder synthesizes everything
    """

    def __init__(self, vram_limit_gb: float = DEFAULT_VRAM_LIMIT_GB,
                 ram_limit_gb: float = DEFAULT_RAM_LIMIT_GB,
                 skip_tools: bool = False,
                 enable_web: bool = True):
        self.vram_limit_gb = vram_limit_gb
        self.ram_limit_gb = ram_limit_gb
        self.skip_tools = skip_tools
        self.enable_web = enable_web

        # Components
        self.monitor: Optional[ResourceMonitor] = None
        self.augmenter = ContextAugmenter(enable_search=enable_web)
        self.tool_executor = ToolExecutor(augmenter=self.augmenter)
        self.router = Router()

        # Model wrappers (shared instances)
        self.models: Dict[str, ModelWrapper] = {}
        # Expert name -> model key mapping
        self.expert_model_map: Dict[str, str] = {}

        # Experts available (depends on what loaded successfully)
        self.available_experts: List[str] = []

        # Context cascade: accumulates all round outputs
        self.context: str = ""

    # ------------------------------------------------------------------
    # Model Loading
    # ------------------------------------------------------------------

    def load_models(self) -> Dict[str, ModelWrapper]:
        """Load all models. Shared models are loaded once and reused.

        Returns dict of model_key -> ModelWrapper.
        """
        # Determine which models to load
        models_to_load: Dict[str, Tuple[str, bool]] = {}  # key -> (model_name, use_4bit)
        shared_keys_seen: set = set()

        for expert_name, profile in EXPERT_REGISTRY.items():
            if expert_name == "tools" and self.skip_tools:
                print(f"  [SKIP] tools expert (--skip-tools)")
                continue

            if profile.shared_model_key:
                sk = profile.shared_model_key
                if sk not in shared_keys_seen:
                    models_to_load[sk] = (profile.model_name, profile.use_4bit)
                    shared_keys_seen.add(sk)
                    self.expert_model_map[expert_name] = sk
                else:
                    # Already loaded, just map
                    self.expert_model_map[expert_name] = sk
            else:
                mk = f"__{expert_name}__"
                models_to_load[mk] = (profile.model_name, profile.use_4bit)
                self.expert_model_map[expert_name] = mk

        print(f"\n{'='*60}")
        print(f"Loading {len(models_to_load)} model(s) for "
              f"{len(self.expert_model_map)} expert(s)...")
        print(f"{'='*60}")

        for model_key, (model_name, use_4bit) in models_to_load.items():
            try:
                wrapper = ModelWrapper(model_name, use_4bit=use_4bit)
                self.models[model_key] = wrapper
            except Exception as e:
                print(f"  [FAIL] {model_key} ({model_name}): {e}")
                # Remove experts that depend on this model
                to_remove = [e for e, mk in self.expert_model_map.items()
                            if mk == model_key]
                for e in to_remove:
                    del self.expert_model_map[e]
                    print(f"    -> expert '{e}' unavailable")

        # Build available experts list
        self.available_experts = list(self.expert_model_map.keys())
        print(f"\nAvailable experts: {self.available_experts}")
        print(f"Models loaded: {list(self.models.keys())}")

        return self.models

    # ------------------------------------------------------------------
    # Expert Generation
    # ------------------------------------------------------------------

    def _build_messages(self, expert_name: str) -> List[Dict[str, str]]:
        """Build chat messages for an expert with system prompt and context."""
        profile = EXPERT_REGISTRY[expert_name]
        return [
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": self.context},
        ]

    def _generate_expert(self, expert_name: str,
                         max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
                         temperature: float = DEFAULT_TEMPERATURE) -> str:
        """Generate output from an expert given the current context."""
        model_key = self.expert_model_map[expert_name]
        model = self.models[model_key]
        messages = self._build_messages(expert_name)

        print(f"  -> Generating with {expert_name} ({model.model_name})...")
        t0 = time.time()
        output = model.generate(messages, max_new_tokens=max_new_tokens,
                                temperature=temperature)
        elapsed = time.time() - t0
        print(f"  <- {expert_name} generated {len(output)} chars in {elapsed:.1f}s")

        return output

    # ------------------------------------------------------------------
    # Tool Execution Loop (for tools expert)
    # ------------------------------------------------------------------

    def _run_tools_loop(self, max_tool_calls: int = 3) -> str:
        """Let the tools expert generate and execute tool calls iteratively.

        After each tool execution, the result is appended to context and
        the tools expert can make another call. Max `max_tool_calls` iterations.
        """
        expert_name = "tools"
        all_outputs = []

        for iteration in range(max_tool_calls):
            output = self._generate_expert(expert_name)
            all_outputs.append(output)

            # Try to extract and execute a tool call
            was_executed, result = self.tool_executor.try_extract_and_execute(output)

            if was_executed and result:
                print(f"  [TOOL] Executed call, result: {len(result)} chars")
                # Append result to context for next iteration
                self.context += f"\n\n[TOOL RESULT]:\n{result}"
            else:
                # No tool call found or execution failed -- done
                break

        return "\n\n".join(all_outputs)

    # ------------------------------------------------------------------
    # Main Solve Pipeline
    # ------------------------------------------------------------------

    def solve(self, problem: str, max_rounds: int = DEFAULT_MAX_ROUNDS,
              temperature: float = DEFAULT_TEMPERATURE,
              final_synthesis: bool = True) -> str:
        """Run the full recursive multi-agent pipeline.

        Args:
            problem: The problem statement / task description
            max_rounds: Number of expert rounds before final synthesis
            temperature: Sampling temperature for generation
            final_synthesis: Whether to run a final coder synthesis round

        Returns:
            Final synthesized solution as text
        """
        # Validate
        if not self.available_experts:
            raise RuntimeError(
                "No models loaded. Call load_models() before solve()."
            )

        print(f"\n{'='*60}")
        print(f"RecursiveMAS -- {len(self.available_experts)} experts, "
              f"{max_rounds} rounds")
        print(f"{'='*60}")

        # Reset router for fresh problem
        self.router.reset()

        # 1. Context augmentation
        print(f"\n[CONTEXT] Augmenting problem...")
        enriched = self.augmenter.enrich(problem)
        self.context = enriched
        print(f"  Augmented context: {len(enriched)} chars")

        # 2. Recursive rounds
        experts_used = []

        for round_num in range(1, max_rounds + 1):
            print(f"\n{'-'*40}")
            print(f"ROUND {round_num}/{max_rounds}")
            print(f"{'-'*40}")

            # Router selects expert
            selected, scores = self.router.select(problem, self.available_experts)
            experts_used.append(selected)

            # Display router scores as bar chart
            print(f"  Router scores:")
            max_score = max(scores.values()) if scores else 1.0
            for expert, score in sorted(scores.items(), key=lambda x: -x[1]):
                bar_len = int(40 * score / max_score) if max_score > 0 else 0
                bar = "#" * bar_len + "-" * (40 - bar_len)
                marker = " <- SELECTED" if expert == selected else ""
                penalty_str = ""
                count = self.router.selection_count.get(expert, 0)
                if count > 1:
                    penalty_str = f" (penalty: {0.4**count:.2f}x)"
                print(f"    {expert:12s} |{bar}| {score:.3f}{penalty_str}{marker}")

            # Show VRAM snapshot
            snapshot = self.monitor.snapshot() if self.monitor else {}
            if snapshot:
                print(f"  VRAM: {snapshot.get('vram_gb', 0):.1f}GB | "
                      f"RAM: {snapshot.get('ram_gb', 0):.1f}GB")

            # Generate with selected expert
            if selected == "tools":
                output = self._run_tools_loop()
            else:
                output = self._generate_expert(
                    selected, temperature=temperature
                )

            # Display output
            print(f"\n  +- {selected.upper()} OUTPUT "
                  f"({'-'*max(1, 46 - len(selected))})")
            # Truncate display if very long
            display = output[:800]
            if len(output) > 800:
                display += f"\n  ... ({len(output) - 800} more chars)"
            for line in display.split('\n'):
                print(f"  | {line}")
            print(f"  +{'-'*58}")

            # Append to cascading context
            self.context += f"\n\n## ROUND {round_num} ({selected.upper()}):\n{output}"

        # 3. Final synthesis
        print(f"\n{'-'*40}")
        print(f"FINAL SYNTHESIS")
        print(f"{'-'*40}")

        # Always use coder for final synthesis if available, else first available expert
        final_expert = "coder" if "coder" in self.available_experts else self.available_experts[0]

        # Build synthesis prompt
        self.context += (
            f"\n\n## FINAL TASK\n"
            f"Synthesize all the above analysis into a complete, "
            f"well-structured final answer. Combine the best insights "
            f"from each round into one coherent response. "
            f"Provide the final solution now."
        )

        final_output = self._generate_expert(
            final_expert,
            max_new_tokens=512,  # more tokens for final answer
            temperature=temperature,
        )

        print(f"\n{'='*60}")
        print(f"FINAL ANSWER")
        print(f"{'='*60}")
        print(final_output)
        print(f"{'='*60}")

        # Summary
        print(f"\nExperts consulted: {' -> '.join(experts_used)} -> {final_expert} (final)")
        if self.monitor:
            snapshot = self.monitor.snapshot()
            print(f"Peak VRAM: {snapshot.get('peak_vram_gb', 0):.1f}GB | "
                  f"Peak RAM: {snapshot.get('peak_ram_gb', 0):.1f}GB")

        return final_output

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startup(self):
        """Start resource monitor and load models."""
        print(f"RecursiveMAS v2 starting up...")
        print(f"VRAM limit: {self.vram_limit_gb}GB | RAM limit: {self.ram_limit_gb}GB")

        # Start resource monitor
        self.monitor = ResourceMonitor(
            vram_limit_gb=self.vram_limit_gb,
            ram_limit_gb=self.ram_limit_gb,
        )
        self.monitor.start()

        # Load models
        self.load_models()

        return self

    def shutdown(self):
        """Clean shutdown."""
        if self.monitor:
            self.monitor.stop()
        # Clear CUDA cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("RecursiveMAS shutdown complete.")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RecursiveMAS v2 -- Text-based recursive multi-agent collaboration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python recursive_mas_v2.py --problem "Write a Python function to merge two sorted lists"
  python recursive_mas_v2.py --problem "Review this code for bugs" --rounds 4
  python recursive_mas_v2.py --problem "Research the best database for my use case" --rounds 3
  python recursive_mas_v2.py --problem "Find the latest Python 3.13 features" --rounds 2
  python recursive_mas_v2.py --problem "Build a REST API endpoint" --vram-limit 8.0 --skip-tools
        """,
    )
    parser.add_argument(
        "--problem", "-p", type=str, required=True,
        help="Problem statement or task description"
    )
    parser.add_argument(
        "--rounds", "-r", type=int, default=DEFAULT_MAX_ROUNDS,
        help=f"Number of expert rounds (default: {DEFAULT_MAX_ROUNDS})"
    )
    parser.add_argument(
        "--vram-limit", type=float, default=DEFAULT_VRAM_LIMIT_GB,
        help=f"VRAM limit in GB (default: {DEFAULT_VRAM_LIMIT_GB})"
    )
    parser.add_argument(
        "--ram-limit", type=float, default=DEFAULT_RAM_LIMIT_GB,
        help=f"RAM limit in GB (default: {DEFAULT_RAM_LIMIT_GB})"
    )
    parser.add_argument(
        "--temperature", "-t", type=float, default=DEFAULT_TEMPERATURE,
        help=f"Sampling temperature (default: {DEFAULT_TEMPERATURE})"
    )
    parser.add_argument(
        "--skip-tools", action="store_true",
        help="Skip loading the Gemma-4-E2B tools model (saves ~7.3GB VRAM)"
    )
    parser.add_argument(
        "--no-web", action="store_true",
        help="Disable web search in context augmentation"
    )
    parser.add_argument(
        "--no-synthesis", action="store_true",
        help="Skip final synthesis round"
    )

    args = parser.parse_args()

    # Build and run RecursiveMAS
    mas = RecursiveMAS(
        vram_limit_gb=args.vram_limit,
        ram_limit_gb=args.ram_limit,
        skip_tools=args.skip_tools,
        enable_web=not args.no_web,
    )

    try:
        mas.startup()

        if not mas.available_experts:
            print("\n[FATAL] No experts available. Check model downloads.")
            sys.exit(1)

        result = mas.solve(
            problem=args.problem,
            max_rounds=args.rounds,
            temperature=args.temperature,
            final_synthesis=not args.no_synthesis,
        )

        print(f"\n[DONE] RecursiveMAS completed successfully.")

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Shutting down...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        mas.shutdown()


if __name__ == "__main__":
    main()
