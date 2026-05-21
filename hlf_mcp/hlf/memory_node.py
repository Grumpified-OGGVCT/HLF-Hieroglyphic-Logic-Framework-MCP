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

import dataclasses
import hashlib
import json
import math
import re
import uuid
from datetime import UTC, datetime
from typing import Any


@dataclasses.dataclass
class MemoryNode:
    node_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""
    content: str = ""
    content_hash: str = ""
    confidence: float = 1.0
    importance: float = 0.5
    ttl_seconds: int | None = None
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = dataclasses.field(default_factory=lambda: datetime.now(UTC).isoformat())
    parent_id: str | None = None
    children: list[str] = dataclasses.field(default_factory=list)
    tags: list[str] = dataclasses.field(default_factory=list)
    embedding: list[float] | None = None
    source: str = ""
    spec_id: str | None = None
    merkle_hash: str = ""
    evidence: "EvidenceContract | None" = None

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
        d = {
            "node_id": self.node_id,
            "entity_id": self.entity_id,
            "content": self.content,
            "content_hash": self.content_hash,
            "confidence": self.confidence,
            "importance": self.importance,
            "ttl_seconds": self.ttl_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parent_id": self.parent_id,
            "children": self.children,
            "tags": self.tags,
            "source": self.source,
            "spec_id": self.spec_id,
            "merkle_hash": self.merkle_hash,
        }
        if self.embedding is not None:
            d["embedding"] = self.embedding
        if self.evidence is not None:
            d["evidence"] = self.evidence.to_dict()
        else:
            d["evidence"] = None
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryNode":
        evidence = None
        if "evidence" in data and data["evidence"]:
            evidence = EvidenceContract.from_dict(data["evidence"])
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
            embedding=data.get("embedding"),
            source=data.get("source", ""),
            spec_id=data.get("spec_id"),
            merkle_hash=data.get("merkle_hash", ""),
            evidence=evidence,
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
    ) -> HLFPointer:
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
            "governance_status": "tombstoned"
            if bool(entry.get("tombstoned", False))
            else "revoked",
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
        "resolved_value": effective_content
        if effective_content is not None
        else entry.get("value"),
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
        # Evidence gate checks
        if node.evidence is not None:
            if node.evidence.revoked:
                return {"stored": False, "reason": "evidence_revoked", "node_id": node.node_id}
            if node.evidence.tombstoned:
                return {"stored": False, "reason": "evidence_tombstoned", "node_id": node.node_id}
        # SHA-256 exact dedup
        if node.content_hash in self._hash_index:
            return {
                "stored": False,
                "reason": "exact_duplicate",
                "node_id": self._hash_index[node.content_hash],
            }
        # Embedding similarity dedup
        node.embedding = node.compute_embedding()
        for existing_id, existing in self._nodes.items():
            if existing.embedding and node.embedding:
                a, b = _align_embeddings(node.embedding, existing.embedding)
                sim = _cosine(a, b)
                if sim > self.dedup_threshold:
                    return {
                        "stored": False,
                        "reason": "near_duplicate",
                        "similarity": round(sim, 4),
                        "node_id": existing_id,
                    }
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
        result: dict[str, Any] = {
            "stored": True,
            "node_id": node.node_id,
            "merkle_hash": node.merkle_hash[:16] + "...",
        }
        if node.evidence is not None and node.evidence.is_stale():
            result["stale_warning"] = "evidence_is_stale"
        return result

    def recall(
        self, entity_id: str = "", query: str = "", top_k: int = 5, tags: list[str] | None = None
    ) -> list[dict[str, Any]]:
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

    def store_with_evidence(self, node: MemoryNode, contract: "EvidenceContract") -> dict[str, Any]:
        """Store a node with an evidence contract, enforcing evidence gates."""
        content_hash = hashlib.sha256(node.content.encode()).hexdigest()

        # Check revocation/tombstoned first
        if contract.revoked:
            return {"stored": False, "reason": "evidence_revoked", "node_id": node.node_id}
        if contract.tombstoned:
            return {"stored": False, "reason": "evidence_tombstoned", "node_id": node.node_id}

        # Auto-fill sha256 if empty
        if not contract.sha256:
            contract.sha256 = content_hash

        # Validate the contract
        valid, errors = contract.validate()
        if not valid:
            return {"stored": False, "reason": "invalid_evidence_contract", "errors": errors, "node_id": node.node_id}

        # Check sha256 mismatch (after auto-fill and validation)
        if contract.sha256 != content_hash:
            return {"stored": False, "reason": "sha256_mismatch", "node_id": node.node_id}

        node.evidence = contract
        node.content_hash = content_hash
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

    def enforce_freshness(self, sha256_list: list[str] | None = None) -> dict[str, Any]:
        """Check freshness of stored evidence nodes."""
        stale_node_ids: list[str] = []
        fresh_count = 0
        stale_count = 0
        target_nodes = (
            [n for n in self._nodes.values() if n.content_hash in sha256_list]
            if sha256_list
            else list(self._nodes.values())
        )
        for node in target_nodes:
            if node.evidence is None:
                fresh_count += 1
            elif node.evidence.is_stale():
                stale_count += 1
                stale_node_ids.append(node.node_id)
            else:
                fresh_count += 1
        return {
            "total_checked": len(target_nodes),
            "fresh_count": fresh_count,
            "stale_count": stale_count,
            "stale_node_ids": stale_node_ids,
        }

    def resolve_supersession(self, sha256: str) -> dict[str, Any]:
        """Resolve supersession chain for a given sha256 using stored nodes."""
        # Build map: sha256 -> superseded_by_sha256 (what supersedes it)
        superseded_by_map: dict[str, str] = {}
        for node in self._nodes.values():
            if node.evidence and node.evidence.supersedes_sha256:
                superseded_by_map[node.evidence.supersedes_sha256] = node.content_hash

        rows: list[dict[str, Any]] = []
        for node in self._nodes.values():
            row: dict[str, Any] = {"sha256": node.content_hash}
            if node.content_hash in superseded_by_map:
                row["superseded_by_sha256"] = superseded_by_map[node.content_hash]
            rows.append(row)
        chain_result = resolve_supersession_chain(sha256, rows)
        found = chain_result["length"] > 0
        latest = chain_result["chain"][-1] if chain_result["chain"] else None
        return {
            "found": found,
            "chain_length": chain_result["length"],
            "latest_sha256": latest or "",
            "chain": chain_result["chain"],
            "cycle_detected": chain_result.get("cycle_detected", False),
        }

    def get_evidence_report(self) -> dict[str, Any]:
        """Generate a summary evidence report across all stored nodes."""
        total = len(self._nodes)
        if total == 0:
            return {
                "total_nodes": 0,
                "nodes_with_evidence": 0,
                "nodes_without_evidence": 0,
                "revoked_count": 0,
                "tombstoned_count": 0,
                "stale_count": 0,
                "average_confidence": 0.0,
                "trust_tier_counts": {},
                "provenance_grade_counts": {},
            }

        with_evidence = 0
        revoked = 0
        tombstoned = 0
        stale = 0
        conf_sum = 0.0
        conf_count = 0
        trust_tier_counts: dict[str, int] = {}
        provenance_grade_counts: dict[str, int] = {}

        for node in self._nodes.values():
            ev = node.evidence
            if ev is not None:
                with_evidence += 1
                if ev.revoked:
                    revoked += 1
                if ev.tombstoned:
                    tombstoned += 1
                if ev.is_stale():
                    stale += 1
                conf_sum += ev.confidence
                conf_count += 1
                trust_tier_counts[ev.trust_tier] = trust_tier_counts.get(ev.trust_tier, 0) + 1
                provenance_grade_counts[ev.provenance_grade] = provenance_grade_counts.get(ev.provenance_grade, 0) + 1

        return {
            "total_nodes": total,
            "nodes_with_evidence": with_evidence,
            "nodes_without_evidence": total - with_evidence,
            "revoked_count": revoked,
            "tombstoned_count": tombstoned,
            "stale_count": stale,
            "average_confidence": conf_sum / conf_count if conf_count else 0.0,
            "trust_tier_counts": trust_tier_counts,
            "provenance_grade_counts": provenance_grade_counts,
        }


