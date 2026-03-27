from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.memory_node import parse_pointer_ref

_EMBODIED_EFFECT_CLASSES = frozenset(
    {
        "guarded_actuation",
        "safety_stop",
        "sensor_read",
        "trajectory_plan",
        "world_state_read",
    }
)
_SIMULATION_ACTION_MODES = frozenset({"replay", "simulation"})
_SPATIAL_BOUND_KEYS = frozenset(
    {
        "max_delta_mm",
        "max_distance_mm",
        "max_rotation_deg",
        "max_step_mm",
        "max_translation_mm",
        "max_velocity_mm_s",
    }
)
_CANONICAL_HOST_NAMES = {
    "sensor_read": "SENSOR_READ",
    "world_state_recall": "WORLD_STATE_RECALL",
    "trajectory_propose": "TRAJECTORY_PROPOSE",
    "guarded_actuate": "GUARDED_ACTUATE",
    "emergency_stop": "EMERGENCY_STOP",
}


def _normalize_host_name(function_name: str) -> str:
    return str(function_name or "").strip().lower()


def _canonical_host_name(function_name: str) -> str:
    normalized = _normalize_host_name(function_name)
    return _CANONICAL_HOST_NAMES.get(normalized, str(function_name or "").strip())


def _is_pointer(value: Any) -> bool:
    return isinstance(value, str) and parse_pointer_ref(value) is not None


def _normalize_pointer_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item) for item in values if _is_pointer(item)]


def _extract_action_envelope(args: list[Any]) -> dict[str, Any]:
    if args and isinstance(args[0], dict):
        return dict(args[0])
    return {}


def _extract_spatial_bounds(envelope: dict[str, Any]) -> dict[str, Any]:
    bounds = envelope.get("bounds") if isinstance(envelope, dict) else None
    if not isinstance(bounds, dict):
        return {}
    return {
        str(key): value
        for key, value in bounds.items()
        if isinstance(key, str) and key in _SPATIAL_BOUND_KEYS and value not in (None, "")
    }


def _has_bounded_spatial_envelope(envelope: dict[str, Any]) -> bool:
    bounds = envelope.get("bounds") if isinstance(envelope, dict) else None
    if not isinstance(bounds, dict) or not str(bounds.get("workspace") or "").strip():
        return False
    spatial_bounds = _extract_spatial_bounds(envelope)
    return any(isinstance(value, (int, float)) and value > 0 for value in spatial_bounds.values())


def is_embodied_policy_trace(policy_trace: dict[str, Any] | None) -> bool:
    if not isinstance(policy_trace, dict):
        return False
    effect_class = str(policy_trace.get("effect_class") or "").strip().lower()
    function_name = _normalize_host_name(str(policy_trace.get("function_name") or ""))
    return effect_class in _EMBODIED_EFFECT_CLASSES or function_name in _CANONICAL_HOST_NAMES


def build_embodied_action_envelope(
    *,
    requested_action: str,
    target_frame: str,
    bounds: dict[str, Any],
    timeout_ms: int,
    operator_intent: str,
    execution_mode: str = "simulation",
    world_state_ref: str = "",
    evidence_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "requested_action": str(requested_action),
        "target_frame": str(target_frame),
        "bounds": dict(bounds),
        "timeout_ms": int(timeout_ms),
        "operator_intent": str(operator_intent),
        "execution_mode": str(execution_mode),
        "world_state_ref": str(world_state_ref),
        "evidence_refs": list(evidence_refs or []),
        "metadata": dict(metadata or {}),
        "supervisory_only": True,
    }


@dataclass(slots=True)
class EmbodiedContractAssessment:
    function_name: str
    embodied: bool
    admitted: bool
    supervisory_only: bool
    simulation_only: bool
    safety_class: str
    review_posture: str
    execution_mode: str
    normalized_args: list[Any] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    approval_requirements: list[dict[str, str]] = field(default_factory=list)
    operator_summary: str = ""
    pointer_fields: list[str] = field(default_factory=list)
    action_envelope: dict[str, Any] = field(default_factory=dict)
    world_state_ref: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    spatial_bounds: dict[str, Any] = field(default_factory=dict)
    bounded_spatial_envelope: bool = False
    proof_obligations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            "embodied": self.embodied,
            "admitted": self.admitted,
            "supervisory_only": self.supervisory_only,
            "simulation_only": self.simulation_only,
            "safety_class": self.safety_class,
            "review_posture": self.review_posture,
            "execution_mode": self.execution_mode,
            "normalized_args": list(self.normalized_args),
            "reasons": list(self.reasons),
            "approval_requirements": [dict(item) for item in self.approval_requirements],
            "operator_summary": self.operator_summary,
            "pointer_fields": list(self.pointer_fields),
            "action_envelope": dict(self.action_envelope),
            "world_state_ref": self.world_state_ref,
            "evidence_refs": list(self.evidence_refs),
            "spatial_bounds": dict(self.spatial_bounds),
            "bounded_spatial_envelope": self.bounded_spatial_envelope,
            "proof_obligations": list(self.proof_obligations),
        }


