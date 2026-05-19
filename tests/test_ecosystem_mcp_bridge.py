"""
Tests for MCP-Native Bridge (ecosystem/mcp_bridge.py).

Validates:
  - MCPBridge: construction, basic registration from CapabilityManifest
  - MCPToolRegistration: to_mcp_tool() output format
  - Input/output schema conversion (HLF types → JSON Schema)
  - Provenance passthrough from DataChannel
  - Two-channel (InstructionChannel + DataChannel) registration
  - Convenience functions
  - Error handling and edge cases
  - Integration with compiler + manifest pipeline

Integration points:
  - hlf_mcp.hlf.capability_manifest.CapabilityManifest
  - hlf_mcp.hlf.compiler.HLFCompiler
  - hlf_mcp.hlf.two_channel_executor (ProvenanceChain, DataChannel)
  - hlf_mcp.hlf.typed_contracts
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())

from hlf_mcp.ecosystem.mcp_bridge import (
    MCPBridge,
    MCPToolRegistration,
    register_manifest_as_mcp_tools,
    manifest_to_mcp_tool_schemas,
    _hlf_type_to_json_schema,
    _input_contract_to_json_schema,
    _output_contract_to_json_schema,
    _effect_class_to_category,
    _effect_safety_class,
)
from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    EFFECT_TO_CAPABILITY,
)
from hlf_mcp.hlf.effect_extractor import EffectExtractor
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
from hlf_mcp.hlf.two_channel_executor import (
    ProvenanceChain,
    InstructionChannel,
    DataChannel,
)
from hlf_mcp.hlf.formal_verifier import (
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    ConstraintKind,
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
    """Create a representative CapabilityManifest with multiple effects."""
    return CapabilityManifest(
        program_id="test_program_001",
        effects=[
            TypedEffectDeclaration(
                function_name="read_data",
                input_contract=InputContract(
                    function_name="read_data",
                    parameters=[
                        TypeContract(name="file_path", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="read_data",
                    return_type=HlfType.STRING,
                ),
                effect_class=EffectClass.FILE_READ,
                failure_modes=[FailureMode.IO_ERROR],
                proof_requirement=ProofRequirement.NONE,
            ),
            TypedEffectDeclaration(
                function_name="search_web",
                input_contract=InputContract(
                    function_name="search_web",
                    parameters=[
                        TypeContract(name="query", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                        TypeContract(name="max_results", hlf_type=HlfType.INTEGER, json_schema_type="integer", required=False),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="search_web",
                    return_type=HlfType.JSON,
                ),
                effect_class=EffectClass.WEB_SEARCH,
                failure_modes=[FailureMode.NETWORK_ERROR, FailureMode.TIMEOUT_ERROR],
                proof_requirement=ProofRequirement.RUNTIME_CHECKED,
                safety_class="watched",
            ),
            TypedEffectDeclaration(
                function_name="run_model",
                input_contract=InputContract(
                    function_name="run_model",
                    parameters=[
                        TypeContract(name="prompt", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="run_model",
                    return_type=HlfType.STRING,
                ),
                effect_class=EffectClass.MODEL_INFERENCE,
                failure_modes=[FailureMode.INFERENCE_ERROR],
                proof_requirement=ProofRequirement.VERIFICATION_ADMITTED,
                safety_class="guarded",
            ),
        ],
        required_capabilities={"filesystem", "network", "model"},
        input_contracts=[],
        output_contracts=[],
        proof_surfaces=[],
        trust_tier="watched",
    )


@pytest.fixture
def sample_data_channel() -> DataChannel:
    """Create a DataChannel with provenance chains."""
    dc = DataChannel()
    dc.track("user_input", source="user", trust=1.0, value="hello")
    dc.track("file_content", source="file", trust=0.8, value="data content")
    return dc


@pytest.fixture
def sample_instruction_channel(sample_manifest: CapabilityManifest) -> InstructionChannel:
    """Create an InstructionChannel from a sample manifest."""
    report = VerificationReport()
    report.add(VerificationResult(
        "test", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK,
        message="OK", solver="fallback",
    ))
    return InstructionChannel(
        bytecode=b"\x00\x01\x02",
        manifest=sample_manifest,
        verification=report,
        signature="",
        program_id=sample_manifest.program_id,
        tier="hearth",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: schema conversion helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaConversion:
    """Unit tests for HLF → JSON Schema type mapping."""

    def test_hlf_string_to_json_schema(self):
        result = _hlf_type_to_json_schema(HlfType.STRING)
        assert result == {"type": "string"}

    def test_hlf_integer_to_json_schema(self):
        result = _hlf_type_to_json_schema(HlfType.INTEGER)
        assert result == {"type": "integer"}

    def test_hlf_number_to_json_schema(self):
        result = _hlf_type_to_json_schema(HlfType.NUMBER)
        assert result == {"type": "number"}

    def test_hlf_boolean_to_json_schema(self):
        result = _hlf_type_to_json_schema(HlfType.BOOLEAN)
        assert result == {"type": "boolean"}

    def test_hlf_json_to_json_schema(self):
        result = _hlf_type_to_json_schema(HlfType.JSON)
        assert result == {"type": "object"}

    def test_input_contract_no_params(self):
        contract = InputContract(function_name="empty", parameters=[])
        schema = _input_contract_to_json_schema(contract)
        assert schema == {"type": "object", "properties": {}}

    def test_input_contract_with_required(self):
        contract = InputContract(
            function_name="test",
            parameters=[
                TypeContract(name="x", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                TypeContract(name="y", hlf_type=HlfType.INTEGER, json_schema_type="integer", required=False),
            ],
        )
        schema = _input_contract_to_json_schema(contract)
        assert schema["type"] == "object"
        assert "x" in schema["properties"]
        assert "y" in schema["properties"]
        assert schema["required"] == ["x"]

    def test_output_contract_to_json_schema(self):
        contract = OutputContract(
            function_name="test",
            return_type=HlfType.STRING,
            output_schema={"type": "string", "format": "markdown"},
        )
        schema = _output_contract_to_json_schema(contract)
        assert schema["type"] == "string"
        assert schema["format"] == "markdown"

    def test_output_contract_fallback_to_return_type(self):
        contract = OutputContract(function_name="test", return_type=HlfType.INTEGER)
        schema = _output_contract_to_json_schema(contract)
        assert schema == {"type": "integer"}

    def test_effect_class_to_category(self):
        assert _effect_class_to_category(EffectClass.FILE_READ) == "filesystem"
        assert _effect_class_to_category(EffectClass.WEB_SEARCH) == "network"
        assert _effect_class_to_category(EffectClass.MODEL_INFERENCE) == "inference"
        assert _effect_class_to_category(EffectClass.LOCAL_ANALYSIS) == "analysis"
        assert _effect_class_to_category(EffectClass.SENSOR_READ) == "embodied"

    def test_effect_safety_class_dangerous(self):
        effect = TypedEffectDeclaration(
            function_name="test",
            input_contract=InputContract(function_name="test", parameters=[]),
            output_contract=OutputContract(function_name="test", return_type=HlfType.ANY),
            effect_class=EffectClass.FILE_WRITE,
            safety_class="critical",
        )
        assert _effect_safety_class(effect) == "potentially_dangerous"

    def test_effect_safety_class_safe(self):
        effect = TypedEffectDeclaration(
            function_name="test",
            input_contract=InputContract(function_name="test", parameters=[]),
            output_contract=OutputContract(function_name="test", return_type=HlfType.ANY),
            effect_class=EffectClass.LOCAL_ANALYSIS,
            safety_class="none",
        )
        assert _effect_safety_class(effect) == "safe"


# ═══════════════════════════════════════════════════════════════════════════════
# MCPBridge registration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPBridgeRegistration:
    """Tests for MCPBridge.register_tools()."""

    def test_bridge_creation(self):
        bridge = MCPBridge()
        assert bridge.tier == "hearth"
        assert bridge.session_id == ""

    def test_register_tools_from_manifest(self, sample_manifest: CapabilityManifest):
        bridge = MCPBridge()
        tools = bridge.register_tools(sample_manifest)
        assert len(tools) == 3
        assert all(isinstance(t, MCPToolRegistration) for t in tools)

    def test_register_tools_names(self, sample_manifest: CapabilityManifest):
        bridge = MCPBridge()
        tools = bridge.register_tools(sample_manifest)
        names = [t.name for t in tools]
        assert "hlf_file_read__read_data" in names
        assert "hlf_web_search__search_web" in names
        assert "hlf_model_inference__run_model" in names

    def test_register_tools_input_schemas(self, sample_manifest: CapabilityManifest):
        bridge = MCPBridge()
        tools = bridge.register_tools(sample_manifest)
        read_tool = tools[0]  # FILE_READ
        assert read_tool.input_schema["type"] == "object"
        assert "file_path" in read_tool.input_schema["properties"]
        assert read_tool.input_schema["required"] == ["file_path"]

    def test_register_tools_with_provenance(self, sample_manifest: CapabilityManifest, sample_data_channel: DataChannel):
        bridge = MCPBridge()
        tools = bridge.register_tools(sample_manifest, provenance_from=sample_data_channel.provenance)
        for tool in tools:
            assert "runtime_provenance" in tool.provenance
            runtime_prov = tool.provenance["runtime_provenance"]
            assert "user_input" in runtime_prov
            assert runtime_prov["user_input"]["source"] == "user"

    def test_register_tools_two_channel(
        self,
        sample_manifest: CapabilityManifest,
        sample_instruction_channel: InstructionChannel,
        sample_data_channel: DataChannel,
    ):
        bridge = MCPBridge()
        tools = bridge.register_tools_from_ast(
            sample_manifest,
            instruction=sample_instruction_channel,
            data=sample_data_channel,
        )
        assert len(tools) == 3
        for tool in tools:
            assert "hlf_instruction_signature" in tool.annotations
            assert "hlf_tier" in tool.annotations
            assert "hlf_program_id" in tool.annotations
            assert "hlf_verification_status" in tool.annotations
            assert tool.annotations["hlf_verification_status"] == "proven"

    def test_register_tool_list_returns_dicts(self, sample_manifest: CapabilityManifest):
        bridge = MCPBridge()
        raw_tools = bridge.register_tool_list([sample_manifest])
        assert len(raw_tools) == 3
        for t in raw_tools:
            assert "name" in t
            assert "description" in t
            assert "inputSchema" in t
            assert "annotations" in t
            assert "hlf_provenance" in t["annotations"]
            assert "hlf_trust_tier" in t["annotations"]

    def test_to_mcp_tool_format(self, sample_manifest: CapabilityManifest):
        bridge = MCPBridge()
        tools = bridge.register_tools(sample_manifest)
        tool_dict = tools[0].to_mcp_tool()
        required_keys = {"name", "description", "inputSchema", "annotations"}
        assert required_keys <= set(tool_dict.keys())
        assert isinstance(tool_dict["inputSchema"], dict)
        assert isinstance(tool_dict["annotations"], dict)


# ═══════════════════════════════════════════════════════════════════════════════
# MCPBridge + Compiler integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPBridgeCompilerIntegration:
    """Tests for MCPBridge with real compiled HLF programs."""

    def test_register_from_compiled_hlf(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
\N{greek capital letter delta} [ANALYZE] query="hello world"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        bridge = MCPBridge()
        tools = bridge.register_tools(manifest)
        assert len(tools) > 0

    def test_register_multi_effect_hlf(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL web_search query="test"
TOOL file_read path="/tmp/data.txt"
\N{greek capital letter delta} [ANALYZE] query="analyze"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        bridge = MCPBridge()
        tools = bridge.register_tools(manifest)
        names = [t.name for t in tools]
        assert any("web_search" in n for n in names)
        assert any("file_read" in n for n in names)

    def test_register_with_provenance_passthrough(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL web_search query="important"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        dc = DataChannel()
        dc.track("query_context", source="agent", trust=0.9, value="research session")
        bridge = MCPBridge()
        tools = bridge.register_tools(manifest, provenance_from=dc.provenance)
        assert len(tools) == 1
        assert "runtime_provenance" in tools[0].provenance
        runtime = tools[0].provenance["runtime_provenance"]
        assert runtime["query_context"]["source"] == "agent"

    def test_register_tool_list_from_compiled(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL memory_read key="session_data"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        raw = manifest_to_mcp_tool_schemas(manifest)
        assert len(raw) == 1
        assert raw[0]["name"].startswith("hlf_")

    def test_convenience_function(self):
        compiler = HLFCompiler()
        source = """[HLF-v3]
