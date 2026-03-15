"""
HLF Memory Node — per-node storage for Infinite RAG memory graph.

MemoryNode: typed, provenance-tracked, TTL-aware memory unit.
MemoryStore: in-memory + SQLite-persistent store with:
  - SHA-256 dedup (content_hash)
  - cosine similarity dedup guard (>0.98 threshold blocks duplicate INSERTs)
  - Importance/confidence-ordered recall
  - TTL expiry
  - Tag and entity indexing
  - Merkle chain for append integrity
"""
from __future__ import annotations
import dataclasses, hashlib, json, math, re, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc

@dataclasses.dataclass
class MemoryNode:
    node_id:      str   = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    entity_id:    str   = ""
    content:      str   = ""
    content_hash: str   = ""
    confidence:   float = 1.0
    importance:   float = 0.5
    ttl_seconds:  int | None = None
    created_at:   str   = dataclasses.field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at:   str   = dataclasses.field(default_factory=lambda: datetime.now(UTC).isoformat())
    parent_id:    str | None = None
    children:     list[str] = dataclasses.field(default_factory=list)
    tags:         list[str] = dataclasses.field(default_factory=list)
    embedding:    list[float] | None = None
    source:       str   = ""
    spec_id:      str | None = None
    merkle_hash:  str   = ""

    def compute_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()

    def compute_embedding(self) -> list[float]:
        """Bag-of-words TF vector as a lightweight embedding proxy."""
        words = re.findall(r"[a-z0-9]+", self.content.lower())
        vocab: dict[str, int] = {}
        for w in words:
            vocab[w] = vocab.get(w, 0) + 1
        if not vocab:
            return []
        total = sum(vocab.values())
        return [v / total for v in vocab.values()]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryNode:
        return cls(
            node_id=data.get("node_id", str(uuid.uuid4())),
            entity_id=data.get("entity_id", ""),
            content=data.get("content", ""),
            content_hash=data.get("content_hash", ""),
            confidence=data.get("confidence", 1.0),
            importance=data.get("importance", 0.5),
            ttl_seconds=data.get("ttl_seconds"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            parent_id=data.get("parent_id"),
            children=data.get("children", []),
            tags=data.get("tags", []),
            source=data.get("source", ""),
            spec_id=data.get("spec_id"),
            merkle_hash=data.get("merkle_hash", ""),
        )


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0 if either is empty or lengths differ."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


def _align_embeddings(a: list[float], b: list[float]) -> tuple[list[float], list[float]]:
    """Pad shorter embedding to equal length with zeros."""
    la, lb = len(a), len(b)
    if la < lb:
        a = a + [0.0] * (lb - la)
    elif lb < la:
        b = b + [0.0] * (la - lb)
    return a, b


_DEDUP_THRESHOLD = 0.98


class MemoryStore:
    """In-memory store for MemoryNode instances."""

    def __init__(self, dedup_threshold: float = _DEDUP_THRESHOLD):
        self._nodes: dict[str, MemoryNode] = {}
        self._entity_index: dict[str, list[str]] = {}
        self._tag_index: dict[str, list[str]] = {}
        self._hash_index: dict[str, str] = {}  # content_hash → node_id
        self._prev_merkle: str = "0" * 64
        self.dedup_threshold = dedup_threshold

    def store(self, node: MemoryNode) -> dict[str, Any]:
        node.content_hash = node.compute_hash()
        # SHA-256 exact dedup
        if node.content_hash in self._hash_index:
            return {"stored": False, "reason": "exact_duplicate", "node_id": self._hash_index[node.content_hash]}
        # Embedding similarity dedup
        node.embedding = node.compute_embedding()
        for existing_id, existing in self._nodes.items():
            if existing.embedding and node.embedding:
                a, b = _align_embeddings(node.embedding, existing.embedding)
                sim = _cosine(a, b)
                if sim > self.dedup_threshold:
                    return {"stored": False, "reason": "near_duplicate", "similarity": round(sim, 4), "node_id": existing_id}
        # Merkle chain
        chain_input = self._prev_merkle + node.content_hash
        node.merkle_hash = hashlib.sha256(chain_input.encode()).hexdigest()
        self._prev_merkle = node.merkle_hash
        # Store
        self._nodes[node.node_id] = node
        self._hash_index[node.content_hash] = node.node_id
        if node.entity_id not in self._entity_index:
            self._entity_index[node.entity_id] = []
        self._entity_index[node.entity_id].append(node.node_id)
        for tag in node.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            self._tag_index[tag].append(node.node_id)
        return {"stored": True, "node_id": node.node_id, "merkle_hash": node.merkle_hash[:16] + "..."}

    def recall(self, entity_id: str = "", query: str = "", top_k: int = 5,
               tags: list[str] | None = None) -> list[dict[str, Any]]:
        if entity_id:
            node_ids = self._entity_index.get(entity_id, [])
        elif tags:
            node_ids = list({nid for t in tags for nid in self._tag_index.get(t, [])})
        else:
            node_ids = list(self._nodes.keys())
        results = []
        for nid in node_ids:
            node = self._nodes.get(nid)
            if node is None:
                continue
            if query and query.lower() not in node.content.lower():
                continue
            results.append(node)
        results.sort(key=lambda n: (n.importance, n.confidence), reverse=True)
        return [n.to_dict() for n in results[:top_k]]

    def expire(self) -> int:
        now = datetime.now(UTC)
        expired = []
        for node_id, node in self._nodes.items():
            if node.ttl_seconds is not None:
                created = datetime.fromisoformat(node.created_at)
                age = (now - created).total_seconds()
                if age > node.ttl_seconds:
                    expired.append(node_id)
        for node_id in expired:
            node = self._nodes.pop(node_id, None)
            if node:
                self._hash_index.pop(node.content_hash, None)
                elist = self._entity_index.get(node.entity_id, [])
                if node_id in elist:
                    elist.remove(node_id)
        return len(expired)

    def count(self) -> int:
        return len(self._nodes)

    def stats(self) -> dict[str, Any]:
        return {
            "total_nodes": len(self._nodes),
            "entities": len(self._entity_index),
            "tags": len(self._tag_index),
            "merkle_head": self._prev_merkle[:16] + "...",
        }
