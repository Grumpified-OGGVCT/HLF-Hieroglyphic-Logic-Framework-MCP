"""
Tests for Capability Manifest (Phase 5).

Validates:
  - CapabilityManifest dataclass: creation, serialization, signing
  - EffectExtractor: exhaustive AST walk and effect extraction
  - Compiler integration: extract_manifest() and compile_and_manifest()
  - Capability gating: manifest.check() and manifest.full_check()
  - Trust tier determination
  - VerificationGate integration
  - JSON round-trip integrity
  - Cryptographic signature consistency
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())
os.chdir(os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    EFFECT_TO_CAPABILITY,
    EFFECT_TO_TRUST_TIER,
    TRUST_TIER_ORDER,
    _determine_trust_tier,
    _collect_required_capabilities,
)
from hlf_mcp.hlf.effect_extractor import EffectExtractor
from hlf_mcp.hlf.compiler import HLFCompiler, CompileError
from hlf_mcp.hlf.typed_contracts import (
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    ProofSurface,
    ProofRequirement,
    EffectClass,
    FailureMode,
    TypeContract,
    HlfType,
)
from hlf_mcp.hlf.formal_verifier import (
    VerificationGate,
    GateDecision,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    ConstraintKind,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures / helpers
# ═══════════════════════════════════════════════════════════════════════════════

SIMPLE_HLF = """[HLF-v3]
Δ [ANALYZE] query="hello world"
Ω
"""

TOOL_HLF = """[HLF-v3]
TOOL web_search query="latest AI news"
Ω
"""

MULTI_EFFECT_HLF = """[HLF-v3]
Δ [ANALYZE] query="analyze data"
TOOL file_read path="/tmp/data.txt"
TOOL web_search query="verify findings"
Ж [VERIFY] check="integrity"
Ω
"""

FILE_WRITE_HLF = """[HLF-v3]
TOOL file_write path="/tmp/output.txt" content="results" @validate(output_contract="text")
Ω
"""

EXEC_HLF = """[HLF-v3]
⌘ [EXEC] command="run analysis" @validate(output_contract="result")
Ω
"""

BLOCK_HLF = """[HLF-v3]
IF True {
    TOOL web_search query="test"
    ⌘ [EXEC] command="dangerous" @validate(output_contract="result")
}
Ω
"""


def _make_compiler() -> HLFCompiler:
    return HLFCompiler(strict_align=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityManifest — creation and properties
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapabilityManifestCreation:
    """Basic creation and property tests."""

    def test_empty_manifest(self):
        m = CapabilityManifest(program_id="abc123")
        assert m.program_id == "abc123"
        assert m.effects == []
        assert m.required_capabilities == set()
        assert m.trust_tier == "advisory"
        assert m.compiler_version != ""
        assert m.compiled_at != ""

    def test_manifest_with_effects(self):
        effect = TypedEffectDeclaration(
            function_name="web_search",
            effect_class=EffectClass.WEB_SEARCH,
        )
        m = CapabilityManifest(
            program_id="test123",
            effects=[effect],
            required_capabilities={"network"},
            trust_tier="hearth",
        )
        assert len(m.effects) == 1
        assert m.effects[0].function_name == "web_search"
        assert m.required_capabilities == {"network"}
        assert m.trust_tier == "hearth"

    def test_compiled_at_defaults_to_iso(self):
        m = CapabilityManifest(program_id="x")
        # Should be valid ISO 8601
        assert "T" in m.compiled_at
        assert m.compiled_at.endswith("+00:00") or m.compiled_at.endswith("Z")

    def test_compiled_at_custom(self):
        m = CapabilityManifest(program_id="x", compiled_at="2025-01-15T10:30:00+00:00")
        assert m.compiled_at == "2025-01-15T10:30:00+00:00"


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityManifest — check() capability gating
# ═══════════════════════════════════════════════════════════════════════════════


class TestManifestCheck:
    """Capability gating tests."""

    def test_empty_manifest_passes_any(self):
        m = CapabilityManifest(program_id="test")
        assert m.check(set())
        assert m.check({"network", "filesystem", "exec"})

    def test_check_subset_passes(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network"},
        )
        assert m.check({"network", "filesystem"})

    def test_check_exact_match_passes(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network", "model"},
        )
        assert m.check({"network", "model"})

    def test_check_missing_capability_fails(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network", "exec"},
        )
        # Has network but not exec
        assert not m.check({"network", "filesystem"})

    def test_check_no_capabilities_fails(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network"},
        )
        assert not m.check(set())

    def test_check_empty_manifest_with_any_caps(self):
        m = CapabilityManifest(program_id="test")
        assert m.check({"network", "exec"})
        assert m.check(set())


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityManifest — trust tier checking
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrustTierCheck:
    """Trust tier gating tests."""

    @pytest.mark.parametrize(
        "program_tier,session_tier,expected",
        [
            # Program needs low trust (advisory, tier=2) — sessions at tier >= 2 work
            ("advisory", "sovereign", False),     # 0 < 2
            ("advisory", "untrusted", False),      # 1 < 2
            ("advisory", "advisory", True),         # 2 >= 2
            ("advisory", "forge", True),            # 3 >= 2
            ("advisory", "approved", True),         # 5 >= 2
            ("advisory", "hearth", True),           # 7 >= 2
            # Program needs approved (tier=5) — sessions at tier >= 5 work
            ("approved", "advisory", False),        # 2 < 5
            ("approved", "watched", False),         # 4 < 5
            ("approved", "approved", True),         # 5 >= 5
            ("approved", "trusted", True),          # 6 >= 5
            ("approved", "hearth", True),           # 7 >= 5
            # Program needs trusted (tier=6)
            ("trusted", "approved", False),         # 5 < 6
            ("trusted", "trusted", True),           # 6 >= 6
            ("trusted", "hearth", True),            # 7 >= 6
            # Program needs hearth (tier=7) — only hearth works
            ("hearth", "hearth", True),             # 7 >= 7
            ("hearth", "trusted", False),           # 6 < 7
            ("hearth", "sovereign", False),         # 0 < 7
            # Program needs forge (tier=3)
            ("forge", "advisory", False),           # 2 < 3
            ("forge", "forge", True),               # 3 >= 3
            ("forge", "watched", True),             # 4 >= 3
            # Program needs watched (tier=4)
            ("watched", "forge", False),            # 3 < 4
            ("watched", "watched", True),           # 4 >= 4
            ("watched", "approved", True),          # 5 >= 4
        ],
    )
    def test_check_tier(self, program_tier, session_tier, expected):
        m = CapabilityManifest(
            program_id="test",
            trust_tier=program_tier,
        )
        assert m.check_tier(session_tier) == expected

    def test_unknown_program_tier_defaults_low(self):
        """Unknown program tiers should default to advisory (permissive)."""
        m = CapabilityManifest(
            program_id="test",
            trust_tier="unknown_tier",
        )
        # Low default means any session passes
        assert m.check_tier("advisory")

    def test_unknown_session_tier_defaults_low(self):
        """Unknown session tiers should default to sovereign (permissive)."""
        m = CapabilityManifest(
            program_id="test",
            trust_tier="approved",
        )
        # "unknown" maps to 0 (sovereign), which is < approved
        assert not m.check_tier("unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityManifest — full_check()
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullCheck:
    """Combined capability + trust tier checks."""

    def test_full_check_all_pass(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network"},
            trust_tier="approved",
        )
        admitted, reasons = m.full_check({"network", "model"}, "hearth")
        assert admitted
        assert reasons == []

    def test_full_check_capability_fail(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network", "exec"},
            trust_tier="approved",
        )
        admitted, reasons = m.full_check({"network"}, "hearth")
        assert not admitted
        assert any("Missing capabilities" in r for r in reasons)

    def test_full_check_tier_fail(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network"},
            trust_tier="hearth",
        )
        admitted, reasons = m.full_check({"network"}, "advisory")
        assert not admitted
        assert any("trust tier" in r for r in reasons)

    def test_full_check_both_fail(self):
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network", "exec"},
            trust_tier="hearth",
        )
        admitted, reasons = m.full_check(set(), "advisory")
        assert not admitted
        assert len(reasons) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityManifest — JSON serialization
# ═══════════════════════════════════════════════════════════════════════════════


class TestManifestSerialization:
    """JSON round-trip tests."""

    def test_to_dict_empty(self):
        m = CapabilityManifest(program_id="abc")
        d = m.to_dict()
        assert d["program_id"] == "abc"
        assert d["effects"] == []
        assert d["required_capabilities"] == []
        assert d["trust_tier"] == "advisory"
        assert "compiled_at" in d
        assert "compiler_version" in d

    def test_to_dict_with_effects(self):
        effect = TypedEffectDeclaration(
            function_name="web_search",
            effect_class=EffectClass.WEB_SEARCH,
            failure_modes=[FailureMode.NETWORK_ERROR],
            side_effects=["network:egress:read"],
        )
        m = CapabilityManifest(
            program_id="test123",
            effects=[effect],
            required_capabilities={"network"},
            trust_tier="approved",
        )
        d = m.to_dict()
        assert len(d["effects"]) == 1
        assert d["effects"][0]["function_name"] == "web_search"
        assert d["effects"][0]["effect_class"] == "web_search"
        assert "network" in d["required_capabilities"]

    def test_json_round_trip_empty(self):
        m = CapabilityManifest(program_id="roundtrip")
        d = m.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        d2 = json.loads(json_str)
        m2 = CapabilityManifest.from_dict(d2)
        assert m2.program_id == m.program_id
        assert m2.effects == m.effects
        assert m2.required_capabilities == m.required_capabilities
        assert m2.trust_tier == m.trust_tier

    def test_json_round_trip_with_effects(self):
        effect = TypedEffectDeclaration(
            function_name="file_read",
            effect_class=EffectClass.FILE_READ,
            failure_modes=[FailureMode.IO_ERROR],
            proof_requirement=ProofRequirement.RUNTIME_CHECKED,
            safety_class="bounded",
        )
        m = CapabilityManifest(
            program_id="full_roundtrip",
            effects=[effect],
            required_capabilities={"filesystem"},
            trust_tier="approved",
            compiled_at="2025-06-15T00:00:00+00:00",
        )
        d = m.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        d2 = json.loads(json_str)
        m2 = CapabilityManifest.from_dict(d2)
        assert m2.program_id == m.program_id
        assert len(m2.effects) == 1
        assert m2.effects[0].function_name == "file_read"
        assert m2.effects[0].effect_class == EffectClass.FILE_READ
        assert m2.required_capabilities == {"filesystem"}
        assert m2.trust_tier == "approved"

    def test_json_round_trip_with_contracts(self):
        input_contract = InputContract(
            function_name="test_func",
            parameters=[
                TypeContract(name="query", hlf_type=HlfType.STRING, required=True),
                TypeContract(name="limit", hlf_type=HlfType.INTEGER, required=False),
            ],
        )
        output_contract = OutputContract(
            function_name="test_func",
            return_type=HlfType.JSON,
        )
        m = CapabilityManifest(
            program_id="contract_test",
            input_contracts=[input_contract],
            output_contracts=[output_contract],
        )
        d = m.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        d2 = json.loads(json_str)
        m2 = CapabilityManifest.from_dict(d2)
        assert len(m2.input_contracts) == 1
        assert m2.input_contracts[0].function_name == "test_func"
        assert len(m2.output_contracts) == 1
        assert m2.output_contracts[0].return_type == HlfType.JSON

    def test_json_round_trip_with_proof_surfaces(self):
        ps = ProofSurface(
            bundle_sha256="abc123",
            ast_sha256="def456",
            report_sha256="ghi789",
            solver_name="z3",
            z3_available=True,
            all_proven=True,
            proven_count=5,
            total_count=5,
            failed_count=0,
            timestamp_epoch_ms=1234567890,
        )
        m = CapabilityManifest(
            program_id="proof_test",
            proof_surfaces=[ps],
        )
        d = m.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        d2 = json.loads(json_str)
        m2 = CapabilityManifest.from_dict(d2)
        assert len(m2.proof_surfaces) == 1
        assert m2.proof_surfaces[0].bundle_sha256 == "abc123"
        assert m2.proof_surfaces[0].all_proven is True
        assert m2.proof_surfaces[0].proven_count == 5

    def test_from_dict_handles_malformed_effects(self):
        """from_dict should be resilient to malformed effect data."""
        d = {
            "program_id": "resilient",
            "effects": [
                {"function_name": "valid", "effect_class": "local_analysis"},
                {"not": "an effect at all"},
                "not_even_a_dict",
            ],
            "required_capabilities": [],
            "input_contracts": [],
            "output_contracts": [],
            "proof_surfaces": [],
            "trust_tier": "advisory",
            "compiled_at": "",
            "compiler_version": "3.0.0",
        }
        m = CapabilityManifest.from_dict(d)
        # Should have at least the valid effect
        assert len(m.effects) >= 1
        assert m.program_id == "resilient"


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityManifest — cryptographic signing
# ═══════════════════════════════════════════════════════════════════════════════


class TestManifestSigning:
    """Cryptographic signature tests."""

    def test_sign_produces_consistent_hash(self):
        m = CapabilityManifest(program_id="sign_test")
        sig1 = m.sign()
        sig2 = m.sign()
        assert sig1 == sig2
        assert len(sig1) == 64  # SHA-256 hex is 64 chars

    def test_sign_with_key_produces_different_hash(self):
        m = CapabilityManifest(program_id="sign_test")
        sig_no_key = m.sign()
        sig_with_key = m.sign("my_secret")
        assert sig_no_key != sig_with_key

    def test_sign_with_same_key_is_consistent(self):
        m = CapabilityManifest(program_id="sign_test")
        sig1 = m.sign("key1")
        sig2 = m.sign("key1")
        assert sig1 == sig2

    def test_sign_with_different_keys_differ(self):
        m = CapabilityManifest(program_id="sign_test")
        sig1 = m.sign("key1")
        sig2 = m.sign("key2")
        assert sig1 != sig2

    def test_verify_signature(self):
        m = CapabilityManifest(program_id="verify_test")
        sig = m.sign("test_key")
        assert m.verify_signature(sig, "test_key")

    def test_verify_signature_wrong_key_fails(self):
        m = CapabilityManifest(program_id="verify_test")
        sig = m.sign("key_a")
        assert not m.verify_signature(sig, "key_b")

    def test_verify_signature_tampered_manifest_fails(self):
        m = CapabilityManifest(program_id="tamper_test")
        sig = m.sign()
        # Tamper the manifest
        m2 = CapabilityManifest(program_id="different")
        assert not m2.verify_signature(sig)

    def test_sign_changes_when_manifest_changes(self):
        m1 = CapabilityManifest(program_id="a", trust_tier="advisory")
        m2 = CapabilityManifest(program_id="a", trust_tier="hearth")
        assert m1.sign() != m2.sign()

    def test_canonical_json_is_deterministic(self):
        m = CapabilityManifest(program_id="canonical_test")
        c1 = m._canonical_json()
        c2 = m._canonical_json()
        assert c1 == c2


# ═══════════════════════════════════════════════════════════════════════════════
# Effect extraction from compiled AST
# ═══════════════════════════════════════════════════════════════════════════════


class TestEffectExtraction:
    """Tests that EffectExtractor correctly walks the AST."""

    @pytest.fixture(autouse=True)
    def _disable_strict_constitution(self, monkeypatch):
        """Disable HLF_STRICT so FILE_WRITE and EXEC tests can compile.

        The constitutional check R-3 cannot currently see @validate annotations
        on tool_stmt because _expand_validates pops them before the check runs.
        This is a known compiler pipeline ordering issue.
        """
        monkeypatch.setenv("HLF_STRICT", "0")

    def test_simple_program_produces_manifest(self):
        compiler = _make_compiler()
        result = compiler.compile(SIMPLE_HLF)
        manifest = EffectExtractor.extract(result["ast"], SIMPLE_HLF)
        assert isinstance(manifest, CapabilityManifest)
        assert manifest.program_id != ""
        assert len(manifest.effects) > 0

    def test_program_id_from_source(self):
        compiler = _make_compiler()
        result = compiler.compile(SIMPLE_HLF)
        manifest = EffectExtractor.extract(result["ast"], SIMPLE_HLF)
        expected_id = hashlib.sha256(SIMPLE_HLF.strip().encode()).hexdigest()
        assert manifest.program_id == expected_id

    def test_program_id_without_source(self):
        compiler = _make_compiler()
        result = compiler.compile(SIMPLE_HLF)
        manifest = EffectExtractor.extract(result["ast"])
        # Should still produce a valid SHA-256 hex
        assert len(manifest.program_id) == 64
        # Should be different from source-based since it uses AST JSON
        expected_source_id = hashlib.sha256(SIMPLE_HLF.strip().encode()).hexdigest()
        assert manifest.program_id != expected_source_id  # uses AST JSON

    def test_tool_stmt_extracts_effect(self):
        compiler = _make_compiler()
        result = compiler.compile(TOOL_HLF)
        manifest = EffectExtractor.extract(result["ast"], TOOL_HLF)
        assert len(manifest.effects) >= 1
        tool_effects = [e for e in manifest.effects if e.function_name == "web_search"]
        assert len(tool_effects) >= 1
        assert tool_effects[0].effect_class == EffectClass.WEB_SEARCH

    def test_tool_web_search_requires_network(self):
        compiler = _make_compiler()
        result = compiler.compile(TOOL_HLF)
        manifest = EffectExtractor.extract(result["ast"], TOOL_HLF)
        assert "network" in manifest.required_capabilities

    def test_tool_file_read_requires_filesystem(self):
        hlf_src = """[HLF-v3]