def _validate_action_envelope(envelope: Any) -> list[str]:
    if not isinstance(envelope, dict):
        return ["Action envelope must be an object."]
    reasons: list[str] = []
    if not str(envelope.get("requested_action") or "").strip():
        reasons.append("Action envelope must include requested_action.")
    if not str(envelope.get("target_frame") or "").strip():
        reasons.append("Action envelope must include target_frame.")
    if not isinstance(envelope.get("bounds"), dict) or not envelope.get("bounds"):
        reasons.append("Action envelope must include non-empty bounds.")
    timeout_ms = envelope.get("timeout_ms")
    if not isinstance(timeout_ms, int) or timeout_ms <= 0:
        reasons.append("Action envelope must include a positive timeout_ms.")
    if not str(envelope.get("operator_intent") or "").strip():
        reasons.append("Action envelope must include operator_intent.")
    execution_mode = str(envelope.get("execution_mode") or "").strip().lower()
    if execution_mode not in _SIMULATION_ACTION_MODES:
        reasons.append(
            "Action envelope execution_mode must be 'simulation' or 'replay' in the packaged embodied lane."
        )
    world_state_ref = str(envelope.get("world_state_ref") or "")
    if world_state_ref and not _is_pointer(world_state_ref):
        reasons.append("Action envelope world_state_ref must be a canonical HLF pointer.")
    evidence_refs = envelope.get("evidence_refs", [])
    if evidence_refs and (
        not isinstance(evidence_refs, list) or any(not _is_pointer(item) for item in evidence_refs)
    ):
        reasons.append("Action envelope evidence_refs must contain canonical HLF pointers.")
    return reasons


