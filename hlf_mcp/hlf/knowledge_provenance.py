"""Knowledge Provenance Chain — Merkle-linked derivation tracking and verification.

Provides:
- ProvenanceChain: Merkle-linked chain of knowledge derivations
- ProvenanceVerifier: verifies claims by walking provenance back to trusted roots
- ProvenanceGapDetector: identifies missing or broken provenance links
- TrustRootRegistry: trusted knowledge roots (constitution, benchmarks, operator-attested)
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ---------------------------------------------------------------------------
# Provenance Node
# ---------------------------------------------------------------------------

class DerivationKind(Enum):
    """How a knowledge claim was derived from its predecessors."""
    DIRECT_OBSERVATION = auto()   # empirically observed
    INFERENCE = auto()            # logically deduced from prior claims
    AGGREGATION = auto()          # combined from multiple sources
    TRANSFORMATION = auto()       # transformed/translated from prior claims
    EXTERNAL_IMPORT = auto()      # imported from external source
    OPERATOR_ATTESTED = auto()    # explicitly attested by a human operator
    CONSTITUTIONAL = auto()       # derived from constitutional rules
    BENCHMARK_VERIFIED = auto()   # verified through benchmark testing


@dataclass(slots=True)
class ProvenanceNode:
    """A single node in the knowledge provenance chain.

    Each node records how a knowledge claim was derived, what predecessors
    it depends on, and cryptographic evidence for the derivation.

    Attributes:
        node_id: Unique identifier for this provenance node.
        claim_hash: SHA-256 hash of the knowledge claim content.
        claim_content: The actual knowledge claim (or a summary).
        derivation_kind: How this claim was derived.
        predecessor_hashes: List of claim hashes this node depends on.
        merkle_hash: Merkle tree hash covering this node and predecessors.
        created_at: Unix timestamp of creation.
        creator_id: Identifier of the agent/process that created this claim.
        evidence: Supporting evidence for the derivation.
        metadata: Arbitrary additional metadata.
    """

    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    claim_hash: str = ""
    claim_content: str = ""
    derivation_kind: DerivationKind = DerivationKind.DIRECT_OBSERVATION
    predecessor_hashes: list[str] = field(default_factory=list)
    merkle_hash: str = ""
    created_at: float = field(default_factory=time.time)
    creator_id: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.claim_hash and self.claim_content:
            self.claim_hash = hashlib.sha256(
                self.claim_content.encode("utf-8")
            ).hexdigest()
        if not self.merkle_hash:
            self.merkle_hash = self._compute_merkle()

    def _compute_merkle(self) -> str:
        """Compute the Merkle hash for this node.

        The Merkle hash covers: claim_content + claim_hash + sorted predecessor_hashes +
        derivation_kind + creator_id + timestamp.
        """
        payload = json.dumps({
            "claim_hash": self.claim_hash,
            "claim_content": self.claim_content,
            "predecessors": sorted(self.predecessor_hashes),
            "derivation_kind": self.derivation_kind.name,
            "creator_id": self.creator_id,
            "created_at": self.created_at,
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify this node's Merkle hash is consistent."""
        return self.merkle_hash == self._compute_merkle()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "claim_hash": self.claim_hash,
            "claim_content": self.claim_content[:200] + "..."
                if len(self.claim_content) > 200 else self.claim_content,
            "derivation_kind": self.derivation_kind.name,
            "predecessor_hashes": self.predecessor_hashes,
            "merkle_hash": self.merkle_hash,
            "created_at": self.created_at,
            "creator_id": self.creator_id,
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Trust Root
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TrustRoot:
    """A trusted root in the knowledge provenance system.

    Trust roots are the ultimate anchors for provenance verification.
    Claims that can be traced back to a trust root are considered verified.

    Attributes:
        root_id: Unique identifier for this trust root.
        claim_hash: The hash of the trusted claim.
        root_type: Category of trust root.
        description: Human-readable description.
        attested_by: Who or what attested to this root.
        attested_at: When the attestation occurred.
        expires_at: Optional expiry for time-bounded trust roots.
        signature: Cryptographic signature over root fields.
    """

    root_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    claim_hash: str = ""
    root_type: str = ""  # constitutional, benchmark, operator_attested, etc.
    description: str = ""
    attested_by: str = ""
    attested_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.signature:
            self.signature = self._compute_signature()

    def _compute_signature(self) -> str:
        payload = json.dumps({
            "root_id": self.root_id,
            "claim_hash": self.claim_hash,
            "root_type": self.root_type,
            "description": self.description,
            "attested_by": self.attested_by,
            "attested_at": self.attested_at,
            "expires_at": self.expires_at,
        }, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def is_expired(self) -> bool:
        """Check if this trust root has expired."""
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    def verify(self) -> bool:
        """Verify the trust root's signature."""
        return self.signature == self._compute_signature() and not self.is_expired()

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "claim_hash": self.claim_hash,
            "root_type": self.root_type,
            "description": self.description,
            "attested_by": self.attested_by,
            "attested_at": self.attested_at,
            "expires_at": self.expires_at,
            "expired": self.is_expired(),
        }


