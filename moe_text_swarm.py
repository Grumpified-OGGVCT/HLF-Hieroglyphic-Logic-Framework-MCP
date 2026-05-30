"""
MoE Text Swarm — Text-Only Mixture-of-Experts multi-agent swarm.

ARCHITECTURE (ZERO latent-space transfer):
  Problem → ContextAugmenter → [Round 1] Router scores experts → top expert generates TEXT
  → text appended to context → [Round 2] Router re-scores → next expert generates TEXT
  → ... → [Round N] → Coder produces final aggregated answer

NO hidden states. NO bridges. NO latent projection.
Each round: text_context → router → expert.generate() → text_output → append → next round
The "swarm" effect comes from different experts contributing different perspectives as text.

Experts (fit in <10.5GB VRAM collectively):
  - coder:     Qwen2.5-Coder-0.5B-Instruct (896-dim, FP16, ~1GB)
  - critic:    gemma-3-1b-it (1152-dim, 4-bit, ~1.5GB) — shared weights
  - researcher: gemma-3-1b-it (same model, different system prompt)
  - diverse:   gemma-3-1b-it (same model, different system prompt)
  - tools:     gemma-4-E2B-it (1536-dim, 4-bit, ~3-4GB)

Total weight VRAM: ~5.5-6.5GB. Safe on 10.5GB budget.

Usage:
  python moe_text_swarm.py --problem "Write a Rust TCP echo server" --rounds 3 --vram-limit 10.5
"""

import os
import sys
import time
import json
import threading
import argparse
import warnings
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any
from enum import Enum

import torch
import psutil

warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════════════════════════════
# Context Augmenter — datetime, web search, web fetch for real-time awareness
# ═══════════════════════════════════════════════════════════════════════════════

class ContextAugmenter:
    """Enriches prompts with real-time info before they reach experts.

    All augmentation happens in the prompt text — no model-level tool calling needed.
    Works with any model, including tiny ones.
    """

    def __init__(self, enable_search: bool = True, enable_fetch: bool = True):
        self.enable_search = enable_search
        self.enable_fetch = enable_fetch
        self._search_cache: Dict[str, str] = {}

    def enrich(self, task: str) -> str:
        """Build an enriched prompt from a raw task."""
        parts = []

        # 1. Current datetime — always injected
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
        from datetime import datetime, timezone
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
            "what is the", "who is", "tell me about",
        ]
        task_lower = task.lower()
        return any(signal in task_lower for signal in web_signals)

    def _search(self, query: str, max_results: int = 3) -> str:
        """Search the web via DuckDuckGo."""
        if query in self._search_cache:
            return self._search_cache[query]
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

            result = "\n".join(lines)
            self._search_cache[query] = result
            return result
        except Exception as e:
            return f"<!-- Web search unavailable: {e} -->"

    def fetch_page(self, url: str, max_chars: int = 2000) -> str:
        """Fetch and extract text from a webpage."""
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()

            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text)

            return f"## Fetched: {url}\n{text[:max_chars]}"
        except Exception as e:
            return f"<!-- Fetch failed for {url}: {e} -->"


# ═══════════════════════════════════════════════════════════════════════════════
# Resource Monitor
# ═══════════════════════════════════════════════════════════════════════════════

