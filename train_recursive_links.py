"""RecursiveLink Training Pipeline — trains CrossModelAdapter bridges for 4-model complementary RecursiveMAS ring:
  Coder(Qwen0.5B,896d) → Router(functiongemma,640d) → Critic(Gemma3,1152d) → Solver(Qwen1.5B,1536d) → Coder
  using the published RecursiveMAS architecture from modeling.py."""

import json, random, torch, torch.nn as nn, torch.nn.functional as F
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

QWEN_DIM, GEMMA_DIM, QWEN15_DIM, FUNCG_DIM, ADAPTER_TYPE = 896, 1152, 1536, 640, "outer_ln_res_adapter"

# ── Corpus: 200 diverse texts (50 code + 50 reasoning + 50 factual + 50 problem-solving) ──
CORPUS = [
    "def fibonacci(n): return n if n < 2 else fibonacci(n-1) + fibonacci(n-2)",
    "class TreeNode: def __init__(self,val): self.val=val; self.left=None; self.right=None",
    "with open('data.txt') as f: lines = [line.strip() for line in f]",
    "import numpy as np; arr=np.array([1,2,3]); print(arr.mean())",
    "def quicksort(a): return a if len(a)<=1 else quicksort([x for x in a[1:] if x<a[0]])+[a[0]]",
    "from collections import defaultdict; d=defaultdict(int); d['a']+=1",
    "async def fetch(url): async with aiohttp.ClientSession() as s: async with s.get(url) as r: return await r.json()",
    "@dataclass class Point: x:float=0.0; y:float=0.0",
    "try: result=10/0\nexcept ZeroDivisionError: print('Cannot divide by zero')",
    "lambda x: x**2 if x>0 else 0",
    "import re; p=re.compile(r'\\d{3}-\\d{4}'); m=p.search('Phone: 123-4567')",
    "def gen(): for i in range(10): yield i*i",
    "lc=[x for x in range(100) if x%2==0]",
    "from functools import lru_cache\n@lru_cache(maxsize=128)\ndef fib(n): return fib(n-1)+fib(n-2) if n>1 else n",
    "import json; data=json.loads('{\"name\":\"Alice\"}'); print(data['name'])",
    "def deco(f):\n def w(*a,**k): print('before'); r=f(*a,**k); print('after'); return r\n return w",
    "class Singleton:\n _inst=None\n def __new__(cls): return cls._inst or super().__new__(cls)",
    "from typing import Generic,TypeVar; T=TypeVar('T'); class Stack(Generic[T]): pass",
    "import sqlite3; c=sqlite3.connect(':memory:'); cur=c.cursor()",
    "def ms(lst):\n if len(lst)<=1: return lst\n m=len(lst)//2; return merge(ms(lst[:m]),ms(lst[m:]))",
    "from pathlib import Path; home=Path.home(); cfg=home/'.config'/'app'",
    "import pickle; with open('m.pkl','wb') as f: pickle.dump(model,f)",
    "import unittest; class T(unittest.TestCase): def test_add(self): self.assertEqual(1+1,2)",
    "from contextlib import contextmanager\n@contextmanager\ndef timer(): yield; print('done')",
    "import hashlib; h=hashlib.sha256(b'data'); print(h.hexdigest())",
    "@dataclass class Cfg: debug:bool=False",
    "import subprocess; r=subprocess.run(['ls','-la'],capture_output=True,text=True)",
    "from enum import Enum; class Color(Enum): RED=1; GREEN=2; BLUE=3",
    "pattern=r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\\d).{8,}$'",
    "import logging; logging.basicConfig(level=logging.INFO); L=logging.getLogger(__name__)",
    "def flat(n): return [i for s in n for i in s]",
    "from itertools import product; list(product('AB','12'))",
    "import threading; lock=threading.Lock(); lock.acquire(); lock.release()",
    "def bs(arr,t): lo,hi=0,len(arr)-1; return bisect(arr,t,lo,hi)",
    "from abc import ABC,abstractmethod; class Animal(ABC):\n @abstractmethod\n def speak(self): pass",
    "@staticmethod\ndef h(): return 'utility'",
    "import time; s=time.perf_counter(); r=compute(); e=time.perf_counter()-s",
    "s='hello world'; v={c for c in s if c in 'aeiou'}; print(v)",
    "def f(*a,**k): print(f'args={a}, kwargs={k}')",
    "from typing import Optional; def g(name:Optional[str]=None)->str: return f'Hi {name}'",
    "import pdb; pdb.set_trace()",
    "m=[[0]*3 for _ in range(3)]; m[0][0]=1",
    "from functools import reduce\ndef chain(*fs): return lambda x: reduce(lambda v,f:f(v),fs,x)",
    "import os; env=os.environ.get('API_KEY','default')",
    "from dataclasses import asdict; cfg_dict=asdict(Cfg(debug=True))",
    "vals=[1,2,None,4]; clean=[v for v in vals if v is not None]",
    "def memo(f):\n cache={}\n def w(*a): return cache.get(a) or cache.setdefault(a,f(*a))\n return w",
    "class LRUCache:\n def __init__(self,c): self.c=c; self.cache=OrderedDict()",
    "import torch; t=torch.randn(3,4); n=torch.nn.functional.normalize(t,dim=-1)",
    "What is the capital of France and why was it chosen?",
    "Explain the difference between weather and climate in simple terms.",
    "If all A are B and all B are C, does it follow that all A are C?",
    "How does photosynthesis convert sunlight into chemical energy?",
    "What would happen if the Earth suddenly stopped rotating?",
    "Describe the process of making bread from flour, water, and yeast.",
    "Why do objects fall to the ground when dropped?",
    "What is the relationship between supply, demand, and market price?",
    "How do vaccines train the immune system to recognize pathogens?",
    "Explain the water cycle from evaporation to precipitation.",
    "What causes the seasons on Earth?",
    "Why is the sky blue during the day but red at sunset?",
    "How does a computer translate high-level code into machine instructions?",
    "What is the difference between speed and velocity?",
    "Explain how tides are caused by the Moon's gravitational pull.",
    "Why do some materials conduct electricity while others do not?",
    "What is entropy and why does it always increase?",
    "How does natural selection drive evolution over generations?",
    "Explain the concept of opportunity cost in economics.",
    "What happens to light when it passes through a prism?",
    "Why can't we breathe underwater like fish can?",
    "How does encryption keep data secure during transmission?",
    "What is the difference between mitosis and meiosis?",
    "Explain how GPS determines your location on Earth.",
    "Why do bridges have expansion joints?",
    "What causes earthquakes and how are they measured?",
    "How does a refrigerator keep food cold?",
    "Why does ice float on water when most solids sink?",
    "Explain the greenhouse effect and its role in climate change.",
    "What is the difference between a virus and a bacterium?",
    "How do airplanes generate lift to stay in the air?",
    "What is blockchain and how does it ensure trust?",
    "Why do we have leap years?",
    "Explain the concept of compound interest with an example.",
    "How does a magnet create a magnetic field?",
    "What is the difference between RAM and ROM in a computer?",
    "Why does metal feel colder than wood at room temperature?",
    "How do neurons transmit signals in the brain?",
    "What is dark matter and why do scientists believe it exists?",
    "Explain the difference between fission and fusion.",
    "How does sonar detect objects underwater?",
    "What causes the northern lights (aurora borealis)?",
    "Why is biodiversity important for ecosystem stability?",
    "How does a microwave oven heat food?",
    "What is the difference between a hypothesis and a theory?",
    "Explain how blood clotting prevents excessive bleeding.",
    "Why do planets orbit the Sun in elliptical paths?",
    "How does a catalytic converter reduce vehicle emissions?",
    "What is the Turing test and what does it measure?",
    "Explain why steel is stronger than pure iron.",
    "The speed of light in a vacuum is approximately 299,792,458 meters per second.",
    "Water boils at 100 degrees Celsius at standard atmospheric pressure.",
    "The human body contains approximately 206 bones.",
    "Earth is the third planet from the Sun in our solar system.",
    "DNA is composed of four nucleotide bases: adenine, thymine, guanine, and cytosine.",
    "The Great Wall of China stretches over 21,000 kilometers.",
    "Mount Everest is the highest mountain on Earth at 8,848 meters above sea level.",
    "The Amazon rainforest produces about 20 percent of the world's oxygen.",
    "A byte consists of 8 bits in modern computing systems.",
    "The periodic table contains 118 confirmed elements.",
    "Sharks have been on Earth for over 400 million years.",
    "The human heart beats approximately 100,000 times per day.",
    "Python was created by Guido van Rossum and first released in 1991.",
    "The Pacific Ocean covers approximately 63 million square miles.",
    "Honey never spoils; archaeologists have found edible honey in ancient Egyptian tombs.",
    "The average distance from Earth to the Moon is about 384,400 kilometers.",
    "Octopuses have three hearts and blue blood.",
    "The first electronic computer, ENIAC, was completed in 1945.",
    "Diamonds are formed under high pressure and temperature deep within the Earth.",
    "The cheetah is the fastest land animal, reaching speeds up to 120 kilometers per hour.",
    "The human brain contains approximately 86 billion neurons.",
    "Jupiter is the largest planet in our solar system with a diameter of 139,820 kilometers.",
    "The Eiffel Tower was completed in 1889 for the World's Fair.",
    "Bananas are berries, but strawberries are not.",
    "The first successful powered flight was achieved by the Wright brothers in 1903.",
    "Gold is a noble metal that does not rust or tarnish.",
    "The Antarctic ice sheet contains about 70 percent of Earth's fresh water.",
    "Lightning can reach temperatures of 30,000 Kelvin, five times hotter than the Sun's surface.",
    "The oldest known living tree is over 4,800 years old.",
    "A day on Venus is longer than a year on Venus.",
    "Caffeine is the world's most widely consumed psychoactive substance.",
    "The blue whale is the largest animal ever known to have existed.",
    "There are more stars in the universe than grains of sand on Earth's beaches.",
    "The first photograph was taken in 1826 by Joseph Nicéphore Niépce.",
    "Platypuses are one of the few mammals that lay eggs.",
    "The Mariana Trench is the deepest part of the ocean at about 11,034 meters.",
    "Sound travels about four times faster in water than in air.",
    "The International Space Station orbits Earth every 90 minutes.",
    "Tigers have striped skin, not just striped fur.",
    "The first email was sent by Ray Tomlinson in 1971.",
    "A single teaspoon of soil contains more microorganisms than there are people on Earth.",
    "The Mona Lisa was painted by Leonardo da Vinci between 1503 and 1519.",
    "Neutron stars are so dense that a teaspoon would weigh about 6 billion tons.",
    "The Sahara Desert is the largest hot desert in the world.",
    "Electric eels can generate shocks of up to 600 volts.",
    "There are more possible chess games than atoms in the observable universe.",
    "The human eye can distinguish approximately 10 million different colors.",
    "A group of flamingos is called a flamboyance.",
    "The first commercial microprocessor was the Intel 4004, released in 1971.",
    "Helium is the only element that cannot be solidified at normal atmospheric pressure.",
    "Design an algorithm to find the longest palindromic substring in linear time.",
    "How would you build a distributed key-value store that ensures consistency?",
    "Propose a solution for reducing plastic waste in oceans using technology.",
    "Given 12 coins with one counterfeit, find it in 3 weighings on a balance scale.",
    "Design a traffic light system for a 4-way intersection that minimizes wait time.",
    "How can we detect and prevent credit card fraud in real-time transactions?",
    "Given a 3x3 grid of lights, find the minimum moves to turn all lights on.",
    "Design a caching strategy for a high-traffic web application with limited memory.",
    "How would you route emergency vehicles through a city to minimize response time?",
    "Solve the classic river crossing puzzle: farmer, wolf, goat, and cabbage.",
    "Design a recommendation system that balances exploration and exploitation.",
    "How would you design a URL shortening service like bit.ly from scratch?",
    "Given a stream of integers, maintain the median in O(log n) per insertion.",
    "Propose an energy storage solution for a solar-powered community.",
    "Design a load balancer that distributes requests across heterogeneous servers.",
    "How would you detect if a linked list has a cycle without extra memory?",
    "Solve the Monty Hall problem and explain why switching doors is optimal.",
    "Design a chat application that supports millions of concurrent users.",
    "How can satellites be used to monitor deforestation in near real-time?",
    "Given an array, find the subarray with the maximum sum in O(n).",
    "Design a system to coordinate autonomous vehicles at an intersection.",
    "How would you implement a spell checker that handles typos and context?",
    "Find the shortest path through a maze using breadth-first search.",
    "Design a peer-to-peer file sharing protocol that resists censorship.",
    "How do you design a secure password reset flow for a web application?",
    "Given two eggs and a 100-floor building, find the critical floor efficiently.",
    "Design a monitoring system that alerts on anomalies in server metrics.",
    "How would you compress a large corpus of text while preserving searchability?",
    "Solve the 8-queens problem: place 8 queens on a chessboard with no attacks.",
    "Design a rate limiter that handles bursty traffic without dropping legitimate requests.",
    "How would you implement distributed consensus in a network with unreliable nodes?",
    "Given a set of intervals, find the maximum number of non-overlapping intervals.",
    "Design a data pipeline that processes terabytes of log data in real time.",
    "How to build a search engine that returns results before the user finishes typing?",
    "Given a binary tree, serialize and deserialize it without losing structure.",
    "Design an elevator control algorithm that minimizes average waiting time.",
    "How would you implement end-to-end encryption for a messaging application?",
    "Implement a LRU cache with O(1) get and put operations.",
    "Design a system to detect and filter spam emails using machine learning.",
    "How to schedule tasks on multiple machines to minimize total completion time?",
    "Given a graph, determine if it is bipartite using breadth-first search.",
    "Design a circuit breaker pattern for handling downstream service failures.",
    "How would you build a real-time collaborative document editor like Google Docs?",
    "Implement a thread-safe connection pool for database connections.",
    "Design a garbage collector that minimizes pause times for interactive applications.",
    "How to partition a database across multiple nodes while maintaining ACID properties?",
    "Given a string, find the longest substring without repeating characters in O(n).",
    "Design a notification system that delivers messages with at-most-once semantics.",
    "How would you detect and mitigate DDoS attacks on a web service?",
    "Implement a Bloom filter and explain the false positive probability trade-off.",
]


