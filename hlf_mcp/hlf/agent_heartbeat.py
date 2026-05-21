"""Multi-Agent Heartbeat Monitor — confidence-based routing for agent swarms.

Provides heartbeat recording, liveliness checking, confidence scoring,
and confidence-weighted routing across multiple agent types.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Dataclass ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class HeartbeatRecord:
    agent_id: str
    agent_type: str
    timestamp: str  # ISO 8601
    status: str  # "alive" | "degraded" | "dead"
    last_action: str
    memory_usage_mb: float
    cpu_percent: float
    uptime_sec: float
    confidence_score: float  # 0.0 – 1.0
    error_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "timestamp": self.timestamp,
            "status": self.status,
            "last_action": self.last_action,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_percent": self.cpu_percent,
            "uptime_sec": self.uptime_sec,
            "confidence_score": self.confidence_score,
            "error_count": self.error_count,
        }


# ── HeartbeatMonitor ───────────────────────────────────────────────────────────


class HeartbeatMonitor:
    """Monitors agent heartbeats, computes confidence scores, and routes by confidence."""

    def __init__(
        self,
        max_history: int = 100,
        dead_threshold_sec: float = 60.0,
    ) -> None:
        self.records: dict[str, list[HeartbeatRecord]] = {}
        self.max_history = max_history
        self.dead_threshold_sec = dead_threshold_sec

    # ── Recording ──────────────────────────────────────────────────────────

    def record_heartbeat(self, record: HeartbeatRecord) -> None:
        """Record a new heartbeat, capping agent history at max_history."""
        self.records.setdefault(record.agent_id, []).append(record)
        # Trim oldest entries if over max_history
        if len(self.records[record.agent_id]) > self.max_history:
            self.records[record.agent_id] = self.records[record.agent_id][-self.max_history:]

    # ── Status ─────────────────────────────────────────────────────────────

    def check_status(self, agent_id: str) -> str:
        """Return 'alive', 'degraded', or 'dead' based on the most recent heartbeat."""
        agent_records = self.records.get(agent_id)
        if not agent_records:
            return "dead"

        latest = agent_records[-1]
        if latest.status == "dead":
            return "dead"
        if latest.status == "degraded":
            return "degraded"

        # Check recency
        elapsed = _elapsed_sec(latest.timestamp)
        if elapsed > self.dead_threshold_sec:
            return "dead"
        return "alive"

    # ── Confidence ─────────────────────────────────────────────────────────

    def get_confidence(self, agent_id: str) -> float:
        """Compute a weighted confidence score for the agent.

        Weights:
          - recency:      0.40  (how recently the agent heartbeat)
          - error_rate:    0.35  (1.0 - error_count / max(1, uptime/60.0))
          - uptime:        0.25  (min(uptime / 3600.0, 1.0) capped at 1hr)
        """
        agent_records = self.records.get(agent_id)
        if not agent_records:
            return 0.0

        latest = agent_records[-1]

        # Recency factor
        elapsed = max(_elapsed_sec(latest.timestamp), 0.0)
        recency = max(0.0, 1.0 - elapsed / max(self.dead_threshold_sec, 1.0))

        # Error rate factor
        minutes_up = max(latest.uptime_sec, 1.0) / 60.0
        error_rate = min(latest.error_count / max(minutes_up, 1.0), 1.0)
        error_factor = max(0.0, 1.0 - error_rate)

        # Uptime factor (capped at 1 hour for normalized scoring)
        uptime_factor = min(latest.uptime_sec / 3600.0, 1.0)

        score = 0.40 * recency + 0.35 * error_factor + 0.25 * uptime_factor
        return round(max(0.0, min(score, 1.0)), 4)

    # ── Routing ────────────────────────────────────────────────────────────

    def route_by_confidence(self, task_type: str) -> str | None:
        """Route to the highest-confidence agent matching the given task type.

        Agents whose status is 'dead' are excluded from routing.
        """
        candidates: list[tuple[str, float]] = []
        for agent_id in self.records:
            agent_records = self.records[agent_id]
            if not agent_records:
                continue
            latest = agent_records[-1]
            if latest.agent_type != task_type:
                continue
            if self.check_status(agent_id) == "dead":
                continue
            conf = self.get_confidence(agent_id)
            candidates.append((agent_id, conf))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    # ── Queries ────────────────────────────────────────────────────────────

    def dead_agents(self) -> list[str]:
        """Return IDs of all agents whose status is 'dead'."""
        return [aid for aid in self.records if self.check_status(aid) == "dead"]

    def aggregate_report(self) -> dict[str, Any]:
        """Generate a full heartbeat report for all tracked agents."""
        report: dict[str, Any] = {
            "generated_at": _iso_now(),
            "total_agents": len(self.records),
            "healthy_agents": 0,
            "degraded_agents": 0,
            "dead_agents": 0,
            "agents": {},
        }

        for agent_id, rec_list in self.records.items():
            if not rec_list:
                continue
            status = self.check_status(agent_id)
            confidence = self.get_confidence(agent_id)
            latest = rec_list[-1]

            if status == "alive":
                report["healthy_agents"] += 1
            elif status == "degraded":
                report["degraded_agents"] += 1
            else:
                report["dead_agents"] += 1

            report["agents"][agent_id] = {
                "agent_type": latest.agent_type,
                "status": status,
                "confidence": confidence,
                "last_heartbeat": latest.timestamp,
                "last_action": latest.last_action,
                "uptime_sec": latest.uptime_sec,
                "error_count": latest.error_count,
                "history_count": len(rec_list),
            }

        return report


# ── Helpers ────────────────────────────────────────────────────────────────────


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _elapsed_sec(timestamp: str) -> float:
    """Compute seconds elapsed since the given ISO timestamp."""
    try:
        ts = time.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        return time.time() - time.mktime(ts)
    except (ValueError, OverflowError):
        return 999999.0  # unparseable → treat as ancient