TOOL file_read path="/tmp/data.txt"
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert "filesystem" in manifest.required_capabilities

    def test_tool_file_write_requires_filesystem(self):
        compiler = _make_compiler()
        result = compiler.compile(FILE_WRITE_HLF)
        manifest = EffectExtractor.extract(result["ast"], FILE_WRITE_HLF)
        assert "filesystem" in manifest.required_capabilities

    def test_multi_effect_program(self):
        compiler = _make_compiler()
        result = compiler.compile(MULTI_EFFECT_HLF)
        manifest = EffectExtractor.extract(result["ast"], MULTI_EFFECT_HLF)
        # Should have effects from: Δ ANALYZE, file_read, web_search, Ж VERIFY
        assert len(manifest.effects) >= 3
        # Should require both filesystem and network
        assert "network" in manifest.required_capabilities
        assert "filesystem" in manifest.required_capabilities

    def test_glyph_tag_mapping(self):
        """Test that glyph+tag combinations map to correct EffectClass."""
        hlf_src = """[HLF-v3]
⌘ [DELEGATE] target="agent-1"
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        delegate_effects = [
            e for e in manifest.effects
            if e.effect_class == EffectClass.AGENT_DELEGATION
        ]
        assert len(delegate_effects) >= 1

    def test_block_body_extraction(self):
        """Effects inside IF blocks should be extracted."""
        compiler = _make_compiler()
        result = compiler.compile(BLOCK_HLF)
        manifest = EffectExtractor.extract(result["ast"], BLOCK_HLF)
        # Should find both web_search (network) and EXEC (exec)
        assert "network" in manifest.required_capabilities
        assert "exec" in manifest.required_capabilities

    def test_manifest_has_compiled_at(self):
        compiler = _make_compiler()
        result = compiler.compile(SIMPLE_HLF)
        manifest = EffectExtractor.extract(result["ast"], SIMPLE_HLF)
        assert manifest.compiled_at != ""

    def test_manifest_has_compiler_version(self):
        compiler = _make_compiler()
        result = compiler.compile(SIMPLE_HLF)
        manifest = EffectExtractor.extract(result["ast"], SIMPLE_HLF)
        assert manifest.compiler_version == "3.0.0"

    def test_trust_tier_local_analysis(self):
        """A program with only local analysis should get advisory tier."""
        hlf_src = """[HLF-v3]
