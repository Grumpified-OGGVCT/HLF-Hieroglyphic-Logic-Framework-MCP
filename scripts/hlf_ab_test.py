#!/usr/bin/env python3
"""
hlf_ab_test.py — CLI wrapper for Commit 8b: A/B Backend Framework.

Real Ollama backends only. No dummies. No mocks.

Usage:
    uv run python scripts/hlf_ab_test.py define --name medical_dx_v1 --domain medical --backends medgemma:4b,llama3.2:latest
    uv run python scripts/hlf_ab_test.py run --test-name medical_dx_v1 --prompts 20
    uv run python scripts/hlf_ab_test.py show --test-name medical_dx_v1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

# ── Path setup ──────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from hlf_mcp.hlf.backend_benchmark import (  # noqa: E402
    BackendBenchmark,
    BackendComparison,
    BenchmarkPrompt,
    BenchmarkRun,
    compare_backends,
    score_response,
)

# ── Constants ───────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_TIMEOUT = 120  # seconds
CONFIG_DIR = Path.home() / ".hlf" / "ab_tests"

# ═══════════════════════════════════════════════════════════════════════════════════
# Built-in Prompt Corpora
# ═══════════════════════════════════════════════════════════════════════════════════

MEDICAL_PROMPTS: list[dict[str, Any]] = [
    {
        "prompt_id": "med_01",
        "text": "A 45-year-old patient presents with sudden chest pain radiating to the left arm, shortness of breath, and diaphoresis. What is the most likely diagnosis and initial treatment?",
        "reference_answer": "The most likely diagnosis is acute myocardial infarction (heart attack). Initial treatment includes aspirin, nitroglycerin, oxygen if saturation is low, morphine for pain, and immediate transport to a cardiac care facility for possible PCI or thrombolysis.",
        "reference_keywords": ["diagnosis", "myocardial infarction", "treatment", "aspirin", "nitroglycerin", "PCI"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "med_02",
        "text": "A patient is taking warfarin for atrial fibrillation. What dietary considerations and drug interactions should be monitored?",
        "reference_answer": "Patients on warfarin must maintain consistent vitamin K intake (green leafy vegetables), avoid cranberry juice in excess, and monitor interactions with antibiotics, NSAIDs, and antiplatelet drugs. Regular INR monitoring is essential.",
        "reference_keywords": ["warfarin", "vitamin K", "INR", "interaction", "monitor", "treatment"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "med_03",
        "text": "A 7-year-old child presents with fever, sore throat, and a sandpaper-like rash that started on the chest and spread. What is the diagnosis and treatment?",
        "reference_answer": "The diagnosis is scarlet fever caused by Group A Streptococcus. Treatment is a 10-day course of penicillin or amoxicillin. Symptomatic treatment includes acetaminophen for fever and adequate hydration.",
        "reference_keywords": ["scarlet fever", "diagnosis", "symptom", "penicillin", "treatment", "streptococcus"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "med_04",
        "text": "What are the classic symptoms of major depressive disorder according to DSM-5 criteria, and what first-line treatment options exist?",
        "reference_answer": "Classic symptoms include depressed mood, anhedonia, significant weight change, insomnia or hypersomnia, fatigue, feelings of worthlessness, diminished concentration, and recurrent thoughts of death. First-line treatment includes SSRIs like fluoxetine, sertraline, or escitalopram, combined with cognitive behavioral therapy.",
        "reference_keywords": ["depressive", "symptom", "anhedonia", "treatment", "SSRI", "diagnosis"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "med_05",
        "text": "A diabetic patient on metformin presents with abdominal pain, nausea, and confusion. Blood gas shows metabolic acidosis with increased anion gap. What is the likely diagnosis and emergency treatment?",
        "reference_answer": "The likely diagnosis is metformin-associated lactic acidosis (MALA). Emergency treatment includes discontinuing metformin, aggressive IV fluid resuscitation, bicarbonate for severe acidosis, and hemodialysis in refractory cases.",
        "reference_keywords": ["diagnosis", "lactic acidosis", "metformin", "treatment", "hemodialysis", "symptom"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "med_06",
        "text": "A patient develops fever, cough, and bilateral interstitial infiltrates 3 days after starting amiodarone. What pulmonary condition should be suspected and how is it managed?",
        "reference_answer": "Amiodarone-induced pulmonary toxicity should be suspected. Management includes discontinuing amiodarone immediately, corticosteroid therapy (prednisone), and supportive respiratory care. Serial pulmonary function tests and imaging are used to monitor recovery.",
        "reference_keywords": ["amiodarone", "pulmonary toxicity", "diagnosis", "treatment", "corticosteroid", "symptom"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "med_07",
        "text": "What are the clinical features of serotonin syndrome and how does it differ from neuroleptic malignant syndrome?",
        "reference_answer": "Serotonin syndrome features hyperthermia, clonus, hyperreflexia, myoclonus, agitation, and diaphoresis. NMS features lead-pipe rigidity, bradyreflexia, and is associated with dopamine antagonists. Treatment for serotonin syndrome includes cyproheptadine and supportive care.",
        "reference_keywords": ["serotonin", "symptom", "clonus", "treatment", "cyproheptadine", "diagnosis"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "med_08",
        "text": "A patient with chronic hepatitis B is started on rituximab. What risk does this combination present and how should it be managed prophylactically?",
        "reference_answer": "Rituximab can cause hepatitis B reactivation leading to fulminant hepatitis. Prophylaxis with entecavir or tenofovir should be started before rituximab and continued for at least 12 months after completion. HBV DNA and LFTs should be monitored regularly.",
        "reference_keywords": ["hepatitis", "rituximab", "reactivation", "prophylaxis", "treatment", "entecavir"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "med_09",
        "text": "An elderly patient on multiple medications presents with confusion, urinary retention, dry mouth, and blurred vision. What class of drug toxicity is most likely responsible?",
        "reference_answer": "Anticholinergic toxicity is most likely. Classic symptoms follow the mnemonic 'hot as a hare, blind as a bat, dry as a bone, red as a beet, mad as a hatter.' Treatment is supportive; physostigmine may be used in severe cases under specialist guidance.",
        "reference_keywords": ["anticholinergic", "symptom", "diagnosis", "treatment", "physostigmine", "toxicity"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "med_10",
        "text": "What is the standard treatment protocol for community-acquired pneumonia in a previously healthy adult, including antibiotic choice and duration?",
        "reference_answer": "Standard treatment for CAP in healthy adults includes a macrolide (azithromycin) or doxycycline for 5-7 days. For patients with comorbidities, a respiratory fluoroquinolone or beta-lactam plus macrolide combination is recommended. Treatment includes supportive care with hydration and antipyretics.",
        "reference_keywords": ["pneumonia", "treatment", "antibiotic", "azithromycin", "macrolide", "diagnosis"],
        "difficulty": "medium",
    },
]

CODE_PROMPTS: list[dict[str, Any]] = [
    {
        "prompt_id": "code_01",
        "text": "Write a Python function that takes a list of integers and returns a new list with only the even numbers, sorted in descending order.",
        "reference_answer": "def filter_even_descending(numbers): return sorted([n for n in numbers if n % 2 == 0], reverse=True)",
        "reference_keywords": ["def", "return", "function", "sorted", "filter"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "code_02",
        "text": "Write a Python function that implements binary search on a sorted list and returns the index of the target element, or -1 if not found.",
        "reference_answer": "def binary_search(arr, target): left, right = 0, len(arr)-1; while left <= right: mid = (left+right)//2; if arr[mid] == target: return mid; elif arr[mid] < target: left = mid+1; else: right = mid-1; return -1",
        "reference_keywords": ["def", "return", "function", "binary", "search"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "code_03",
        "text": "Write a Python function that checks if a given string is a valid palindrome, ignoring spaces, punctuation, and case.",
        "reference_answer": "def is_palindrome(s): cleaned = ''.join(c.lower() for c in s if c.isalnum()); return cleaned == cleaned[::-1]",
        "reference_keywords": ["def", "return", "function", "palindrome"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "code_04",
        "text": "Write a Python function that performs a depth-first search traversal on a graph represented as an adjacency list.",
        "reference_answer": "def dfs(graph, start, visited=None): if visited is None: visited = set(); visited.add(start); for neighbor in graph[start]: if neighbor not in visited: dfs(graph, neighbor, visited); return visited",
        "reference_keywords": ["def", "return", "function", "dfs", "visited", "graph"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "code_05",
        "text": "Write a Python function that merges two sorted lists into a single sorted list without using built-in sort.",
        "reference_answer": "def merge_sorted(a, b): result = []; i = j = 0; while i < len(a) and j < len(b): if a[i] < b[j]: result.append(a[i]); i += 1; else: result.append(b[j]); j += 1; result.extend(a[i:]); result.extend(b[j:]); return result",
        "reference_keywords": ["def", "return", "function", "merge", "sorted"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "code_06",
        "text": "Write a Python function that implements the Fibonacci sequence using dynamic programming with memoization.",
        "reference_answer": "def fib(n, memo=None): if memo is None: memo = {}; if n in memo: return memo[n]; if n <= 1: return n; memo[n] = fib(n-1, memo) + fib(n-2, memo); return memo[n]",
        "reference_keywords": ["def", "return", "function", "fibonacci", "memo"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "code_07",
        "text": "Write a Python function that finds the longest common subsequence between two strings using dynamic programming.",
        "reference_answer": "def lcs(s1, s2): m, n = len(s1), len(s2); dp = [[0]*(n+1) for _ in range(m+1)]; for i in range(1,m+1): for j in range(1,n+1): if s1[i-1] == s2[j-1]: dp[i][j] = dp[i-1][j-1]+1; else: dp[i][j] = max(dp[i-1][j], dp[i][j-1]); return dp[m][n]",
        "reference_keywords": ["def", "return", "function", "subsequence", "dynamic"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "code_08",
        "text": "Write a Python function decorator that measures and prints the execution time of the decorated function.",
        "reference_answer": "import time; def timer(func): def wrapper(*args, **kwargs): start = time.time(); result = func(*args, **kwargs); print(f'{func.__name__} took {time.time()-start:.4f}s'); return result; return wrapper",
        "reference_keywords": ["def", "return", "function", "decorator", "time"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "code_09",
        "text": "Write a Python function that validates whether a given binary tree is a valid binary search tree (BST).",
        "reference_answer": "def is_valid_bst(root, min_val=float('-inf'), max_val=float('inf')): if root is None: return True; if root.val <= min_val or root.val >= max_val: return False; return is_valid_bst(root.left, min_val, root.val) and is_valid_bst(root.right, root.val, max_val)",
        "reference_keywords": ["def", "return", "function", "bst", "binary", "valid"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "code_10",
        "text": "Write a Python function that implements a simple LRU (Least Recently Used) cache using collections.OrderedDict.",
        "reference_answer": "from collections import OrderedDict; class LRUCache: def __init__(self, capacity): self.cache = OrderedDict(); self.capacity = capacity; def get(self, key): if key not in self.cache: return -1; self.cache.move_to_end(key); return self.cache[key]; def put(self, key, value): self.cache[key] = value; self.cache.move_to_end(key); if len(self.cache) > self.capacity: self.cache.popitem(last=False)",
        "reference_keywords": ["def", "return", "function", "LRU", "cache", "OrderedDict"],
        "difficulty": "medium",
    },
]

MATH_PROMPTS: list[dict[str, Any]] = [
    {
        "prompt_id": "math_01",
        "text": "A train travels 240 km in 3 hours. What is its average speed in km/h? Show your solution.",
        "reference_answer": "Speed = Distance / Time = 240 km / 3 h = 80 km/h. The result is 80 km/h.",
        "reference_keywords": ["solution", "result", "compute", "80"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "math_02",
        "text": "If x^2 + 6x + 9 = 0, solve for x and show all steps of the solution.",
        "reference_answer": "x^2 + 6x + 9 = 0 factors as (x+3)^2 = 0, so x = -3. The result is x = -3.",
        "reference_keywords": ["solution", "result", "compute", "-3"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "math_03",
        "text": "A rectangle has a perimeter of 50 cm and an area of 150 cm^2. Find its length and width. Show your complete solution.",
        "reference_answer": "Let l and w be length and width. 2l + 2w = 50 → l + w = 25, and lw = 150. Solving: w = 25 - l, l(25-l) = 150, l^2 - 25l + 150 = 0, l = 15 or l = 10. So dimensions are 15 × 10, result is length=15, width=10.",
        "reference_keywords": ["solution", "result", "compute", "15", "10"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "math_04",
        "text": "Compute the derivative of f(x) = 3x^4 - 2x^3 + x^2 - 5x + 7 with respect to x.",
        "reference_answer": "f'(x) = 12x^3 - 6x^2 + 2x - 5. The result is obtained by applying the power rule to each term.",
        "reference_keywords": ["solution", "result", "compute", "derivative", "12x^3"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "math_05",
        "text": "In a lottery where you choose 6 numbers from 49, what is the probability of matching exactly 4 numbers? Show the computation.",
        "reference_answer": "C(6,4) * C(43,2) / C(49,6) = 15 * 903 / 13,983,816 = 13,545 / 13,983,816 ≈ 0.0009686. The result is approximately 0.097%.",
        "reference_keywords": ["solution", "result", "compute", "probability"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "math_06",
        "text": "A car depreciates in value by 15% per year. If it costs $30,000 new, what is its value after 5 years? Round to the nearest dollar.",
        "reference_answer": "Value = 30000 * (1 - 0.15)^5 = 30000 * (0.85)^5 = 30000 * 0.4437 = 13,311. The result is approximately $13,311.",
        "reference_keywords": ["solution", "result", "compute", "depreciation"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "math_07",
        "text": "Find the area between the curve y = x^2 and y = 2x + 3 for the region where they intersect. Show all steps.",
        "reference_answer": "Intersection: x^2 = 2x + 3 → x^2 - 2x - 3 = 0 → (x-3)(x+1) = 0 → x = -1, x = 3. Area = ∫[-1 to 3] (2x+3 - x^2) dx = [x^2 + 3x - x^3/3]|-1 to 3 = (9+9-9) - (1-3+1/3) = 9 - (-5/3) = 32/3. The result is 32/3.",
        "reference_keywords": ["solution", "result", "compute", "integral"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "math_08",
        "text": "A population of bacteria doubles every 3 hours. If you start with 500 bacteria, how many will there be after 24 hours? Show the solution.",
        "reference_answer": "Number of doublings = 24 / 3 = 8. Final population = 500 * 2^8 = 500 * 256 = 128,000. The result is 128,000 bacteria.",
        "reference_keywords": ["solution", "result", "compute", "exponential"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "math_09",
        "text": "Compute the eigenvalues of the 2x2 matrix [[3, 1], [2, 4]] and show your work.",
        "reference_answer": "Characteristic equation: det([[3-λ, 1], [2, 4-λ]]) = (3-λ)(4-λ) - 2 = λ^2 - 7λ + 10 = 0. Factoring: (λ-2)(λ-5) = 0. The eigenvalues are λ = 2 and λ = 5. Result: eigenvalues are 2 and 5.",
        "reference_keywords": ["solution", "result", "compute", "eigenvalue"],
        "difficulty": "hard",
    },
    {
        "prompt_id": "math_10",
        "text": "If sin(θ) = 3/5 and θ is in quadrant II, compute cos(θ) and tan(θ).",
        "reference_answer": "In QII, cos is negative. cos^2(θ) = 1 - sin^2(θ) = 1 - 9/25 = 16/25, so cos(θ) = -4/5. tan(θ) = sin/cos = (3/5)/(-4/5) = -3/4. The result is cos(θ) = -4/5, tan(θ) = -3/4.",
        "reference_keywords": ["solution", "result", "compute", "trigonometry"],
        "difficulty": "medium",
    },
]

GENERAL_PROMPTS: list[dict[str, Any]] = [
    {
        "prompt_id": "gen_01",
        "text": "Explain the process of photosynthesis in plants and its importance for life on Earth.",
        "reference_answer": "Photosynthesis is the process by which plants convert carbon dioxide and water into glucose and oxygen using sunlight energy, catalyzed by chlorophyll. It is essential because it produces oxygen for respiration and forms the base of most food chains.",
        "reference_keywords": ["answer", "because", "result", "photosynthesis", "oxygen"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "gen_02",
        "text": "What caused the fall of the Roman Empire? Provide at least three contributing factors.",
        "reference_answer": "The fall of the Roman Empire resulted from multiple factors: economic troubles including inflation and over-taxation, military overspending and barbarian invasions, political corruption and instability, the division of the empire, and the rise of Christianity shifting power structures.",
        "reference_keywords": ["answer", "because", "result", "roman", "empire"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "gen_03",
        "text": "How does a combustion engine work? Explain the four-stroke cycle.",
        "reference_answer": "A four-stroke engine operates through: intake (fuel-air mixture enters), compression (piston compresses mixture), power (spark plug ignites, expanding gases push piston), and exhaust (burned gases exit). This cycle repeats, converting chemical energy to mechanical motion.",
        "reference_keywords": ["answer", "because", "result", "engine", "stroke"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "gen_04",
        "text": "What is the greenhouse effect and why is it important for Earth's climate?",
        "reference_answer": "The greenhouse effect is the trapping of heat by atmospheric gases like CO2, methane, and water vapor. It keeps Earth warm enough for life, but human activities have intensified it, causing global warming and climate change.",
        "reference_keywords": ["answer", "because", "result", "greenhouse", "climate"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "gen_05",
        "text": "Explain what blockchain technology is and describe three potential applications beyond cryptocurrency.",
        "reference_answer": "Blockchain is a decentralized, immutable digital ledger. Applications include: supply chain tracking for transparency, healthcare record management for secure patient data sharing, and voting systems for tamper-proof elections.",
        "reference_keywords": ["answer", "because", "result", "blockchain", "technology"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "gen_06",
        "text": "What are the main differences between renewable and non-renewable energy sources? Give examples of each.",
        "reference_answer": "Renewable energy comes from sources that naturally replenish, like solar, wind, hydro, and geothermal. Non-renewable sources deplete over time, like coal, oil, natural gas, and uranium. The key difference is sustainability because renewables don't run out.",
        "reference_keywords": ["answer", "because", "result", "renewable", "energy"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "gen_07",
        "text": "Describe the water cycle and explain how human activities can disrupt it.",
        "reference_answer": "The water cycle involves evaporation, transpiration, condensation, precipitation, and collection. Humans disrupt it through deforestation (reducing transpiration), urbanization (increasing runoff), pollution (contaminating water), and climate change (altering precipitation patterns).",
        "reference_keywords": ["answer", "because", "result", "water", "cycle"],
        "difficulty": "easy",
    },
    {
        "prompt_id": "gen_08",
        "text": "What is the theory of evolution by natural selection? Explain the key mechanisms and provide evidence.",
        "reference_answer": "Natural selection is the process where organisms with traits better suited to their environment survive and reproduce more. Key mechanisms include variation, inheritance, selection pressure, and differential reproduction. Evidence includes fossil records, DNA comparisons, and observed adaptation in species.",
        "reference_keywords": ["answer", "because", "result", "evolution", "natural selection"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "gen_09",
        "text": "How does the human immune system defend against pathogens? Describe both innate and adaptive immunity.",
        "reference_answer": "Innate immunity provides immediate, non-specific defense through barriers (skin), phagocytes, and inflammation. Adaptive immunity is specific and develops memory through B cells (antibodies) and T cells (cell-mediated). Together they protect because they recognize and eliminate pathogens.",
        "reference_keywords": ["answer", "because", "result", "immune", "immunity"],
        "difficulty": "medium",
    },
    {
        "prompt_id": "gen_10",
        "text": "Explain the concept of supply and demand in economics and how it determines market prices.",
        "reference_answer": "Supply is the quantity producers offer at a given price; demand is the quantity consumers want. Market equilibrium occurs where supply equals demand. When demand exceeds supply, prices rise; when supply exceeds demand, prices fall. This self-correcting mechanism determines prices because markets seek equilibrium.",
        "reference_keywords": ["answer", "because", "result", "supply", "demand"],
        "difficulty": "easy",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════════
# Prompt Corpora Registry
# ═══════════════════════════════════════════════════════════════════════════════════

PROMPT_CORPORA: dict[str, list[dict[str, Any]]] = {
    "medical": MEDICAL_PROMPTS,
    "code": CODE_PROMPTS,
    "math": MATH_PROMPTS,
    "general": GENERAL_PROMPTS,
}

CORPUS_KEYWORDS: dict[str, list[str]] = {
    "medical": ["diagnosis", "treatment", "symptom"],
    "code": ["def", "return", "function"],
    "math": ["solution", "result", "compute"],
    "general": ["answer", "because", "result"],
}


def build_prompts(domain: str, limit: int = 10) -> list[BenchmarkPrompt]:
    """Build BenchmarkPrompt objects from the specified domain corpus.

    Args:
        domain: One of 'medical', 'code', 'math', 'general'.
        limit: Maximum number of prompts to return.

    Returns:
        List of BenchmarkPrompt objects.

    Raises:
        ValueError: If domain is not recognized.
    """
    if domain not in PROMPT_CORPORA:
        raise ValueError(
            f"Unknown domain '{domain}'. Available domains: {', '.join(sorted(PROMPT_CORPORA))}"
        )

    prompts_data = PROMPT_CORPORA[domain][:limit]
    return [
        BenchmarkPrompt(
            prompt_id=p["prompt_id"],
            text=p["text"],
            domain=domain,
            reference_answer=p["reference_answer"],
            reference_keywords=p["reference_keywords"],
            difficulty=p["difficulty"],
        )
        for p in prompts_data
    ]


# ═══════════════════════════════════════════════════════════════════════════════════
# Real Ollama Backend Factory — NO dummies, NO mocks in production code
# ═══════════════════════════════════════════════════════════════════════════════════


def check_ollama_running() -> bool:
    """Check whether the Ollama server is reachable.

    Returns:
        True if Ollama returns a response, False otherwise.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def make_ollama_backend(model_name: str) -> Callable[[str], str]:
    """Create a callable backend that queries a real Ollama model.

    The returned callable has the model name accessible as an attribute for
    reporting purposes.

    Args:
        model_name: The Ollama model name (e.g., 'llama3.2:latest').

    Returns:
        A callable (prompt: str) -> str that POSTs to Ollama and returns the
        generated response text.

    Raises:
        RuntimeError: If Ollama server is not running at call time.
        requests.RequestException: On connection failure after retries.
    """
    if not check_ollama_running():
        raise RuntimeError(
            "Ollama server is not running at {}. "
            "Start Ollama and try again.".format(OLLAMA_BASE_URL)
        )

    def _ollama_call(prompt: str) -> str:
        """Call the Ollama model and return the generated text."""
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }
        try:
            resp = requests.post(
                OLLAMA_GENERATE_URL,
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "")
            if not response_text:
                raise RuntimeError(
                    f"Model '{model_name}' returned empty response for prompt: "
                    f"{prompt[:80]}..."
                )
            return response_text
        except requests.Timeout as exc:
            raise requests.Timeout(
                f"Ollama model '{model_name}' timed out after {OLLAMA_TIMEOUT}s"
            ) from exc
        except requests.ConnectionError as exc:
            raise requests.ConnectionError(
                f"Failed to connect to Ollama at {OLLAMA_BASE_URL}. "
                "Is the server running?"
            ) from exc

    # Attach model_name as an attribute for introspection in tests/CLI output
    _ollama_call.model_name = model_name  # type: ignore[attr-defined]
    return _ollama_call