# ---------------------------------------------------------------------------
# Trust Root Registry
# ---------------------------------------------------------------------------

class TrustRootRegistry:
    """Registry of trusted knowledge roots.

    Maintains the set of claims that serve as verification anchors for
    provenance chain walking. Supports registration, revocation, expiry,
    and lookup operations.
    """

    def __init__(self) -> None:
        self._roots: dict[str, TrustRoot] = {}  # root_id → TrustRoot
        self._by_hash: dict[str, list[str]] = {}  # claim_hash → [root_id, ...]
        self._by_type: dict[str, list[str]] = {}  # root_type → [root_id, ...]

    def register(
        self,
        claim_hash: str,
        root_type: str,
        description: str = "",
        attested_by: str = "",
        expires_at: float | None = None,
    ) -> TrustRoot:
        """Register a new trust root.

        Args:
            claim_hash: SHA-256 hash of the trusted claim.
            root_type: Category (constitutional, benchmark, operator_attested, etc.).
            description: Human-readable description.
            attested_by: Identifier of the attesting entity.
            expires_at: Optional Unix timestamp for expiry.

        Returns:
            The newly created TrustRoot.

        Raises:
            ValueError: If a trust root with this claim_hash already exists
                and is not expired.
        """
        # Check for existing non-expired root with same hash
        existing_ids = self._by_hash.get(claim_hash, [])
        for rid in existing_ids:
            existing = self._roots.get(rid)
            if existing and not existing.is_expired():
                raise ValueError(
                    f"Trust root for claim_hash '{claim_hash[:16]}...' already "
                    f"exists (root_id={rid})."
                )

        root = TrustRoot(
            claim_hash=claim_hash,
            root_type=root_type,
            description=description,
            attested_by=attested_by,
            expires_at=expires_at,
        )

        self._roots[root.root_id] = root
        self._by_hash.setdefault(claim_hash, []).append(root.root_id)
        self._by_type.setdefault(root_type, []).append(root.root_id)

        return root

    def revoke(self, root_id: str) -> bool:
        """Revoke a trust root by marking it expired.

        Args:
            root_id: The trust root ID to revoke.

        Returns:
            True if the root was found and revoked.
        """
        root = self._roots.get(root_id)
        if root is None:
            return False
        root.expires_at = time.time() - 1.0  # expired 1 second ago
        return True

    def lookup(self, claim_hash: str) -> TrustRoot | None:
        """Look up a trust root by claim hash.

        Returns the first active trust root matching the hash.

        Args:
            claim_hash: The claim hash to look up.

        Returns:
            TrustRoot if found and active, None otherwise.
        """
        root_ids = self._by_hash.get(claim_hash, [])
        for rid in root_ids:
            root = self._roots.get(rid)
            if root and root.verify():
                return root
        return None

    def is_trusted(self, claim_hash: str) -> bool:
        """Check if a claim hash corresponds to a trust root.

        Args:
            claim_hash: The claim hash to check.

        Returns:
            True if the claim is a registered, active trust root.
        """
        return self.lookup(claim_hash) is not None

    def list_by_type(self, root_type: str) -> list[TrustRoot]:
        """List all active trust roots of a given type.

        Args:
            root_type: The root type to filter by.

        Returns:
            List of active TrustRoots.
        """
        root_ids = self._by_type.get(root_type, [])
        return [
            self._roots[rid]
            for rid in root_ids
            if self._roots[rid].verify()
        ]

    def list_all(self) -> list[TrustRoot]:
        """List all active trust roots.

        Returns:
            List of all active TrustRoots.
        """
        return [r for r in self._roots.values() if r.verify()]

    def count(self) -> dict[str, int]:
        """Count trust roots by type.

        Returns:
            Dict mapping root_type to count of active roots.
        """
        counts: dict[str, int] = {}
        for r in self._roots.values():
            if r.verify():
                counts[r.root_type] = counts.get(r.root_type, 0) + 1
        return counts

    def cleanup_expired(self) -> int:
        """Remove expired trust roots from the registry.

        Returns:
            Number of roots cleaned up.
        """
        expired_ids = [
            rid for rid, r in self._roots.items() if r.is_expired()
        ]
        for rid in expired_ids:
            del self._roots[rid]
        return len(expired_ids)