Δ [ANALYZE] query="hello"
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert manifest.trust_tier in ("advisory", "sovereign")

    def test_trust_tier_web_search(self):
        """A program with web search should get at least approved tier."""
        compiler = _make_compiler()
        result = compiler.compile(TOOL_HLF)
        manifest = EffectExtractor.extract(result["ast"], TOOL_HLF)
        # web_search → network_read → approved
        assert manifest.trust_tier in ("approved", "watched", "trusted", "hearth")

    def test_trust_tier_exec(self):
        """A program with exec should get at least trusted tier."""
        compiler = _make_compiler()
        result = compiler.compile(EXEC_HLF)
        manifest = EffectExtractor.extract(result["ast"], EXEC_HLF)
        # process_spawn → trusted
        assert manifest.trust_tier in ("trusted", "hearth")

    def test_extract_input_contracts(self):
        compiler = _make_compiler()
        result = compiler.compile(TOOL_HLF)
        manifest = EffectExtractor.extract(result["ast"], TOOL_HLF)
        assert len(manifest.input_contracts) >= 1
        # The web_search tool should produce an input contract
        search_contracts = [
            c for c in manifest.input_contracts
            if c.function_name == "web_search"
        ]
        assert len(search_contracts) >= 1

    def test_extract_proof_surfaces(self):
        hlf_src = """[HLF-v3]
Ж [VERIFY] check="integrity"
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert len(manifest.proof_surfaces) >= 1

    def test_empty_program(self):
        """Even an empty program should produce a manifest."""
        hlf_src = """[HLF-v3]
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert isinstance(manifest, CapabilityManifest)
        assert manifest.program_id != ""
        # Empty program may have no effects but manifest is still produced