# ═══════════════════════════════════════════════════════════════════════════════════
# Config Persistence
# ═══════════════════════════════════════════════════════════════════════════════════


def _ensure_config_dir() -> Path:
    """Ensure the config directory exists and return it."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def _get_config_path(test_name: str) -> Path:
    """Get the JSON config file path for a test."""
    return _ensure_config_dir() / f"{test_name}.json"


def _get_results_path(test_name: str) -> Path:
    """Get the JSON results file path for a test."""
    return _ensure_config_dir() / f"{test_name}_results.json"


def save_config(test_name: str, domain: str, backends: list[str]) -> dict[str, Any]:
    """Save a test configuration to disk.

    Args:
        test_name: Unique name for the test.
        domain: Domain string (medical, code, math, general).
        backends: List of Ollama model names.

    Returns:
        The config dict that was saved.

    Raises:
        ValueError: If a test with that name already exists.
    """
    config_path = _get_config_path(test_name)
    if config_path.exists():
        raise ValueError(
            f"Test '{test_name}' already exists. Use a different name or delete "
            f"{config_path} first."
        )

    config: dict[str, Any] = {
        "name": test_name,
        "domain": domain,
        "backends": backends,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def load_config(test_name: str) -> dict[str, Any]:
    """Load a test configuration from disk.

    Args:
        test_name: The test name to load.

    Returns:
        The config dict.

    Raises:
        FileNotFoundError: If no config exists for test_name.
    """
    config_path = _get_config_path(test_name)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Test '{test_name}' not found. Config file expected at {config_path}. "
            "Use 'define' to create a test first."
        )

    return json.loads(config_path.read_text(encoding="utf-8"))


def save_results(test_name: str, run: BenchmarkRun) -> Path:
    """Serialize benchmark results to disk.

    Args:
        test_name: The test name.
        run: The completed BenchmarkRun.

    Returns:
        Path to the saved results file.
    """
    results_path = _get_results_path(test_name)

    serializable: dict[str, Any] = {
        "test_name": test_name,
        "run_id": run.run_id,
        "backends": run.backends,
        "domains": run.domains,
        "n_prompts": len(run.prompts),
        "total_time_ms": run.total_time_ms,
        "comparisons": {},
    }

    for key, comp in run.comparisons.items():
        serializable["comparisons"][key] = {
            "backend_a": comp.backend_a,
            "backend_b": comp.backend_b,
            "domain": comp.domain,
            "n_prompts": comp.n_prompts,
            "mean_a": comp.mean_a,
            "mean_b": comp.mean_b,
            "std_a": comp.std_a,
            "std_b": comp.std_b,
            "diff_mean": comp.diff_mean,
            "cohens_d": comp.cohens_d,
            "p_value": comp.p_value,
            "confidence_95_lower": comp.confidence_95_lower,
            "confidence_95_upper": comp.confidence_95_upper,
            "winner": comp.winner,
            "significant": comp.significant,
            "recommendation": comp.recommendation,
        }

    results_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    return results_path


def load_results(test_name: str) -> dict[str, Any]:
    """Load benchmark results from disk.

    Args:
        test_name: The test name.

    Returns:
        The results dict.

    Raises:
        FileNotFoundError: If no results exist for this test.
    """
    results_path = _get_results_path(test_name)
    if not results_path.exists():
        raise FileNotFoundError(
            f"No results found for test '{test_name}'. "
            f"Expected at {results_path}. Run the test first."
        )

    return json.loads(results_path.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════════════
# CLI Commands
# ═══════════════════════════════════════════════════════════════════════════════════


def _effect_size_desc(cohens_d: float) -> str:
    """Return a human-readable description of Cohen's d magnitude."""
    abs_d = abs(cohens_d)
    if abs_d > 0.8:
        return "large"
    elif abs_d > 0.5:
        return "medium"
    elif abs_d > 0.2:
        return "small"
    return "negligible"


