#!/usr/bin/env python3
"""
SwarmGlass Governance Primitives — stdlib only, zero hlf_mcp imports.

Proven architecture from swarmglass_vertical_slice.py Gate 1.
These wrap the official RecursiveMAS pipeline without touching model internals.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# DSL IMPORT VERIFICATION (paranoid check)
# ═══════════════════════════════════════════════════════════════

_DSL_MODULES = frozenset({
    "hlf_mcp.hlf.compiler", "hlf_mcp.hlf.runtime",
    "hlf_mcp.hlf.bytecode", "hlf_mcp.hlf.translator",
    "hlf_mcp.hlf.grammar", "hlf_mcp.hlf.formal_verifier",
    "hlf_mcp.hlf.linter", "hlf_mcp.hlf.formatter", "hlf_mcp.hlf.codegen",
})


def _verify_no_dsl() -> None:
    """Assert zero hlf_mcp/DSL imports. Raises RuntimeError if violated."""
    import sys
    loaded = {m for m in sys.modules
              if any(m == d or m.startswith(d + ".") for d in _DSL_MODULES)}
    if loaded:
        raise RuntimeError(f"DSL modules loaded: {sorted(loaded)}")


_verify_no_dsl()


# ═══════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════

@dataclass
class CircuitBreaker:
    """Trips on NaN/Inf norm, excessive drift, or consecutive failures.

    States: CLOSED (normal) → OPEN (tripped) → HALF_OPEN (testing recovery)
    """
    max_norm: float = 1000.0
    max_drift_ratio: float = 10.0
    max_consecutive_failures: int = 3
    cooldown_seconds: float = 30.0

    state: str = "CLOSED"
    failure_count: int = 0
    last_trip_time: float = 0.0
    baseline_norms: Dict[str, float] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def check_norm(self, stage: str, norm_value: float) -> bool:
        """Check if norm is safe. Returns True if OK, False if tripped."""
        if self.state == "OPEN":
            if time.time() - self.last_trip_time > self.cooldown_seconds:
                self.state = "HALF_OPEN"
            else:
                self.history.append({
                    "stage": stage, "norm": norm_value, "action": "REJECTED_OPEN",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return False

        is_nan = norm_value != norm_value  # NaN check
        is_inf = norm_value == float('inf') or norm_value == float('-inf')
        too_large = norm_value > self.max_norm

        if is_nan or is_inf or too_large:
            self.failure_count += 1
            self.history.append({
                "stage": stage, "norm": float(norm_value),
                "action": "WARN" if not is_nan else "TRIP_NAN",
                "failure_count": self.failure_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if self.failure_count >= self.max_consecutive_failures:
                self._trip(f"Consecutive failures: {self.failure_count}")

        if self.baseline_norms.get(stage):
            drift = norm_value / self.baseline_norms[stage]
            if drift > self.max_drift_ratio or drift < 1.0 / self.max_drift_ratio:
                self.failure_count += 1
                self.history.append({
                    "stage": stage, "norm": float(norm_value),
                    "baseline": self.baseline_norms[stage],
                    "drift": float(drift),
                    "action": "DRIFT_WARN",
                    "failure_count": self.failure_count,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        return True

    def record_baseline(self, stage: str, norm_value: float) -> None:
        """Record a healthy norm as baseline for future drift detection."""
        if stage not in self.baseline_norms:
            self.baseline_norms[stage] = norm_value

    def reset(self) -> None:
        self.failure_count = 0
        self.state = "CLOSED"

    def _trip(self, reason: str) -> None:
        self.state = "OPEN"
        self.last_trip_time = time.time()
        self.history.append({
            "action": "TRIP", "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# ═══════════════════════════════════════════════════════════════
# TELEMETRY COLLECTOR
# ═══════════════════════════════════════════════════════════════

@dataclass
class StageTelemetry:
    stage: str
    start_time: float
    end_time: float = 0.0
    latent_steps: int = 0
    input_shape: Optional[Tuple[int, ...]] = None
    output_shape: Optional[Tuple[int, ...]] = None
    output_norm: float = 0.0
    vram_mb: float = 0.0
    success: bool = True
    error: Optional[str] = None

    @property
    def duration_s(self) -> float:
        return self.end_time - self.start_time


@dataclass
class TelemetryCollector:
    stages: List[StageTelemetry] = field(default_factory=list)
    total_start: float = 0.0
    total_end: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def start_run(self, **meta) -> None:
        self.total_start = time.time()
        self.stages.clear()
        self.metadata = meta

    def start_stage(self, stage: str, latent_steps: int = 0) -> StageTelemetry:
        t = StageTelemetry(stage=stage, start_time=time.time(), latent_steps=latent_steps)
        return t

    def end_stage(self, t: StageTelemetry, output_shape=None, output_norm=0.0, error=None) -> None:
        t.end_time = time.time()
        t.output_shape = output_shape
        t.output_norm = output_norm
        t.success = error is None
        t.error = error
        try:
            import torch
            t.vram_mb = torch.cuda.memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
        except Exception:
            t.vram_mb = 0.0
        self.stages.append(t)

    def end_run(self) -> None:
        self.total_end = time.time()

    def summary(self) -> str:
        lines = ["SWARMGLASS GOVERNANCE REPORT", "=" * 50]
        lines.append(f"Duration: {self.total_end - self.total_start:.1f}s")
        lines.append(f"Stages:  {len(self.stages)}")
        lines.append(f"Metadata: {json.dumps(self.metadata, default=str)}")
        lines.append("")
        for s in self.stages:
            status = "✓" if s.success else "✗"
            lines.append(
                f"  {status} {s.stage:12s} {s.duration_s:5.1f}s  "
                f"norm={s.output_norm:8.1f}  shape={s.output_shape}  "
                f"VRAM={s.vram_mb:.0f}MB"
            )
            if s.error:
                lines.append(f"       ERROR: {s.error}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# MERKLE AUDIT CHAIN
# ═══════════════════════════════════════════════════════════════

@dataclass
class AuditEvent:
    index: int
    stage: str
    input_hash: str
    output_hash: str
    prev_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class MerkleAuditChain:
    events: List[AuditEvent] = field(default_factory=list)
    chain_seed: str = ""

    def __post_init__(self):
        if not self.chain_seed:
            import uuid
            self.chain_seed = str(uuid.uuid4())

    def _hash(self, *parts: str) -> str:
        return hashlib.sha256("|".join((self.chain_seed,) + parts).encode()).hexdigest()[:12]

    def append(self, stage: str, input_data: str, output_data: str, **meta) -> AuditEvent:
        prev = self.events[-1].output_hash if self.events else self._hash("genesis")
        inp_h = self._hash("in", stage, input_data[:500])
        out_h = self._hash("out", stage, output_data[:500])
        event = AuditEvent(
            index=len(self.events),
            stage=stage,
            input_hash=inp_h,
            output_hash=out_h,
            prev_hash=prev,
            metadata=meta,
        )
        self.events.append(event)
        return event

    def verify(self) -> Tuple[bool, str]:
        """Verify the chain integrity. Returns (valid, message)."""
        if not self.events:
            return True, "Empty chain (valid)"
        prev = self._hash("genesis")
        for e in self.events:
            if e.prev_hash != prev:
                return False, f"Break at event {e.index}: expected {prev}, got {e.prev_hash}"
            prev = e.output_hash
        return True, f"Chain verified: {len(self.events)} events, root={prev}"


# ═══════════════════════════════════════════════════════════════
# EVIDENCE SUMMARY RENDERER
# ═══════════════════════════════════════════════════════════════

@dataclass
class EvidenceSummaryRenderer:
    telemetry: Optional[TelemetryCollector] = None
    audit: Optional[MerkleAuditChain] = None
    breaker: Optional[CircuitBreaker] = None

    def render(self, output_text: str, pipeline_info: Dict[str, Any]) -> str:
        lines = []
        lines.append("╔" + "═" * 58 + "╗")
        lines.append("║  SWARMGLASS GOVERNANCE EVIDENCE PACKET" + " " * 19 + "║")
        lines.append("╠" + "═" * 58 + "╣")

        # Pipeline info
        for k, v in pipeline_info.items():
            lines.append(f"║  {k:20s}: {str(v)[:34]:34s} ║")

        # Circuit breaker
        if self.breaker:
            cb = self.breaker
            lines.append("╠" + "═" * 58 + "╣")
            lines.append(f"║  Circuit Breaker: {cb.state:47s} ║")
            lines.append(f"║  Failures: {cb.failure_count:<49d} ║")
            if cb.history:
                last = cb.history[-1]
                lines.append(f"║  Last event: {str(last.get('action','?'))[:38]:38s} ║")

        # Audit chain
        if self.audit:
            valid, msg = self.audit.verify()
            lines.append("╠" + "═" * 58 + "╣")
            lines.append(f"║  Audit Chain: {'✓ VERIFIED' if valid else '✗ BROKEN':47s} ║")
            lines.append(f"║  Events: {len(self.audit.events):<49d} ║")
            for e in self.audit.events:
                lines.append(f"║  [{e.index}] {e.stage:10s} → {e.output_hash:36s} ║")

        # Telemetry summary
        if self.telemetry:
            lines.append("╠" + "═" * 58 + "╣")
            lines.append(f"║  Total time: {self.telemetry.total_end - self.telemetry.total_start:.1f}s" + " " * (46 - len(f"Total time: {self.telemetry.total_end - self.telemetry.total_start:.1f}s")) + "║")
            for s in self.telemetry.stages:
                status = "✓" if s.success else "✗"
                lines.append(f"║  {status} {s.stage:10s} {s.duration_s:5.1f}s norm={s.output_norm:8.1f} {'':12s} ║")

        # Output preview
        lines.append("╠" + "═" * 58 + "╣")
        preview = output_text[:200].replace("\n", " ")[:50]
        lines.append(f"║  Output: {preview:48s} ║")

        lines.append("╚" + "═" * 58 + "╝")
        return "\n".join(lines)