@dataclasses.dataclass
class EvidenceContract:
    sha256: str = ""
    confidence: float = 0.5
    trust_tier: str = "trusted"
    provenance_grade: str = "evidence-backed"
    source_authority_label: str = "canonical"
    source_file: str = ""
    collector: str = ""
    collected_at: str = ""
    fresh_until: str | None = None
    revoked: bool = False
    tombstoned: bool = False
    supersedes_sha256: str = ""
    artifact_form: str = "test-artifact"
    memory_stratum: str = "working"
    storage_tier: str = "hot"
    collection_metadata: dict[str, Any] | None = None
    workflow_run_url: str = ""

    _VALID_TRUST_TIERS = {"verified", "validated", "trusted", "untrusted", "local", "normalized"}
    _VALID_PROVENANCE = {"evidence-backed", "declared", "heuristic", "none"}
    _VALID_AUTHORITIES = {"canonical", "derived", "advisory", "unverified", "external", "draft"}
    _VALID_ARTIFACT_FORMS = {"test-artifact", "governance-report", "memory-node", "specification", "fixture",
                             "raw_intake", "canonical_knowledge"}
    _VALID_MEMORY_STRATA = {"working", "archive", "cache", "episodic", "semantic", "provenance"}
    _VALID_STORAGE_TIERS = {"hot", "warm", "cold"}

    def validate(self) -> tuple[bool, list[str]]:
        errors = []
        if not self.sha256:
            errors.append("sha256 is required")
        elif not re.fullmatch(r"[0-9a-fA-F]{64}", self.sha256):
            errors.append("sha256 must be 64 hex characters")
        if self.confidence < 0.0 or self.confidence > 1.0:
            errors.append("confidence must be in [0.0, 1.0]")
        if self.trust_tier not in self._VALID_TRUST_TIERS:
            errors.append(f"trust_tier must be one of {sorted(self._VALID_TRUST_TIERS)}")
        if self.provenance_grade not in self._VALID_PROVENANCE:
            errors.append(f"provenance_grade must be one of {sorted(self._VALID_PROVENANCE)}")
        if self.source_authority_label not in self._VALID_AUTHORITIES:
            errors.append(f"source_authority_label must be one of {sorted(self._VALID_AUTHORITIES)}")
        if self.artifact_form not in self._VALID_ARTIFACT_FORMS:
            errors.append(f"artifact_form must be one of {sorted(self._VALID_ARTIFACT_FORMS)}")
        if self.memory_stratum not in self._VALID_MEMORY_STRATA:
            errors.append(f"memory_stratum must be one of {sorted(self._VALID_MEMORY_STRATA)}")
        if self.storage_tier not in self._VALID_STORAGE_TIERS:
            errors.append(f"storage_tier must be one of {sorted(self._VALID_STORAGE_TIERS)}")
        if self.supersedes_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", self.supersedes_sha256):
            errors.append("supersedes_sha256 must be 64 hex characters or empty")
        return len(errors) == 0, errors

    def is_stale(self, now_ts: float | None = None) -> bool:
        if self.fresh_until is None:
            return False
        try:
            from datetime import datetime as _dt
            parsed = _dt.fromisoformat(self.fresh_until)
            now = _dt.now(UTC) if now_ts is None else _dt.fromtimestamp(now_ts, tz=UTC)
            return parsed < now
        except (ValueError, OSError):
            return False

    def is_trusted_for_governance(self) -> bool:
        if self.revoked or self.tombstoned:
            return False
        if self.trust_tier not in ("verified", "validated"):
            return False
        if self.source_authority_label not in ("canonical", "derived"):
            return False
        return True

    def has_source_lineage(self) -> bool:
        return bool(self.source_file and self.collector and self.collected_at)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "sha256": self.sha256,
            "confidence": self.confidence,
            "trust_tier": self.trust_tier,
            "provenance_grade": self.provenance_grade,
            "source_authority_label": self.source_authority_label,
            "source_file": self.source_file,
            "collector": self.collector,
            "collected_at": self.collected_at,
            "fresh_until": self.fresh_until,
            "revoked": self.revoked,
            "tombstoned": self.tombstoned,
            "supersedes_sha256": self.supersedes_sha256,
            "artifact_form": self.artifact_form,
            "memory_stratum": self.memory_stratum,
            "storage_tier": self.storage_tier,
            "workflow_run_url": self.workflow_run_url,
        }
        if self.collection_metadata is not None:
            result["collection_metadata"] = self.collection_metadata
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EvidenceContract":
        if not data:
            return cls()
        return cls(
            sha256=data.get("sha256", ""),
            confidence=data.get("confidence", 0.5),
            trust_tier=data.get("trust_tier", "trusted"),
            provenance_grade=data.get("provenance_grade", "evidence-backed"),
            source_authority_label=data.get("source_authority_label", "canonical"),
            source_file=data.get("source_file", ""),
            collector=data.get("collector", ""),
            collected_at=data.get("collected_at", ""),
            fresh_until=data.get("fresh_until"),
            revoked=data.get("revoked", False),
            tombstoned=data.get("tombstoned", False),
            supersedes_sha256=data.get("supersedes_sha256", ""),
            artifact_form=data.get("artifact_form", "test-artifact"),
            memory_stratum=data.get("memory_stratum", "working"),
            storage_tier=data.get("storage_tier", "hot"),
            collection_metadata=data.get("collection_metadata"),
            workflow_run_url=data.get("workflow_run_url", ""),
        )

    @classmethod
    def normalize(cls, data: dict[str, Any] | None) -> "EvidenceContract":
        """Normalize a raw evidence dict from the RAG/storage layer into a valid EvidenceContract.

        Handles the divergences between rag/memory.py output format and EvidenceContract fields:
        - ``freshness_status`` / ``superseded`` (rag) vs ``fresh_until`` / ``supersedes_sha256`` (contract)
        - ``revoked`` / ``tombstoned`` as int (SQLite) vs bool
        - ``source_lineage`` nested dict → flat ``source_file`` / ``collector`` / ``collected_at``
        - Extra storage-layer fields go into ``collection_metadata``
        """
        if not data:
            return cls()

        # ── Core identity ──────────────────────────────────────────────────
        sha256 = str(data.get("sha256", "") or data.get("content_hash", "") or "").strip()

        # ── Boolean coercion (SQLite uses INTEGER 0/1) ─────────────────────
        revoked = bool(data.get("revoked", False))
        tombstoned = bool(data.get("tombstoned", False))

        # ── Trust tier ─────────────────────────────────────────────────────
        trust_tier = str(data.get("trust_tier") or "trusted").strip().lower()
        if trust_tier not in cls._VALID_TRUST_TIERS:
            trust_tier = "trusted"

        # ── Provenance ─────────────────────────────────────────────────────
        provenance_grade = str(data.get("provenance_grade") or "declared").strip().lower()
        if provenance_grade not in cls._VALID_PROVENANCE:
            provenance_grade = "declared"

        # ── Authority ──────────────────────────────────────────────────────
        source_authority_label = str(
            data.get("source_authority_label") or "canonical"
        ).strip().lower()
        if source_authority_label not in cls._VALID_AUTHORITIES:
            source_authority_label = "canonical"

        # ── Source lineage (flat or nested) ────────────────────────────────
        source_lineage = data.get("source_lineage") if isinstance(data.get("source_lineage"), dict) else {}
        source_file = str(
            data.get("source_file") or data.get("source_path")
            or source_lineage.get("source_file") or source_lineage.get("source_path") or ""
        )
        collector = str(
            data.get("collector") or source_lineage.get("collector") or ""
        )
        collected_at = str(
            data.get("collected_at")
            or source_lineage.get("collected_at") or ""
        )
        source_capture = data.get("source_capture")
        if isinstance(source_capture, dict) and not collected_at:
            collected_at = str(source_capture.get("captured_at", ""))

        # ── Freshness ──────────────────────────────────────────────────────
        fresh_until = data.get("fresh_until") or None

        # ── Supersession ────────────────────────────────────────────────────
        supersedes_sha256 = str(
            data.get("supersedes_sha256") or data.get("superseded_by_sha256") or ""
        ).strip()
        if supersedes_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", supersedes_sha256):
            supersedes_sha256 = ""

        # ── Artifact form ──────────────────────────────────────────────────
        artifact_form = str(data.get("artifact_form") or "raw_intake").strip().lower()
        if artifact_form not in cls._VALID_ARTIFACT_FORMS:
            artifact_form = "raw_intake"

        # ── Memory stratum ─────────────────────────────────────────────────
        memory_stratum = str(data.get("memory_stratum") or "working").strip().lower()
        if memory_stratum not in cls._VALID_MEMORY_STRATA:
            memory_stratum = "working"

        # ── Storage tier ───────────────────────────────────────────────────
        storage_tier = str(data.get("storage_tier") or "hot").strip().lower()
        if storage_tier not in cls._VALID_STORAGE_TIERS:
            storage_tier = "hot"

        # ── Workflow URL ───────────────────────────────────────────────────
        workflow_run_url = str(data.get("workflow_run_url") or "")

        # ── Confidence ─────────────────────────────────────────────────────
        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        # ── Collection metadata (capture excess storage-layer fields) ───────
        known_keys = {
            "sha256", "content_hash", "confidence", "trust_tier", "provenance_grade",
            "source_authority_label", "source_file", "source_path", "collector",
            "collected_at", "fresh_until", "freshness_status", "revoked", "tombstoned",
            "supersedes_sha256", "superseded", "artifact_form", "memory_stratum",
            "storage_tier", "workflow_run_url", "source_lineage", "source_capture",
            "operator_summary", "operator_identity", "admission_decision",
            "salience_score", "promotion_eligible", "state", "topic", "content",
            "provenance", "tags", "entry_kind", "domain", "solution_kind",
            "evaluation", "evaluation_id", "evaluation_authority",
            "content_hash_valid", "integrity_status", "supersession_chain_length",
            "pointer", "pointer_alias", "artifact_contract", "artifact_kind",
            "canonicalized", "source_lineage_present", "source_lineage_hash",
        }
        excess = {k: v for k, v in data.items() if k not in known_keys}
        collection_metadata = data.get("collection_metadata")
        if isinstance(collection_metadata, dict) and collection_metadata:
            excess = {**collection_metadata, **excess}
        elif not excess:
            collection_metadata = None
        else:
            collection_metadata = excess

        return cls(
            sha256=sha256,
            confidence=confidence,
            trust_tier=trust_tier,
            provenance_grade=provenance_grade,
            source_authority_label=source_authority_label,
            source_file=source_file,
            collector=collector,
            collected_at=collected_at,
            fresh_until=fresh_until,
            revoked=revoked,
            tombstoned=tombstoned,
            supersedes_sha256=supersedes_sha256,
            artifact_form=artifact_form,
            memory_stratum=memory_stratum,
            storage_tier=storage_tier,
            collection_metadata=collection_metadata,
            workflow_run_url=workflow_run_url,
        )


