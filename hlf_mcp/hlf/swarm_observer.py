"""
Swarm Observer — real-time progress streaming for multi-agent HLF coordination.

Emits events as swarm phases start, progress, complete, or error.
Consumers subscribe to receive structured progress updates.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SwarmEvent:
    """A single progress event from the swarm."""

    event_id: str
    swarm_id: str
    phase_id: str
    agent_id: str
    role: str
    event_type: str  # started | progress | complete | error | cancelled
    timestamp_ns: int
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class SwarmObserver:
    """Observable hub for swarm progress events.

    Agents and tools subscribe to get real-time updates.
    All events are timestamped and carry structured payload.
    """

    def __init__(self) -> None:
        self._subscribers: list[Callable[[SwarmEvent], None]] = []
        self._event_log: list[SwarmEvent] = []
        self._counter = 0

    def subscribe(self, callback: Callable[[SwarmEvent], None]) -> None:
        """Register a callback to receive events."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[SwarmEvent], None]) -> None:
        """Remove a callback."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def emit(
        self,
        swarm_id: str,
        phase_id: str,
        agent_id: str,
        role: str,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> SwarmEvent:
        """Emit an event to all subscribers and log it."""
        self._counter += 1
        event = SwarmEvent(
            event_id=f"evt-{self._counter:06d}",
            swarm_id=swarm_id,
            phase_id=phase_id,
            agent_id=agent_id,
            role=role,
            event_type=event_type,
            timestamp_ns=time.perf_counter_ns(),
            message=message,
            payload=payload or {},
        )
        self._event_log.append(event)
        for cb in self._subscribers:
            try:
                cb(event)
            except Exception:
                pass  # Never let a subscriber break the swarm
        return event

    def get_log(self, swarm_id: str | None = None) -> list[SwarmEvent]:
        """Return events, optionally filtered by swarm_id."""
        if swarm_id is None:
            return list(self._event_log)
        return [e for e in self._event_log if e.swarm_id == swarm_id]

    def latest_for(self, swarm_id: str, phase_id: str | None = None) -> SwarmEvent | None:
        """Return the most recent event for a swarm (and optionally phase)."""
        candidates = [e for e in self._event_log if e.swarm_id == swarm_id]
        if phase_id:
            candidates = [e for e in candidates if e.phase_id == phase_id]
        return candidates[-1] if candidates else None

    def clear(self) -> None:
        """Clear all events and subscribers."""
        self._event_log.clear()
        self._subscribers.clear()
        self._counter = 0