@dataclass
class AdapterConfig:
    adapter_type: str = ADAPTER_TYPE
    source_model: str = ""; target_model: str = ""
    in_dim: int = 0; out_dim: int = 0
    source_hidden_dim: int = 0; target_hidden_dim: int = 0
    loss_fn: str = "mse+cosine_similarity"
    training_steps: int = 200; corpus_size: int = 200; final_loss: float = 0.0

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class CrossModelAdapter(nn.Module):
    """Published RecursiveMAS RecursiveLink architecture (modeling.py:139-159)."""
    def __init__(self, in_dim, out_dim, adapter_type=ADAPTER_TYPE):
        super().__init__()
        self.adapter_type = adapter_type
        self.in_dim, self.out_dim = in_dim, out_dim
        hidden_dim = out_dim * 2
        self.proj1 = nn.Linear(in_dim, hidden_dim)
        self.act = nn.GELU()
        self.proj2 = nn.Linear(hidden_dim, out_dim)
        self.ln_source = nn.LayerNorm(in_dim)
        self.ln_target = nn.LayerNorm(out_dim)
        self.residual_proj = nn.Linear(in_dim, out_dim)

    def forward(self, x):
        h = self.ln_source(x)
        out = self.proj2(self.act(self.proj1(h)))
        out = out + self.residual_proj(x)
        return self.ln_target(out)