@dataclasses.dataclass
class FreshnessVerdict:
    admissible: bool
    freshness_status: str = "fresh"
    reasons: list[str] = dataclasses.field(default_factory=list)
    superseded_by_sha256: str = ""
    supersession_chain_length: int = 0


def validate_evidence_contract(contract: EvidenceContract) -> tuple[bool, list[str]]:
    return contract.validate()


def merge_evidence_contracts(a: EvidenceContract, b: EvidenceContract) -> EvidenceContract:
    """Merge two contracts: b's non-default values override a's, except for revocation flags which OR."""
    def _is_default(name: str, value: Any) -> bool:
        defaults = {
            "sha256": "", "confidence": 0.5, "trust_tier": "trusted",
            "provenance_grade": "evidence-backed", "source_authority_label": "canonical",
            "source_file": "", "collector": "", "collected_at": "",
            "fresh_until": None, "revoked": False, "tombstoned": False,
            "supersedes_sha256": "", "artifact_form": "test-artifact",
            "memory_stratum": "working", "storage_tier": "hot",
            "workflow_run_url": "",
        }
        return name in defaults and value == defaults[name]

    fields = dataclasses.fields(EvidenceContract)
    merged = {}
    for f in fields:
        av = getattr(a, f.name)
        bv = getattr(b, f.name)
        if f.name in ("revoked", "tombstoned"):
            merged[f.name] = av or bv
        elif f.name == "confidence":
            merged[f.name] = max(av, bv)
        elif f.name == "source_authority_label":
            # Upgrade: canonical > derived > advisory > unverified
            rank = {"canonical": 4, "derived": 3, "advisory": 2, "unverified": 1}
            merged[f.name] = av if rank.get(av, 0) >= rank.get(bv, 0) else bv
        elif f.name == "provenance_grade":
            rank = {"evidence-backed": 4, "declared": 3, "heuristic": 2, "none": 1}
            merged[f.name] = av if rank.get(av, 0) >= rank.get(bv, 0) else bv
        elif f.name == "artifact_form":
            rank = {"governance-report": 5, "specification": 4, "fixture": 3, "memory-node": 2, "test-artifact": 1}
            ra = rank.get(av, 0)
            rb = rank.get(bv, 0)
            if ra > rb:
                merged[f.name] = av
            elif rb > ra:
                merged[f.name] = bv
            elif not _is_default(f.name, bv):
                merged[f.name] = bv
            else:
                merged[f.name] = av
        elif f.name == "fresh_until":
            # Use the later (fresher) date
            if av is None:
                merged[f.name] = bv
            elif bv is None:
                merged[f.name] = av
            else:
                merged[f.name] = av if av >= bv else bv
        elif f.name == "collection_metadata":
            merged_meta = dict(av or {})
            if bv:
                merged_meta.update(bv)
            merged[f.name] = merged_meta if merged_meta else None
        elif isinstance(av, str) and not av and isinstance(bv, str) and bv:
            merged[f.name] = bv  # non-empty string from b overrides empty from a
        elif not _is_default(f.name, bv):
            merged[f.name] = bv
        else:
            merged[f.name] = av
    return EvidenceContract(**merged)


