#!/usr/bin/env python3
"""Query the local HLF memory store to see what knowledge we have."""

from hlf_mcp import server

# Get memory stats
stats = server.memory_store.stats()
print("=" * 70)
print("HLF MEMORY STORE STATUS")
print("=" * 70)
print(f"Total facts: {stats.get('total_facts', 0)}")
print(f"Memory strata: {stats.get('memory_strata', {})}")
print(f"Storage tiers: {stats.get('storage_tiers', {})}")

# Try to query for knowledge about server_completion or governed routing
print("\n" + "=" * 70)
print("SEARCHING FOR: 'governed completion' or 'server registration'")
print("=" * 70)

try:
    results = server.memory_store.query(
        "governed completion tool registration MCP",
        top_k=5,
        include_archive=False
    )
    print(f"Query results: {results.get('count', 0)} fact(s)")
    for i, result in enumerate(results.get('results', [])[:3], 1):
        print(f"\n[{i}] {result.get('topic', 'unknown-topic')}")
        content_preview = (result.get('content') or "")[:200]
        print(f"    {content_preview}...")
except Exception as e:
    print(f"Query failed: {e}")

# Try HKS exemplars
print("\n" + "=" * 70)
print("SEARCHING HKS EXEMPLARS: 'MCP tool registration'")
print("=" * 70)

try:
    results = server.memory_store.query(
        "MCP tool registration pattern",
        top_k=3,
        entry_kind="hks_exemplar",
        include_archive=False
    )
    print(f"HKS results: {results.get('count', 0)} exemplar(s)")
    for i, result in enumerate(results.get('results', [])[:3], 1):
        print(f"\n[{i}] {result.get('domain', 'general')} / {result.get('solution_kind', 'pattern')}")
        print(f"    Problem: {(result.get('problem') or '')[:150]}")
except Exception as e:
    print(f"HKS query failed: {e}")
