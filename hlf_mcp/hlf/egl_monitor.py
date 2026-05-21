"""
EGL (Evolutionary Generality Loss) Monitoring Pipeline.

Tracks whether the agent swarm is becoming too specialized (losing
generality) over time. Inspired by MAP-Elites quality-diversity
algorithms and Yunjue's EGL metric.

Key Concepts:
  - Diversity Score: How varied are agent behaviors across tasks?
  - Specialization Index: Is one agent dominating a capability?
  - Generality Loss %: Trend line showing capability narrowing.
  - Quality-Diversity Grid: MAP-Elites style behavior × performance map.

Usage:
    monitor = EGLMonitor()
    monitor.record_behavior("sentinel", "security.scan", performance=0.95)
    monitor.record_behavior("scribe", "security.scan", performance=0.72)
    report = monitor.get_egl_report()
"""

from __future__ import annotations

import math
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


# ─── Data Types ─────────────────────────────────────────────────────────────

@dataclass
class BehaviorRecord:
    """A single observed agent behavior."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = ""
    capability: str = ""          # e.g., "security.scan", "code.generate"
    performance: float = 0.0      # [0.0, 1.0]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "performance": self.performance,
            "timestamp": self.timestamp,
        }


@dataclass
class EGLMetric:
    """A point-in-time EGL measurement."""
    timestamp: float = field(default_factory=time.time)
    diversity_score: float = 0.0        # Shannon entropy of capability distribution
    specialization_index: float = 0.0   # Gini coefficient of agent dominance
    generality_loss_pct: float = 0.0    # % decrease from baseline diversity
    active_capabilities: int = 0
    active_agents: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "diversity_score": round(self.diversity_score, 4),
            "specialization_index": round(self.specialization_index, 4),
            "generality_loss_pct": round(self.generality_loss_pct, 2),
            "active_capabilities": self.active_capabilities,
            "active_agents": self.active_agents,
        }


@dataclass
class QDCell:
    """A cell in the Quality-Diversity grid (MAP-Elites inspired)."""
    capability: str = ""
    agent_id: str = ""
    best_performance: float = 0.0
    sample_count: int = 0
    last_updated: float = field(default_factory=time.time)


# ─── EGL Alert ──────────────────────────────────────────────────────────────

@dataclass
class EGLAlert:
    """An alert triggered by EGL threshold breach."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    alert_type: str = ""          # convergence | dominance | stagnation
    message: str = ""
    severity: str = "warning"     # warning | critical
    metric: EGLMetric | None = None
    timestamp: float = field(default_factory=time.time)


# ─── EGL Monitor ────────────────────────────────────────────────────────────