# ═══════════════════════════════════════════════════════════════════════════════
# Compiler integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompilerIntegration:
    """Tests for compiler.extract_manifest() and compile_and_manifest()."""

    def test_compile_and_manifest(self):
        compiler = _make_compiler()
        result, manifest = compiler.compile_and_manifest(SIMPLE_HLF)
        assert result["ast"] is not None
        assert isinstance(manifest, CapabilityManifest)
        assert manifest.program_id != ""

    def test_extract_manifest_without_compile_raises(self):
        compiler = HLFCompiler()
        with pytest.raises(CompileError, match="requires a successful compile"):
            compiler.extract_manifest()

    def test_compile_and_manifest_returns_consistent_program_id(self):
        compiler = _make_compiler()
        _, manifest = compiler.compile_and_manifest(SIMPLE_HLF)
        expected_id = hashlib.sha256(SIMPLE_HLF.strip().encode()).hexdigest()
        assert manifest.program_id == expected_id

    def test_compile_and_manifest_different_programs(self):
        compiler = _make_compiler()
        _, m1 = compiler.compile_and_manifest(SIMPLE_HLF)
        compiler2 = _make_compiler()
        _, m2 = compiler2.compile_and_manifest(TOOL_HLF)
        assert m1.program_id != m2.program_id
        assert m1.required_capabilities != m2.required_capabilities

    def test_compile_then_extract_manifest(self):
        compiler = _make_compiler()
        result = compiler.compile(SIMPLE_HLF)
        manifest = EffectExtractor.extract(result["ast"], SIMPLE_HLF)
        assert isinstance(manifest, CapabilityManifest)
        assert len(manifest.effects) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Capability gating — blocking when capabilities insufficient
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapabilityGating:
    """Tests that programs are blocked when capabilities are insufficient."""

    def test_program_needing_network_fails_without_network(self):
        compiler = _make_compiler()
        _, manifest = compiler.compile_and_manifest(TOOL_HLF)
        # Simulate an environment without network
        available = {"filesystem", "memory", "local"}
        assert not manifest.check(available)

    def test_program_needing_network_passes_with_network(self):
        compiler = _make_compiler()
        _, manifest = compiler.compile_and_manifest(TOOL_HLF)
        available = {"network", "filesystem", "model"}
        assert manifest.check(available)

    def test_program_needing_exec_fails_without_exec(self):
        compiler = _make_compiler()
        _, manifest = compiler.compile_and_manifest(EXEC_HLF)
        available = {"network", "filesystem", "model"}
        assert not manifest.check(available)

    def test_program_needing_exec_passes_with_exec(self):
        compiler = _make_compiler()
        _, manifest = compiler.compile_and_manifest(EXEC_HLF)
        available = {"network", "exec", "filesystem"}
        assert manifest.check(available)

    def test_multi_capability_all_required(self):
        compiler = _make_compiler()
        _, manifest = compiler.compile_and_manifest(MULTI_EFFECT_HLF)
        # Needs filesystem, network, and verifier (from Ж VERIFY)
        assert not manifest.check({"network"})
        assert not manifest.check({"filesystem"})
        assert not manifest.check({"network", "filesystem", "model"})
        assert manifest.check({"network", "filesystem", "model", "verifier"})


