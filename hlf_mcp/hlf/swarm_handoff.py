"""
Swarm Handoff — cryptographic handoff receipts, capability attestation,
and handoff timeout/abort contracts for swarm-to-swarm coordination.

Provides:
  - SwarmHandoffContract: defines the terms of a swarm-to-swarm handoff
  - HandoffReceipt: cryptographic receipt proving a handoff completed
  - CapabilityAttestation: verifiable attestation of swarm capabilities
  - SwarmHandoffManager: orchestrates handoff lifecycle with timeout/abort

Integration points:
  - hlf_mcp.hlf.orchestration_failure_recovery: vector clock for causal ordering
  - hlf_mcp.hlf.routing.capability_router: CapabilityRouter for attestation
  - hlf_mcp.persona.gate_integration: PersonaGate for persona-aware attestation
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# HandoffStatus enum
# ---------------------------------------------------------------------------


class HandoffStatus(str, Enum):
    """Status of a swarm-to-swarm handoff."""
    PENDING = "pending"
    NEGOTIATING = "negotiating"
    ATTESTING = "attesting"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    ABORTED = "aborted"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# SwarmHandoffContract — terms of a handoff
# ---------------------------------------------------------------------------


@dataclass
class SwarmHandoffContract:
    """Defines the terms of a swarm-to-swarm handoff.

    Attributes:
        contract_id: Unique contract identifier.
        source_swarm: Swarm handing off work.
        target_swarm: Swarm receiving work.
        required_capabilities: Capabilities the target must attest to.
        handoff_timeout_seconds: Maximum time for handoff to complete.
        required_gates: Gates that must pass (e.g., cove_review).
        payload_schema: Expected shape of the handoff payload.
        escalation_swarm: Swarm to escalate to on failure.
        metadata: Arbitrary key-value tags.
        created_at: Contract creation timestamp.
    """

    contract_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_swarm: str = ""
    target_swarm: str = ""
    required_capabilities: list[str] = field(default_factory=list)
    handoff_timeout_seconds: float = 60.0
    required_gates: list[str] = field(default_factory=list)
    payload_schema: dict[str, Any] = field(default_factory=dict)
    escalation_swarm: str = "operator"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "source_swarm": self.source_swarm,
            "target_swarm": self.target_swarm,
            "required_capabilities": list(self.required_capabilities),
            "handoff_timeout_seconds": self.handoff_timeout_seconds,
            "required_gates": list(self.required_gates),
            "payload_schema": dict(self.payload_schema),
            "escalation_swarm": self.escalation_swarm,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SwarmHandoffContract":
        return cls(
            contract_id=str(data.get("contract_id", str(uuid.uuid4()))),
            source_swarm=str(data.get("source_swarm", "")),
            target_swarm=str(data.get("target_swarm", "")),
            required_capabilities=[
                str(c) for c in data.get("required_capabilities", []) or []
            ],
            handoff_timeout_seconds=float(data.get("handoff_timeout_seconds", 60.0)),
            required_gates=[str(g) for g in data.get("required_gates", []) or []],
            payload_schema=dict(data.get("payload_schema", {})),
            escalation_swarm=str(data.get("escalation_swarm", "operator")),
            metadata=dict(data.get("metadata", {})),
            created_at=float(data.get("created_at", time.time())),
        )

    def is_expired(self, now: float | None = None) -> bool:
        """Check if the contract has exceeded its timeout."""
        t = now if now is not None else time.time()
        return (t - self.created_at) > self.handoff_timeout_seconds


# ---------------------------------------------------------------------------
# HandoffReceipt — cryptographic proof of handoff completion
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class HandoffReceipt:
    """Cryptographic receipt proving a handoff completed or was aborted.

    Attributes:
        receipt_id: Unique receipt identifier.
        contract_id: The handoff contract this receipt references.
        source_swarm: Swarm that handed off.
        target_swarm: Swarm that received.
        status: Final status of the handoff.
        payload_hash: SHA-256 of the transferred payload.
        attestation_hash: SHA-256 of the capability attestation.
        gate_results: Results of each required gate.
        signature: HMAC-SHA256 signature over receipt contents.
        issued_at: Timestamp of issuance.
        issuer: Node/persona that issued the receipt.
    """

    receipt_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str = ""
    source_swarm: str = ""
    target_swarm: str = ""
    status: str = HandoffStatus.PENDING.value
    payload_hash: str = ""
    attestation_hash: str = ""
    gate_results: list[dict[str, Any]] = field(default_factory=list)
    signature: str = ""
    issued_at: float = field(default_factory=time.time)
    issuer: str = ""

    def __post_init__(self) -> None:
        if not self.signature:
            self.signature = self._compute_signature()

    def _compute_signature(self) -> str:
        """Compute HMAC-SHA256 signature over the receipt contents."""
        payload = json.dumps(
            {
                "receipt_id": self.receipt_id,
                "contract_id": self.contract_id,
                "source_swarm": self.source_swarm,
                "target_swarm": self.target_swarm,
                "status": self.status,
                "payload_hash": self.payload_hash,
                "attestation_hash": self.attestation_hash,
                "gate_results": self.gate_results,
                "issued_at": self.issued_at,
                "issuer": self.issuer,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify(self) -> bool:
        """Verify the receipt's signature matches its contents."""
        return self.signature == self._compute_signature()

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "contract_id": self.contract_id,
            "source_swarm": self.source_swarm,
            "target_swarm": self.target_swarm,
            "status": self.status,
            "payload_hash": self.payload_hash,
            "attestation_hash": self.attestation_hash,
            "gate_results": list(self.gate_results),
            "signature": self.signature,
            "issued_at": self.issued_at,
            "issuer": self.issuer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandoffReceipt":
        return cls(
            receipt_id=str(data.get("receipt_id", str(uuid.uuid4()))),
            contract_id=str(data.get("contract_id", "")),
            source_swarm=str(data.get("source_swarm", "")),
            target_swarm=str(data.get("target_swarm", "")),
            status=str(data.get("status", HandoffStatus.PENDING.value)),
            payload_hash=str(data.get("payload_hash", "")),
            attestation_hash=str(data.get("attestation_hash", "")),
            gate_results=list(data.get("gate_results", []) or []),
            signature=str(data.get("signature", "")),
            issued_at=float(data.get("issued_at", time.time())),
            issuer=str(data.get("issuer", "")),
        )