def assess_embodied_host_call(
    function_name: str,
    args: list[Any],
    policy_trace: dict[str, Any] | None = None,
) -> EmbodiedContractAssessment:
    canonical_name = _canonical_host_name(function_name)
    if not is_embodied_policy_trace(policy_trace):
        return EmbodiedContractAssessment(
            function_name=canonical_name,
            embodied=False,
            admitted=True,
            supervisory_only=False,
            simulation_only=False,
            safety_class="none",
            review_posture="none",
            execution_mode="direct",
            normalized_args=list(args),
        )

    execution_mode = str((policy_trace or {}).get("execution_mode") or "direct").strip().lower()
    review_posture = str((policy_trace or {}).get("review_posture") or "none").strip().lower()
    safety_class = str((policy_trace or {}).get("safety_class") or "none").strip().lower()
    supervisory_only = bool((policy_trace or {}).get("supervisory_only", True))
    reasons = [
        "Packaged embodied execution is constrained to a supervisory boundary and does not claim live low-level control.",
    ]
    normalized_name = _normalize_host_name(function_name)
    pointer_fields = [
        str(item)
        for item in (policy_trace or {}).get("evidence_pointer_fields", [])
        if isinstance(item, str) and item
    ]
    action_envelope = _extract_action_envelope(args)
    world_state_ref = ""
    evidence_refs: list[str] = []
    spatial_bounds = _extract_spatial_bounds(action_envelope)
    bounded_spatial_envelope = _has_bounded_spatial_envelope(action_envelope)
    proof_obligations = ["supervisory_only", "simulation_mode"]
    approval_requirements: list[dict[str, str]] = []
    admitted = True

    if not supervisory_only:
        admitted = False
        reasons.append("Embodied host-function contracts must remain supervisory_only in the packaged surface.")

    if review_posture == "operator_review":
        approval_requirements.append(
            {"type": "embodied_review", "scope": "tool", "value": canonical_name}
        )

    if normalized_name == "sensor_read":
        proof_obligations.append("positive_max_age_ms")
        read_mode = str(args[2] if len(args) >= 3 else "").strip().lower()
        max_age_ms = args[3] if len(args) >= 4 else None
        if read_mode not in _SIMULATION_ACTION_MODES:
            admitted = False
            reasons.append("SENSOR_READ is limited to simulation or replay-backed reads in the packaged product.")
        if not isinstance(max_age_ms, int) or max_age_ms <= 0:
            admitted = False
            reasons.append("SENSOR_READ requires a positive max_age_ms.")

    elif normalized_name == "world_state_recall":
        proof_obligations.extend(["world_state_ref", "positive_max_age_ms"])
        world_state_ref = str(args[0] if args else "")
        if not _is_pointer(args[0] if args else ""):
            admitted = False
            reasons.append("WORLD_STATE_RECALL requires a canonical world_state_ref pointer.")
        max_age_ms = args[2] if len(args) >= 3 else None
        if not isinstance(max_age_ms, int) or max_age_ms <= 0:
            admitted = False
            reasons.append("WORLD_STATE_RECALL requires a positive max_age_ms.")

    elif normalized_name == "trajectory_propose":
        world_state_ref = str(args[1] if len(args) >= 2 else "")
        evidence_refs = _normalize_pointer_list(action_envelope.get("evidence_refs", []))
        proof_obligations.extend(["positive_timeout_ms", "bounded_spatial_envelope", "world_state_ref"])
        if not _is_pointer(args[1] if len(args) >= 2 else ""):
            admitted = False
            reasons.append("TRAJECTORY_PROPOSE requires a canonical world_state_ref pointer.")
        envelope_reasons = _validate_action_envelope(args[0] if args else None)
        if envelope_reasons:
            admitted = False
            reasons.extend(envelope_reasons)

    elif normalized_name == "guarded_actuate":
        world_state_ref = str(action_envelope.get("world_state_ref") or "")
        evidence_refs = _normalize_pointer_list(args[1] if len(args) >= 2 else None)
        proof_obligations.extend(["positive_timeout_ms", "bounded_spatial_envelope", "evidence_refs"])
        envelope_reasons = _validate_action_envelope(args[0] if args else None)
        if envelope_reasons:
            admitted = False
            reasons.extend(envelope_reasons)
        evidence_refs = args[1] if len(args) >= 2 else None
        if not isinstance(evidence_refs, list) or not evidence_refs:
            admitted = False
            reasons.append("GUARDED_ACTUATE requires non-empty evidence_refs.")
        elif any(not _is_pointer(item) for item in evidence_refs):
            admitted = False
            reasons.append("GUARDED_ACTUATE evidence_refs must be canonical HLF pointers.")
        if not str(args[2] if len(args) >= 3 else "").strip():
            admitted = False
            reasons.append("GUARDED_ACTUATE requires operator_intent.")

    elif normalized_name == "emergency_stop":
        proof_obligations.append("simulation_mode")
        emergency_mode = str(args[2] if len(args) >= 3 else "").strip().lower()
        if emergency_mode not in _SIMULATION_ACTION_MODES:
            admitted = False
            reasons.append("EMERGENCY_STOP is limited to simulation or replay-backed execution in this slice.")
        if not str(args[0] if args else "").strip():
            admitted = False
            reasons.append("EMERGENCY_STOP requires a reason.")
        if not str(args[1] if len(args) >= 2 else "").strip():
            admitted = False
            reasons.append("EMERGENCY_STOP requires a scope.")

    simulation_only = execution_mode in {"simulation_only", "replay_only"}
    operator_summary = (
        f"{canonical_name} is packaged as a supervisory embodied contract with safety_class="
        f"{safety_class}, review_posture={review_posture}, execution_mode={execution_mode}."
    )
    return EmbodiedContractAssessment(
        function_name=canonical_name,
        embodied=True,
        admitted=admitted,
        supervisory_only=supervisory_only,
        simulation_only=simulation_only,
        safety_class=safety_class,
        review_posture=review_posture,
        execution_mode=execution_mode,
        normalized_args=list(args),
        reasons=reasons,
        approval_requirements=approval_requirements,
        operator_summary=operator_summary,
        pointer_fields=pointer_fields,
        action_envelope=action_envelope,
        world_state_ref=world_state_ref,
        evidence_refs=evidence_refs,
        spatial_bounds=spatial_bounds,
        bounded_spatial_envelope=bounded_spatial_envelope,
        proof_obligations=proof_obligations,
    )


def build_simulated_embodied_result(
    function_name: str,
    args: list[Any],
    assessment: EmbodiedContractAssessment,
) -> dict[str, Any]:
    payload = {
        "host_fn": _canonical_host_name(function_name),
        "status": "simulation_only",
        "supervisory_only": assessment.supervisory_only,
        "simulation_only": assessment.simulation_only,
        "safety_class": assessment.safety_class,
        "review_posture": assessment.review_posture,
        "operator_summary": assessment.operator_summary,
    }
    normalized_name = _normalize_host_name(function_name)
    if normalized_name in {"trajectory_propose", "guarded_actuate"}:
        payload["action_envelope"] = args[0] if args else {}
    if normalized_name == "guarded_actuate":
        payload["evidence_refs"] = list(args[1] if len(args) >= 2 and isinstance(args[1], list) else [])
        payload["operator_intent"] = str(args[2] if len(args) >= 3 else "")
        payload["operator_review_required"] = bool(assessment.approval_requirements)
    elif normalized_name == "sensor_read":
        payload["sensor_id"] = str(args[0] if args else "")
        payload["modality"] = str(args[1] if len(args) >= 2 else "")
        payload["read_mode"] = str(args[2] if len(args) >= 3 else "")
    elif normalized_name == "world_state_recall":
        payload["world_state_ref"] = str(args[0] if args else "")
        payload["frame"] = str(args[1] if len(args) >= 2 else "")
    elif normalized_name == "emergency_stop":
        payload["reason"] = str(args[0] if args else "")
        payload["scope"] = str(args[1] if len(args) >= 2 else "")
    return payload