def _load_model(name, load_in_4bit=False, dtype=None):
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    if load_in_4bit:
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                                  bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4")
        model = AutoModelForCausalLM.from_pretrained(name, quantization_config=bnb,
                                                      device_map="auto", trust_remote_code=True)
    else:
        model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=dtype or torch.float16,
                                                      device_map="auto", trust_remote_code=True)
    tok = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    model.eval()
    for p in model.parameters(): p.requires_grad = False
    return model, tok


def _hidden_size(m): return m.config.hidden_size


def _get_hidden_and_ids(model, tok, text, max_len=100):
    inp = tok(text, return_tensors="pt", truncation=True, max_length=max_len)
    ids = inp["input_ids"].to(model.device)
    am = inp["attention_mask"].to(model.device)
    with torch.no_grad():
        out = model(input_ids=ids, attention_mask=am, output_hidden_states=True)
        return out.hidden_states[-1], ids, am


def _get_target_embedding(model, tok, text, max_len=100):
    """Tokenize with TARGET tokenizer and get input embeddings — avoids vocab mismatch."""
    inp = tok(text, return_tensors="pt", truncation=True, max_length=max_len)
    ids = inp["input_ids"].to(model.device)
    with torch.no_grad():
        return model.get_input_embeddings()(ids), ids


