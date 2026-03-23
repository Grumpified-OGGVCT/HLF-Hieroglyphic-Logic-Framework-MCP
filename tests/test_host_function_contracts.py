from __future__ import annotations

import json

import pytest

from hlf_mcp.hlf.registry import HostFunction, HostFunctionRegistry


def _valid_function(**overrides: object) -> dict[str, object]:
    function: dict[str, object] = {
        "name": "READ",
        "args": [{"name": "path", "type": "path"}],
        "returns": "string",
        "tier": ["hearth"],
        "gas": 1,
        "backend": "builtin",
        "sensitive": False,
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "path"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "string"},
        "effect_class": "file_read",
        "failure_type": "io_error",
        "audit_requirement": "standard",
    }
    function.update(overrides)
    return function


def _write_registry(path, function: dict[str, object]) -> None:
    path.write_text(
        json.dumps({"version": "1.5.0", "functions": [function]}, indent=2),
        encoding="utf-8",
    )


def test_registry_rejects_missing_typed_contract_fields(tmp_path) -> None:
    registry_path = tmp_path / "host_functions.json"
    _write_registry(
        registry_path,
        {
            "name": "READ",
            "args": [{"name": "path", "type": "path"}],
            "returns": "string",
            "tier": ["hearth"],
            "gas": 1,
            "backend": "builtin",
            "sensitive": False,
            "output_schema": {"type": "string"},
            "effect_class": "file_read",
            "failure_type": "io_error",
        },
    )

    with pytest.raises(ValueError, match="missing typed contract fields"):
        HostFunctionRegistry(json_path=str(registry_path))


def test_registry_rejects_malformed_input_schema(tmp_path) -> None:
    registry_path = tmp_path / "host_functions.json"
    _write_registry(
        registry_path,
        _valid_function(
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "path"}},
                "required": ["missing"],
                "additionalProperties": False,
            }
        ),
    )

    with pytest.raises(ValueError, match="required references unknown properties"):
        HostFunctionRegistry(json_path=str(registry_path))


def test_host_function_accepts_new_contract_fields() -> None:
    function = HostFunction.from_dict(
        _valid_function(
            safety_class="critical",
            review_posture="operator_review",
            execution_mode="simulation_preferred",
            supervisory_only=True,
            evidence_pointer_fields=["artifact_id", "trace_id"],
        )
    )

    assert function.safety_class == "critical"
    assert function.review_posture == "operator_review"
    assert function.execution_mode == "simulation_preferred"
    assert function.supervisory_only is True
    assert function.evidence_pointer_fields == ["artifact_id", "trace_id"]


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("safety_class", "unsafe", "safety_class must be one of"),
        ("review_posture", "pre_review", "review_posture must be one of"),
        ("execution_mode", "indirect", "execution_mode must be one of"),
        (
            "evidence_pointer_fields",
            ["artifact_id", 7],
            "evidence_pointer_fields must be a list of strings",
        ),
    ],
)
def test_host_function_rejects_invalid_new_contract_fields(
    field_name: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        HostFunction.from_dict(_valid_function(**{field_name: value}))
