"""
Tests for REST API Bridge (ecosystem/rest_bridge.py).

Validates:
  - RESTBridge: construction, OpenAPI spec generation
  - RESTEndpoint: to_openapi_operation() output format
  - Input/output contract → OpenAPI schema conversion
  - Trust-tier enforcement via security schemes
  - HTTP method determination per effect class
  - Multi-manifest OpenAPI generation
  - JSON serialization of generated spec
  - Integration with CapabilityManifest and compiler
"""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())

from hlf_mcp.ecosystem.rest_bridge import (
    RESTBridge,
    RESTEndpoint,
    generate_openapi_from_manifests,
    generate_openapi_json_from_manifests,
    _hlf_type_to_openapi_type,
    _input_contract_to_openapi_request_body,
    _output_contract_to_openapi_response,
    _param_to_openapi_property,
    _determine_http_method,
    _effect_to_path,
    _build_security_for_tier,
    _effect_class_to_category as _rest_effect_category,
)
from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    TRUST_TIER_ORDER,
)
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.typed_contracts import (
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    EffectClass,
    FailureMode,
    ProofRequirement,
    HlfType,
    TypeContract,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _disable_strict_for_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable HLF_STRICT so FILE_WRITE and EXEC tests can compile."""
    monkeypatch.setenv("HLF_STRICT", "0")

@pytest.fixture
def sample_manifest() -> CapabilityManifest:
    """A multi-effect manifest for REST endpoint generation."""
    return CapabilityManifest(
        program_id="rest_test_001",
        effects=[
            TypedEffectDeclaration(
                function_name="read_file",
                input_contract=InputContract(
                    function_name="read_file",
                    parameters=[
                        TypeContract(name="path", hlf_type=HlfType.STRING, json_schema_type="string", required=True, constraints={"description": "File path to read"}),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="read_file",
                    return_type=HlfType.STRING,
                    output_schema={"type": "string"},
                ),
                effect_class=EffectClass.FILE_READ,
            ),
            TypedEffectDeclaration(
                function_name="write_file",
                input_contract=InputContract(
                    function_name="write_file",
                    parameters=[
                        TypeContract(name="path", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                        TypeContract(name="content", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="write_file",
                    return_type=HlfType.STRING,
                ),
                effect_class=EffectClass.FILE_WRITE,
                safety_class="guarded",
            ),
            TypedEffectDeclaration(
                function_name="search",
                input_contract=InputContract(
                    function_name="search",
                    parameters=[
                        TypeContract(name="query", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="search",
                    return_type=HlfType.JSON,
                ),
                effect_class=EffectClass.WEB_SEARCH,
            ),
            TypedEffectDeclaration(
                function_name="memory_lookup",
                input_contract=InputContract(
                    function_name="memory_lookup",
                    parameters=[
                        TypeContract(name="key", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="memory_lookup",
                    return_type=HlfType.JSON,
                ),
                effect_class=EffectClass.MEMORY_READ,
            ),
            TypedEffectDeclaration(
                function_name="delegate_task",
                input_contract=InputContract(
                    function_name="delegate_task",
                    parameters=[
                        TypeContract(name="target", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                        TypeContract(name="instruction", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="delegate_task",
                    return_type=HlfType.JSON,
                ),
                effect_class=EffectClass.AGENT_DELEGATION,
                safety_class="critical",
            ),
            TypedEffectDeclaration(
                function_name="sensor_poll",
                input_contract=InputContract(
                    function_name="sensor_poll",
                    parameters=[
                        TypeContract(name="sensor_id", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="sensor_poll",
                    return_type=HlfType.JSON,
                ),
                effect_class=EffectClass.SENSOR_READ,
            ),
        ],
        required_capabilities={"filesystem", "network", "memory", "agent", "embodied"},
        input_contracts=[],
        output_contracts=[],
        proof_surfaces=[],
        trust_tier="trusted",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: type conversion helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpenAPITypeConversion:
    """Unit tests for HLF → OpenAPI type mapping."""

    def test_param_to_openapi_property_basic(self):
        param = TypeContract(name="test", hlf_type=HlfType.STRING, json_schema_type="string", required=True)
        prop = _param_to_openapi_property(param)
        assert prop["type"] == "string"

    def test_param_to_openapi_property_with_constraints(self):
        param = TypeContract(
            name="count",
            hlf_type=HlfType.INTEGER,
            json_schema_type="integer",
            required=True,
            constraints={"minimum": 0, "maximum": 100, "description": "Count of items"},
        )
        prop = _param_to_openapi_property(param)
        assert prop["type"] == "integer"
        assert prop["minimum"] == 0
        assert prop["maximum"] == 100
        assert prop["description"] == "Count of items"

    def test_hlf_type_conversion(self):
        assert _hlf_type_to_openapi_type(HlfType.STRING) == "string"
        assert _hlf_type_to_openapi_type(HlfType.INTEGER) == "integer"
        assert _hlf_type_to_openapi_type(HlfType.NUMBER) == "number"
        assert _hlf_type_to_openapi_type(HlfType.BOOLEAN) == "boolean"
        assert _hlf_type_to_openapi_type(HlfType.JSON) == "object"
        assert _hlf_type_to_openapi_type(HlfType.LIST) == "array"
        assert _hlf_type_to_openapi_type(HlfType.MAP) == "object"

    def test_input_contract_to_request_body(self):
        contract = InputContract(
            function_name="test",
            parameters=[
                TypeContract(name="x", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                TypeContract(name="y", hlf_type=HlfType.INTEGER, json_schema_type="integer", required=False),
            ],
        )
        body = _input_contract_to_openapi_request_body(contract)
        assert body is not None
        assert body["required"] is True
        assert "application/json" in body["content"]
        schema = body["content"]["application/json"]["schema"]
        assert "x" in schema["properties"]
        assert schema["required"] == ["x"]

    def test_input_contract_empty_returns_none(self):
        contract = InputContract(function_name="empty", parameters=[])
        assert _input_contract_to_openapi_request_body(contract) is None

    def test_output_contract_to_response(self):
        contract = OutputContract(
            function_name="test",
            return_type=HlfType.STRING,
            output_schema={"type": "string", "format": "uri"},
        )
        response = _output_contract_to_openapi_response(contract)
        assert "200" in response
        assert response["200"]["content"]["application/json"]["schema"]["format"] == "uri"

    def test_http_method_determination(self):
        assert _determine_http_method(EffectClass.FILE_READ) == "GET"
        assert _determine_http_method(EffectClass.FILE_WRITE) == "POST"
        assert _determine_http_method(EffectClass.MODEL_INFERENCE) == "POST"
        assert _determine_http_method(EffectClass.NETWORK_READ) == "GET"
        assert _determine_http_method(EffectClass.AGENT_DELEGATION) == "POST"
        assert _determine_http_method(EffectClass.MEMORY_READ) == "GET"

    def test_security_for_approved_tier(self):
        security = _build_security_for_tier("approved")
        assert len(security) == 1
        assert "ApiKeyAuth" in security[0]

    def test_security_for_trusted_tier(self):
        security = _build_security_for_tier("trusted")
        assert len(security) == 2
        assert "ApiKeyAuth" in security[0]
        assert "HlfTrustToken" in security[1]

    def test_security_for_advisory_tier(self):
        security = _build_security_for_tier("advisory")
        assert security == []

    def test_effect_category_mapping(self):
        assert _rest_effect_category(EffectClass.FILE_READ) == "filesystem"
        assert _rest_effect_category(EffectClass.MODEL_INFERENCE) == "inference"
        assert _rest_effect_category(EffectClass.SENSOR_READ) == "embodied"
        assert _rest_effect_category(EffectClass.LOCAL_ANALYSIS) == "analysis"
        assert _rest_effect_category(EffectClass.ASSERTION) == "analysis"


# ═══════════════════════════════════════════════════════════════════════════════
# RESTBridge OpenAPI generation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRESTBridgeOpenAPIGeneration:
    """Tests for RESTBridge.generate_openapi_spec()."""

    def test_bridge_creation(self):
        bridge = RESTBridge()
        assert bridge.title == "HLF REST API"
        assert bridge.version == "1.0.0"

    def test_generate_openapi_spec(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge(title="Test API", version="2.0.0")
        spec = bridge.generate_openapi_spec([sample_manifest])
        assert spec["openapi"] == "3.1.0"
        assert spec["info"]["title"] == "Test API"
        assert spec["info"]["version"] == "2.0.0"
        assert "paths" in spec
        assert len(spec["paths"]) >= 5  # One per effect

    def test_generate_openapi_json(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge()
        json_str = bridge.generate_openapi_json([sample_manifest])
        assert isinstance(json_str, str)
        spec = json.loads(json_str)
        assert spec["openapi"] == "3.1.0"
        assert "paths" in spec

    def test_paths_have_correct_structure(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([sample_manifest])
        paths = spec["paths"]
        # Verify each path has an HTTP method
        for path, methods in paths.items():
            assert isinstance(methods, dict)
            for method, op in methods.items():
                assert "operationId" in op
                assert "responses" in op

    def test_post_methods_have_request_body(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([sample_manifest])
        has_post_with_body = False
        for path, methods in spec["paths"].items():
            if "post" in methods:
                op = methods["post"]
                if "requestBody" in op:
                    has_post_with_body = True
                    break
        assert has_post_with_body, "At least one POST endpoint should have a request body"

    def test_tags_are_generated(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([sample_manifest])
        tags = spec.get("tags", [])
        tag_names = {t["name"] for t in tags}
        assert "filesystem" in tag_names
        assert "network" in tag_names

    def test_security_in_operations(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([sample_manifest])
        paths = spec["paths"]
        # Agent delegation should have security
        found_secure = False
        for path, methods in paths.items():
            if "agent" in path:
                for method, op in methods.items():
                    if op.get("security"):
                        found_secure = True
                        break
        assert found_secure, "Agent delegation endpoints should have security requirements"

    def test_server_override(self, sample_manifest: CapabilityManifest):
        servers = [{"url": "https://api.example.com", "description": "Production"}]
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([sample_manifest], servers=servers)
        assert spec["servers"] == servers

    def test_custom_api_keys_in_spec(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge(api_keys={"prod-key": "Production API key", "test-key": "Test key"})
        spec = bridge.generate_openapi_spec([sample_manifest])
        assert "components" in spec
        assert "securitySchemes" in spec["components"]
        assert "ApiKeyAuth" in spec["components"]["securitySchemes"]
        assert "HlfTrustToken" in spec["components"]["securitySchemes"]


# ═══════════════════════════════════════════════════════════════════════════════
# RESTEndpoint tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRESTEndpoint:
    """Tests for RESTEndpoint dataclass."""

    def test_endpoint_creation(self):
        ep = RESTEndpoint(
            method="GET",
            path="/api/v1/filesystem/read",
            summary="Read file",
            description="Read a file from the filesystem",
            operation_id="get_filesystem_read",
            tags=["filesystem"],
            trust_tier="approved",
        )
        assert ep.method == "GET"
        assert ep.path == "/api/v1/filesystem/read"
        assert ep.trust_tier == "approved"

    def test_to_openapi_operation(self):
        ep = RESTEndpoint(
            method="GET",
            path="/api/v1/memory/read",
            summary="Memory read",
            description="Read from memory",
            operation_id="get_memory_read",
            tags=["memory"],
            category="memory",
            responses={"200": {"description": "OK"}},
            trust_tier="approved",
            security=[{"ApiKeyAuth": []}],
        )
        op = ep.to_openapi_operation()
        assert op["operationId"] == "get_memory_read"
        assert op["x-hlf-trust-tier"] == "approved"
        assert op["x-hlf-category"] == "memory"
        assert op["security"] == [{"ApiKeyAuth": []}]


# ═══════════════════════════════════════════════════════════════════════════════
# Compiler integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRESTBridgeCompilerIntegration:
    """Tests for RESTBridge with real compiled HLF programs."""

    def test_openapi_from_compiled_program(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL web_search query="test query"
\N{greek capital letter delta} [ANALYZE] query="analyze this"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        spec = generate_openapi_from_manifests([manifest], title="Test", version="1.0")
        assert "paths" in spec
        assert len(spec["paths"]) >= 1

    def test_openapi_from_multi_manifest(self):
        compiler = HLFCompiler()
        src1 = """[HLF-v3]
TOOL file_read path="/tmp/a.txt"
\N{greek capital letter omega}
"""
        src2 = """[HLF-v3]
TOOL web_search query="search"
\N{greek capital letter omega}
"""
        _, m1 = compiler.compile_and_manifest(src1)
        _, m2 = compiler.compile_and_manifest(src2)
        bridge = RESTBridge(title="Multi API")
        spec = bridge.generate_openapi_spec([m1, m2])
        assert len(spec["paths"]) >= 2

    def test_json_output_roundtrip(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL web_search query="test"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        json_str = generate_openapi_json_from_manifests([manifest])
        spec = json.loads(json_str)
        assert spec["openapi"] == "3.1.0"

    def test_read_effects_use_get(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL file_read path="/tmp/readme.txt"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        spec = generate_openapi_from_manifests([manifest])
        for path, methods in spec["paths"].items():
            assert "get" in methods, f"Read effect should use GET, got: {list(methods.keys())}"

    def test_write_effects_use_post(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL file_write path="/tmp/out.txt" content="hello" @validate(output_contract="text")
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        spec = generate_openapi_from_manifests([manifest])
        # Find any path that contains 'file' or 'write' — should use POST
        found_write_path = False
        for path, methods in spec["paths"].items():
            if "file" in path.lower() or "write" in path.lower():
                found_write_path = True
                assert "post" in methods, f"Write effect should use POST, got: {list(methods.keys())}"
        assert found_write_path, "No write effect path found in spec"

    def test_mutating_effects_get_post(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL memory_write key="session" value="data" @validate(output_contract="json")
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        spec = generate_openapi_from_manifests([manifest])
        found_memory_path = False
        for path, methods in spec["paths"].items():
            if "memory" in path.lower():
                found_memory_path = True
                assert "post" in methods, f"Memory write should use POST, got: {list(methods.keys())}"
        assert found_memory_path, "No memory write path found in spec"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestRESTBridgeEdgeCases:
    """Edge case tests for RESTBridge."""

    def test_empty_manifest_list(self):
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([])
        assert spec["paths"] == {}

    def test_empty_effects_manifest(self):
        manifest = CapabilityManifest(program_id="empty")
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([manifest])
        assert spec["paths"] == {}

    def test_single_effect_manifest(self):
        manifest = CapabilityManifest(
            program_id="solo",
            effects=[
                TypedEffectDeclaration(
                    function_name="ping",
                    input_contract=InputContract(function_name="ping", parameters=[]),
                    output_contract=OutputContract(function_name="ping", return_type=HlfType.BOOLEAN),
                    effect_class=EffectClass.LOCAL_ANALYSIS,
                ),
            ],
        )
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([manifest])
        assert len(spec["paths"]) == 1

    def test_effect_class_to_category_covers_all(self):
        for ec in EffectClass:
            cat = _rest_effect_category(ec)
            assert isinstance(cat, str) and len(cat) > 0

    def test_trust_tier_in_operation_extensions(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([sample_manifest])
        for path, methods in spec["paths"].items():
            for method, op in methods.items():
                assert "x-hlf-trust-tier" in op
                assert "x-hlf-category" in op

    def test_generated_paths_are_valid(self, sample_manifest: CapabilityManifest):
        bridge = RESTBridge()
        spec = bridge.generate_openapi_spec([sample_manifest])
        for path in spec["paths"]:
            assert path.startswith("/api/v1/")

    def test_compiled_then_openapi_roundtrip(self):
        """Full integration: compile HLF → manifest → OpenAPI spec."""
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL web_search query="latest AI news"
TOOL file_read path="/tmp/data.txt"
TOOL memory_read key="user_prefs"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        bridge = RESTBridge(title="HLF Integration Test")
        spec = bridge.generate_openapi_spec([manifest])
        json_str = bridge.generate_openapi_json([manifest])
        restored = json.loads(json_str)
        assert restored == spec
        assert len(spec["paths"]) == 3