def _mean_pool(hidden_or_emb, attention_mask):
    """Mean-pool hidden states or embeddings across sequence length using attention mask."""
    mask = attention_mask.unsqueeze(-1).float()
    return (hidden_or_emb * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)


def _loss(pred, tgt):
    # Both are [batch, dim] after mean-pooling
    p, t = pred.float(), tgt.float()
    mse = F.mse_loss(p, t)
    cos = F.cosine_similarity(p, t, dim=-1)
    return mse + (1.0 - cos.mean())


def _validate(adapter, src_m, src_tok, tgt_m, tgt_tok):
    texts = ["The meaning of life is to explore", "def hello(): return 'world'",
             "What is the speed of light in a vacuum?"]
    losses = []
    for t in texts:
        h, _, am = _get_hidden_and_ids(src_m, src_tok, t)
        emb, _ = _get_target_embedding(tgt_m, tgt_tok, t)
        src_pooled = _mean_pool(adapter(h.float()), am)
        tgt_pooled = _mean_pool(emb, torch.ones(1, emb.size(1), device=emb.device))
        losses.append(_loss(src_pooled, tgt_pooled).item())
    return sum(losses) / len(losses)


def train_bridge(src_m, src_tok, tgt_m, tgt_tok, adapter, corpus, steps=200, lr=1e-3,
                 label="bridge", save_dir=Path("trained_adapters"), save_name="adapter"):
    adapter.train().to(device="cuda", dtype=torch.float32)  # FP32 for training stability
    opt = torch.optim.AdamW(adapter.parameters(), lr=lr)
    losses, indices, step = [], list(range(len(corpus))), 0
    bar = "=" * 50
    print(f"\n{bar}\n  {label}\n  {adapter.in_dim}->{adapter.out_dim}  "
          f"params={sum(p.numel() for p in adapter.parameters()):,}  steps={steps}\n{bar}")
    while step < steps:
        random.shuffle(indices)
        for idx in indices:
            if step >= steps: break
            h, _, am = _get_hidden_and_ids(src_m, src_tok, corpus[idx])
            emb, _ = _get_target_embedding(tgt_m, tgt_tok, corpus[idx])
            # Mean-pool to sentence-level representation for cross-vocabulary alignment
            # Cast hidden to float32 for stable adapter forward (adapter is FP32)
            src_pooled = _mean_pool(adapter(h.float()), am)
            tgt_pooled = _mean_pool(emb, torch.ones(1, emb.size(1), device=emb.device))
            opt.zero_grad()
            L = _loss(src_pooled, tgt_pooled)
            L.backward()
            torch.nn.utils.clip_grad_norm_(adapter.parameters(), max_norm=1.0)
            opt.step()
            losses.append(L.item()); step += 1
            if step % 10 == 0 or step == 1 or step == steps:
                avg10 = sum(losses[-10:]) / min(10, len(losses))
                print(f"  step {step:>4d}/{steps}  loss={L.item():.6f}  avg10={avg10:.6f}")
    final = sum(losses[-20:]) / min(20, len(losses))
    val = _validate(adapter, src_m, src_tok, tgt_m, tgt_tok)
    print(f"  final_loss={final:.6f}  val_loss={val:.6f}")
    save_dir.mkdir(parents=True, exist_ok=True)
    torch.save(adapter.state_dict(), save_dir / f"{save_name}.pt")
    cfg = AdapterConfig(source_model=str(src_m.config._name_or_path),
                        target_model=str(tgt_m.config._name_or_path),
                        in_dim=adapter.in_dim, out_dim=adapter.out_dim,
                        source_hidden_dim=_hidden_size(src_m), target_hidden_dim=_hidden_size(tgt_m),
                        training_steps=steps, corpus_size=len(corpus), final_loss=final)
    with open(save_dir / f"{save_name}_config.json", "w") as f:
        json.dump(cfg.to_dict(), f, indent=2)
    print(f"  saved -> {save_dir / f'{save_name}.pt'}")
    return {"label": label, "final_loss": final, "val_loss": val}