def build_evidence_chain_hash(contract: EvidenceContract) -> str:
    """Deterministic SHA-256 chain hash of contract fields."""
    d = contract.to_dict()
    # Sort keys for determinism, exclude collection_metadata which is unstructured
    d.pop("collection_metadata", None)
    canonical = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def check_evidence_freshness(
    evidence_row: dict[str, Any],
    purpose: str = "default",
) -> FreshnessVerdict:
    """Check if a memory evidence row is fresh/admissible for the given purpose."""
    freshness = evidence_row.get("freshness_status", "fresh")
    superseded = evidence_row.get("superseded_by_sha256", "")
    revoked = evidence_row.get("revoked", False)
    tombstoned = evidence_row.get("tombstoned", False)
    content_hash_valid = evidence_row.get("content_hash_valid", True)

    # Mandatory purposes reject stale, revoked, tombstoned, superseded
    mandatory_purposes = {"execution_admission", "governance_vote", "audit_entry"}
    overridable_purposes = {"default", "memory_recall", "dream_cycle"}
    unrestricted_purposes = {"benchmark", "dream_proposal", "media_synthesis"}

    # Tampered content hash is always hard-rejected regardless of purpose
    if content_hash_valid is False:
        return FreshnessVerdict(False, "tampered", ["Content hash does not match — evidence may be tampered"])

    if purpose in unrestricted_purposes:
        reasons = []
        if freshness == "stale":
            reasons.append("Evidence is stale but admitted under unrestricted purpose")
        if superseded:
            reasons.append(f"Superseded by {superseded} but admitted under unrestricted purpose")
        return FreshnessVerdict(
            admissible=True,
            freshness_status=freshness,
            reasons=reasons,
            superseded_by_sha256=superseded,
        )

    if revoked:
        return FreshnessVerdict(False, "revoked", ["Evidence has been revoked"])
    if tombstoned:
        return FreshnessVerdict(False, "tombstoned", ["Evidence has been tombstoned"])

    if purpose in mandatory_purposes:
        if freshness == "stale":
            return FreshnessVerdict(False, "stale", ["Evidence is stale"], superseded_by_sha256=superseded)
        if superseded:
            return FreshnessVerdict(False, "superseded", [f"Superseded by {superseded}"], superseded_by_sha256=superseded, supersession_chain_length=1)
        return FreshnessVerdict(True, freshness)

    # Overridable: flag but don't reject
    if freshness == "stale" or superseded:
        return FreshnessVerdict(
            True, freshness,
            reasons=["Evidence is flagged but admitted (overridable purpose)"],
            superseded_by_sha256=superseded,
        )
    return FreshnessVerdict(True, freshness)


def resolve_supersession_chain(
    sha256: str,
    rows: list[dict[str, Any]],
    max_depth: int = 50,
) -> dict[str, Any]:
    """Walk the supersession chain from the given sha256 through the rows."""
    visited = set()
    chain = []
    current = sha256
    depth = 0

    while current and depth < max_depth:
        if current in visited:
            return {
                "head": sha256,
                "chain": chain,
                "length": len(chain),
                "cycle_detected": True,
                "terminal": current,
            }
        visited.add(current)
        # Find row with matching sha256
        match = None
        for row in rows:
            if row.get("sha256", row.get("content_hash", "")) == current:
                match = row
                break
        if not match:
            break
        chain.append(current)
        next_hash = match.get("superseded_by_sha256", "") or match.get("supersedes_sha256", "")
        current = next_hash
        depth += 1

    return {
        "head": sha256,
        "chain": chain,
        "length": len(chain),
        "cycle_detected": False,
        "terminal": chain[-1] if chain else (sha256 if sha256 else None),
    }
