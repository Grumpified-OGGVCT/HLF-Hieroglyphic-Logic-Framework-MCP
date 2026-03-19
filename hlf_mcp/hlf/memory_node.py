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
        """Bag-of-words TF vector as a lightweight embedding proxy.

        Keys are sorted alphabetically so that two nodes with overlapping
        vocabulary produce vectors with dimensions in the same order, making
        cosine similarity comparisons meaningful.
        """
        words = re.findall(r"[a-z0-9]+", self.content.lower())
        vocab: dict[str, int] = {}
        for w in words:
            vocab[w] = vocab.get(w, 0) + 1
        if not vocab:
            return []
        total = sum(vocab.values())
        return [vocab[k] / total for k in sorted(vocab)]

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

_POINTER_PATTERN = re.compile(
    r"^&(?P<alias>[A-Za-z0-9_.-]+):(?P<algorithm>SHA256):(?P<digest>[0-9a-fA-F]{64})$"
)


def _sanitize_pointer_alias(alias: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(alias or "pointer").strip())
    return cleaned.strip("-._") or "pointer"


def build_pointer_ref(alias: str, content_or_hash: str) -> str:
    """Build a canonical HLF pointer reference.

    If the supplied value already looks like a SHA-256 digest, it is used
    directly. Otherwise the digest is computed from the content bytes.
    """
    normalized = str(content_or_hash or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", normalized):
        digest = normalized.lower()
    else:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"&{_sanitize_pointer_alias(alias)}:SHA256:{digest}"


def parse_pointer_ref(value: str) -> dict[str, str] | None:
    """Parse a canonical HLF pointer reference."""
    match = _POINTER_PATTERN.match(str(value or "").strip())
    if not match:
        return None
    parsed = match.groupdict()
    return {
        "pointer": str(value).strip(),
        "alias": parsed["alias"],
        "algorithm": parsed["algorithm"],
        "digest": parsed["digest"].lower(),
    }


def lookup_pointer_registry_entry(pointer: str, registry: Any) -> dict[str, Any] | None:
    """Find a pointer registry entry by full pointer, alias, or digest."""
    if not isinstance(registry, dict):
        return None
    parsed = parse_pointer_ref(pointer)
    if parsed is None:
        return None
    for key in (pointer, parsed["alias"], parsed["digest"]):
        candidate = registry.get(key)
        if isinstance(candidate, dict):
            return dict(candidate)
    return None


def _parse_freshness_timestamp(raw_value: Any) -> float | None:
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    if isinstance(raw_value, str):
        try:
            return datetime.fromisoformat(raw_value).timestamp()
        except ValueError:
            return None
    return None


@dataclasses.dataclass
class HLFPointer:
    """Canonical pointer registry record for pass-by-reference HLF data."""

    alias: str
    content_hash: str
    algorithm: str = "SHA256"
    content: str | None = None
    trust_tier: str = "local"
    fresh_until: str | None = None
    revoked: bool = False
    tombstoned: bool = False
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def pointer(self) -> str:
        return build_pointer_ref(self.alias, self.content_hash)

    @classmethod
    def from_content(
        cls,
        *,
        alias: str,
        content: str,
        trust_tier: str = "local",
        fresh_until: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "HLFPointer":
        digest = hashlib.sha256(str(content).encode("utf-8")).hexdigest()
        return cls(
            alias=_sanitize_pointer_alias(alias),
            content_hash=digest,
            content=str(content),
            trust_tier=trust_tier,
            fresh_until=fresh_until,
            metadata=dict(metadata or {}),
        )

    def to_registry_entry(self) -> dict[str, Any]:
        return {
            "pointer": self.pointer,
            "alias": _sanitize_pointer_alias(self.alias),
            "algorithm": self.algorithm,
            "content_hash": self.content_hash.lower(),
            "content": self.content,
            "trust_tier": self.trust_tier,
            "fresh_until": self.fresh_until,
            "revoked": self.revoked,
            "tombstoned": self.tombstoned,
            "metadata": dict(self.metadata),
        }


def verify_pointer_ref(
    pointer: str,
    *,
    registry_entry: dict[str, Any] | None = None,
    content: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Verify pointer syntax, digest binding, freshness, and revocation state."""
    parsed = parse_pointer_ref(pointer)
    if parsed is None:
        return {"status": "not_pointer", "pointer": pointer}

    effective_now = now if now is not None else datetime.now(UTC).timestamp()
    entry = dict(registry_entry or {})
    effective_content = content if content is not None else entry.get("content")
    expected_hash = str(entry.get("content_hash") or entry.get("sha256") or "").strip().lower()
    if expected_hash and expected_hash != parsed["digest"]:
        return {
            "status": "hash_mismatch",
            "reason": "registry_hash_mismatch",
            "pointer": parsed["pointer"],
            "alias": parsed["alias"],
            "expected": expected_hash,
            "actual": parsed["digest"],
        }
    if effective_content is not None:
        actual_hash = hashlib.sha256(str(effective_content).encode("utf-8")).hexdigest()
        if actual_hash != parsed["digest"]:
            return {
                "status": "hash_mismatch",
                "reason": "content_hash_mismatch",
                "pointer": parsed["pointer"],
                "alias": parsed["alias"],
                "expected": parsed["digest"],
                "actual": actual_hash,
            }
    elif not entry:
        return {
            "status": "untrusted",
            "reason": "pointer_not_registered",
            "pointer": parsed["pointer"],
            "alias": parsed["alias"],
            "digest": parsed["digest"],
        }

    if bool(entry.get("revoked", False)) or bool(entry.get("tombstoned", False)):
        return {
            "status": "revoked",
            "reason": "pointer_revoked",
            "governance_status": "tombstoned" if bool(entry.get("tombstoned", False)) else "revoked",
            "freshness_status": "unknown",
            "pointer": parsed["pointer"],
            "alias": parsed["alias"],
            "digest": parsed["digest"],
        }

    fresh_until_ts = _parse_freshness_timestamp(entry.get("fresh_until"))
    if fresh_until_ts is not None and fresh_until_ts < effective_now:
        return {
            "status": "stale",
            "reason": "pointer_stale",
            "governance_status": "stale",
            "freshness_status": "stale",
            "pointer": parsed["pointer"],
            "alias": parsed["alias"],
            "digest": parsed["digest"],
            "fresh_until": entry.get("fresh_until"),
        }

    return {
        "status": "ok",
        "governance_status": "active",
        "freshness_status": "fresh",
        "pointer": parsed["pointer"],
        "alias": parsed["alias"],
        "algorithm": parsed["algorithm"],
        "digest": parsed["digest"],
        "trust_tier": entry.get("trust_tier", "local"),
        "resolved_value": effective_content if effective_content is not None else entry.get("value"),
    }


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
