"""HLF Knowledge — memory governance contract enforcement.

Provides freshness guarantees, cross-witness consistency proofs, and
memory lease management integrated with the witness governance and
entropy anchor subsystems.
"""

from hlf_mcp.hlf.knowledge.consistency_proof import (
    ConsistencyProof,
    ConsistencyProofResult,
)
from hlf_mcp.hlf.knowledge.freshness_guarantee import (
    FreshnessGuarantee,
    FreshnessGuaranteeChecker,
)
from hlf_mcp.hlf.knowledge.memory_lease import (
    LeaseManager,
    LeaseViolationError,
    MemoryLease,
)

__all__ = [
    "ConsistencyProof",
    "ConsistencyProofResult",
    "FreshnessGuarantee",
    "FreshnessGuaranteeChecker",
    "LeaseManager",
    "LeaseViolationError",
    "MemoryLease",
]