# ---------------------------------------------------------------------------
# CapabilityAttestation — verifiable capability proof
# ---------------------------------------------------------------------------


@dataclass
class CapabilityAttestation:
    """Verifiable attestation of a swarm's capabilities.

    Attributes:
        attestation_id: Unique attestation identifier.
        swarm_id: Swarm being attested.
        capabilities: Map of capability_name → attested_level (0.0 to 1.0).
        attested_by: Entity that performed the attestation.
        valid_from: Attestation validity start.
        valid_until: Attestation expiry.
        checksum: SHA-256 integrity hash.
    """

    attestation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    swarm_id: str = ""
    capabilities: dict[str, float] = field(default_factory=dict)
    attested_by: str = ""
    valid_from: float = field(default_factory=time.time)
    valid_until: float = field(default_factory=lambda: time.time() + 86400)
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        payload = json.dumps(
            {
                "swarm_id": self.swarm_id,
                "capabilities": self.capabilities,
                "attested_by": self.attested_by,
                "valid_from": self.valid_from,
                "valid_until": self.valid_until,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def is_valid(self, now: float | None = None) -> bool:
        """Check if the attestation is currently valid."""
        t = now if now is not None else time.time()
        return self.valid_from <= t <= self.valid_until

    def satisfies(self, required: dict[str, float]) -> bool:
        """Check if this attestation satisfies all required capability levels.

        Args:
            required: Map of capability_name → minimum_level.

        Returns:
            True if all required capabilities are attested at sufficient levels.
        """
        for cap, min_level in required.items():
            attested_level = self.capabilities.get(cap, 0.0)
            if attested_level < min_level:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "attestation_id": self.attestation_id,
            "swarm_id": self.swarm_id,
            "capabilities": dict(self.capabilities),
            "attested_by": self.attested_by,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityAttestation":
        return cls(
            attestation_id=str(data.get("attestation_id", str(uuid.uuid4()))),
            swarm_id=str(data.get("swarm_id", "")),
            capabilities={
                str(k): float(v)
                for k, v in data.get("capabilities", {}).items()
            },
            attested_by=str(data.get("attested_by", "")),
            valid_from=float(data.get("valid_from", time.time())),
            valid_until=float(data.get("valid_until", time.time() + 86400)),
            checksum=str(data.get("checksum", "")),
        )

    def verify_integrity(self) -> bool:
        """Verify the attestation checksum."""
        return self.checksum == self._compute_checksum()


# ---------------------------------------------------------------------------
# SwarmHandoffManager — handoff lifecycle orchestrator
# ---------------------------------------------------------------------------


class SwarmHandoffManager:
    """Orchestrates swarm-to-swarm handoff lifecycle.

    Manages the full handoff flow:
      1. Contract negotiation — agree on required capabilities and gates
      2. Capability attestation — target swarm proves its capabilities
      3. Gate validation — required gates are checked
      4. Payload transfer — cryptographic receipt issued
      5. Timeout/abort — handles expiration and cancellation

    Usage::

        manager = SwarmHandoffManager()
        contract = manager.negotiate(
            source_swarm="swarm-a",
            target_swarm="swarm-b",
            required_capabilities=["code_generation", "test_execution"],
        )
        manager.provide_attestation("swarm-b", attestation)
        receipt = manager.complete_handoff(
            contract.contract_id,
            payload={"tasks": [...]},
        )
        assert receipt.status == HandoffStatus.COMPLETED.value
    """

    def __init__(
        self,
        max_active_handoffs: int = 100,
        default_timeout: float = 60.0,
    ) -> None:
        self._contracts: dict[str, SwarmHandoffContract] = {}
        self._attestations: dict[str, CapabilityAttestation] = {}
        self._receipts: dict[str, HandoffReceipt] = {}
        self._handoff_state: dict[str, dict[str, Any]] = {}
        self._max_active = max_active_handoffs
        self._default_timeout = default_timeout
        self._aborted_count: int = 0
        self._completed_count: int = 0

    # ------------------------------------------------------------------
    # Public API — negotiation
    # ------------------------------------------------------------------

    def negotiate(
        self,
        source_swarm: str,
        target_swarm: str,
        required_capabilities: list[str] | None = None,
        required_gates: list[str] | None = None,
        timeout_seconds: float | None = None,
        payload_schema: dict[str, Any] | None = None,
    ) -> SwarmHandoffContract:
        """Negotiate a new handoff contract.

        Args:
            source_swarm: Swarm handing off.
            target_swarm: Swarm receiving.
            required_capabilities: Capabilities the target must attest.
            required_gates: Gates that must pass.
            timeout_seconds: Handoff timeout.
            payload_schema: Expected payload shape.

        Returns:
            The negotiated SwarmHandoffContract.
        """
        contract = SwarmHandoffContract(
            source_swarm=source_swarm,
            target_swarm=target_swarm,
            required_capabilities=list(required_capabilities or []),
            required_gates=list(required_gates or ["cove_review"]),
            handoff_timeout_seconds=(
                timeout_seconds if timeout_seconds is not None else self._default_timeout
            ),
            payload_schema=dict(payload_schema or {}),
        )
        self._contracts[contract.contract_id] = contract
        self._handoff_state[contract.contract_id] = {
            "status": HandoffStatus.NEGOTIATING.value,
            "started_at": time.time(),
            "attestation_provided": False,
            "gates_passed": [],
            "gates_failed": [],
        }

        # Evict old handoffs if over capacity
        self._evict_if_needed()

        return contract

    def provide_attestation(
        self,
        contract_id: str,
        attestation: CapabilityAttestation,
    ) -> bool:
        """Provide a capability attestation for a handoff contract.

        Args:
            contract_id: The handoff contract ID.
            attestation: The capability attestation to provide.

        Returns:
            True if the attestation satisfies the contract requirements.
        """
        contract = self._contracts.get(contract_id)
        if contract is None:
            return False

        if contract.is_expired():
            self._update_state(contract_id, HandoffStatus.TIMED_OUT)
            return False

        self._attestations[contract_id] = attestation

        if not attestation.is_valid():
            self._update_state(contract_id, HandoffStatus.REJECTED, "attestation_expired")
            return False

        # Verify attestation satisfies required capabilities
        required_levels = {cap: 0.5 for cap in contract.required_capabilities}
        if not attestation.satisfies(required_levels):
            self._update_state(
                contract_id, HandoffStatus.REJECTED, "insufficient_capabilities"
            )
            return False

        self._handoff_state[contract_id]["attestation_provided"] = True
        self._update_state(contract_id, HandoffStatus.ATTESTING)
        return True

    def validate_gate(
        self, contract_id: str, gate_name: str, passed: bool, detail: str = ""
    ) -> dict[str, Any]:
        """Record the result of a gate validation.

        Args:
            contract_id: The handoff contract ID.
            gate_name: Name of the gate being validated.
            passed: Whether the gate passed.
            detail: Human-readable detail.

        Returns:
            Dict with gate result and current handoff status.
        """
        contract = self._contracts.get(contract_id)
        if contract is None:
            return {"error": "contract_not_found", "contract_id": contract_id}

        if contract.is_expired():
            self._update_state(contract_id, HandoffStatus.TIMED_OUT)
            return {"error": "contract_expired", "contract_id": contract_id}

        entry = {"gate": gate_name, "passed": passed, "detail": detail}
        state = self._handoff_state[contract_id]

        if passed:
            state["gates_passed"].append(entry)
        else:
            state["gates_failed"].append(entry)

        if state["gates_failed"]:
            self._update_state(contract_id, HandoffStatus.REJECTED, f"gate_failed:{gate_name}")
        elif self._all_required_gates_passed(contract_id):
            self._update_state(contract_id, HandoffStatus.ACCEPTED)

        return {
            "contract_id": contract_id,
            "gate": gate_name,
            "passed": passed,
            "handoff_status": state["status"],
        }

    def complete_handoff(
        self,
        contract_id: str,
        payload: dict[str, Any],
        issuer: str = "",
    ) -> HandoffReceipt | None:
        """Complete a handoff and issue a cryptographic receipt.

        Args:
            contract_id: The handoff contract ID.
            payload: The transferred payload.
            issuer: Entity issuing the receipt.

        Returns:
            HandoffReceipt if the handoff is accepted, None otherwise.
        """
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        state = self._handoff_state.get(contract_id, {})
        current_status = state.get("status", HandoffStatus.PENDING.value)

        if current_status not in (
            HandoffStatus.ACCEPTED.value,
            HandoffStatus.ATTESTING.value,
        ):
            return None

        if contract.is_expired():
            self._update_state(contract_id, HandoffStatus.TIMED_OUT)
            return None

        # Compute payload hash
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        # Compute attestation hash
        attestation = self._attestations.get(contract_id)
        attestation_hash = attestation.checksum if attestation else ""

        # Collect gate results
        gate_results = (
            state.get("gates_passed", []) + state.get("gates_failed", [])
        )

        receipt = HandoffReceipt(
            contract_id=contract_id,
            source_swarm=contract.source_swarm,
            target_swarm=contract.target_swarm,
            status=HandoffStatus.COMPLETED.value,
            payload_hash=payload_hash,
            attestation_hash=attestation_hash,
            gate_results=list(gate_results),
            issuer=issuer,
        )

        self._receipts[receipt.receipt_id] = receipt
        self._update_state(contract_id, HandoffStatus.COMPLETED)
        self._completed_count += 1

        return receipt

    def abort_handoff(
        self, contract_id: str, reason: str = "", issuer: str = ""
    ) -> HandoffReceipt | None:
        """Abort a handoff and issue an abort receipt.

        Args:
            contract_id: The handoff contract ID.
            reason: Why the handoff was aborted.
            issuer: Entity issuing the abort.

        Returns:
            HandoffReceipt with ABORTED status, or None if contract not found.
        """
        contract = self._contracts.get(contract_id)
        if contract is None:
            return None

        receipt = HandoffReceipt(
            contract_id=contract_id,
            source_swarm=contract.source_swarm,
            target_swarm=contract.target_swarm,
            status=HandoffStatus.ABORTED.value,
            gate_results=[{"gate": "abort", "passed": False, "detail": reason}],
            issuer=issuer,
        )

        self._receipts[receipt.receipt_id] = receipt
        self._update_state(contract_id, HandoffStatus.ABORTED)
        self._aborted_count += 1

        return receipt

    def check_timeouts(self) -> list[str]:
        """Check all active handoffs for timeout and expire them.

        Returns:
            List of contract IDs that timed out.
        """
        now = time.time()
        timed_out: list[str] = []

        for contract_id, contract in self._contracts.items():
            state = self._handoff_state.get(contract_id, {})
            status = state.get("status", HandoffStatus.PENDING.value)

            if status in (
                HandoffStatus.COMPLETED.value,
                HandoffStatus.ABORTED.value,
                HandoffStatus.TIMED_OUT.value,
                HandoffStatus.REJECTED.value,
            ):
                continue

            if contract.is_expired(now):
                self._update_state(contract_id, HandoffStatus.TIMED_OUT)
                timed_out.append(contract_id)

        return timed_out

    def get_contract(self, contract_id: str) -> SwarmHandoffContract | None:
        """Retrieve a handoff contract by ID."""
        return self._contracts.get(contract_id)

    def get_receipt(self, receipt_id: str) -> HandoffReceipt | None:
        """Retrieve a handoff receipt by ID."""
        return self._receipts.get(receipt_id)

    def get_status(self, contract_id: str) -> dict[str, Any]:
        """Get the current status of a handoff."""
        state = self._handoff_state.get(contract_id, {})
        contract = self._contracts.get(contract_id)
        return {
            "contract_id": contract_id,
            "status": state.get("status", "unknown"),
            "source_swarm": contract.source_swarm if contract else "",
            "target_swarm": contract.target_swarm if contract else "",
            "attestation_provided": state.get("attestation_provided", False),
            "gates_passed_count": len(state.get("gates_passed", [])),
            "gates_failed_count": len(state.get("gates_failed", [])),
            "elapsed_seconds": (
                time.time() - state.get("started_at", time.time())
                if state else 0
            ),
            "expired": contract.is_expired() if contract else False,
        }

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate handoff statistics."""
        now = time.time()
        total = len(self._contracts)
        active = sum(
            1 for cid, state in self._handoff_state.items()
            if state.get("status") not in (
                HandoffStatus.COMPLETED.value,
                HandoffStatus.ABORTED.value,
                HandoffStatus.TIMED_OUT.value,
                HandoffStatus.REJECTED.value,
            )
        )
        expired = sum(
            1 for c in self._contracts.values() if c.is_expired(now)
        )

        return {
            "total_contracts": total,
            "active_handoffs": active,
            "completed": self._completed_count,
            "aborted": self._aborted_count,
            "expired": expired,
            "receipts_issued": len(self._receipts),
        }

    def list_active_handoffs(self) -> list[dict[str, Any]]:
        """List all currently active handoffs."""
        active: list[dict[str, Any]] = []
        for contract_id, state in self._handoff_state.items():
            status = state.get("status", "")
            if status not in (
                HandoffStatus.COMPLETED.value,
                HandoffStatus.ABORTED.value,
                HandoffStatus.TIMED_OUT.value,
                HandoffStatus.REJECTED.value,
            ):
                active.append(self.get_status(contract_id))
        return active

    def clear(self) -> None:
        """Clear all contracts, attestations, and receipts."""
        self._contracts.clear()
        self._attestations.clear()
        self._receipts.clear()
        self._handoff_state.clear()
        self._aborted_count = 0
        self._completed_count = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update_state(
        self, contract_id: str, status: HandoffStatus, detail: str = ""
    ) -> None:
        """Update the state of a handoff."""
        if contract_id in self._handoff_state:
            self._handoff_state[contract_id]["status"] = status.value
            if detail:
                self._handoff_state[contract_id]["last_detail"] = detail

    def _all_required_gates_passed(self, contract_id: str) -> bool:
        """Check if all required gates for a contract have passed."""
        contract = self._contracts.get(contract_id)
        if contract is None:
            return False
        state = self._handoff_state.get(contract_id, {})
        passed_gate_names = {
            entry["gate"] for entry in state.get("gates_passed", [])
        }
        required = set(contract.required_gates)
        return required.issubset(passed_gate_names)

    def _evict_if_needed(self) -> None:
        """Evict oldest completed/aborted contracts if over capacity."""
        active = sum(
            1 for state in self._handoff_state.values()
            if state.get("status") not in (
                HandoffStatus.COMPLETED.value,
                HandoffStatus.ABORTED.value,
                HandoffStatus.TIMED_OUT.value,
                HandoffStatus.REJECTED.value,
            )
        )
        if active <= self._max_active:
            return

        # Evict oldest terminated contracts
        terminated = [
            (cid, c.created_at)
            for cid, c in self._contracts.items()
            if self._handoff_state.get(cid, {}).get("status") in (
                HandoffStatus.COMPLETED.value,
                HandoffStatus.ABORTED.value,
                HandoffStatus.TIMED_OUT.value,
                HandoffStatus.REJECTED.value,
            )
        ]
        terminated.sort(key=lambda x: x[1])

        to_remove = active - self._max_active
        for cid, _ in terminated[:to_remove]:
            self._contracts.pop(cid, None)
            self._handoff_state.pop(cid, None)
            self._attestations.pop(cid, None)
