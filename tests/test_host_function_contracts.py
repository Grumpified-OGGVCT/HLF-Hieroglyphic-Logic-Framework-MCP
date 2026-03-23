from __future__ import annotations

import json

import pytest

from hlf_mcp.hlf.registry import HostFunctionRegistry


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
        {
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
                "required": ["missing"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "string"},
            "effect_class": "file_read",
            "failure_type": "io_error",
            "audit_requirement": "standard",
        },
    )

    with pytest.raises(ValueError, match="required references unknown properties"):
        HostFunctionRegistry(json_path=str(registry_path))
