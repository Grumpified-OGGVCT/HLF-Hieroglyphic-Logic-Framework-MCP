"""Validate HKS compounding memory loop: store -> recall -> compound."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hlf_mcp.rag.memory import RAGMemory

db_path = os.path.join(tempfile.gettempdir(), "hlf_test_compound.db")
# Remove any previous test db
for f in [db_path, db_path + "-wal", db_path + "-shm"]:
    if os.path.exists(f):
        os.unlink(f)

mem = RAGMemory(db_path=db_path)

# Phase 1: Store an initial translation
result = mem.store(
    content="\u0394 [GOAL] Audit system logs \u03a9",
    topic="hlf_translation_contracts",
    confidence=0.95,
    provenance="governed_recall",
    entry_kind="hks_exemplar",
    domain="translation",
    metadata={
        "intent": "Check system logs for errors",
        "governed_evidence": {
            "source_type": "translation_pipeline",
            "artifact_form": "hlf_source",
            "salience_score": 0.95,
            "source_authority_label": "governed",
            "branch": "main",
        },
    },
    bypass_vector_dedup=True,
)
print(f"Phase 1 - Store: {'stored' if result.get('stored') else 'duplicate: ' + str(result.get('duplicate_reason', ''))}")

# Phase 2: Query with similar intent — should find the stored translation
result2 = mem.query(
    "Audit system logs for security issues",
    top_k=3,
    topic="hlf_translation_contracts",
    min_confidence=0.5,
    purpose="translation_memory",
)
hits = result2.get("results", [])
top_conf = hits[0].get("confidence", 0) if hits else 0
print(f"Phase 2 - Query: {len(hits)} hits, top confidence: {top_conf}")

# Phase 3: Store a second translation, similar topic
result3 = mem.store(
    content="\u0394 [GOAL] Review security logs \u0394 [CONSTRAINT] read-only \u03a9",
    topic="hlf_translation_contracts",
    confidence=0.95,
    provenance="governed_recall",
    entry_kind="hks_exemplar",
    domain="translation",
    metadata={
        "intent": "Review security audit logs read-only",
        "governed_evidence": {
            "source_type": "translation_pipeline",
            "artifact_form": "hlf_source",
            "salience_score": 0.95,
            "source_authority_label": "governed",
            "branch": "main",
        },
    },
    bypass_vector_dedup=True,
)
print(f"Phase 3 - Second store: {'stored' if result3.get('stored') else 'duplicate: ' + str(result3.get('duplicate_reason', ''))}")

# Phase 4: Query again — should get 2 hits
result4 = mem.query(
    "Check security logs",
    top_k=5,
    topic="hlf_translation_contracts",
    min_confidence=0.3,
    purpose="translation_memory",
)
hits4 = result4.get("results", [])
print(f"Phase 4 - After two stores: {len(hits4)} hits")

# Phase 5: Query for a completely different topic — should get low confidence
result5 = mem.query(
    "Bake a chocolate cake",
    top_k=3,
    topic="hlf_translation_contracts",
    min_confidence=0.1,
    purpose="translation_memory",
)
hits5 = result5.get("results", [])
top5 = hits5[0].get("confidence", 0) if hits5 else 0
print(f"Phase 5 - Unrelated query: {len(hits5)} hits, top confidence: {top5}")

# Success check
assert result.get("stored"), "Phase 1 failed: initial store should succeed"
assert len(hits) >= 1, "Phase 2 failed: should find stored translation"
assert result3.get("stored"), "Phase 3 failed: second store should succeed"
assert len(hits4) >= 2, "Phase 4 failed: should have at least 2 hits after 2 stores"

# Cleanup
for f in [db_path, db_path + "-wal", db_path + "-shm"]:
    try:
        if os.path.exists(f):
            os.unlink(f)
    except Exception:
        pass

print("\n=== HKS COMPOUNDING LOOP: VALIDATED ===")
print("store -> recall -> compound store -> richer recall: WORKS")
print(f"Phase 2: {len(hits)} hit(s) at {top_conf} confidence after 1 store")
print(f"Phase 4: {len(hits4)} hit(s) after 2 stores")
print(f"Phase 5: {len(hits5)} hit(s) for unrelated query (low relevance expected)")