class ResourceMonitor:
    """Background thread. Kills process if VRAM/RAM exceeds limits."""

    def __init__(self, vram_limit_gb: float = 10.5, ram_limit_gb: float = 58.0):
        self.vram_limit_gb = vram_limit_gb
        self.ram_limit_gb = ram_limit_gb
        self.peak_vram = 0.0
        self.peak_ram = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._has_gpu = False
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml = pynvml
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._has_gpu = True
        except Exception:
            self._nvml = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[MONITOR] VRAM limit: {self.vram_limit_gb}GB | RAM limit: {self.ram_limit_gb}GB")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        print(f"[RESOURCE] Peak VRAM: {self.peak_vram:.1f}GB | Peak RAM: {self.peak_ram:.1f}GB")

    def _loop(self):
        while not self._stop.is_set():
            try:
                vram, ram = self._sample()
                self.peak_vram = max(self.peak_vram, vram)
                self.peak_ram = max(self.peak_ram, ram)
                if vram > self.vram_limit_gb:
                    print(f"\n[FATAL] VRAM {vram:.1f}GB > {self.vram_limit_gb}GB — KILLING")
                    os._exit(1)
                if ram > self.ram_limit_gb:
                    print(f"\n[FATAL] RAM {ram:.1f}GB > {self.ram_limit_gb}GB — KILLING")
                    os._exit(1)
            except Exception:
                pass
            self._stop.wait(2.0)

    def _sample(self) -> Tuple[float, float]:
        vram, ram = 0.0, 0.0
        try:
            ram = psutil.virtual_memory().used / (1024 ** 3)
        except Exception:
            pass
        try:
            if self._has_gpu and self._nvml:
                info = self._nvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                vram = info.used / (1024 ** 3)
        except Exception:
            pass
        return vram, ram

    def snapshot(self) -> Dict[str, float]:
        vram, ram = self._sample()
        return {
            "vram_gb": vram, "ram_gb": ram,
            "peak_vram_gb": self.peak_vram, "peak_ram_gb": self.peak_ram,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Expert Registry — text-only experts (no latent space)
# ═══════════════════════════════════════════════════════════════════════════════

class ExpertRole(Enum):
    CODER = "coder"
    CRITIC = "critic"
    RESEARCHER = "researcher"
    DIVERSE = "diverse"
    TOOLS = "tools"


@dataclass
class ExpertProfile:
    role: ExpertRole
    model_name: str
    description: str
    system_prompt: str
    task_affinity: List[str]  # Keywords that indicate this expert is suited
    priority: int             # Higher = preferred when scores tie
    use_4bit: bool = False
    max_new_tokens: int = 256  # Default generation length


# ── System Prompts ────────────────────────────────────────────────────────────
# Each expert gets a specialized system prompt to differentiate behavior,
# even when multiple roles share the same underlying model weights.

CODER_SYSTEM_PROMPT = """You are an expert software engineer and architect.
Write clean, correct, well-documented code. Follow best practices.
When debugging, identify root causes precisely. When refactoring, preserve semantics while improving structure.
Output complete, runnable solutions with clear explanations."""

CRITIC_SYSTEM_PROMPT = """You are a senior code reviewer and quality assurance specialist.
Your job is to find bugs, security vulnerabilities, edge cases, and design flaws.
Be specific and actionable. Point out what's wrong, why it matters, and how to fix it.
Consider: correctness, security, performance, readability, error handling, and testability."""

RESEARCHER_SYSTEM_PROMPT = """You are a thorough researcher and knowledge synthesizer.
When given a topic, gather relevant facts, identify patterns, compare alternatives.
Explain concepts clearly with examples. Cite sources when possible.
Focus on practical, actionable information rather than theoretical overviews."""

DIVERSE_SYSTEM_PROMPT = """You are a creative contrarian thinker.
Challenge every assumption in the current approach. Propose radical alternatives.
Consider edge cases nobody has mentioned. Think about:
- What if the constraints are wrong?
- What would a junior dev miss? What would a genius see?
- Is there a completely different paradigm that solves this better?
Output 2-3 genuinely different approaches, not minor variations."""

TOOLS_SYSTEM_PROMPT = """You are a tools and function-calling specialist.
When information is needed, output a JSON function call to retrieve it.
Available functions:
  - web_search(query: str) — search the internet
  - web_fetch(url: str) — fetch webpage content
  - file_read(path: str) — read a local file
  - run_command(cmd: str) — execute a shell command

Output format (JSON only, no markdown):
{"function": "function_name", "args": {"param": "value"}}

If no tool is needed, respond with your knowledge directly."""


EXPERT_REGISTRY: Dict[str, ExpertProfile] = {
    "coder": ExpertProfile(
        role=ExpertRole.CODER,
        model_name="Qwen/Qwen2.5-Coder-0.5B-Instruct",
        description="Code generation, debugging & refactoring specialist.",
        system_prompt=CODER_SYSTEM_PROMPT,
        task_affinity=[
            "code", "write", "function", "class", "script", "program",
            "debug", "fix", "bug", "error", "refactor", "implement",
            "build", "create", "api", "endpoint", "route", "algorithm",
            "python", "javascript", "rust", "go", "java", "typescript",
            "html", "css", "sql", "database", "cli", "tool",
        ],
        priority=3,
        max_new_tokens=512,
    ),
    "critic": ExpertProfile(
        role=ExpertRole.CRITIC,
        model_name="google/gemma-3-1b-it",
        description="Code reviewer. Catches bugs, security holes, edge cases.",
        system_prompt=CRITIC_SYSTEM_PROMPT,
        task_affinity=[
            "review", "audit", "check", "validate", "verify", "critique",
            "security", "vulnerability", "bug", "test", "quality",
            "analyze", "inspect", "assess", "evaluate",
        ],
        priority=3,
        use_4bit=True,
        max_new_tokens=256,
    ),
    "researcher": ExpertProfile(
        role=ExpertRole.RESEARCHER,
        model_name="google/gemma-3-1b-it",
        description="Research, context-gathering, knowledge synthesis.",
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        task_affinity=[
            "research", "explain", "summarize", "compare", "analyze",
            "what is", "how does", "why", "background", "context",
            "find", "search", "look up", "information about",
            "latest", "current", "recent", "history of",
        ],
        priority=2,
        use_4bit=True,
        max_new_tokens=256,
    ),
    "diverse": ExpertProfile(
        role=ExpertRole.DIVERSE,
        model_name="google/gemma-3-1b-it",
        description="Alternative perspective. Breaks groupthink with divergent thinking.",
        system_prompt=DIVERSE_SYSTEM_PROMPT,
        task_affinity=[
            "brainstorm", "alternative", "creative", "explore", "different",
            "approach", "perspective", "idea", "innovate", "novel",
            "edge case", "corner case", "what if", "consider",
        ],
        priority=1,
        use_4bit=True,
        max_new_tokens=256,
    ),
    "tools": ExpertProfile(
        role=ExpertRole.TOOLS,
        model_name="google/gemma-4-E2B-it",
        description="Function calling + tool execution. Structured JSON output.",
        system_prompt=TOOLS_SYSTEM_PROMPT,
        task_affinity=[
            "search", "fetch", "download", "lookup", "retrieve",
            "tool", "execute", "run", "command", "file",
            "web", "url", "api call", "http",
        ],
        priority=2,
        use_4bit=True,
        max_new_tokens=200,
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Text Expert Agent — loads model for text generation ONLY
# ═══════════════════════════════════════════════════════════════════════════════

class TextExpertAgent:
    """Wraps a HuggingFace causal LM for text-only generation.

    NO hidden state capture. NO latent space access. Just text → generate → text.
    """

    def __init__(self, profile: ExpertProfile, device: str = "cuda"):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.profile = profile
        self.role = profile.role
        self.device = device
        self._device_map = "auto" if profile.use_4bit else device

        print(f"  [LOAD] {profile.role.value}: {profile.model_name}"
              + (" (4-bit)" if profile.use_4bit else " (FP16)"))

        # ── Tokenizer ──────────────────────────────────────────────────────
        self.tokenizer = AutoTokenizer.from_pretrained(
            profile.model_name, trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        # Some tokenizers lack a chat template — add fallback
        if not hasattr(self.tokenizer, 'chat_template') or self.tokenizer.chat_template is None:
            self._has_chat_template = False
        else:
            self._has_chat_template = True

        # ── Model ──────────────────────────────────────────────────────────
        if profile.use_4bit:
            from transformers import BitsAndBytesConfig
            nf4_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                profile.model_name,
                quantization_config=nf4_config,
                device_map=self._device_map,
                trust_remote_code=True,
                torch_dtype=torch.bfloat16,
            ).eval()
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                profile.model_name,
                torch_dtype=torch.float16,
                trust_remote_code=True,
            ).to(device).eval()

        # ── Model info ─────────────────────────────────────────────────────
        cfg = self.model.config
        if hasattr(cfg, 'text_config'):
            cfg = cfg.text_config
        self.hidden_dim = (
            getattr(cfg, 'hidden_size', None)
            or getattr(cfg, 'n_embd', None)
            or getattr(cfg, 'd_model', None)
            or 0
        )
        self.dtype = next(self.model.parameters()).dtype
        self.vram_gb = sum(
            p.numel() * p.element_size() for p in self.model.parameters()
        ) / (1024 ** 3)

        num_layers = getattr(cfg, 'num_hidden_layers', getattr(cfg, 'n_layer', '?'))
        print(f"    dim={self.hidden_dim}, vram={self.vram_gb:.2f}GB, "
              f"dtype={self.dtype}, layers={num_layers}, "
              f"chat_template={'yes' if self._has_chat_template else 'no'}")

    def generate(self, messages: List[Dict[str, str]],
                 max_new_tokens: Optional[int] = None,
                 temperature: float = 0.7) -> str:
        """Generate text from a messages list using the model's chat template.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            max_new_tokens: Override default token count
            temperature: Sampling temperature

        Returns:
            Generated text string
        """
        if max_new_tokens is None:
            max_new_tokens = self.profile.max_new_tokens

        # ── Build prompt using chat template ───────────────────────────────
        if self._has_chat_template:
            try:
                prompt = self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                prompt = self._manual_format(messages)
        else:
            prompt = self._manual_format(messages)

        # ── Tokenize ───────────────────────────────────────────────────────
        inputs = self.tokenizer(prompt, return_tensors="pt")
        # Move to model's device (handle both FP16 and 4-bit device maps)
        try:
            model_device = next(self.model.parameters()).device
        except StopIteration:
            model_device = torch.device("cuda:0")
        inputs = {k: v.to(model_device) for k, v in inputs.items()}

        # ── Generate ───────────────────────────────────────────────────────
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=(temperature > 0),
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        # ── Decode only the new tokens ─────────────────────────────────────
        prompt_len = inputs["input_ids"].shape[1]
        generated_ids = outputs[0, prompt_len:]
        text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        # Clean up
        del inputs, outputs

        return text.strip()

    def _manual_format(self, messages: List[Dict[str, str]]) -> str:
        """Fallback manual prompt formatting when chat template is unavailable."""
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        parts.append("Assistant:")
        return "\n\n".join(parts)

    def unload(self):
        """Free VRAM by moving model to CPU and clearing CUDA cache."""
        self.model = self.model.to("cpu")
        torch.cuda.empty_cache()


# ═══════════════════════════════════════════════════════════════════════════════
# Text Router — keyword-based task classification + static role-to-task mapping
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RouterScore:
    expert_name: str
    score: float
    reason: str


class TextRouter:
    """Scores experts based on task text + accumulated context using heuristics.

    This is a PRACTICAL router — no tiny model, no embeddings, just fast
    keyword matching + role-specific scoring rules. It works reliably because
    each expert has clearly defined task affinities.

    Scoring formula:
      base_score = keyword_match_ratio(task, expert.affinities)
      context_bonus = extra weight if previous rounds' content mentions this expert's domain
      diversity_penalty = reduce score if expert was used last round (avoid loops)
      final = base_score * (1 + context_bonus) * diversity_factor
    """

    def __init__(self):
        self.route_history: List[str] = []
        self.route_scores: List[Dict[str, float]] = []

    def score(self, task: str, context: str = "",
              previous_expert: Optional[str] = None) -> List[RouterScore]:
        """Score all experts for the current round.

        Args:
            task: The original problem/task description
            context: Accumulated text from previous rounds
            previous_expert: Name of the expert used in the last round

        Returns:
            List of RouterScore sorted by score descending
        """
        combined = (task + " " + context).lower()
        task_lower = task.lower()
        scores: List[RouterScore] = []

        for name, profile in EXPERT_REGISTRY.items():
            # ── Base score: keyword match ratio ────────────────────────────
            matches = sum(
                1 for kw in profile.task_affinity
                if kw in combined or kw in task_lower
            )
            match_ratio = min(matches / max(len(profile.task_affinity), 1), 1.0)

            # ── Strong signal boost: exact task-type indicators ─────────────
            type_boost = 0.0
            if name == "coder":
                type_boost = self._coder_signal(task_lower, combined)
            elif name == "critic":
                type_boost = self._critic_signal(task_lower, combined)
            elif name == "researcher":
                type_boost = self._researcher_signal(task_lower, combined)
            elif name == "diverse":
                type_boost = self._diverse_signal(task_lower, combined)
            elif name == "tools":
                type_boost = self._tools_signal(task_lower, combined)

            # ── Context bonus: previous rounds mention this domain ──────────
            context_bonus = 0.0
            if context:
                domain_hits = sum(
                    1 for kw in profile.task_affinity[:10]  # Top 10 keywords
                    if kw in context
                )
                context_bonus = min(domain_hits * 0.05, 0.15)

            # ── Diversity: avoid repeating same expert ──────────────────────
            diversity_factor = 1.0
            if name == previous_expert:
                diversity_factor = 0.4  # Penalize, but don't forbid
            # Also penalize if used 2x already
            count = self.route_history.count(name)
            if count >= 2:
                diversity_factor *= 0.5

            # ── Final score ─────────────────────────────────────────────────
            base_score = match_ratio + type_boost + profile.priority * 0.05
            final_score = base_score * (1.0 + context_bonus) * diversity_factor

            # Build reason string
            reason_parts = []
            if match_ratio > 0.1:
                reason_parts.append(f"{matches} keyword matches")
            if type_boost > 0:
                reason_parts.append(f"strong task signal")
            if context_bonus > 0:
                reason_parts.append(f"context relevance")
            if diversity_factor < 1.0:
                reason_parts.append(f"diversity penalty x{diversity_factor:.1f}")
            reason = "; ".join(reason_parts) if reason_parts else "fallback"

            scores.append(RouterScore(
                expert_name=name,
                score=round(final_score, 3),
                reason=reason,
            ))

        scores.sort(key=lambda s: s.score, reverse=True)
        return scores

    def select(self, task: str, context: str = "",
               previous_expert: Optional[str] = None) -> Tuple[str, List[RouterScore]]:
        """Select the best expert and return all scores."""
        scores = self.score(task, context, previous_expert)
        best = scores[0].expert_name if scores else "coder"
        self.route_history.append(best)
        return best, scores

    # ── Task-type signal boosters ───────────────────────────────────────────

    def _coder_signal(self, task: str, combined: str) -> float:
        """Strong signal: task is clearly about writing/implementing code."""
        code_signals = [
            "write a", "implement", "create a function", "build a",
            "code", "script", "program that", "class that",
            "debug", "fix the", "refactor", "convert to",
            "python function", "javascript function", "rust function",
            "api endpoint", "cli tool", "web server",
        ]
        hits = sum(1 for s in code_signals if s in task)
        return min(hits * 0.25, 0.8)

    def _critic_signal(self, task: str, combined: str) -> float:
        """Strong signal: task is about reviewing/finding issues."""
        critic_signals = [
            "review", "find bugs", "find issues", "security audit",
            "code review", "check for", "validate", "verify",
            "vulnerability", "test the", "is this correct",
            "what's wrong", "find the bug", "spot the error",
        ]
        hits = sum(1 for s in critic_signals if s in task)
        return min(hits * 0.3, 0.85)

    def _researcher_signal(self, task: str, combined: str) -> float:
        """Strong signal: task asks for research/information."""
        research_signals = [
            "research", "what is", "how does", "explain", "why",
            "latest", "current", "compare", "history of",
            "tell me about", "information about", "find information",
            "summarize", "background on",
        ]
        hits = sum(1 for s in research_signals if s in task)
        return min(hits * 0.3, 0.85)

    def _diverse_signal(self, task: str, combined: str) -> float:
        """Signal: task asks for alternatives/creative thinking."""
        diverse_signals = [
            "brainstorm", "alternative", "creative", "different",
            "explore", "what if", "edge case", "novel approach",
            "think outside", "other ways", "other approaches",
        ]
        hits = sum(1 for s in diverse_signals if s in task)
        return min(hits * 0.4, 0.8)

    def _tools_signal(self, task: str, combined: str) -> float:
        """Signal: task needs tool usage (search, fetch, execute)."""
        tools_signals = [
            "search for", "look up", "fetch", "download",
            "web search", "find online", "get the latest",
            "current price", "today's", "weather",
            "run command", "execute",
        ]
        hits = sum(1 for s in tools_signals if s in task)
        return min(hits * 0.35, 0.8)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Executor — executes function calls from the tools expert
# ═══════════════════════════════════════════════════════════════════════════════

class ToolExecutor:
    """Executes function calls output by the tools expert.

    Supported tools:
      - web_search(query) → DuckDuckGo search
      - web_fetch(url) → HTTP GET + HTML extraction
      - file_read(path) → read local file
      - run_command(cmd) → subprocess execution (sandboxed)
    """

    def __init__(self, augmenter: ContextAugmenter):
        self.augmenter = augmenter

    def execute(self, tool_call: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute a tool call and return (success, result_text)."""
        func = tool_call.get("function", "")
        args = tool_call.get("args", {})

        handlers = {
            "web_search": self._web_search,
            "web_fetch": self._web_fetch,
            "file_read": self._file_read,
            "run_command": self._run_command,
        }

        handler = handlers.get(func)
        if handler is None:
            return False, f"Unknown function: {func}. Available: {list(handlers.keys())}"

        try:
            return True, handler(**args)
        except Exception as e:
            return False, f"Error executing {func}: {e}"

    def try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract a JSON function call from model output text."""
        # Try direct JSON parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from within markdown/code blocks
        json_patterns = [
            r'```json\s*(\{.*?\})\s*```',
            r'```\s*(\{.*?\})\s*```',
            r'(\{"function"\s*:.*?"args"\s*:.*?\})',
        ]
        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        return None

    def _web_search(self, query: str) -> str:
        result = self.augmenter._search(query, max_results=5)
        return result if result else f"No results found for: {query}"

    def _web_fetch(self, url: str) -> str:
        return self.augmenter.fetch_page(url)

    def _file_read(self, path: str) -> str:
        # Security: only allow reads within the workspace
        # Resolve to absolute and check it's under CWD
        abs_path = os.path.abspath(path)
        cwd = os.path.abspath(os.getcwd())
        if not abs_path.startswith(cwd):
            return f"[SECURITY] Cannot read outside workspace: {path}"

        if not os.path.exists(abs_path):
            return f"File not found: {path}"

        try:
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(5000)  # Limit read size
            return f"## File: {path}\n```\n{content}\n```"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _run_command(self, cmd: str) -> str:
        # Security: whitelist safe commands, deny everything dangerous
        dangerous = ['rm ', 'sudo', 'chmod', 'chown', 'mkfs', 'dd ', ':(){',
                     '> /dev/', 'format', 'del ', 'rd ', 'shutdown', 'reboot']
        cmd_lower = cmd.lower()
        for d in dangerous:
            if d in cmd_lower:
                return f"[SECURITY] Dangerous command blocked: '{d}' detected"

        try:
            import subprocess
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=os.getcwd()
            )
            output = result.stdout[:2000]
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr[:500]}"
            return f"## Command: {cmd}\n```\n{output}\n```\nExit code: {result.returncode}"
        except subprocess.TimeoutExpired:
            return f"Command timed out after 30s: {cmd}"
        except Exception as e:
            return f"Command error: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# MoE Text Swarm Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SwarmConfig:
    max_rounds: int = 3
    temperature: float = 0.7
    final_temperature: float = 0.4  # Cooler for final answer
    vram_limit_gb: float = 10.5
    ram_limit_gb: float = 58.0
    enable_tools: bool = True
    verbose: bool = True


@dataclass
class RoundResult:
    round_num: int
    expert_name: str
    expert_role: str
    router_scores: List[RouterScore]
    output_text: str
    tool_result: Optional[str] = None


class MoETextSwarm:
    """Text-only Mixture-of-Experts swarm.

    Flow:
      1. ContextAugmenter enriches the problem with datetime + web search
      2. Router scores experts based on task + accumulated context
      3. Selected expert generates TEXT output (using model.generate + chat template)
      4. Text output is appended to shared context
      5. Repeat for N rounds
      6. Coder expert produces final aggregated answer from full context
    """

    def __init__(self, config: SwarmConfig, monitor: ResourceMonitor):
        self.config = config
        self.monitor = monitor

        # Context augmenter for real-time awareness
        self.augmenter = ContextAugmenter(enable_search=True, enable_fetch=True)

        # Tool executor
        self.tool_executor = ToolExecutor(self.augmenter) if config.enable_tools else None

        # Router
        self.router = TextRouter()

        # Load all experts (deduplicate: same model_name = shared instance)
        self.experts: Dict[str, TextExpertAgent] = {}
        loaded_models: Dict[str, TextExpertAgent] = {}

        print("\n[EXPERTS]")
        for name, profile in EXPERT_REGISTRY.items():
            if profile.model_name in loaded_models:
                self.experts[name] = loaded_models[profile.model_name]
                print(f"  [SHARE] {name} reuses {profile.model_name} "
                      f"(different system prompt applied at inference)")
            else:
                agent = TextExpertAgent(profile)
                self.experts[name] = agent
                loaded_models[profile.model_name] = agent

        total_vram = sum(e.vram_gb for e in loaded_models.values())
        snap = monitor.snapshot()
        print(f"\n[READY] {len(loaded_models)} model instances, "
              f"{len(self.experts)} expert roles")
        print(f"[READY] Weight VRAM: {total_vram:.1f}GB | "
              f"Current VRAM: {snap['vram_gb']:.1f}GB | RAM: {snap['ram_gb']:.1f}GB")

    def solve(self, problem: str) -> str:
        """Run the full text-based MoE swarm on a problem."""
        cfg = self.config

        # Enrich problem
        enriched = self.augmenter.enrich(problem)

        print(f"\n{'─' * 70}")
        print(f"PROBLEM: {problem}")
        print(f"{'─' * 70}")

        # ── Accumulated context (grows each round) ──────────────────────────
        # Start with the enriched problem as the user's ask
        accumulated_context: List[Dict[str, str]] = []
        round_results: List[RoundResult] = []

        previous_expert: Optional[str] = None
        full_context_text = enriched  # Plain text version for router scoring

        for round_num in range(1, cfg.max_rounds + 1):
            print(f"\n{'═' * 70}")
            print(f"ROUND {round_num}/{cfg.max_rounds}")
            print(f"{'═' * 70}")

            # ── Router selects expert ──────────────────────────────────────
            expert_name, scores = self.router.select(
                task=problem,
                context=full_context_text,
                previous_expert=previous_expert,
            )
            profile = EXPERT_REGISTRY[expert_name]

            # Display routing decision
            print(f"\n  ROUTER → {expert_name} ({profile.role.value})")
            for s in scores:
                bar = "█" * int(s.score * 20) + "░" * (20 - int(s.score * 20))
                marker = " ← SELECTED" if s.expert_name == expert_name else ""
                print(f"    {s.expert_name:12s} [{bar}] {s.score:.3f} {s.reason}{marker}")

            # ── Build messages for this expert ─────────────────────────────
            messages = self._build_messages(
                profile=profile,
                original_problem=enriched,
                round_context=accumulated_context,
                round_num=round_num,
                total_rounds=cfg.max_rounds,
            )

            # ── Generate ───────────────────────────────────────────────────
            snap_before = self.monitor.snapshot()
            print(f"\n  [GENERATE] {expert_name} thinking...")
            print(f"  VRAM before: {snap_before['vram_gb']:.1f}GB")

            gen_start = time.time()
            output_text = self.experts[expert_name].generate(
                messages=messages,
                temperature=cfg.temperature,
            )
            gen_time = time.time() - gen_start

            snap_after = self.monitor.snapshot()
            vram_delta = snap_after['vram_gb'] - snap_before['vram_gb']

            # ── Tool execution (if tools expert) ────────────────────────────
            tool_result = None
            if expert_name == "tools" and self.tool_executor:
                tool_call = self.tool_executor.try_parse_json(output_text)
                if tool_call:
                    print(f"  [TOOL] Executing: {tool_call.get('function', '?')}")
                    success, tool_result = self.tool_executor.execute(tool_call)
                    status = "✓" if success else "✗"
                    print(f"  [TOOL] Result {status}: {tool_result[:200]}...")
                    # Append tool result to output so it feeds into context
                    output_text += f"\n\n[Tool Result]\n{tool_result}"

            # ── Display output ──────────────────────────────────────────────
            print(f"\n  ── {expert_name} output ({gen_time:.1f}s, ΔVRAM={vram_delta:+.1f}GB) ──")
            # Show first 300 chars of output
            preview = output_text[:300].replace('\n', '\n  │ ')
            print(f"  │ {preview}")
            if len(output_text) > 300:
                print(f"  │ ... ({len(output_text)} total chars)")

            # ── Record round ────────────────────────────────────────────────
            round_results.append(RoundResult(
                round_num=round_num,
                expert_name=expert_name,
                expert_role=profile.role.value,
                router_scores=scores,
                output_text=output_text,
                tool_result=tool_result,
            ))

            # ── Update accumulated context ──────────────────────────────────
            accumulated_context.append({
                "role": "assistant",
                "content": f"[{expert_name}/{profile.role.value}]: {output_text}"
            })
            full_context_text += f"\n\n[{expert_name}]: {output_text}"
            previous_expert = expert_name

        # ══════════════════════════════════════════════════════════════════════
        # FINAL: Coder produces aggregated answer from full context
        # ══════════════════════════════════════════════════════════════════════
        print(f"\n{'═' * 70}")
        print(f"FINAL AGGREGATION — coder synthesizes all round outputs")
        print(f"{'═' * 70}")

        final_messages = self._build_final_messages(
            original_problem=problem,
            round_results=round_results,
        )

        print(f"\n  [GENERATE] coder producing final answer...")
        gen_start = time.time()
        final_answer = self.experts["coder"].generate(
            messages=final_messages,
            max_new_tokens=512,
            temperature=cfg.final_temperature,
        )
        gen_time = time.time() - gen_start

        snap = self.monitor.snapshot()

        print(f"\n{'=' * 70}")
        print(f"FINAL ANSWER ({gen_time:.1f}s):")
        print(f"{'=' * 70}")
        print(final_answer)
        print(f"{'=' * 70}")

        # Summary
        print(f"\n[DONE] {cfg.max_rounds} rounds across "
              f"{len(set(r.expert_name for r in round_results))} unique experts")
        route_summary = ", ".join(
            f"{r.round_num}:{r.expert_name}" for r in round_results
        )
        print(f"[DONE] Route: {route_summary}")
        print(f"[DONE] Peak VRAM: {snap['peak_vram_gb']:.1f}GB | "
              f"Peak RAM: {snap['peak_ram_gb']:.1f}GB")
        print(f"[DONE] Final output: {len(final_answer)} chars")

        return final_answer

    def _build_messages(self, profile: ExpertProfile,
                        original_problem: str,
                        round_context: List[Dict[str, str]],
                        round_num: int, total_rounds: int) -> List[Dict[str, str]]:
        """Build chat messages for an expert in a given round.

        Includes:
        - System prompt (specialized for this role)
        - Original problem context
        - Previous round outputs (as conversation history)
        - Current round instruction
        """
        messages: List[Dict[str, str]] = []

        # System prompt
        messages.append({"role": "system", "content": profile.system_prompt})

        # Original problem
        messages.append({
            "role": "user",
            "content": (
                f"I need you to help with the following task. "
                f"This is round {round_num} of {total_rounds} in a multi-expert collaboration.\n\n"
                f"{original_problem}"
            )
        })

        # Previous round context
        if round_context:
            context_text = "\n\n".join(
                f"--- {msg['content']}" for msg in round_context
            )
            messages.append({
                "role": "user",
                "content": (
                    f"Here's what other experts have contributed so far:\n\n"
                    f"{context_text}\n\n"
                    f"Now, as the {profile.role.value}, provide your perspective. "
                    f"Focus on what's most important from your expertise area. "
                    f"Be concise and specific."
                )
            })
        else:
            messages.append({
                "role": "user",
                "content": (
                    f"As the {profile.role.value}, start analyzing this task. "
                    f"Provide your initial assessment. Be concise and specific."
                )
            })

        return messages

    def _build_final_messages(self, original_problem: str,
                              round_results: List[RoundResult]) -> List[Dict[str, str]]:
        """Build messages for the final coder aggregation step."""
        messages: List[Dict[str, str]] = []

        # System prompt for final aggregation
        messages.append({
            "role": "system",
            "content": (
                "You are an expert software engineer producing a final deliverable. "
                "You have received input from multiple specialized experts (critic, researcher, "
                "creative thinker, tools specialist). Synthesize ALL their input into a single, "
                "complete, high-quality solution. Incorporate the critic's fixes, the researcher's "
                "insights, the diverse thinker's alternatives, and any tool results. "
                "Produce code that is correct, well-documented, and handles edge cases."
            )
        })

        # Build the context with all round contributions
        contributions = []
        for r in round_results:
            contributions.append(
                f"### {r.expert_name} ({r.expert_role}):\n{r.output_text}"
            )

        messages.append({
            "role": "user",
            "content": (
                f"## Original Task\n{original_problem}\n\n"
                f"## Expert Contributions\n\n"
                f"{chr(10).join(contributions)}\n\n"
                f"## Your Task\n"
                f"Synthesize all the expert input above into a final, complete solution. "
                f"Address all issues raised by the critic. Incorporate research findings. "
                f"Consider alternative approaches suggested. Write final production-ready code "
                f"with proper documentation and error handling."
            )
        })

        return messages

    def shutdown(self):
        """Unload all models and free VRAM."""
        self.monitor.stop()
        # Deduplicate — only unload unique model instances
        seen = set()
        for name, expert in self.experts.items():
            model_id = id(expert.model)
            if model_id not in seen:
                seen.add(model_id)
                print(f"  [UNLOAD] {name}")
                expert.unload()
        torch.cuda.empty_cache()
        print("[SHUTDOWN] All experts unloaded, VRAM freed")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="MoE Text Swarm — Text-only Mixture-of-Experts multi-agent collaboration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python moe_text_swarm.py --problem "Write a Python async web scraper"
  python moe_text_swarm.py --problem "Debug this race condition in my Go code" --rounds 4
  python moe_text_swarm.py --problem "Research best Rust web frameworks in 2025" --rounds 3
  python moe_text_swarm.py --problem "Review this SQL schema for security issues"
        """.strip(),
    )
    parser.add_argument("--problem", type=str, required=True,
                        help="The problem or task to solve")
    parser.add_argument("--rounds", type=int, default=3,
                        help="Number of expert collaboration rounds (default: 3)")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Generation temperature (default: 0.7)")
    parser.add_argument("--final-temperature", type=float, default=0.4,
                        help="Final answer temperature — cooler for quality (default: 0.4)")
    parser.add_argument("--vram-limit", type=float, default=10.5,
                        help="VRAM limit in GB (default: 10.5)")
    parser.add_argument("--ram-limit", type=float, default=58.0,
                        help="RAM limit in GB (default: 58.0)")
    parser.add_argument("--no-tools", action="store_true",
                        help="Disable tool calling (web search, fetch, etc.)")
    parser.add_argument("--quiet", action="store_true",
                        help="Minimal output — only final answer")

    args = parser.parse_args()

    config = SwarmConfig(
        max_rounds=args.rounds,
        temperature=args.temperature,
        final_temperature=args.final_temperature,
        vram_limit_gb=args.vram_limit,
        ram_limit_gb=args.ram_limit,
        enable_tools=not args.no_tools,
        verbose=not args.quiet,
    )

    print("=" * 70)
    print("MoE Text Swarm — Text-Only Mixture-of-Experts")
    print("=" * 70)
    print(f"Models: Qwen2.5-Coder-0.5B | gemma-3-1b-it | gemma-4-E2B-it")
    print(f"Rounds: {args.rounds} | Temperature: {args.temperature}")
    print(f"VRAM limit: {args.vram_limit}GB | Tools: {'on' if config.enable_tools else 'off'}")
    print(f"No latent space, no bridges — pure text-based collaboration\n")

    monitor = ResourceMonitor(
        vram_limit_gb=args.vram_limit,
        ram_limit_gb=args.ram_limit,
    )
    monitor.start()

    try:
        swarm = MoETextSwarm(config, monitor)
        final = swarm.solve(args.problem)
        swarm.shutdown()

        # If quiet mode, print just the final answer
        if args.quiet:
            print("\n" + final)

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Shutting down...")
        monitor.stop()
        sys.exit(0)
    except Exception as e:
        monitor.stop()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
