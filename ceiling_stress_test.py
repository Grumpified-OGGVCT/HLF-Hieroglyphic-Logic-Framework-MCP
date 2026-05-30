"""MicroSquad Ceiling Stress Test — Pushes reasoning to its breaking point.
Tiers 6-10: formal proofs, systems design, advanced algorithms, multi-file code gen, edge cases.
Runs with governed_pipeline in local mode (no cloud backup — we want to see where it fails)."""

import json, time, sys, os

sys.path.insert(0, r"C:\Users\gerry\generic_workspace\HLF_MCP")

CEILING_QUESTIONS = {
    "Tier 6 - Formal Proofs": [
        "Prove by induction that the sum of the first n odd numbers equals n². Show the base case and inductive step explicitly.",
        "Prove: if a graph has n vertices and n edges, it must contain at least one cycle. Provide a rigorous proof.",
        "Prove that √2 is irrational using proof by contradiction. Show every logical step.",
    ],
    "Tier 7 - Systems Design": [
        "Explain how Raft consensus works. Include leader election, log replication, and how it handles network partitions. Give pseudocode for the leader election timeout mechanism.",
        "A social media app has 100M users. Design a sharding strategy for the posts table. Explain shard key choice, rebalancing strategy, and how you'd handle cross-shard queries for a user's feed.",
        "Design a rate limiter that can handle 1M requests/second across a distributed system. Explain the algorithm, data structures, and how you handle clock skew between nodes.",
    ],
    "Tier 8 - Advanced Algorithms": [
        "Solve the 0/1 knapsack problem: given items with weights [2,3,4,5] and values [3,4,5,6], capacity 8. Show the DP table and trace the optimal selection.",
        "Implement the Levenshtein edit distance algorithm. Given 'kitten' and 'sitting', show the full DP matrix and trace the edits.",
        "Design an admissible and consistent heuristic for A* pathfinding on a grid with diagonal movement. Prove it's both admissible and consistent.",
    ],
    "Tier 9 - Multi-File Code Gen": [
        "Create a minimal task queue system in Python with 3 files: queue.py (Redis-backed enqueue/dequeue), worker.py (processes tasks with retries), and main.py (wires them together with example usage). Include error handling for Redis connection failures.",
        "Write a Python library with 3 modules: parser.py (recursive descent JSON parser from scratch), validator.py (schema validation against a JSON Schema-like spec), and serializer.py (pretty-printer with configurable indentation). Include __init__.py that exports the public API.",
    ],
    "Tier 10 - Edge Cases & Ambiguity": [
        "What is 0/0? Explain the mathematical reasoning. If this is used in a program that must NOT crash, what should it return and why?",
        "A function is specified as: 'Given a list, return the most frequent element.' What edge cases exist? List at least 5 and how you'd handle each. Then implement it.",
        "You have a sorting algorithm that must be stable, in-place, and O(n log n) worst-case. Is this possible? If yes, which algorithm? If no, why not (prove the impossibility)?",
    ],
}


RESULTS = {"results": {}}
total_start = time.time()

# Check if governed_pipeline is importable
try:
    from hlf_mcp.recursivemas.governed_pipeline import governed_pipeline
    print("✅ governed_pipeline imported")
except Exception as e:
    print(f"❌ Import failed: {e}")
    # Try alternative path
    sys.path.insert(0, r"C:\Users\gerry\generic_workspace\HLF_MCP\hlf_mcp")
    from recursivemas.governed_pipeline import governed_pipeline

for tier_name, questions in CEILING_QUESTIONS.items():
    print(f"\n{'='*70}")
    print(f">>> {tier_name}")
    print(f"{'='*70}")
    RESULTS["results"][tier_name] = []

    for q in questions:
        short_q = q[:80] + "..." if len(q) > 80 else q
        print(f"\n📝 Question: {short_q}")
        t0 = time.time()

        try:
            result = governed_pipeline(
                question=q,
                mode="local",
                style="sequential_light",
                load_in_4bit=False,
                max_tokens=1024,
            )
            elapsed = time.time() - t0
            answer = result.get("output_text", "") if isinstance(result, dict) else str(result)
            success = answer is not None and len(answer.strip()) > 20
            if success:
                print(f"✅ PASS ({elapsed:.1f}s)")
                print(f"   Answer preview: {answer[:200]}...")
            else:
                print(f"❌ FAIL — answer too short or None: {repr(answer)[:100]}")
            RESULTS["results"][tier_name].append({
                "question": q,
                "success": success,
                "answer": answer[:500] if answer else None,
                "time_s": elapsed,
            })
        except Exception as e:
            elapsed = time.time() - t0
            print(f"💥 CRASH ({elapsed:.1f}s): {type(e).__name__}: {e}")
            RESULTS["results"][tier_name].append({
                "question": q,
                "success": False,
                "crash": f"{type(e).__name__}: {e}",
                "time_s": elapsed,
            })

total_time = time.time() - total_start
RESULTS["total_time"] = total_time

# Count results
passed = sum(
    1 for tier in RESULTS["results"].values()
    for r in tier if r.get("success")
)
total_qs = sum(len(v) for v in CEILING_QUESTIONS.values())
RESULTS["summary"] = {"passed": passed, "total": total_qs, "rate": f"{passed}/{total_qs}"}

outpath = r"C:\Users\gerry\generic_workspace\HLF_MCP\microsquad_ceiling_results.json"
with open(outpath, "w") as f:
    json.dump(RESULTS, f, indent=2)

print(f"\n{'='*70}")
print(f"CEILING BENCHMARK COMPLETE: {passed}/{total_qs} passed ({total_time:.0f}s)")
print(f"Results saved to: {outpath}")
print(f"{'='*70}")