TOOL web_search query="test"
\N{greek capital letter omega}
"""
        _, manifest = compiler.compile_and_manifest(source)
        regs = register_manifest_as_mcp_tools(manifest)
        assert len(regs) == 1
        assert isinstance(regs[0], MCPToolRegistration)


# ═══════════════════════════════════════════════════════════════════════════════
# MCPToolRegistration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPToolRegistration:
    """Tests for MCPToolRegistration dataclass."""

    def test_default_values(self):
        reg = MCPToolRegistration(
            name="test_tool",
            description="A test tool",
        )
        assert reg.name == "test_tool"
        assert reg.description == "A test tool"
        assert reg.input_schema == {"type": "object", "properties": {}}
        assert reg.annotations == {}
        assert reg.provenance == {}

    def test_to_mcp_tool_includes_all_fields(self):
        reg = MCPToolRegistration(
            name="test",
            description="desc",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            output_schema={"type": "string"},
            annotations={"k": "v"},
            category="analysis",
            trust_tier="advisory",
            provenance={"manifest_signature": "abc123"},
        )
        tool = reg.to_mcp_tool()
        assert tool["name"] == "test"
        assert tool["description"] == "desc"
        assert tool["inputSchema"]["properties"]["x"]["type"] == "string"
        assert tool["annotations"]["k"] == "v"
        assert tool["annotations"]["hlf_provenance"]["manifest_signature"] == "abc123"
        assert tool["annotations"]["hlf_trust_tier"] == "advisory"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPBridgeEdgeCases:
    """Edge case tests for MCPBridge."""

    def test_empty_manifest(self):
        manifest = CapabilityManifest(program_id="empty")
        bridge = MCPBridge()
        tools = bridge.register_tools(manifest)
        assert tools == []

    def test_unknown_effect_class(self):
        """Effects with unknown/non-standard effect classes still register."""
        manifest = CapabilityManifest(
            program_id="unknown_effect",
            effects=[
                TypedEffectDeclaration(
                    function_name="weird_tool",
                    input_contract=InputContract(function_name="weird_tool", parameters=[]),
                    output_contract=OutputContract(function_name="weird_tool", return_type=HlfType.ANY),
                    effect_class=EffectClass.ENVIRONMENT_READ,
                ),
            ],
        )
        bridge = MCPBridge()
        tools = bridge.register_tools(manifest)
        assert len(tools) == 1
        assert tools[0].category == "environment"

    def test_effect_with_many_failure_modes(self):
        manifest = CapabilityManifest(
            program_id="fragile",
            effects=[
                TypedEffectDeclaration(
                    function_name="risky",
                    input_contract=InputContract(function_name="risky", parameters=[]),
                    output_contract=OutputContract(function_name="risky", return_type=HlfType.STRING),
                    effect_class=EffectClass.NETWORK_WRITE,
                    failure_modes=[
                        FailureMode.NETWORK_ERROR,
                        FailureMode.TIMEOUT_ERROR,
                        FailureMode.IO_ERROR,
                        FailureMode.VALIDATION_ERROR,
                        FailureMode.POLICY_DENIED,
                        FailureMode.GOVERNANCE_ERROR,
                    ],
                ),
            ],
        )
        bridge = MCPBridge()
        tools = bridge.register_tools(manifest)
        assert len(tools) == 1
        assert "failure_modes" in tools[0].annotations
        assert len(tools[0].annotations["failure_modes"]) == 6

    def test_no_provenance_passthrough(self):
        manifest = CapabilityManifest(
            program_id="no_prov",
            effects=[
                TypedEffectDeclaration(
                    function_name="simple",
                    input_contract=InputContract(function_name="simple", parameters=[]),
                    output_contract=OutputContract(function_name="simple", return_type=HlfType.BOOLEAN),
                    effect_class=EffectClass.LOCAL_ANALYSIS,
                ),
            ],
        )
        bridge = MCPBridge()
        tools = bridge.register_tools(manifest)
        assert len(tools) == 1
        assert "runtime_provenance" not in tools[0].provenance

    def test_manifest_signature_in_provenance(self, sample_manifest: CapabilityManifest):
        bridge = MCPBridge()
        tools = bridge.register_tools(sample_manifest)
        for tool in tools:
            assert "manifest_signature" in tool.provenance
            assert len(tool.provenance["manifest_signature"]) == 64  # SHA-256 hex

    def test_json_serializable_annotations(self, sample_manifest: CapabilityManifest):
        bridge = MCPBridge()
        tools = bridge.register_tools(sample_manifest)
        for tool in tools:
            tool_dict = tool.to_mcp_tool()
            # Verify full round-trip through JSON
            encoded = json.dumps(tool_dict)
            decoded = json.loads(encoded)
            assert decoded == tool_dict