# ---------------------------------------------------------------------------
# Provenance Chain
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProvenanceChain:
    """A Merkle-linked chain of knowledge derivation nodes.

    The chain starts from one or more trust roots and links each derived
    claim to its predecessors via cryptographic hashes. This enables
    verification of any claim by walking back to trusted roots.

    Attributes:
        chain_id: Unique identifier for this provenance chain.
        nodes: Ordered list of ProvenanceNodes in the chain.
        root_hashes: Set of claim hashes that are trust roots for this chain.
        created_at: Timestamp of chain creation.
    """

    chain_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nodes: list[ProvenanceNode] = field(default_factory=list)
    root_hashes: set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)

    def add_node(self, node: ProvenanceNode) -> ProvenanceNode:
        """Add a node to the provenance chain.

        Validates that all predecessor hashes reference nodes already in
        the chain or registered trust roots.

        Args:
            node: The ProvenanceNode to add.

        Returns:
            The added node (for chaining).

        Raises:
            ValueError: If a predecessor hash cannot be resolved.
        """
        known_hashes = {n.claim_hash for n in self.nodes} | self.root_hashes

        for pred_hash in node.predecessor_hashes:
            if pred_hash not in known_hashes:
                raise ValueError(
                    f"Predecessor hash '{pred_hash[:16]}...' not found in chain "
                    f"or trust roots. Add the predecessor first."
                )

        if not node.verify_integrity():
            raise ValueError(
                f"Node '{node.node_id}' failed integrity check — "
                "Merkle hash mismatch."
            )

        self.nodes.append(node)
        return node

    def get_node_by_hash(self, claim_hash: str) -> ProvenanceNode | None:
        """Find a node in the chain by its claim hash.

        Args:
            claim_hash: The claim hash to search for.

        Returns:
            ProvenanceNode if found, None otherwise.
        """
        for node in self.nodes:
            if node.claim_hash == claim_hash:
                return node
        return None

    def get_provenance_path(
        self, claim_hash: str, max_depth: int = 100
    ) -> list[ProvenanceNode]:
        """Walk the provenance path from a claim back to its roots.

        Args:
            claim_hash: The claim hash to trace.
            max_depth: Maximum depth to walk (prevents cycles).

        Returns:
            Ordered list of ProvenanceNodes from the claim to its deepest root.
        """
        path: list[ProvenanceNode] = []
        visited: set[str] = set()
        current_hash = claim_hash

        for _ in range(max_depth):
            if current_hash in visited:
                break  # cycle detected
            if current_hash in self.root_hashes:
                break  # reached a trust root

            node = self.get_node_by_hash(current_hash)
            if node is None:
                break  # dead end

            visited.add(current_hash)
            path.append(node)

            # Follow the first predecessor (depth-first)
            if node.predecessor_hashes:
                current_hash = node.predecessor_hashes[0]
            else:
                break  # leaf node

        return path

    def verify_chain_integrity(self) -> dict[str, Any]:
        """Verify the integrity of the entire provenance chain.

        Checks each node's Merkle hash and predecessor references.

        Returns:
            Dict with verification results.
        """
        violations: list[dict[str, Any]] = []
        known_hashes = set(self.root_hashes)

        for i, node in enumerate(self.nodes):
            node_violations: list[str] = []

            if not node.verify_integrity():
                node_violations.append("merkle_hash_mismatch")

            for pred_hash in node.predecessor_hashes:
                if pred_hash not in known_hashes:
                    node_violations.append(
                        f"unresolved_predecessor:{pred_hash[:16]}..."
                    )

            if node_violations:
                violations.append({
                    "node_index": i,
                    "node_id": node.node_id,
                    "claim_hash": node.claim_hash,
                    "violations": node_violations,
                })

            known_hashes.add(node.claim_hash)

        return {
            "valid": len(violations) == 0,
            "total_nodes": len(self.nodes),
            "violation_count": len(violations),
            "violations": violations,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "node_count": len(self.nodes),
            "root_count": len(self.root_hashes),
            "created_at": self.created_at,
            "nodes": [n.to_dict() for n in self.nodes],
            "root_hashes": list(self.root_hashes),
        }


