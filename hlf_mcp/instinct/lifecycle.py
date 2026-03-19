"""
Instinct SDD (Specify-Delegate-Do) Lifecycle.

Deterministic mission state machine:
  Specify → Plan → Execute → Verify → Merge

Rules:
  - Phase skips are blocked (must advance sequentially)
  - Backward transitions are blocked unless override=True
  - The Verify→Merge transition requires CoVE gate pass
  - Each phase transition is logged to the ALIGN Ledger
  - SPEC_SEAL opcodes lock missions with SHA-256 checksums
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.instinct.orchestration import (
    execution_ready_for_verification,
    normalize_execution_trace,
    normalize_task_dag,
    summarize_execution_trace,
)

# ── Phase definitions ──────────────────────────────────────────────────────────

PHASES = ["specify", "plan", "execute", "verify", "merge"]
PHASE_INDEX: dict[str, int] = {p: i for i, p in enumerate(PHASES)}

# Transition gate rules
_GATES: dict[str, dict[str, Any]] = {
    "specify": {
        "description": "Mission is being specified",
        "requires": [],
        "produces": ["mission_spec"],
    },
    "plan": {
        "description": "Mission plan is being developed",
        "requires": ["mission_spec"],
        "produces": ["mission_plan"],
    },
    "execute": {
        "description": "Mission is executing",
        "requires": ["mission_plan"],
        "produces": ["execution_artifacts"],
    },
    "verify": {
        "description": "CoVE adversarial verification gate",
        "requires": ["execution_artifacts"],
        "produces": ["verification_report"],
        "cove_gate": True,
    },
    "merge": {
        "description": "Merging verified results",
        "requires": ["verification_report"],
        "produces": ["merged_state"],
        "requires_cove_pass": True,
    },
}

_ALLOWED_NEXT: dict[str, list[str]] = {
    "specify": ["plan"],
    "plan": ["execute"],
    "execute": ["verify"],
    "verify": ["merge"],
    "merge": [],
}


@dataclass(slots=True)
class SDDRealignmentEvent:
    triggered_by: str
    change_type: str
    change_description: str
    affected_nodes: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class InstinctLifecycle:
    """Thread-safe Instinct SDD mission state machine."""

    def __init__(self) -> None:
        self._missions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ledger: list[dict[str, Any]] = []

    def step(
        self,
        mission_id: str,
        phase: str,
        payload: dict[str, Any] | None = None,
        override: bool = False,
        cove_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Advance a mission to the specified phase.

        Returns the mission state dict.
        """
        payload = payload or {}
        phase = phase.lower().strip()

        if phase not in PHASE_INDEX:
            return _err(mission_id, f"Unknown phase '{phase}'. Valid phases: {PHASES}")

        with self._lock:
            mission = self._missions.get(mission_id)

            # New mission — must start at specify
            if mission is None:
                if phase != "specify":
                    return _err(mission_id, f"New mission must start at 'specify', got '{phase}'")
                mission = _new_mission(mission_id, payload)
                self._missions[mission_id] = mission
                self._log_ledger(mission_id, "created", phase, payload)
                return _ok_state(mission)

            current = mission["current_phase"]
            current_idx = PHASE_INDEX[current]
            target_idx = PHASE_INDEX[phase]

            # Already at target
            if current == phase:
                return _ok_state(mission, note="already_at_phase")

            # Backward transition blocked
            if target_idx < current_idx and not override:
                return _err(
                    mission_id,
                    f"Backward transition blocked: {current} → {phase}. "
                    f"Use override=True to force.",
                )

            # Skip blocked
            if target_idx > current_idx + 1 and not override:
                skipped = PHASES[current_idx + 1]
                return _err(
                    mission_id,
                    f"Phase skip blocked: cannot go from '{current}' to '{phase}' "
                    f"without completing '{skipped}'.",
                )

            # CoVE gate for verify→merge
            if phase == "merge" and current == "verify":
                cove_passed = _run_cove_gate(mission, cove_result)
                if not cove_passed and not override:
                    mission["cove_failures"] = mission.get("cove_failures", 0) + 1
                    self._log_ledger(mission_id, "cove_gate_fail", phase, payload)
                    return {
                        "mission_id": mission_id,
                        "status": "blocked",
                        "current_phase": current,
                        "allowed_next": _ALLOWED_NEXT.get(current, []),
                        "error": "CoVE verification gate failed. Mission halted before merge.",
                        "cove_gate": {"passed": False, "failures": mission["cove_failures"]},
                    }
                mission["cove_gate_passed"] = True

            if phase == "verify" and mission.get("task_dag"):
                if (
                    not execution_ready_for_verification(
                        mission.get("task_dag", []),
                        mission.get("execution_trace", []),
                    )
                    and not override
                ):
                    return {
                        "mission_id": mission_id,
                        "status": "blocked",
                        "current_phase": current,
                        "allowed_next": _ALLOWED_NEXT.get(current, []),
                        "error": "Execution trace is incomplete or contains failed nodes. Mission halted before verify.",
                        "execution_summary": summarize_execution_trace(
                            mission.get("execution_trace", []),
                            task_dag=mission.get("task_dag", []),
                        ),
                    }

            # Advance phase
            mission["current_phase"] = phase
            mission["phase_history"].append(
                {
                    "phase": phase,
                    "timestamp": time.time(),
                    "payload_keys": list(payload.keys()),
                }
            )
            mission["artifacts"][phase] = {
                "payload": payload,
                "timestamp": time.time(),
                "sha256": hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode()
                ).hexdigest(),
            }
            if phase == "specify":
                mission["topic"] = str(payload.get("topic") or mission.get("topic") or mission_id)
                if payload:
                    mission["spec"] = copy.deepcopy(payload)
            elif phase == "plan":
                if payload:
                    mission["spec"] = copy.deepcopy(payload)
                if isinstance(payload.get("task_dag"), list):
                    mission["task_dag"] = normalize_task_dag(payload.get("task_dag", []))
            elif phase == "execute":
                if isinstance(payload.get("task_dag"), list):
                    mission["task_dag"] = normalize_task_dag(payload.get("task_dag", []))
                if isinstance(payload.get("execution_trace"), list):
                    mission["execution_trace"] = normalize_execution_trace(
                        payload.get("execution_trace", []),
                        task_dag=mission.get("task_dag", []),
                    )
                    mission["execution_summary"] = summarize_execution_trace(
                        mission["execution_trace"],
                        task_dag=mission.get("task_dag", []),
                    )
            elif phase == "verify" and payload:
                mission["verification_report"] = copy.deepcopy(payload)

            # Seal on merge
            if phase == "merge":
                mission["sealed"] = True
                mission["seal_hash"] = hashlib.sha256(
                    json.dumps(mission["artifacts"], sort_keys=True, default=str).encode()
                ).hexdigest()

            self._log_ledger(mission_id, "transitioned", phase, payload)
            return _ok_state(mission)

    def get_mission(self, mission_id: str) -> dict[str, Any] | None:
        with self._lock:
            m = self._missions.get(mission_id)
            return copy.deepcopy(m) if m else None

    def realign(self, mission_id: str, event: SDDRealignmentEvent) -> dict[str, Any]:
        with self._lock:
            mission = self._missions.get(mission_id)
            if mission is None:
                return _err(mission_id, f"Mission '{mission_id}' not found")
            if mission.get("sealed", False):
                return _err(mission_id, "Cannot realign a sealed mission")

            realignment_payload = {
                "triggered_by": event.triggered_by,
                "change_type": event.change_type,
                "change_description": event.change_description,
                "affected_nodes": list(event.affected_nodes),
                "timestamp": event.timestamp,
            }
            mission.setdefault("realignment_events", []).append(realignment_payload)
            mission.setdefault("spec", {})
            if isinstance(mission["spec"], dict):
                mission["spec"].setdefault("_realignments", []).append(
                    {
                        "by": event.triggered_by,
                        "type": event.change_type,
                        "desc": event.change_description,
                        "ts": event.timestamp,
                    }
                )
            mission["phase_history"].append(
                {
                    "phase": mission["current_phase"],
                    "timestamp": event.timestamp,
                    "payload_keys": [],
                    "notes": f"REALIGNMENT: {event.change_type} - {event.change_description}",
                }
            )
            self._log_ledger(
                mission_id, "realignment", mission["current_phase"], realignment_payload
            )
            return _ok_state(mission)

    def list_missions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "mission_id": m["mission_id"],
                    "topic": m.get("topic", ""),
                    "current_phase": m["current_phase"],
                    "sealed": m.get("sealed", False),
                    "created_at": m["created_at"],
                    "realignment_count": len(m.get("realignment_events", [])),
                    "plan_nodes": len(m.get("task_dag", [])),
                    "execution_summary": copy.deepcopy(m.get("execution_summary", {})),
                }
                for m in self._missions.values()
            ]

    def _log_ledger(
        self,
        mission_id: str,
        event: str,
        phase: str,
        payload: dict[str, Any],
    ) -> None:
        self._ledger.append(
            {
                "mission_id": mission_id,
                "event": event,
                "phase": phase,
                "timestamp": time.time(),
                "payload_sha256": hashlib.sha256(str(payload).encode()).hexdigest(),
            }
        )

    def get_ledger(self, mission_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if mission_id:
                return [e for e in self._ledger if e["mission_id"] == mission_id]
            return list(self._ledger)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _new_mission(mission_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": mission_id,
        "topic": str(payload.get("topic") or mission_id),
        "current_phase": "specify",
        "phase_history": [
            {"phase": "specify", "timestamp": time.time(), "payload_keys": list(payload.keys())}
        ],
        "artifacts": {
            "specify": {
                "payload": payload,
                "timestamp": time.time(),
                "sha256": hashlib.sha256(str(payload).encode()).hexdigest(),
            }
        },
        "spec": copy.deepcopy(payload),
        "task_dag": list(payload.get("task_dag", []))
        if isinstance(payload.get("task_dag"), list)
        else [],
        "execution_trace": [],
        "execution_summary": {
            "total_nodes": len(payload.get("task_dag", []))
            if isinstance(payload.get("task_dag"), list)
            else 0,
            "recorded_nodes": 0,
            "completed_nodes": 0,
            "failed_nodes": 0,
            "delegated_nodes": 0,
            "escalated_nodes": 0,
            "all_nodes_recorded": False,
            "all_nodes_succeeded": False,
        },
        "verification_report": None,
        "realignment_events": [],
        "created_at": time.time(),
        "sealed": False,
        "seal_hash": None,
        "cove_gate_passed": False,
        "cove_failures": 0,
    }


def _ok_state(mission: dict[str, Any], note: str | None = None) -> dict[str, Any]:
    phase = mission["current_phase"]
    result = {
        "mission_id": mission["mission_id"],
        "topic": mission.get("topic", ""),
        "status": "ok",
        "current_phase": phase,
        "allowed_next": _ALLOWED_NEXT.get(phase, []),
        "sealed": mission.get("sealed", False),
        "seal_hash": mission.get("seal_hash"),
        "cove_gate": {
            "passed": mission.get("cove_gate_passed", False),
            "failures": mission.get("cove_failures", 0),
        },
        "phase_history": mission.get("phase_history", []),
        "spec": copy.deepcopy(mission.get("spec")),
        "task_dag": copy.deepcopy(mission.get("task_dag", [])),
        "execution_trace": copy.deepcopy(mission.get("execution_trace", [])),
        "execution_summary": copy.deepcopy(mission.get("execution_summary", {})),
        "verification_report": copy.deepcopy(mission.get("verification_report")),
        "realignment_events": copy.deepcopy(mission.get("realignment_events", [])),
        "gate_info": _GATES.get(phase, {}),
        "error": None,
    }
    if note:
        result["note"] = note
    return result


def _err(mission_id: str, message: str) -> dict[str, Any]:
    return {
        "mission_id": mission_id,
        "status": "error",
        "current_phase": None,
        "allowed_next": [],
        "error": message,
        "cove_gate": None,
        "sealed": False,
        "seal_hash": None,
    }


def _run_cove_gate(mission: dict[str, Any], cove_result: dict[str, Any] | None) -> bool:
    """Evaluate CoVE gate.

    If cove_result is provided with passed=True, use that.
    Otherwise perform a basic heuristic check on the verify artifact.
    """
    if cove_result is not None:
        return bool(cove_result.get("passed", False))

    verification_report = mission.get("verification_report")
    if isinstance(verification_report, dict):
        if "all_proven" in verification_report:
            return bool(verification_report.get("all_proven", False))
        if verification_report.get("verdict"):
            return str(verification_report.get("verdict", "")).upper() in {
                "APPROVED",
                "PASSED",
                "PROVEN",
            }
        results = verification_report.get("results")
        if isinstance(results, list) and results:
            failing_statuses = {"counterexample", "error", "failed", "blocked"}
            return not any(
                str(item.get("status", "")).lower() in failing_statuses
                for item in results
                if isinstance(item, dict)
            )

    verify_artifact = mission.get("artifacts", {}).get("verify", {})
    if not verify_artifact:
        return False
    payload = verify_artifact.get("payload", {})
    # CoVE passes if verify payload has any non-empty result
    return bool(payload)