def main():
    import argparse
    p = argparse.ArgumentParser(description="Train RecursiveLink adapters for 4-model RecursiveMAS ring")
    p.add_argument("--steps", type=int, default=200)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--qwen-model", default="Qwen/Qwen2.5-Coder-0.5B-Instruct")
    p.add_argument("--funcg-model", default="google/functiongemma-270m-it")
    p.add_argument("--gemma-model", default="google/gemma-3-1b-it")
    p.add_argument("--qwen15-model", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    p.add_argument("--save-dir", default="trained_adapters")
    p.add_argument("--skip-q2f", action="store_true", help="Skip Qwen0.5B->functiongemma")
    p.add_argument("--skip-f2g", action="store_true", help="Skip functiongemma->Gemma")
    p.add_argument("--skip-q2g", action="store_true", help="Skip Qwen0.5B->Gemma")
    p.add_argument("--skip-g2q", action="store_true", help="Skip Gemma->Qwen0.5B")
    p.add_argument("--skip-g2q15", action="store_true", help="Skip Gemma->Qwen1.5B")
    p.add_argument("--skip-q152q05", action="store_true", help="Skip Qwen1.5B->Qwen0.5B")
    p.add_argument("--skip-all-existing", action="store_true", help="Skip qwen<->gemma (existing adapters)")
    p.add_argument("--ring-only", action="store_true", help="Only train ring adapters (q2f,f2g,g2q15,q152q05)")
    args = p.parse_args()
    save_dir = Path(args.save_dir)

    print("=" * 50 + "\n  RecursiveLink Training Pipeline (4-Model Complementary Ring)\n" + "=" * 50)
    print("  Coder(Qwen0.5B,896d) -> Router(funcG,640d) -> Critic(Gemma3,1152d) -> Solver(Qwen1.5B,1536d) -> Coder")

    print("\n[1] Loading models...")
    print("  Qwen2.5-Coder-0.5B-Instruct (FP16)")
    qm, qt = _load_model(args.qwen_model, load_in_4bit=False, dtype=torch.float16)
    assert _hidden_size(qm) == QWEN_DIM, f"Qwen hidden mismatch: {_hidden_size(qm)}"
    print(f"    hidden={_hidden_size(qm)}  params={sum(p.numel() for p in qm.parameters())/1e6:.0f}M  {next(qm.parameters()).device}")

    print("  functiongemma-270m-it (FP32, 270M params — FP16 unstable on this model)")
    fm, ft = _load_model(args.funcg_model, load_in_4bit=False, dtype=torch.float32)
    assert _hidden_size(fm) == FUNCG_DIM, f"funcG hidden mismatch: {_hidden_size(fm)}"
    print(f"    hidden={_hidden_size(fm)}  params={sum(p.numel() for p in fm.parameters())/1e6:.0f}M  {next(fm.parameters()).device}")

    print("  Gemma-3-1B-IT (4-bit)")
    gm, gt = _load_model(args.gemma_model, load_in_4bit=True)
    assert _hidden_size(gm) == GEMMA_DIM, f"Gemma hidden mismatch: {_hidden_size(gm)}"
    print(f"    hidden={_hidden_size(gm)}  params={sum(p.numel() for p in gm.parameters())/1e6:.0f}M  {next(gm.parameters()).device}")

    print("  Qwen2.5-Coder-1.5B-Instruct (4-bit)")
    q15m, q15t = _load_model(args.qwen15_model, load_in_4bit=True)
    assert _hidden_size(q15m) == QWEN15_DIM, f"Qwen1.5B hidden mismatch: {_hidden_size(q15m)}"
    print(f"    hidden={_hidden_size(q15m)}  params={sum(p.numel() for p in q15m.parameters())/1e6:.0f}M  {next(q15m.parameters()).device}")

    if torch.cuda.is_available():
        print(f"  VRAM: {torch.cuda.memory_allocated()/1e9:.1f}GB / {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB")

    print(f"\n[2] Adapters + corpus ({len(CORPUS)} examples)")
    q2f = CrossModelAdapter(QWEN_DIM, FUNCG_DIM)          # Qwen0.5B→funcG: 896→640
    f2g = CrossModelAdapter(FUNCG_DIM, GEMMA_DIM)          # funcG→Gemma: 640→1152
    q2g = CrossModelAdapter(QWEN_DIM, GEMMA_DIM)
    g2q = CrossModelAdapter(GEMMA_DIM, QWEN_DIM)
    g2q15 = CrossModelAdapter(GEMMA_DIM, QWEN15_DIM)       # Gemma→Qwen1.5B: 1152→1536
    q152q05 = CrossModelAdapter(QWEN15_DIM, QWEN_DIM)      # Qwen1.5B→Qwen0.5B: 1536→896
    print(f"  qwen->funcG:     {sum(p.numel() for p in q2f.parameters()):,} params")
    print(f"  funcG->gemma:    {sum(p.numel() for p in f2g.parameters()):,} params")
    print(f"  qwen->gemma:     {sum(p.numel() for p in q2g.parameters()):,} params")
    print(f"  gemma->qwen:     {sum(p.numel() for p in g2q.parameters()):,} params")
    print(f"  gemma->qwen1.5B: {sum(p.numel() for p in g2q15.parameters()):,} params")
    print(f"  qwen1.5B->qwen:  {sum(p.numel() for p in q152q05.parameters()):,} params")

    # Resolve skip flags
    skip_q2g = args.skip_q2g or args.skip_all_existing or args.ring_only
    skip_g2q = args.skip_g2q or args.skip_all_existing or args.ring_only

    print(f"\n[3] Training ({args.steps} steps/bridge) -> {save_dir.absolute()}")
    results = []
    if not args.skip_q2f:
        results.append(train_bridge(qm, qt, fm, ft, q2f, CORPUS, steps=args.steps,
                                     lr=args.lr, label="qwen->funcG (896->640)",
                                     save_dir=save_dir, save_name="qwen_to_funcg"))
    if not args.skip_f2g:
        results.append(train_bridge(fm, ft, gm, gt, f2g, CORPUS, steps=args.steps,
                                     lr=args.lr, label="funcG->gemma (640->1152)",
                                     save_dir=save_dir, save_name="funcg_to_gemma"))
    if not skip_q2g:
        results.append(train_bridge(qm, qt, gm, gt, q2g, CORPUS, steps=args.steps,
                                     lr=args.lr, label="qwen->gemma (896->1152)",
                                     save_dir=save_dir, save_name="qwen_to_gemma"))
    if not skip_g2q:
        results.append(train_bridge(gm, gt, qm, qt, g2q, CORPUS, steps=args.steps,
                                     lr=args.lr, label="gemma->qwen (1152->896)",
                                     save_dir=save_dir, save_name="gemma_to_qwen"))
    if not args.skip_g2q15:
        results.append(train_bridge(gm, gt, q15m, q15t, g2q15, CORPUS, steps=args.steps,
                                     lr=args.lr, label="gemma->qwen1.5B (1152->1536)",
                                     save_dir=save_dir, save_name="gemma_to_qwen15"))
    if not args.skip_q152q05:
        results.append(train_bridge(q15m, q15t, qm, qt, q152q05, CORPUS, steps=args.steps,
                                     lr=args.lr, label="qwen1.5B->qwen (1536->896)",
                                     save_dir=save_dir, save_name="qwen15_to_qwen05"))

    print(f"\n{'='*50}\n  Summary\n{'='*50}")
    for r in results:
        print(f"  {r['label']:35s}  final={r['final_loss']:.6f}  val={r['val_loss']:.6f}")
    print(f"\n  Adapters saved -> {save_dir.absolute()}")
    if not results:
        print("  (no adapters trained — all skipped)")


if __name__ == "__main__":
    main()