class EGLMonitor:
    """Tracks agent behavior diversity and detects generality loss.

    Uses Shannon entropy for diversity and Gini coefficient for
    specialization dominance detection.
    """

    def __init__(
        self,
        *,
        convergence_threshold: float = 0.3,
        dominance_threshold: float = 0.8,
        window_size: int = 100,
    ) -> None:
        self._records: list[BehaviorRecord] = []
        self._metrics_history: list[EGLMetric] = []
        self._alerts: list[EGLAlert] = []
        self._baseline_diversity: float | None = None

        # MAP-Elites grid: (capability, agent) → QDCell
        self._qd_grid: dict[tuple[str, str], QDCell] = {}

        # Config
        self._convergence_threshold = convergence_threshold
        self._dominance_threshold = dominance_threshold
        self._window_size = window_size

    @property
    def record_count(self) -> int:
        return len(self._records)

    def record_behavior(
        self,
        agent_id: str,
        capability: str,
        *,
        performance: float = 1.0,
    ) -> BehaviorRecord:
        """Record an observed agent behavior."""
        record = BehaviorRecord(
            agent_id=agent_id,
            capability=capability,
            performance=max(0.0, min(1.0, performance)),
        )
        self._records.append(record)

        # Update QD grid
        key = (capability, agent_id)
        cell = self._qd_grid.get(key)
        if cell is None:
            cell = QDCell(capability=capability, agent_id=agent_id)
            self._qd_grid[key] = cell
        cell.sample_count += 1
        cell.best_performance = max(cell.best_performance, record.performance)
        cell.last_updated = time.time()

        return record

    def compute_diversity(
        self, records: list[BehaviorRecord] | None = None
    ) -> float:
        """Compute Shannon entropy of capability distribution.

        Higher = more diverse. 0 = all behaviors identical.
        """
        recs = records or self._records[-self._window_size:]
        if not recs:
            return 0.0

        counts: dict[str, int] = defaultdict(int)
        for r in recs:
            counts[r.capability] += 1

        total = len(recs)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def compute_specialization(
        self, records: list[BehaviorRecord] | None = None
    ) -> float:
        """Compute Gini coefficient of agent capability dominance.

        0 = perfectly equal. 1 = one agent does everything.
        """
        recs = records or self._records[-self._window_size:]
        if not recs:
            return 0.0

        agent_counts: dict[str, int] = defaultdict(int)
        for r in recs:
            agent_counts[r.agent_id] += 1

        values = sorted(agent_counts.values())
        n = len(values)
        if n <= 1:
            return 0.0

        total = sum(values)
        cumulative = 0.0
        weighted_sum = 0.0
        for i, v in enumerate(values):
            cumulative += v
            weighted_sum += (i + 1) * v

        gini = (2 * weighted_sum) / (n * total) - (n + 1) / n
        return max(0.0, min(1.0, gini))

    def measure(self) -> EGLMetric:
        """Take a point-in-time EGL measurement."""
        recent = self._records[-self._window_size:]
        diversity = self.compute_diversity(recent)
        specialization = self.compute_specialization(recent)

        # Set baseline on first measurement
        if self._baseline_diversity is None and diversity > 0:
            self._baseline_diversity = diversity

        # Generality loss
        loss_pct = 0.0
        if self._baseline_diversity and self._baseline_diversity > 0:
            loss_pct = max(
                0.0,
                (1 - diversity / self._baseline_diversity) * 100,
            )

        agents = set(r.agent_id for r in recent)
        capabilities = set(r.capability for r in recent)

        metric = EGLMetric(
            diversity_score=diversity,
            specialization_index=specialization,
            generality_loss_pct=loss_pct,
            active_capabilities=len(capabilities),
            active_agents=len(agents),
        )
        self._metrics_history.append(metric)

        # Check thresholds
        self._check_alerts(metric)

        return metric

    def _check_alerts(self, metric: EGLMetric) -> None:
        """Check if the metric breaches any thresholds."""
        if metric.diversity_score < self._convergence_threshold and metric.active_capabilities > 1:
            self._alerts.append(EGLAlert(
                alert_type="convergence",
                message=(
                    f"Diversity score {metric.diversity_score:.3f} below "
                    f"threshold {self._convergence_threshold}"
                ),
                severity="critical",
                metric=metric,
            ))

        if metric.specialization_index > self._dominance_threshold:
            self._alerts.append(EGLAlert(
                alert_type="dominance",
                message=(
                    f"Specialization index {metric.specialization_index:.3f} "
                    f"exceeds threshold {self._dominance_threshold}"
                ),
                severity="warning",
                metric=metric,
            ))

    def get_qd_grid(self) -> list[dict[str, Any]]:
        """Get the MAP-Elites quality-diversity grid."""
        return [
            {
                "capability": cell.capability,
                "agent_id": cell.agent_id,
                "best_performance": cell.best_performance,
                "sample_count": cell.sample_count,
            }
            for cell in sorted(
                self._qd_grid.values(),
                key=lambda c: c.best_performance,
                reverse=True,
            )
        ]

    def get_alerts(
        self, *, limit: int = 20, severity: str | None = None
    ) -> list[dict[str, Any]]:
        """Get recent alerts."""
        alerts = list(self._alerts)
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        alerts.reverse()
        return [
            {
                "alert_id": a.alert_id,
                "type": a.alert_type,
                "message": a.message,
                "severity": a.severity,
                "timestamp": a.timestamp,
            }
            for a in alerts[:limit]
        ]

    def get_egl_report(self) -> dict[str, Any]:
        """Get a comprehensive EGL report."""
        metric = self.measure() if self._records else EGLMetric()
        return {
            "current": metric.to_dict(),
            "baseline_diversity": self._baseline_diversity,
            "total_records": self.record_count,
            "qd_grid_size": len(self._qd_grid),
            "alert_count": len(self._alerts),
            "history_length": len(self._metrics_history),
        }