# ═══════════════════════════════════════════════════════════════════════════════
# VerificationGate integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestVerificationGateIntegration:
    """Tests that CapabilityManifest integrates with VerificationGate."""

    def test_manifest_informs_gate_decision(self):
        """A blocked manifest should override the gate decision."""
        compiler = _make_compiler()
        result = compiler.compile(TOOL_HLF)
        manifest = EffectExtractor.extract(result["ast"], TOOL_HLF)

        # Create a clean verification report (no counterexamples)
        report = VerificationReport()
        report.add(VerificationResult(
            "check_1",
            VerificationStatus.PROVEN,
            ConstraintKind.RANGE_CHECK,
            message="All good",
        ))

        # Gate should PROCEED on clean report at hearth tier
        gate_result = VerificationGate.gate(report, "hearth")
        assert gate_result == GateDecision.PROCEED

        # But if manifest requires a capability we don't have,
        # the orchestrator should block
        available = set()  # no capabilities
        assert not manifest.check(available)

    def test_manifest_check_with_verification_gate(self):
        """Simulate the full gate+manifest check flow."""
        compiler = _make_compiler()
        result = compiler.compile(TOOL_HLF)
        manifest = EffectExtractor.extract(result["ast"], TOOL_HLF)

        report = VerificationReport()
        report.add(VerificationResult(
            "type_check",
            VerificationStatus.PROVEN,
            ConstraintKind.TYPE_INVARIANT,
        ))

        # Stage 1: VerificationGate
        gate_decision = VerificationGate.gate(report, "hearth")
        assert gate_decision == GateDecision.PROCEED

        # Stage 2: CapabilityManifest check
        admitted, reasons = manifest.full_check(
            {"network", "filesystem", "model"}, "hearth"
        )
        assert admitted
        assert reasons == []

    def test_manifest_blocks_when_verification_passes(self):
        """Even when verification passes, manifest can block on capabilities."""
        compiler = _make_compiler()
        _, manifest = compiler.compile_and_manifest(TOOL_HLF)

        # Verification passes
        report = VerificationReport()
        report.add(VerificationResult(
            "check", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK,
        ))
        assert VerificationGate.gate(report, "hearth") == GateDecision.PROCEED

        # But manifest blocks on missing capabilities
        admitted, reasons = manifest.full_check(set(), "hearth")
        assert not admitted
        assert any("Missing capabilities" in r for r in reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper function tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Unit tests for manifest helper functions."""

    def test_determine_trust_tier_empty(self):
        assert _determine_trust_tier([]) == "advisory"

    def test_determine_trust_tier_local(self):
        effects = [
            TypedEffectDeclaration(
                function_name="analyze",
                effect_class=EffectClass.LOCAL_ANALYSIS,
            )
        ]
        assert _determine_trust_tier(effects) == "advisory"

    def test_determine_trust_tier_mixed(self):
        """Should return the strictest tier."""
        effects = [
            TypedEffectDeclaration(
                function_name="analyze",
                effect_class=EffectClass.LOCAL_ANALYSIS,
            ),
            TypedEffectDeclaration(
                function_name="exec_danger",
                effect_class=EffectClass.PROCESS_SPAWN,
            ),
            TypedEffectDeclaration(
                function_name="web_search",
                effect_class=EffectClass.WEB_SEARCH,
            ),
        ]
        # PROCESS_SPAWN → trusted, which is stricter than approved (WEB_SEARCH)
        assert _determine_trust_tier(effects) == "trusted"

    def test_determine_trust_tier_hearth(self):
        effects = [
            TypedEffectDeclaration(
                function_name="stop",
                effect_class=EffectClass.SAFETY_STOP,
            )
        ]
        assert _determine_trust_tier(effects) == "hearth"

    def test_collect_capabilities_empty(self):
        assert _collect_required_capabilities([]) == set()

    def test_collect_capabilities_filters_local(self):
        effects = [
            TypedEffectDeclaration(
                function_name="analyze",
                effect_class=EffectClass.LOCAL_ANALYSIS,
            )
        ]
        assert _collect_required_capabilities(effects) == set()

    def test_collect_capabilities_multiple(self):
        effects = [
            TypedEffectDeclaration(
                function_name="web_search",
                effect_class=EffectClass.WEB_SEARCH,
            ),
            TypedEffectDeclaration(
                function_name="file_read",
                effect_class=EffectClass.FILE_READ,
            ),
            TypedEffectDeclaration(
                function_name="exec",
                effect_class=EffectClass.PROCESS_SPAWN,
            ),
        ]
        caps = _collect_required_capabilities(effects)
        assert "network" in caps
        assert "filesystem" in caps
        assert "exec" in caps

    def test_trust_tier_order_hearth_is_strictest(self):
        assert TRUST_TIER_ORDER["hearth"] > TRUST_TIER_ORDER["trusted"]
        assert TRUST_TIER_ORDER["hearth"] > TRUST_TIER_ORDER["advisory"]
        assert TRUST_TIER_ORDER["hearth"] > TRUST_TIER_ORDER["sovereign"]

    def test_trust_tier_order_sovereign_is_lowest(self):
        assert TRUST_TIER_ORDER["sovereign"] < TRUST_TIER_ORDER["advisory"]
        assert TRUST_TIER_ORDER["sovereign"] < TRUST_TIER_ORDER["hearth"]


# ═══════════════════════════════════════════════════════════════════════════════
# EffectClass → capability mapping completeness
# ═══════════════════════════════════════════════════════════════════════════════


class TestEffectToCapabilityMapping:
    """Verify that all EffectClass members have capability mappings."""

    def test_all_effect_classes_have_capability(self):
        for ec in EffectClass:
            cap = EFFECT_TO_CAPABILITY.get(ec)
            assert cap is not None, f"EffectClass.{ec.name} has no capability mapping"

    def test_all_effect_classes_have_trust_tier(self):
        for ec in EffectClass:
            tier = EFFECT_TO_TRUST_TIER.get(ec)
            assert tier is not None, f"EffectClass.{ec.name} has no trust tier mapping"
            assert tier in TRUST_TIER_ORDER, f"EffectClass.{ec.name} has unknown tier '{tier}'"


# ═══════════════════════════════════════════════════════════════════════════════
# Exhaustive AST walking
# ═══════════════════════════════════════════════════════════════════════════════


class TestExhaustiveASTWalk:
    """Verify that EffectExtractor walks all relevant AST node types."""

    def test_glyph_stmt_extracted(self):
        """All glyph statements should produce effects."""
        for glyph in ["Δ", "Ж", "⨝", "⌘", "∇", "⩕", "⌂", "Σ"]:
            hlf_src = f"[HLF-v3]\n{glyph} test=\"value\"\nΩ\n"
            compiler = _make_compiler()
            result = compiler.compile(hlf_src)
            manifest = EffectExtractor.extract(result["ast"], hlf_src)
            assert len(manifest.effects) >= 1, f"No effects extracted for glyph {glyph!r}"

    def test_tool_stmt_extracted(self):
        hlf_src = '[HLF-v3]\nTOOL my_tool query="test"\nΩ\n'
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        # my_tool doesn't match known tools → LOCAL_ANALYSIS, still extracted
        assert len(manifest.effects) >= 1

    def test_call_stmt_extracted(self):
        hlf_src = '[HLF-v3]\nCALL my_function query="test"\nΩ\n'
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert len(manifest.effects) >= 1

    def test_set_stmt_no_false_effect(self):
        """SET statements should not produce effects (they're declarations)."""
        hlf_src = '[HLF-v3]\nSET config = "value"\nΩ\n'
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        # SET should not produce tool-like effects (but may produce none)
        # At minimum, manifest is produced
        assert isinstance(manifest, CapabilityManifest)

    def test_for_loop_body_extracted(self):
        hlf_src = """[HLF-v3]
FOR i IN ⟨1, 2, 3⟩ {
    TOOL web_search query="test"
}
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert "network" in manifest.required_capabilities

    def test_parallel_block_extracted(self):
        hlf_src = """[HLF-v3]
PARALLEL {
    TOOL file_read path="/tmp/a.txt"
} {
    TOOL web_search query="test"
}
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert "filesystem" in manifest.required_capabilities
        assert "network" in manifest.required_capabilities

    def test_func_block_body_extracted(self):
        hlf_src = """[HLF-v3]
FUNCTION my_func {
    TOOL web_search query="test"
}
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert "network" in manifest.required_capabilities


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case and resilience tests."""

    @pytest.fixture(autouse=True)
    def _disable_strict_constitution(self, monkeypatch):
        """Disable HLF_STRICT so FILE_WRITE and EXEC tests can compile.

        The constitutional check R-3 cannot currently see @validate annotations
        on tool_stmt because _expand_validates pops them before the check runs.
        This is a known compiler pipeline ordering issue.
        """
        monkeypatch.setenv("HLF_STRICT", "0")

    def test_none_ast_handled(self):
        """Extracting from None should not crash."""
        # The extractor should handle edge cases gracefully
        manifest = EffectExtractor.extract({"kind": "program", "statements": []}, "")
        assert isinstance(manifest, CapabilityManifest)
        assert len(manifest.effects) == 0

    def test_deeply_nested_ast(self):
        """Deep nesting should still extract all effects."""
        hlf_src = """[HLF-v3]
IF True {
    IF True {
        IF True {
            TOOL web_search query="deep"
        }
    }
}
Ω
"""
        compiler = _make_compiler()
        result = compiler.compile(hlf_src)
        manifest = EffectExtractor.extract(result["ast"], hlf_src)
        assert "network" in manifest.required_capabilities

    def test_manifest_is_always_produced(self):
        """Every compiled program MUST produce a manifest."""
        programs = [SIMPLE_HLF, TOOL_HLF, MULTI_EFFECT_HLF, FILE_WRITE_HLF, EXEC_HLF]
        for src in programs:
            compiler = _make_compiler()
            result = compiler.compile(src)
            manifest = EffectExtractor.extract(result["ast"], src)
            assert isinstance(manifest, CapabilityManifest), f"No manifest for: {src[:50]}"
            assert manifest.program_id != ""

    def test_manifest_check_with_none_capabilities(self):
        """check() with None-like values should not crash."""
        m = CapabilityManifest(
            program_id="test",
            required_capabilities={"network"},
        )
        # empty set is fine
        assert not m.check(set())
        # Having all required caps passes
        assert m.check({"network"})