def cmd_define(args: argparse.Namespace) -> int:
    """Handle the 'define' subcommand."""
    backends_list = [b.strip() for b in args.backends.split(",") if b.strip()]

    if not backends_list:
        print("Error: At least one backend model name is required.", file=sys.stderr)
        return 1

    # Validate domain exists
    if args.domain not in PROMPT_CORPORA:
        print(
            f"Error: Unknown domain '{args.domain}'. "
            f"Available: {', '.join(sorted(PROMPT_CORPORA))}",
            file=sys.stderr,
        )
        return 1

    try:
        config = save_config(args.name, args.domain, backends_list)
        print(f"Test '{args.name}' defined:")
        print(f"  Domain: {config['domain']}")
        print(f"  Backends: {', '.join(config['backends'])}")
        print(f"  Config saved to: {_get_config_path(args.name)}")
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Handle the 'run' subcommand."""
    try:
        config = load_config(args.test_name)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Check Ollama is running
    if not check_ollama_running():
        print(
            f"Error: Ollama server is not running at {OLLAMA_BASE_URL}. "
            "Start Ollama and try again.",
            file=sys.stderr,
        )
        return 1

    domain = config["domain"]
    backend_names = config["backends"]
    n_prompts = args.prompts

    # Build prompts from corpus
    prompts = build_prompts(domain, limit=n_prompts)
    if len(prompts) < n_prompts:
        print(
            f"Warning: Only {len(prompts)} prompts available in '{domain}' corpus "
            f"(requested {n_prompts}). Proceeding with {len(prompts)}."
        )

    # Create real Ollama backends
    backends: dict[str, Callable[[str], str]] = {}
    for name in backend_names:
        try:
            backend_fn = make_ollama_backend(name)
            backends[name] = backend_fn
        except RuntimeError as exc:
            print(f"Error creating backend '{name}': {exc}", file=sys.stderr)
            return 1

    # Run benchmark
    print(f"Running A/B test '{args.test_name}'...")
    print(f"  Domain: {domain}")
    print(f"  Backends: {', '.join(backend_names)}")
    print(f"  Prompts: {len(prompts)}")

    benchmark = BackendBenchmark(backends=backends, prompts=prompts)
    start = time.monotonic()
    run = benchmark.run(n_trials=len(prompts))
    elapsed = time.monotonic() - start

    # Save results
    results_path = save_results(args.test_name, run)
    print(f"\nBenchmark complete in {elapsed:.1f}s")
    print(f"Results saved to: {results_path}")

    # Quick summary
    for key, comp in run.comparisons.items():
        print(f"\n  {comp.backend_a} vs {comp.backend_b} ({comp.domain}):")
        print(f"    {comp.backend_a}: {comp.mean_a:.3f}")
        print(f"    {comp.backend_b}: {comp.mean_b:.3f}")
        if comp.winner != "tie":
            print(f"    Winner: {comp.winner} (p={comp.p_value:.4f}, d={comp.cohens_d:.3f})")
        else:
            print(f"    Result: tie (p={comp.p_value:.4f})")

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Handle the 'show' subcommand."""
    try:
        config = load_config(args.test_name)
        results = load_results(args.test_name)
    except (FileNotFoundError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    domain = config["domain"]
    backends = config["backends"]
    n_prompts = results.get("n_prompts", 0)

    print(f"Test: {args.test_name}")
    print(f"Backends: {', '.join(backends)}")
    print(f"Prompts: {n_prompts}")
    print()

    comparisons = results.get("comparisons", {})
    if not comparisons:
        print("No comparisons found in results.")
        return 0

    print("Comparisons:")
    for key, comp in comparisons.items():
        c_backend_a = comp["backend_a"]
        c_backend_b = comp["backend_b"]
        c_domain = comp["domain"]
        mean_a_val = comp["mean_a"]
        mean_b_val = comp["mean_b"]
        n = comp["n_prompts"]

        # Reconstruct Wilson intervals from the stored means
        import math as _math
        correct_a = round(mean_a_val * n)
        correct_b = round(mean_b_val * n)
        ci_a_lower, ci_a_upper = _wilson_ci(correct_a, n)
        ci_b_lower, ci_b_upper = _wilson_ci(correct_b, n)
        diff = comp["diff_mean"]
        cohens_d = comp["cohens_d"]
        p_value = comp["p_value"]
        winner = comp["winner"]
        effect = _effect_size_desc(cohens_d)

        print(f"  {c_backend_a} vs {c_backend_b} ({c_domain} domain)")
        print(f"    {c_backend_a}: {mean_a_val:.2f} ± {ci_a_upper - mean_a_val:.2f} (95% CI)")
        print(f"    {c_backend_b}: {mean_b_val:.2f} ± {ci_b_upper - mean_b_val:.2f} (95% CI)")
        print(f"    Difference: {diff:+.3f}")
        print(f"    Cohen's d: {cohens_d:.3f} ({effect})")
        print(f"    p-value: {p_value:.4f}")
        if winner != "tie":
            print(f"    Winner: {winner} ✓")
        else:
            print(f"    Winner: tie")
        print(f"    Recommendation: {comp['recommendation']}")
        print()

    return 0


def _wilson_ci(successes: int, n_trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    (Inline copy to keep the CLI self-contained for display.)
    """
    if n_trials == 0:
        return (0.0, 1.0)
    p = successes / n_trials
    import math
    denominator = 1 + z**2 / n_trials
    center = (p + z**2 / (2 * n_trials)) / denominator
    margin = z * math.sqrt(
        (p * (1 - p) + z**2 / (4 * n_trials)) / n_trials
    ) / denominator
    return (center - margin, center + margin)


# ═══════════════════════════════════════════════════════════════════════════════════
# Argument Parser
# ═══════════════════════════════════════════════════════════════════════════════════


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for hlf_ab_test."""
    parser = argparse.ArgumentParser(
        prog="hlf-ab-test",
        description="A/B Backend Framework CLI — compare Ollama models statistically.",
        epilog="Real Ollama backends only. No dummies, no mocks.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── define ──────────────────────────────────────────────────────────────
    define_parser = subparsers.add_parser(
        "define",
        help="Define a new A/B test configuration",
        description="Create a new A/B test configuration with specified domain and backends.",
    )
    define_parser.add_argument(
        "--name", required=True,
        help="Unique name for the test (e.g., medical_dx_v1)",
    )
    define_parser.add_argument(
        "--domain", required=True,
        choices=list(PROMPT_CORPORA.keys()),
        help="Test domain (medical, code, math, general)",
    )
    define_parser.add_argument(
        "--backends", required=True,
        help="Comma-separated list of Ollama model names (e.g., medgemma:4b,llama3.2:latest)",
    )

    # ── run ─────────────────────────────────────────────────────────────────
    run_parser = subparsers.add_parser(
        "run",
        help="Run a defined A/B test",
        description="Execute an A/B test against real Ollama backends.",
    )
    run_parser.add_argument(
        "--test-name", required=True,
        help="Name of the test to run (must be previously defined)",
    )
    run_parser.add_argument(
        "--prompts", type=int, default=10,
        help="Number of prompts to use from the domain corpus (default: 10, max: 10)",
    )

    # ── show ────────────────────────────────────────────────────────────────
    show_parser = subparsers.add_parser(
        "show",
        help="Display results of a completed A/B test",
        description="Show statistical comparison results for a previously run test.",
    )
    show_parser.add_argument(
        "--test-name", required=True,
        help="Name of the test to display results for",
    )

    return parser


# ═══════════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    """Main entry point for hlf_ab_test CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "define":
        return cmd_define(args)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "show":
        return cmd_show(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
