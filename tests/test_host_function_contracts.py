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


# ── API-Keeper + SearXng Contract Tests ────────────────────────────────────────

def test_apikeeper_store_contract() -> None:
    """apikeeper.store must have credential_store effect_class."""
    fn = HostFunction.from_dict({
        "name": "apikeeper.store",
        "args": [
            {"name": "credential_id", "type": "string"},
            {"name": "credential_value", "type": "string"},
            {"name": "metadata", "type": "map"},
        ],
        "returns": "map",
        "tier": ["forge", "sovereign"],
        "gas": 2,
        "backend": "apikeeper",
        "sensitive": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "credential_id": {"type": "string"},
                "credential_value": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["credential_id", "credential_value"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object"},
        "effect_class": "credential_store",
        "failure_type": "io_error",
        "audit_requirement": "full",
    })
    assert fn.effect_class == "credential_store"
    assert fn.sensitive is True


def test_apikeeper_rotate_contract() -> None:
    """apikeeper.rotate must have credential_rotate effect_class."""
    fn = HostFunction.from_dict({
        "name": "apikeeper.rotate",
        "args": [{"name": "credential_id", "type": "string"}],
        "returns": "string",
        "tier": ["sovereign"],
        "gas": 3,
        "backend": "apikeeper",
        "sensitive": True,
        "input_schema": {
            "type": "object",
            "properties": {"credential_id": {"type": "string"}},
            "required": ["credential_id"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "string"},
        "effect_class": "credential_rotate",
        "failure_type": "io_error",
        "audit_requirement": "full",
    })
    assert fn.effect_class == "credential_rotate"
    assert "sovereign" in fn.tiers
    assert "hearth" not in fn.tiers  # rotation is sovereign-only


def test_apikeeper_audit_contract() -> None:
    """apikeeper.audit must have credential_audit effect_class."""
    fn = HostFunction.from_dict({
        "name": "apikeeper.audit",
        "args": [{"name": "credential_id", "type": "string"}],
        "returns": "list",
        "tier": ["forge", "sovereign"],
        "gas": 1,
        "backend": "apikeeper",
        "sensitive": False,
        "input_schema": {
            "type": "object",
            "properties": {"credential_id": {"type": "string"}},
            "required": ["credential_id"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "array"},
        "effect_class": "credential_audit",
        "failure_type": "execution_error",
        "audit_requirement": "standard",
    })
    assert fn.effect_class == "credential_audit"
    assert fn.sensitive is False  # audit trail is not sensitive


def test_searxng_search_contract() -> None:
    """searxng.search must have web_search effect_class."""
    fn = HostFunction.from_dict({
        "name": "searxng.search",
        "args": [
            {"name": "query", "type": "string"},
            {"name": "num_results", "type": "int"},
        ],
        "returns": "list",
        "tier": ["forge", "sovereign"],
        "gas": 5,
        "backend": "searxng",
        "sensitive": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "array"},
        "effect_class": "web_search",
        "failure_type": "network_error",
        "audit_requirement": "sensitive_hash",
    })
    assert fn.effect_class == "web_search"
    assert fn.gas == 5


def test_searxng_crawl_contract() -> None:
    """searxng.crawl must have web_crawl effect_class."""
    fn = HostFunction.from_dict({
        "name": "searxng.crawl",
        "args": [
            {"name": "url", "type": "string"},
            {"name": "depth", "type": "int"},
        ],
        "returns": "string",
        "tier": ["forge", "sovereign"],
        "gas": 8,
        "backend": "searxng",
        "sensitive": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "depth": {"type": "integer"},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "string"},
        "effect_class": "web_crawl",
        "failure_type": "network_error",
        "audit_requirement": "sensitive_hash",
    })
    assert fn.effect_class == "web_crawl"
    assert fn.gas == 8


def test_registry_loads_new_functions() -> None:
    """The governance registry must contain all 5 new host functions."""
    import json
    from pathlib import Path

    registry_path = Path(__file__).parent.parent / "governance" / "host_functions.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    names = {fn["name"] for fn in data["functions"]}

    expected = {"apikeeper.store", "apikeeper.rotate", "apikeeper.audit",
                "searxng.search", "searxng.crawl"}
    for name in expected:
        assert name in names, f"{name} missing from governance/host_functions.json"

    # WEB_SEARCH must use searxng backend
    web_search = next(fn for fn in data["functions"] if fn["name"] == "WEB_SEARCH")
    assert web_search["backend"] == "searxng", "WEB_SEARCH backend must be searxng"