# ---------------------------------------------------------------------------
# Provenance Verifier
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ProvenanceVerification:
    """Result of verifying a knowledge claim against its provenance.

    Attributes:
        verified: Whether the claim is fully verified.
        claim_hash: The hash of the claim that was verified.
        trust_root_found: Whether a trust root was reached.
        depth: Number of nodes traversed to reach a root.
        path: The provenance path from claim to root.
        gaps: Any gaps or breaks found in the provenance chain.
        confidence: Confidence in the verification (0.0 - 1.0).
        rationale: Human-readable explanation.
    """

    verified: bool
    claim_hash: str
    trust_root_found: bool
    depth: int
    path: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "claim_hash": self.claim_hash,
            "trust_root_found": self.trust_root_found,
            "depth": self.depth,
            "path": self.path,
            "gaps": self.gaps,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


class ProvenanceVerifier:
    """Verifies knowledge claims by walking provenance chains to trusted roots.

    Given a claim hash and a provenance chain, walks backward through
    derivation links until reaching a registered trust root or hitting
    a dead end.
    """

    def __init__(self, trust_registry: TrustRootRegistry | None = None) -> None:
        """Initialize the verifier.

        Args:
            trust_registry: Optional TrustRootRegistry for root lookup.
        """
        self._registry = trust_registry or TrustRootRegistry()

    def verify(
        self,
        claim_hash: str,
        chain: ProvenanceChain,
        max_depth: int = 100,
    ) -> ProvenanceVerification:
        """Verify a claim by walking its provenance chain.

        Args:
            claim_hash: The claim hash to verify.
            chain: The ProvenanceChain containing derivation history.
            max_depth: Maximum depth to walk.

        Returns:
            ProvenanceVerification with full analysis.
        """
        # Check if the claim itself is a trust root
        if self._registry.is_trusted(claim_hash):
            root = self._registry.lookup(claim_hash)
            return ProvenanceVerification(
                verified=True,
                claim_hash=claim_hash,
                trust_root_found=True,
                depth=0,
                path=[],
                gaps=[],
                confidence=1.0,
                rationale=f"Claim is a registered trust root (type: {root.root_type if root else 'unknown'}).",
            )

        # Walk the provenance path
        path: list[dict[str, Any]] = []
        gaps: list[str] = []
        visited: set[str] = set()
        current_hash = claim_hash
        depth = 0

        for _ in range(max_depth):
            if current_hash in visited:
                gaps.append(f"Cycle detected at depth {depth}: {current_hash[:16]}...")
                break
            visited.add(current_hash)

            # Check if we've reached a trust root
            if self._registry.is_trusted(current_hash):
                root = self._registry.lookup(current_hash)
                return ProvenanceVerification(
                    verified=True,
                    claim_hash=claim_hash,
                    trust_root_found=True,
                    depth=depth,
                    path=path,
                    gaps=gaps,
                    confidence=self._compute_confidence(depth, len(gaps), has_root=True),
                    rationale=f"Verified: reached trust root '{root.root_type}' at depth {depth}.",
                )

            # Also check chain root_hashes
            if current_hash in chain.root_hashes:
                return ProvenanceVerification(
                    verified=True,
                    claim_hash=claim_hash,
                    trust_root_found=True,
                    depth=depth,
                    path=path,
                    gaps=gaps,
                    confidence=self._compute_confidence(depth, len(gaps), has_root=True),
                    rationale=f"Verified: reached chain root at depth {depth}.",
                )

            node = chain.get_node_by_hash(current_hash)
            if node is None:
                gaps.append(
                    f"Missing provenance node for hash {current_hash[:16]}... at depth {depth}"
                )
                break

            path.append({
                "node_id": node.node_id,
                "claim_hash": node.claim_hash,
                "derivation_kind": node.derivation_kind.name,
                "depth": depth,
            })

            depth += 1

            if not node.predecessor_hashes:
                # Leaf node — no predecessors but not a trust root
                gaps.append(
                    f"Leaf node reached at depth {depth}: {current_hash[:16]}... "
                    "has no predecessors and is not a trust root."
                )
                break

            current_hash = node.predecessor_hashes[0]

        # Exhausted depth or hit a gap
        return ProvenanceVerification(
            verified=False,
            claim_hash=claim_hash,
            trust_root_found=False,
            depth=depth,
            path=path,
            gaps=gaps,
            confidence=self._compute_confidence(depth, len(gaps), has_root=False),
            rationale=(
                f"Verification incomplete: {len(gaps)} gap(s) found. "
                f"Walked {depth} nodes without reaching a trust root."
            ),
        )

    def verify_batch(
        self,
        claim_hashes: list[str],
        chain: ProvenanceChain,
    ) -> list[ProvenanceVerification]:
        """Verify multiple claims against a provenance chain.

        Args:
            claim_hashes: List of claim hashes to verify.
            chain: The ProvenanceChain.

        Returns:
            List of ProvenanceVerification results.
        """
        return [self.verify(ch, chain) for ch in claim_hashes]

    def verification_summary(
        self,
        results: list[ProvenanceVerification],
    ) -> dict[str, Any]:
        """Summarize a batch of verification results.

        Args:
            results: List of ProvenanceVerification results.

        Returns:
            Summary dict with pass/fail counts and gap analysis.
        """
        if not results:
            return {
                "total": 0,
                "verified": 0,
                "failed": 0,
                "average_depth": 0.0,
                "average_confidence": 0.0,
                "all_gaps": [],
            }

        verified = sum(1 for r in results if r.verified)
        failed = len(results) - verified
        avg_depth = sum(r.depth for r in results) / len(results)
        avg_conf = sum(r.confidence for r in results) / len(results)
        all_gaps: list[str] = []
        for r in results:
            all_gaps.extend(r.gaps)

        return {
            "total": len(results),
            "verified": verified,
            "failed": failed,
            "pass_rate_pct": round(verified / len(results) * 100, 1),
            "average_depth": round(avg_depth, 1),
            "average_confidence": round(avg_conf, 4),
            "all_gaps": all_gaps,
        }

    @staticmethod
    def _compute_confidence(depth: int, gap_count: int, has_root: bool) -> float:
        """Compute verification confidence from depth and gaps."""
        if has_root and gap_count == 0:
            # Shorter chains = higher confidence
            depth_penalty = min(depth / 20.0, 0.3)
            return round(1.0 - depth_penalty, 4)
        if has_root:
            gap_penalty = min(gap_count * 0.15, 0.5)
            return round(0.7 - gap_penalty, 4)
        return round(max(0.1, 0.5 - gap_count * 0.2), 4)


