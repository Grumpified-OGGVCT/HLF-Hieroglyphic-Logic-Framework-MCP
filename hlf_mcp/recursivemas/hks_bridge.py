"""
HKS Memory Bridge for MicroSquad
================================
Gives tiny RecursiveMAS models access to HLF_MCP's HKS (Human Knowledge System)
— the SQLite-backed governed memory that's been here since day one.

Queries the existing HKS via `hlf_mcp.rag.memory.RAGMemory`, then injects
relevant facts, code patterns, and proven solutions into the MicroSquad prompt
BEFORE the latent reasoning loop runs.

Architecture:
  Question → HKS query (RAGMemory) → Knowledge injection → MicroSquad → Answer
                                      ↑
                            (validated facts, exemplars, code patterns)

This is NOT a new memory system. It IS the HKS.
"""

import re
import time
from pathlib import Path
from typing import Any

from hlf_mcp.rag.memory import RAGMemory

# ── Singleton ──

_hks_instance: RAGMemory | None = None


def get_hks(db_path: str | None = None) -> RAGMemory:
    """Get or create the shared HKS memory instance."""
    global _hks_instance
    if _hks_instance is None:
        resolved = db_path or str(
            Path(__file__).resolve().parent.parent.parent / "db" / "hlf_memory.db"
        )
        _hks_instance = RAGMemory(db_path=resolved)
    return _hks_instance


# ── Keyword extraction ──

def _extract_keywords(text: str, min_len: int = 3) -> list[str]:
    """Extract meaningful keywords from text for HKS queries."""
    # Strip code blocks for cleaner keyword extraction
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    words = re.findall(r"[a-zA-Z_]\w{2,}", cleaned.lower())
    # Longer words are more specific — weight by length
    scored: dict[str, int] = {}
    for w in words:
        if len(w) >= min_len:
            scored[w] = scored.get(w, 0) + len(w)
    return [w for w, _ in sorted(scored.items(), key=lambda x: -x[1])[:8]]


# ── Knowledge retrieval ──

def retrieve_knowledge(
    question: str,
    top_k: int = 8,
    max_chars: int = 2000,
    use_prefix: bool = True,
) -> str:
    """Query HKS for relevant knowledge and return a compact context string.

    Uses a single broad query per keyword to the HKS, letting the
    sparse-vector+graph ranking surface the most relevant results
    regardless of domain or entry kind. Fast: typically <2s.
    """
    hks = get_hks()
    keywords = _extract_keywords(question)
    if not keywords:
        return ""

    seen: set[str] = set()
    snippets: list[tuple[float, str]] = []

    # Single broad query with top keywords — let HKS ranking do the work
    for kw in keywords[:5]:
        try:
            result = hks.query(kw, top_k=top_k)
        except Exception:
            continue
        for item in result.get("results", []):
            content = item.get("content", "").strip()
            if not content or len(content) < 10:
                continue
            key = content[:100]
            if key in seen:
                continue
            seen.add(key)
            rank = float(
                item.get("retrieval_contract", {}).get("rank_score", 0.5)
            )
            snippets.append((rank, content[:600]))

    snippets.sort(key=lambda x: -x[0])
    selected = [s[1] for s in snippets[:top_k * 2]]
    combined = "\n---\n".join(selected)

    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n... [truncated]"

    if not combined.strip():
        return ""

    if use_prefix:
        return (
            "=== EXTERNAL KNOWLEDGE (HKS Memory) ===\n"
            + combined
            + "\n=== END HKS ===\n\n"
        )
    return combined


def augment_prompt(question: str, max_chars: int = 2000) -> str:
    """One-shot: query HKS and build an augmented prompt."""
    knowledge = retrieve_knowledge(question, max_chars=max_chars)
    if knowledge:
        return knowledge + question
    return question


# ── Self-test ──

if __name__ == "__main__":
    print("=" * 60)
    print("HKS Memory Bridge — Self Test")
    print("=" * 60)

    t0 = time.time()
    hks = get_hks()
    print(f"\nHKS loaded in {time.time() - t0:.2f}s")

    # Count what's in the store
    result = hks.query("coding", top_k=1)
    count = result.get("count", 0)
    print(f"HKS fact_store entries: {count}")

    # Test augmentation
    test_questions = [
        "Write a Python binary search function",
        "How do I handle retries with exponential backoff?",
        "Create a Flask API endpoint",
    ]
    for q in test_questions:
        t1 = time.time()
        augmented = augment_prompt(q)
        elapsed = time.time() - t1
        added = len(augmented) - len(q)
        print(f"\n  Q: {q}")
        print(f"  -> {added} chars added from HKS in {elapsed:.3f}s")

    print("\nHKS Bridge ready.")
