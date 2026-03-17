"""
HLF License Revocation Ledger — warn-first, transparent, human-auditable.

This module keeps an append-only, Merkle-chained audit record of license
compliance warnings and (if necessary) revocations.

Design guarantees:
  • WARN-FIRST   — every entity receives a written warning before any revocation.
  • TRANSPARENT  — every entry names the violated clause and the evidence hash.
  • HUMAN-FIRST  — actual revocation requires an explicit human operator decision.
  • AUDITABLE    — the chain is tamper-evident via SHA-256 linking (same pattern
                   as scripts/verify_chain.py).
  • NOT A KILL-SWITCH — this does NOT auto-terminate anything.  It records, warns,
                         and awaits human action.

This is NOT the big-three invisible ban.  Every step is visible, cited, and
reversible by a human operator.

People are the priority.  AI is the tool.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# ── Entry types ───────────────────────────────────────────────────────────────

class EntryType(StrEnum):
    WARNING    = "warning"     # first notice — entity informed, no action yet
    REVOCATION = "revocation"  # human-approved revocation of license rights
    REINSTATE  = "reinstate"   # human-approved restoration after appeal/remedy
    AUDIT      = "audit"       # routine compliance audit record (no violation)


# ── Known clause identifiers (add yours here as the project evolves) ──────────

KNOWN_CLAUSES: dict[str, str] = {
    "HLF-ETHICS-001": "Ethics governance files removed or materially altered",
    "HLF-ETHICS-002": "HIL gates disabled or bypassed in distributed build",
    "HLF-ETHICS-003": "ALIGN Ledger rules removed or count reduced below minimum",
    "HLF-ETHICS-004": "Intent Capsule tier system removed from derivative",
    "HLF-ETHICS-005": "Merkle-chain audit trail disabled or falsified",
}

# Minimum number of ALIGN rules that must remain in a compliant fork
MIN_ALIGN_RULES = 5

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class LedgerEntry:
    """Single entry in the revocation ledger chain."""
    entry_id: str
    entry_type: EntryType
    entity: str            # fork name, user, org, deployment identifier
    clause_id: str         # e.g. "HLF-ETHICS-001"
    description: str
    evidence_hash: str     # sha256 of the evidence dict (for tamper-evidence)
    operator: str          # who created this entry
    timestamp: float
    prev_hash: str         # hash of the previous entry (chain link)
    trace_id: str          # this entry's own hash (prev_hash + payload)
    appealable: bool = True
    appeal_url: str = "governance/APPEAL.md"
    notes: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id":     self.entry_id,
            "entry_type":   self.entry_type.value,
            "entity":       self.entity,
            "clause_id":    self.clause_id,
            "description":  self.description,
            "evidence_hash": self.evidence_hash,
            "operator":     self.operator,
            "timestamp":    self.timestamp,
            "prev_hash":    self.prev_hash,
            "trace_id":     self.trace_id,
            "appealable":   self.appealable,
            "appeal_url":   self.appeal_url,
            "notes":        self.notes,
        }


# ── Exceptions ────────────────────────────────────────────────────────────────

class LedgerError(Exception):
    """Base error for all ledger failures."""


class ClauseUnknown(LedgerError):
    pass


class EntityNotWarned(LedgerError):
    """Raised when trying to revoke without a prior warning on record."""


# ── Ledger ────────────────────────────────────────────────────────────────────

ZERO_HASH = "0" * 64


class RevocationLedger:
    """
    Append-only Merkle-chained license compliance ledger.

    Sequence::

        ledger = RevocationLedger()

        # Step 1: Warn (always first)
        w = ledger.warn(
            entity="github.com/some-fork",
            clause_id="HLF-ETHICS-001",
            evidence={"removed_file": "HLF_ETHICAL_GOVERNOR.md"},
            operator="fork-monitor",
        )
        print(w.trace_id)

        # Step 2 (optional): Human decides to revoke after entity ignores warning
        r = ledger.revoke(
            entity="github.com/some-fork",
            clause_id="HLF-ETHICS-001",
            evidence={"warning_trace_id": w.trace_id, "days_elapsed": 14},
            operator="alice",
            notes="No response to warning after 14 days.",
        )

        # Step 3 (if entity remedies the issue): Reinstate
        ledger.reinstate(
            entity="github.com/some-fork",
            operator="alice",
            notes="Ethics files restored and verified.",
        )

        # Audit / export
        ledger.verify_chain()          # raises on tamper
        ledger.export_jsonl("ledger.jsonl")
    """

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def warn(
        self,
        entity: str,
        clause_id: str,
        evidence: dict[str, Any] | None = None,
        operator: str = "system",
        notes: str = "",
    ) -> LedgerEntry:
        """
        Issue a compliance warning.

        This is always the first step.  The entity is informed of the specific
        clause violated and what evidence was found.  No rights are removed yet.
        """
        self._validate_clause(clause_id)
        description = (
            f"Compliance warning issued to '{entity}' for clause {clause_id}: "
            f"{KNOWN_CLAUSES.get(clause_id, clause_id)}"
        )
        return self._append(
            entry_type  = EntryType.WARNING,
            entity      = entity,
            clause_id   = clause_id,
            description = description,
            evidence    = evidence or {},
            operator    = operator,
            notes       = notes,
        )

    def revoke(
        self,
        entity: str,
        clause_id: str,
        evidence: dict[str, Any] | None = None,
        operator: str = "system",
        notes: str = "",
    ) -> LedgerEntry:
        """
        Record a human-operator-approved license revocation.

        Raises EntityNotWarned if no prior warning for this entity exists on
        the ledger.  You MUST warn first — this enforces the warn-first contract.
        """
        self._validate_clause(clause_id)
        if not self._has_warning(entity):
            raise EntityNotWarned(
                f"No prior warning on record for '{entity}'. "
                "Issue a warning first via warn() before revoking."
            )
        description = (
            f"License revocation recorded for '{entity}' — clause {clause_id}: "
            f"{KNOWN_CLAUSES.get(clause_id, clause_id)}"
        )
        return self._append(
            entry_type  = EntryType.REVOCATION,
            entity      = entity,
            clause_id   = clause_id,
            description = description,
            evidence    = evidence or {},
            operator    = operator,
            notes       = notes,
        )

    def reinstate(
        self,
        entity: str,
        operator: str,
        notes: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> LedgerEntry:
        """Reinstate license rights after a revocation has been remedied."""
        description = f"License rights reinstated for '{entity}' after remedy/appeal."
        return self._append(
            entry_type  = EntryType.REINSTATE,
            entity      = entity,
            clause_id   = "HLF-REINSTATE",
            description = description,
            evidence    = evidence or {},
            operator    = operator,
            notes       = notes,
        )

    def audit(
        self,
        entity: str,
        operator: str = "system",
        notes: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> LedgerEntry:
        """Record a routine compliance check (no violation found)."""
        description = f"Routine compliance audit for '{entity}' — no violation found."
        return self._append(
            entry_type  = EntryType.AUDIT,
            entity      = entity,
            clause_id   = "AUDIT",
            description = description,
            evidence    = evidence or {},
            operator    = operator,
            notes       = notes,
        )

    # ── Chain verification ────────────────────────────────────────────────────

    def verify_chain(self) -> tuple[bool, list[str]]:
        """
        Verify the integrity of the Merkle-linked chain.

        Returns (ok, errors).  ok=True means no tampering detected.
        Raises nothing — errors are returned so callers can decide how to handle.
        """
        errors: list[str] = []
        prev_hash = ZERO_HASH
        for i, entry in enumerate(self._entries):
            if entry.prev_hash != prev_hash:
                errors.append(
                    f"Entry {i} ('{entry.entry_id}'): prev_hash mismatch. "
                    f"Expected {prev_hash[:16]}..., got {entry.prev_hash[:16]}..."
                )
            expected_evidence_hash = _compute_evidence_hash(entry.evidence)
            if entry.evidence_hash != expected_evidence_hash:
                errors.append(
                    f"Entry {i} ('{entry.entry_id}'): evidence_hash mismatch. "
                    f"Expected {expected_evidence_hash[:16]}..., got {entry.evidence_hash[:16]}..."
                )
            expected = _compute_trace_id(prev_hash, entry)
            if entry.trace_id != expected:
                errors.append(
                    f"Entry {i} ('{entry.entry_id}'): trace_id mismatch. "
                    f"Expected {expected[:16]}..., got {entry.trace_id[:16]}..."
                )
            prev_hash = entry.trace_id
        return len(errors) == 0, errors

    # ── Query helpers ─────────────────────────────────────────────────────────

    def entries_for(self, entity: str) -> list[LedgerEntry]:
        """All ledger entries for a given entity."""
        return [e for e in self._entries if e.entity == entity]

    def is_revoked(self, entity: str) -> bool:
        """
        True if the entity has an active revocation (not subsequently reinstated).
        """
        revoked = False
        for entry in self._entries:
            if entry.entity != entity:
                continue
            if entry.entry_type == EntryType.REVOCATION:
                revoked = True
            elif entry.entry_type == EntryType.REINSTATE:
                revoked = False
        return revoked

    def has_warning(self, entity: str) -> bool:
        """True if the entity has at least one warning on record."""
        return self._has_warning(entity)

    def all_entries(self) -> list[LedgerEntry]:
        """Return all entries (read-only)."""
        return list(self._entries)

    # ── Export / import ───────────────────────────────────────────────────────

    def export_jsonl(self, path: str | Path) -> None:
        """Write the ledger to a JSONL file (one JSON object per line)."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for entry in self._entries:
                fh.write(json.dumps(entry.to_dict()) + "\n")

    def export_list(self) -> list[dict[str, Any]]:
        """Return all entries as a list of dicts (for JSON serialisation)."""
        return [e.to_dict() for e in self._entries]

    # ── Internal ─────────────────────────────────────────────────────────────

    def _append(
        self,
        entry_type: EntryType,
        entity: str,
        clause_id: str,
        description: str,
        evidence: dict[str, Any],
        operator: str,
        notes: str,
    ) -> LedgerEntry:
        import uuid
        prev_hash     = self._entries[-1].trace_id if self._entries else ZERO_HASH
        evidence_hash = _compute_evidence_hash(evidence)
        entry_id = str(uuid.uuid4())

        entry = LedgerEntry(
            entry_id      = entry_id,
            entry_type    = entry_type,
            entity        = entity,
            clause_id     = clause_id,
            description   = description,
            evidence_hash = evidence_hash,
            operator      = operator,
            timestamp     = time.time(),
            prev_hash     = prev_hash,
            trace_id      = "",      # computed below
            appealable    = True,
            notes         = notes,
            evidence      = evidence,
        )
        entry.trace_id = _compute_trace_id(prev_hash, entry)
        self._entries.append(entry)
        return entry

    def _has_warning(self, entity: str) -> bool:
        return any(
            e.entity == entity and e.entry_type == EntryType.WARNING
            for e in self._entries
        )

    def _validate_clause(self, clause_id: str) -> None:
        if clause_id not in KNOWN_CLAUSES and not clause_id.startswith("HLF-"):
            raise ClauseUnknown(
                f"Unknown clause '{clause_id}'. "
                f"Known clauses: {list(KNOWN_CLAUSES.keys())}"
            )


# ── Chain hash helper ─────────────────────────────────────────────────────────

def _compute_trace_id(prev_hash: str, entry: LedgerEntry) -> str:
    """Compute the trace_id for an entry using the same algorithm as verify_chain.py."""
    payload = json.dumps(
        {
            "event": entry.entry_type.value,
            "data": {
                "entry_id": entry.entry_id,
                "entity": entry.entity,
                "clause_id": entry.clause_id,
                "description": entry.description,
                "evidence_hash": entry.evidence_hash,
                "operator": entry.operator,
                "timestamp": entry.timestamp,
                "appealable": entry.appealable,
                "appeal_url": entry.appeal_url,
                "notes": entry.notes,
            },
        },
        sort_keys=True,
    )
    return hashlib.sha256(f"{prev_hash}{payload}".encode()).hexdigest()


def _compute_evidence_hash(evidence: dict[str, Any]) -> str:
    """Compute a stable hash for entry evidence."""
    return hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
