"""
ALS Schema Enforcement — Audit Logging Standard Schema.

Enforces a structured schema for all audit log entries across the
Sovereign OS. Ensures consistency, queryability, and tamper-evidence
for the Audit Logging Service (ALS).

Schema Fields (required):
  - timestamp: ISO 8601 UTC
  - event_type: Categorized event identifier
  - agent_id: Source agent SPIFFE ID or name
  - severity: INFO | WARNING | CRITICAL | FATAL
  - message: Human-readable description
  - correlation_id: Request/trace correlation

Schema Fields (optional):
  - metadata: Arbitrary key-value pairs
  - gas_consumed: Gas units for this event
  - duration_ms: Operation duration
  - parent_event_id: For event chains

Usage:
    schema = ALSSchema()
    entry = schema.create_entry(
        event_type="agent.execution.started",
        agent_id="sentinel",
        message="Sentinel daemon started",
    )
    validated = schema.validate(entry)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── Severity ───────────────────────────────────────────────────────────────

class ALSSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


# ─── Event Categories ───────────────────────────────────────────────────────

VALID_EVENT_PREFIXES = frozenset({
    "agent.",         # Agent lifecycle and actions
    "daemon.",        # Daemon events
    "security.",      # Security events (ALIGN, gates)
    "hlf.",           # HLF compilation, execution
    "tool.",          # Tool invocations
    "model.",         # Model routing events
    "gas.",           # Gas consumption events
    "governance.",    # ADR, policy changes
    "system.",        # System lifecycle
    "pipeline.",      # Pipeline execution
})


# ─── Schema Validation ─────────────────────────────────────────────────────

REQUIRED_FIELDS = frozenset({
    "event_id",
    "timestamp",
    "event_type",
    "agent_id",
    "severity",
    "message",
    "correlation_id",
})

OPTIONAL_FIELDS = frozenset({
    "metadata",
    "gas_consumed",
    "duration_ms",
    "parent_event_id",
    "source_file",
    "source_line",
    "tags",
})


@dataclass
class ValidationError:
    """A schema validation error."""
    field: str
    error: str

    def __str__(self) -> str:
        return f"{self.field}: {self.error}"


@dataclass
class ValidationResult:
    """Result of ALS schema validation."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [str(e) for e in self.errors],
            "warnings": self.warnings,
        }


# ─── ALS Entry ──────────────────────────────────────────────────────────────

