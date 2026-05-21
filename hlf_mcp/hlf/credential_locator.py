"""Credential Locator — metadata registry for credential lifecycle management.

Stores REFERENCES to credentials (not secrets) — where they live,
when they expire, when they rotate, and their sensitivity.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Dataclass ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class CredentialRef:
    ref_id: str
    name: str
    credential_type: str  # "api_key" | "token" | "password" | "certificate" | "secret"
    location: str  # "env" | "vault" | "config_file" | "keyring" | "mcp_server"
    location_detail: str  # e.g., env var name, file path
    scope: str  # "global" | "service" | "agent" | "workflow"
    rotation_days: int = 0  # 0 = no rotation
    last_rotated: str | None = None
    expires_at: str | None = None
    is_valid: bool = True
    sensitivity: str = "medium"  # "low" | "medium" | "high" | "critical"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "name": self.name,
            "credential_type": self.credential_type,
            "location": self.location,
            "location_detail": self.location_detail,
            "scope": self.scope,
            "rotation_days": self.rotation_days,
            "last_rotated": self.last_rotated,
            "expires_at": self.expires_at,
            "is_valid": self.is_valid,
            "sensitivity": self.sensitivity,
        }


# ── CredentialLocator ──────────────────────────────────────────────────────────


class CredentialLocator:
    """Registry of credential metadata — stores references, not secrets."""

    def __init__(self, credentials: dict[str, CredentialRef] | None = None) -> None:
        self.credentials: dict[str, CredentialRef] = credentials or {}

    # ── Registration & lookup ──────────────────────────────────────────────

    def register(self, ref: CredentialRef) -> None:
        """Register a credential reference, overwriting any with the same ref_id."""
        self.credentials[ref.ref_id] = ref
        logger.info("Registered credential: %s (type=%s, location=%s)",
                     ref.ref_id, ref.credential_type, ref.location)

    def locate(self, name: str) -> CredentialRef | None:
        """Find a credential by name (matches against both ref_id and name field)."""
        for ref in self.credentials.values():
            if ref.ref_id == name or ref.name == name:
                return ref
        return None

    # ── Expiry & rotation ──────────────────────────────────────────────────

    def list_expiring(self, within_days: int = 30) -> list[CredentialRef]:
        """List credentials that expire within the given number of days."""
        now_ts = time.time()
        threshold = now_ts + (within_days * 86400)
        expiring: list[CredentialRef] = []
        for ref in self.credentials.values():
            if ref.expires_at is None:
                continue
            exp_ts = _parse_iso_to_unix(ref.expires_at)
            if exp_ts is not None and exp_ts <= threshold and ref.is_valid:
                expiring.append(ref)
        return sorted(expiring, key=lambda r: r.expires_at or "")

    def list_due_rotation(self) -> list[CredentialRef]:
        """List credentials whose rotation window has elapsed."""
        due: list[CredentialRef] = []
        for ref in self.credentials.values():
            if ref.rotation_days <= 0:
                continue
            if ref.last_rotated is None:
                # Never rotated — due immediately
                due.append(ref)
                continue
            rot_ts = _parse_iso_to_unix(ref.last_rotated)
            if rot_ts is None:
                due.append(ref)
                continue
            next_rotation = rot_ts + (ref.rotation_days * 86400)
            if time.time() >= next_rotation:
                due.append(ref)
        return due

    def mark_rotated(self, ref_id: str) -> None:
        """Update last_rotated to now for the given credential."""
        ref = self.credentials.get(ref_id)
        if ref is None:
            logger.warning("mark_rotated: unknown credential %s", ref_id)
            return
        ref.last_rotated = _iso_now()
        logger.info("Marked credential %s as rotated", ref_id)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def lifecycle_chain(self) -> list[dict[str, Any]]:
        """Return the full lifecycle chain for every credential.

        Stages: registered → active → expiring → rotated → retired.
        """
        stages: list[dict[str, Any]] = []
        for ref in self.credentials.values():
            stage = _determine_lifecycle_stage(ref)
            stages.append({
                "ref_id": ref.ref_id,
                "name": ref.name,
                "stage": stage,
                "is_valid": ref.is_valid,
                "sensitivity": ref.sensitivity,
                "expires_at": ref.expires_at,
                "last_rotated": ref.last_rotated,
            })
        return stages

    # ── Reporting ──────────────────────────────────────────────────────────

    def audit_report(self) -> str:
        """Generate a Markdown audit report: expiring, due rotation, invalid."""
        lines = ["# Credential Locator Audit Report", "", f"**Total credentials:** {len(self.credentials)}", ""]

        # Expiring
        expiring = self.list_expiring(within_days=30)
        lines.append(f"## Expiring (within 30 days) — {len(expiring)}")
        if expiring:
            lines.append("")
            lines.append("| ID | Name | Type | Expires | Sensitivity |")
            lines.append("|----|------|------|---------|-------------|")
            for ref in expiring:
                lines.append(f"| {ref.ref_id} | {ref.name} | {ref.credential_type} | "
                             f"{ref.expires_at} | **{ref.sensitivity.upper()}** |")
        else:
            lines.append("")
            lines.append("✅ None")

        # Due rotation
        due = self.list_due_rotation()
        lines.append("")
        lines.append(f"## Due Rotation — {len(due)}")
        if due:
            lines.append("")
            lines.append("| ID | Name | Rotation (days) | Last Rotated |")
            lines.append("|----|------|-----------------|--------------|")
            for ref in due:
                lr = ref.last_rotated or "never"
                lines.append(f"| {ref.ref_id} | {ref.name} | {ref.rotation_days} | {lr} |")
        else:
            lines.append("")
            lines.append("✅ None")

        # Invalid
        invalid = [ref for ref in self.credentials.values() if not ref.is_valid]
        lines.append("")
        lines.append(f"## Invalid — {len(invalid)}")
        if invalid:
            lines.append("")
            lines.append("| ID | Name | Type | Location | Sensitivity |")
            lines.append("|----|------|------|----------|-------------|")
            for ref in invalid:
                lines.append(f"| {ref.ref_id} | {ref.name} | {ref.credential_type} | "
                             f"{ref.location}:{ref.location_detail} | **{ref.sensitivity.upper()}** |")
        else:
            lines.append("")
            lines.append("✅ None")

        # Lifecycle summary
        stages = self.lifecycle_chain()
        lines.append("")
        lines.append("## Lifecycle Summary")
        lines.append("")
        lines.append("| ID | Name | Stage | Valid | Sensitivity |")
        lines.append("|----|------|-------|-------|-------------|")
        for s in stages:
            valid_icon = "✅" if s["is_valid"] else "❌"
            lines.append(f"| {s['ref_id']} | {s['name']} | {s['stage']} | "
                         f"{valid_icon} | **{s['sensitivity'].upper()}** |")

        return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso_to_unix(ts: str) -> float | None:
    """Parse an ISO 8601 timestamp to a Unix timestamp, or None if unparseable."""
    try:
        return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, OverflowError):
        return None


def _determine_lifecycle_stage(ref: CredentialRef) -> str:
    """Determine the current lifecycle stage of a credential."""
    if not ref.is_valid:
        return "retired"
    now = time.time()

    # Check expiry
    if ref.expires_at:
        exp_ts = _parse_iso_to_unix(ref.expires_at)
        if exp_ts is not None and now >= exp_ts:
            return "expired"

        # Expiring within 14 days
        if exp_ts is not None and (exp_ts - now) <= 14 * 86400:
            return "expiring"

    # Check rotation
    if ref.rotation_days > 0 and ref.last_rotated:
        rot_ts = _parse_iso_to_unix(ref.last_rotated)
        if rot_ts is not None:
            next_rotation = rot_ts + (ref.rotation_days * 86400)
            if now <= next_rotation:
                return "rotated"

    return "active"