# ---------------------------------------------------------------------------
# Provenance Gap Detector
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GapReport:
    """Report of provenance gaps found in a knowledge graph.

    Attributes:
        total_nodes: Total nodes checked.
        gap_count: Number of gaps found.
        gaps: Detailed gap descriptions.
        orphan_nodes: Nodes with no predecessors and no trust root status.
        broken_links: Hashes referenced as predecessors but not found.
        recommendations: Suggested fixes for each gap.
    """

    total_nodes: int
    gap_count: int
    gaps: list[dict[str, Any]] = field(default_factory=list)
    orphan_nodes: list[str] = field(default_factory=list)
    broken_links: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "gap_count": self.gap_count,
            "gaps": self.gaps,
            "orphan_nodes": self.orphan_nodes,
            "broken_links": self.broken_links,
            "recommendations": self.recommendations,
        }


class ProvenanceGapDetector:
    """Identifies knowledge claims with missing or broken provenance links.

    Scans a ProvenanceChain for structural issues: orphan nodes, broken
    predecessor references, and claims that cannot be traced to any root.
    """

    def __init__(self, trust_registry: TrustRootRegistry | None = None) -> None:
        """Initialize the gap detector.

        Args:
            trust_registry: Optional TrustRootRegistry for root status checking.
        """
        self._registry = trust_registry or TrustRootRegistry()

    def detect_gaps(self, chain: ProvenanceChain) -> GapReport:
        """Detect all provenance gaps in a chain.

        Args:
            chain: The ProvenanceChain to analyze.

        Returns:
            GapReport with all detected issues.
        """
        total = len(chain.nodes)
        gaps: list[dict[str, Any]] = []
        orphans: list[str] = []
        broken: list[str] = []
        recommendations: list[str] = []

        if total == 0:
            return GapReport(
                total_nodes=0,
                gap_count=0,
                recommendations=["Chain is empty — add nodes and trust roots."],
            )

        known_hashes = set(chain.root_hashes)
        node_map: dict[str, ProvenanceNode] = {}

        for node in chain.nodes:
            node_map[node.claim_hash] = node

            # Check integrity
            if not node.verify_integrity():
                gaps.append({
                    "type": "integrity_failure",
                    "node_id": node.node_id,
                    "claim_hash": node.claim_hash,
                    "detail": "Merkle hash does not match computed hash.",
                })
                recommendations.append(
                    f"Node {node.node_id}: recompute and fix Merkle hash."
                )

            known_hashes.add(node.claim_hash)

        # Check each node's predecessors
        for node in chain.nodes:
            if not node.predecessor_hashes:
                # Check if it's an orphan
                if node.claim_hash not in chain.root_hashes and not self._registry.is_trusted(node.claim_hash):
                    orphans.append(node.claim_hash)
                    gaps.append({
                        "type": "orphan_node",
                        "node_id": node.node_id,
                        "claim_hash": node.claim_hash,
                        "detail": "No predecessors and not a trust root.",
                    })
                    recommendations.append(
                        f"Node {node.node_id}: either link to a predecessor "
                        "or register as a trust root."
                    )
                continue

            # Check predecessor references
            for pred_hash in node.predecessor_hashes:
                if pred_hash not in known_hashes:
                    broken.append(pred_hash)
                    gaps.append({
                        "type": "broken_link",
                        "node_id": node.node_id,
                        "claim_hash": node.claim_hash,
                        "missing_predecessor": pred_hash,
                        "detail": f"Predecessor {pred_hash[:16]}... not found.",
                    })
                    recommendations.append(
                        f"Node {node.node_id}: add node for missing predecessor "
                        f"{pred_hash[:16]}... or remove the reference."
                    )

        return GapReport(
            total_nodes=total,
            gap_count=len(gaps),
            gaps=gaps,
            orphan_nodes=orphans,
            broken_links=broken,
            recommendations=recommendations,
        )

    def detect_unreachable(
        self, chain: ProvenanceChain, target_hash: str
    ) -> dict[str, Any]:
        """Check if a specific claim is unreachable from any trust root.

        Args:
            chain: The ProvenanceChain to analyze.
            target_hash: The claim hash to check.

        Returns:
            Dict with reachability status and path information.
        """
        # BFS from all root hashes
        root_hashes = set(chain.root_hashes)
        for node in chain.nodes:
            if self._registry.is_trusted(node.claim_hash):
                root_hashes.add(node.claim_hash)

        node_map = {n.claim_hash: n for n in chain.nodes}

        visited: set[str] = set()
        queue = list(root_hashes)

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current == target_hash:
                return {
                    "reachable": True,
                    "target_hash": target_hash,
                    "from_roots": list(root_hashes & visited),
                }

            # Find nodes that list 'current' as predecessor
            for node in chain.nodes:
                if current in node.predecessor_hashes:
                    queue.append(node.claim_hash)

        return {
            "reachable": False,
            "target_hash": target_hash,
            "visited_count": len(visited),
            "reason": "No path from any trust root to target claim.",
        }

    def audit_chain(
        self, chain: ProvenanceChain
    ) -> dict[str, Any]:
        """Perform a comprehensive audit of a provenance chain.

        Combines gap detection, integrity verification, and reachability
        analysis into a single audit report.

        Args:
            chain: The ProvenanceChain to audit.

        Returns:
            Comprehensive audit dict.
        """
        gap_report = self.detect_gaps(chain)
        integrity = chain.verify_chain_integrity()

        # Reachability audit: check every node
        unreachable_count = 0
        for node in chain.nodes:
            if node.claim_hash not in chain.root_hashes:
                result = self.detect_unreachable(chain, node.claim_hash)
                if not result["reachable"]:
                    unreachable_count += 1

        return {
            "chain_id": chain.chain_id,
            "total_nodes": chain.nodes_count if hasattr(chain, 'nodes_count') else len(chain.nodes),
            "root_count": len(chain.root_hashes),
            "integrity_valid": integrity["valid"],
            "integrity_violations": integrity["violation_count"],
            "provenance_gaps": gap_report.gap_count,
            "orphan_count": len(gap_report.orphan_nodes),
            "broken_link_count": len(gap_report.broken_links),
            "unreachable_count": unreachable_count,
            "health_pct": round(
                100.0
                * (1.0 - gap_report.gap_count / max(len(chain.nodes), 1))
                * (1.0 if integrity["valid"] else 0.5),
                1,
            ),
            "recommendations": gap_report.recommendations,
        }