@dataclass
class ALSEntry:
    """A structured audit log entry conforming to the ALS schema."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""
    agent_id: str = ""
    severity: ALSSeverity = ALSSeverity.INFO
    message: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: dict[str, Any] = field(default_factory=dict)
    gas_consumed: int | None = None
    duration_ms: float | None = None
    parent_event_id: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "severity": self.severity.value,
            "message": self.message,
            "correlation_id": self.correlation_id,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        if self.gas_consumed is not None:
            d["gas_consumed"] = self.gas_consumed
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.parent_event_id:
            d["parent_event_id"] = self.parent_event_id
        if self.tags:
            d["tags"] = self.tags
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


# ─── ALS Schema ─────────────────────────────────────────────────────────────

class ALSSchema:
    """ALS Schema validator and entry factory.

    Enforces consistent audit log entries across the entire system.
    """

    def __init__(self, *, strict: bool = True) -> None:
        self._strict = strict  # fail on unknown fields in strict mode

    def create_entry(
        self,
        event_type: str,
        agent_id: str,
        message: str,
        *,
        severity: ALSSeverity = ALSSeverity.INFO,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        gas_consumed: int | None = None,
        duration_ms: float | None = None,
        parent_event_id: str | None = None,
        tags: list[str] | None = None,
    ) -> ALSEntry:
        """Create a new ALS entry with defaults filled in."""
        entry = ALSEntry(
            event_type=event_type,
            agent_id=agent_id,
            message=message,
            severity=severity,
            metadata=metadata or {},
            gas_consumed=gas_consumed,
            duration_ms=duration_ms,
            parent_event_id=parent_event_id,
            tags=tags or [],
        )
        if correlation_id:
            entry.correlation_id = correlation_id
        return entry

    def validate(self, entry: ALSEntry | dict[str, Any]) -> ValidationResult:
        """Validate an entry against the ALS schema.

        Returns:
            ValidationResult with errors and warnings.
        """
        if isinstance(entry, ALSEntry):
            data = entry.to_dict()
        else:
            data = entry

        errors: list[ValidationError] = []
        warnings: list[str] = []

        # Check required fields
        for req in REQUIRED_FIELDS:
            if req not in data or not data[req]:
                errors.append(ValidationError(req, "required field missing or empty"))

        # Validate event_type format
        event_type = data.get("event_type", "")
        if event_type:
            has_valid_prefix = any(event_type.startswith(p) for p in VALID_EVENT_PREFIXES)
            if not has_valid_prefix:
                warnings.append(f"event_type '{event_type}' has no recognized prefix")

        # Validate severity
        severity = data.get("severity", "")
        if severity:
            try:
                ALSSeverity(severity)
            except ValueError:
                errors.append(ValidationError(
                    "severity",
                    f"Invalid severity: '{severity}'. Must be INFO|WARNING|CRITICAL|FATAL",
                ))

        # Validate timestamp
        ts = data.get("timestamp")
        if ts is not None:
            if not isinstance(ts, (int, float)):
                errors.append(ValidationError("timestamp", "must be numeric"))
            elif ts <= 0:
                errors.append(ValidationError("timestamp", "must be positive"))

        # Check for unknown fields in strict mode
        if self._strict:
            known = REQUIRED_FIELDS | OPTIONAL_FIELDS
            for key in data:
                if key not in known:
                    warnings.append(f"Unknown field: '{key}'")

        # Validate gas_consumed
        gas = data.get("gas_consumed")
        if gas is not None and (not isinstance(gas, int) or gas < 0):
            errors.append(ValidationError("gas_consumed", "must be non-negative integer"))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_batch(self, entries: list[ALSEntry | dict[str, Any]]) -> dict[str, Any]:
        """Validate multiple entries and return aggregate stats."""
        results = [self.validate(e) for e in entries]
        valid = sum(1 for r in results if r.valid)
        return {
            "total": len(entries),
            "valid": valid,
            "invalid": len(entries) - valid,
            "all_valid": valid == len(entries),
            "errors": [
                {"index": i, "errors": [str(e) for e in r.errors]}
                for i, r in enumerate(results) if not r.valid
            ],
        }


# ─── ALS Logger ─────────────────────────────────────────────────────────────

class ALSLogger:
    """Structured logger that writes ALS-compliant entries.

    Wraps the schema to provide a simple logging API.
    """

    def __init__(
        self,
        agent_id: str,
        *,
        schema: ALSSchema | None = None,
        max_buffer: int = 1000,
    ) -> None:
        self._agent_id = agent_id
        self._schema = schema or ALSSchema()
        self._buffer: list[ALSEntry] = []
        self._max_buffer = max_buffer

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    def log(
        self,
        event_type: str,
        message: str,
        *,
        severity: ALSSeverity = ALSSeverity.INFO,
        **kwargs: Any,
    ) -> ALSEntry:
        """Log an ALS entry."""
        entry = self._schema.create_entry(
            event_type=event_type,
            agent_id=self._agent_id,
            message=message,
            severity=severity,
            **kwargs,
        )
        if len(self._buffer) >= self._max_buffer:
            self._buffer.pop(0)
        self._buffer.append(entry)
        return entry

    def get_entries(
        self,
        *,
        limit: int = 50,
        severity: ALSSeverity | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get buffered entries with optional filters."""
        entries = list(self._buffer)
        if severity:
            entries = [e for e in entries if e.severity == severity]
        if event_type:
            entries = [e for e in entries if e.event_type.startswith(event_type)]
        entries.reverse()
        return [e.to_dict() for e in entries[:limit]]

    def flush(self, path: Path | str) -> int:
        """Flush buffer to a JSON Lines file."""
        p = Path(path)
        with p.open("a", encoding="utf-8") as f:
            for entry in self._buffer:
                f.write(entry.to_json() + "\n")
        count = len(self._buffer)
        self._buffer.clear()
        return count

    def clear(self) -> None:
        self._buffer.clear()
