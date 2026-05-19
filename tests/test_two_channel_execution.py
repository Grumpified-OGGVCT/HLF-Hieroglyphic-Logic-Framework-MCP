"""
Tests for Two-Channel Execution Model (Phase 6).

Validates:
  - InstructionChannel: creation, integrity verification, tamper detection
  - DataChannel: input tracking, provenance chains, trust degradation
  - ProvenanceChain: immutability, cascade degradation, boundary crossing
  - TwoChannelExecutor: full execution pipeline, gating integration
  - Integration with CapabilityManifest (Phase 5)
  - Integration with VerificationGate (Phase 3)
  - Full two-channel execution cycle
  - Provenance immutability
  - Compiler InstructionChannel production
"""

from __future__ import annotations

import hashlib
import os

import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())

from hlf_mcp.hlf.two_channel_executor import (
    ProvenanceChain,
    InstructionChannel,
    DataChannel,
    ExecutionResult,
    TwoChannelExecutor,
    build_instruction_channel,
    build_data_channel,
)
from hlf_mcp.hlf.capability_manifest import CapabilityManifest
from hlf_mcp.hlf.formal_verifier import (
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    VerificationGate,
    GateDecision,
    VerificationBlockedError,
    ConstraintKind,
    FormalVerifier,
)
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.bytecode import HLFBytecode


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures / helpers
# ═══════════════════════════════════════════════════════════════════════════════

SIMPLE_HLF = """[HLF-v3]
Δ [ANALYZE] query="hello world"
Ω
"""


def _make_verification_report(all_proven: bool = True) -> VerificationReport:
    """Build a VerificationReport for testing."""
    report = VerificationReport()
    if all_proven:
        report.add(
            VerificationResult(
                "range_check",
                VerificationStatus.PROVEN,
                ConstraintKind.RANGE_CHECK,
                message="All constraints satisfied",
                solver="fallback",
            )
        )
    else:
        report.add(
            VerificationResult(
                "range_check",
                VerificationStatus.COUNTEREXAMPLE,
                ConstraintKind.RANGE_CHECK,
                message="Value out of bounds",
                solver="fallback",
            )
        )
    return report


def _make_manifest(trust_tier: str = "advisory") -> CapabilityManifest:
    """Build a CapabilityManifest for testing."""
    return CapabilityManifest(
        program_id=hashlib.sha256(b"test_program").hexdigest(),
        trust_tier=trust_tier,
        required_capabilities={"local"},
    )


def _make_bytecode() -> bytes:
    """Build test bytecode."""
    return hashlib.sha256(b"test_bytecode").digest() + b"\x00" * 16


# ═══════════════════════════════════════════════════════════════════════════════
# ProvenanceChain tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProvenanceChain:
    """Tests for ProvenanceChain — the pointer provenance primitive."""

    def test_creation_with_defaults(self) -> None:
        chain = ProvenanceChain(source="agent_alpha")
        assert chain.source == "agent_alpha"
        assert chain.trust == 1.0
        assert chain.path == []
        assert chain.timestamp != ""

    def test_creation_with_explicit_values(self) -> None:
        chain = ProvenanceChain(
            source="file_system",
            path=["read", "parsed"],
            trust=0.8,
            timestamp="2024-01-01T00:00:00Z",
        )
        assert chain.source == "file_system"
        assert chain.path == ["read", "parsed"]
        assert chain.trust == 0.8
        assert chain.timestamp == "2024-01-01T00:00:00Z"

    def test_trust_clamped_to_range(self) -> None:
        chain_high = ProvenanceChain(source="test", trust=2.5)
        assert chain_high.trust == 1.0

        chain_low = ProvenanceChain(source="test", trust=-0.5)
        assert chain_low.trust == 0.0

    def test_degrade_reduces_trust(self) -> None:
        chain = ProvenanceChain(source="agent", trust=1.0)
        degraded = chain.degrade(0.9)
        assert degraded.trust == pytest.approx(0.9)
        assert len(degraded.path) == 1
        assert "degraded(0.9000)" in degraded.path[0]

    def test_degrade_cascades_trust(self) -> None:
        chain = ProvenanceChain(source="agent", trust=1.0)
        degraded1 = chain.degrade(0.9)
        degraded2 = degraded1.degrade(0.8)
        degraded3 = degraded2.degrade(0.7)

        assert degraded1.trust == pytest.approx(0.9)
        assert degraded2.trust == pytest.approx(0.72)
        assert degraded3.trust == pytest.approx(0.504)
        assert len(degraded3.path) == 3

    def test_degrade_does_not_mutate_original(self) -> None:
        chain = ProvenanceChain(source="agent", trust=1.0)
        degraded = chain.degrade(0.5)
        assert chain.trust == 1.0
        assert chain.path == []
        assert degraded.trust == 0.5
        assert len(degraded.path) == 1

    def test_cross_boundary_records_transition(self) -> None:
        chain = ProvenanceChain(source="agent", trust=0.9)
        crossed = chain.cross_boundary("agent→vm", "vm_sandbox")
        assert crossed.source == "vm_sandbox"
        assert crossed.trust == 0.5  # Reset to baseline
        assert len(crossed.path) == 1
        assert "boundary:agent→vm" in crossed.path[0]

    def test_immutable_proof_hash_is_deterministic(self) -> None:
        chain = ProvenanceChain(source="agent", trust=0.8)
        h1 = chain.is_immutable_proof()
        h2 = chain.is_immutable_proof()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_immutable_proof_changes_on_degradation(self) -> None:
        chain = ProvenanceChain(source="agent", trust=1.0)
        h1 = chain.is_immutable_proof()
        degraded = chain.degrade(0.5)
        h2 = degraded.is_immutable_proof()
        assert h1 != h2

    def test_serialization_roundtrip(self) -> None:
        chain = ProvenanceChain(
            source="network",
            path=["fetch", "parse", "validate"],
            trust=0.75,
            timestamp="2024-06-15T12:00:00Z",
        )
        data = chain.to_dict()
        restored = ProvenanceChain.from_dict(data)
        assert restored.source == chain.source
        assert restored.path == chain.path
        assert restored.trust == chain.trust
        assert restored.timestamp == chain.timestamp


# ═══════════════════════════════════════════════════════════════════════════════
# DataChannel tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDataChannel:
    """Tests for DataChannel — dynamic, provenance-tracked data."""

    def test_track_creates_provenance(self) -> None:
        data = DataChannel()
        chain = data.track("input_x", "agent_alpha", trust=0.95, value=42)
        assert data.inputs["input_x"] == 42
        assert data.provenance["input_x"] is chain
        assert chain.source == "agent_alpha"
        assert chain.trust == 0.95

    def test_track_raises_on_duplicate(self) -> None:
        data = DataChannel()
        data.track("input_x", "agent_alpha", trust=0.95)
        with pytest.raises(ValueError, match="already recorded and immutable"):
            data.track("input_x", "agent_beta", trust=0.5)

    def test_degrade_reduces_trust_in_place(self) -> None:
        data = DataChannel()
        data.track("input_x", "agent_alpha", trust=1.0)
        degraded = data.degrade("input_x", 0.8)
        assert degraded.trust == 0.8
        assert data.provenance["input_x"].trust == 0.8

    def test_degrade_raises_on_missing(self) -> None:
        data = DataChannel()
        with pytest.raises(KeyError, match="No provenance for 'nonexistent'"):
            data.degrade("nonexistent", 0.5)

    def test_cross_boundary_records_transition(self) -> None:
        data = DataChannel()
        data.track("sensor_data", "sensor_hub", trust=0.9, value={"temp": 25})
        crossed = data.cross_boundary("sensor_data", "sensor→planner", "planner")
        assert crossed.source == "planner"
        assert crossed.trust == 0.5
        assert len(crossed.path) == 1
        assert "boundary:sensor→planner" in crossed.path[0]

    def test_cross_boundary_raises_on_missing(self) -> None:
        data = DataChannel()
        with pytest.raises(KeyError, match="No provenance for 'nonexistent'"):
            data.cross_boundary("nonexistent", "test", "new")

    def test_get_provenance(self) -> None:
        data = DataChannel()
        data.track("x", "source_a", trust=0.7)
        chain = data.get_provenance("x")
        assert chain.source == "source_a"
        assert chain.trust == 0.7

    def test_get_provenance_raises_on_missing(self) -> None:
        data = DataChannel()
        with pytest.raises(KeyError, match="No provenance for 'x'"):
            data.get_provenance("x")

    def test_check_trust(self) -> None:
        data = DataChannel()
        data.track("high", "agent", trust=0.9)
        data.track("low", "agent", trust=0.3)
        assert data.check_trust("high", 0.8) is True
        assert data.check_trust("low", 0.8) is False
        assert data.check_trust("nonexistent", 0.5) is False

    def test_all_provenance_hashes(self) -> None:
        data = DataChannel()
        data.track("a", "agent", trust=0.9)
        data.track("b", "file", trust=0.7)
        hashes = data.all_provenance_hashes()
        assert "a" in hashes
        assert "b" in hashes
        assert len(hashes["a"]) == 64

    def test_to_dict_includes_provenance(self) -> None:
        data = DataChannel(capabilities={"filesystem", "network"})
        data.track("x", "agent", trust=0.8, value="hello")
        d = data.to_dict()
        assert d["input_count"] == 1
        assert "x" in d["input_names"]
        assert "x" in d["provenance"]
        assert d["provenance"]["x"]["source"] == "agent"
        assert "filesystem" in d["capabilities"]


# ═══════════════════════════════════════════════════════════════════════════════
# InstructionChannel tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInstructionChannel:
    """Tests for InstructionChannel — immutable, signed instructions."""

    def test_creation_and_auto_signature(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        assert channel.signature != ""
        assert len(channel.signature) == 64
        assert channel.tier == "hearth"

    def test_is_intact_returns_true_for_valid_channel(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        assert channel.is_intact() is True

    def test_is_intact_detects_tampered_bytecode(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        # Tamper with bytecode
        channel.bytecode = b"tampered_bytecode"
        assert channel.is_intact() is False

    def test_is_intact_detects_tampered_manifest(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        # Tamper with manifest
        channel.manifest = _make_manifest(trust_tier="hearth")
        assert channel.is_intact() is False

    def test_is_intact_detects_tampered_tier(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        channel.tier = "sovereign"
        assert channel.is_intact() is False

    def test_to_dict_produces_expected_structure(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        d = channel.to_dict()
        assert "program_id" in d
        assert "bytecode_sha256" in d
        assert "bytecode_length" in d
        assert "manifest" in d
        assert "verification" in d
        assert "signature" in d
        assert "tier" in d
        assert d["bytecode_length"] == len(bytecode)


# ═══════════════════════════════════════════════════════════════════════════════
# build_instruction_channel / build_data_channel tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildFactories:
    """Tests for the factory functions that construct channels."""

    def test_build_instruction_channel_with_all_args(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = build_instruction_channel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            program_id="test123",
            tier="forge",
            signer_key="key1",
        )
        assert channel.program_id == "test123"
        assert channel.tier == "forge"
        assert channel.is_intact() is True

    def test_build_instruction_channel_auto_derives_program_id(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report()

        channel = build_instruction_channel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
        )
        assert channel.program_id == manifest.program_id

    def test_build_data_channel_with_inputs(self) -> None:
        data = build_data_channel(
            inputs={"x": 10, "y": 20},
            capabilities={"network"},
        )
        assert data.inputs["x"] == 10
        assert data.inputs["y"] == 20
        assert "x" in data.provenance
        assert "y" in data.provenance
        assert data.provenance["x"].source == "agent"
        assert data.provenance["x"].trust == 0.95
        assert "network" in data.capabilities

    def test_build_data_channel_empty(self) -> None:
        data = build_data_channel()
        assert data.inputs == {}
        assert data.provenance == {}
        assert data.capabilities == set()


# ═══════════════════════════════════════════════════════════════════════════════
# TwoChannelExecutor tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTwoChannelExecutor:
    """Tests for the full TwoChannelExecutor execution pipeline."""

    def test_execute_with_valid_channels(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(
            inputs={"query": "test"},
            capabilities={"local"},
        )

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        assert result.status == "ok"
        assert result.executed is True
        assert result.gate_decision == GateDecision.PROCEED
        assert result.instruction_intact is True
        assert result.manifest_ok is True
        assert len(result.provenance) == 1  # query input tracked

    def test_execute_detects_tampered_instruction(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        # Tamper
        instruction.bytecode = b"corrupted"

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        assert result.status == "blocked"
        assert result.executed is False
        assert result.instruction_intact is False
        assert "tampered" in result.error_message.lower()

    def test_execute_blocks_on_counterexample_at_hearth(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report(all_proven=False)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        assert result.status == "blocked"
        assert result.executed is False
        assert result.gate_decision == GateDecision.BLOCK

    def test_execute_proceeds_on_counterexample_at_sovereign(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest(trust_tier="sovereign")
        verification = _make_verification_report(all_proven=False)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="sovereign")

        # Sovereign tier: manifest check passes (tier matches),
        # verification gate proceeds despite counterexample
        assert result.gate_decision == GateDecision.PROCEED

    def test_execute_blocks_on_missing_capability(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        manifest.required_capabilities = {"network", "filesystem"}
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})  # only local, missing network+filesystem

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        assert result.status == "blocked"
        assert result.manifest_ok is False
        assert len(result.manifest_blocked_reasons) > 0

    def test_execute_blocks_on_insufficient_trust_tier(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest(trust_tier="hearth")  # requires hearth
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="advisory")

        assert result.status == "blocked"
        assert result.manifest_ok is False

    def test_full_cycle_preserves_provenance(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(
            inputs={"alpha": "input_a", "beta": "input_b"},
            capabilities={"local"},
        )

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        assert result.status == "ok"
        assert "alpha" in result.provenance
        assert "beta" in result.provenance
        assert result.provenance["alpha"].source == "agent"
        assert result.provenance["beta"].source == "agent"

    def test_provenance_is_present_in_result_dict(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(
            inputs={"key1": "val1"},
            capabilities={"local"},
        )

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")
        d = result.to_dict()

        assert "provenance" in d
        assert "key1" in d["provenance"]
        assert d["provenance"]["key1"]["source"] == "agent"
        assert "provenance_hashes" in d
        assert "key1" in d["provenance_hashes"]


# ═══════════════════════════════════════════════════════════════════════════════
# Compiler → InstructionChannel integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompilerInstructionChannel:
    """Tests for HLFCompiler.compile_to_instruction_channel()."""

    def test_compile_to_instruction_channel_basic(self) -> None:
        compiler = HLFCompiler()
        channel = compiler.compile_to_instruction_channel(
            SIMPLE_HLF,
            tier="hearth",
        )
        assert channel is not None
        assert channel.is_intact() is True
        assert len(channel.bytecode) > 0
        assert channel.manifest is not None
        assert channel.verification is not None
        assert channel.signature != ""

    def test_compile_to_instruction_channel_tier(self) -> None:
        compiler = HLFCompiler()
        channel = compiler.compile_to_instruction_channel(
            SIMPLE_HLF,
            tier="forge",
        )
        assert channel.tier == "forge"

    def test_compile_result_contains_channel(self) -> None:
        compiler = HLFCompiler()
        channel = compiler.compile_to_instruction_channel(SIMPLE_HLF)
        assert len(channel.signature) == 64


# ═══════════════════════════════════════════════════════════════════════════════
# Two-channel code_execution integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTwoChannelCodeExecution:
    """Tests for execute_two_channel_hlf()."""

    def test_basic_execution(self) -> None:
        from hlf_mcp.hlf.code_execution import execute_two_channel_hlf

        source = (
            "[HLF-v3]\n"
            "MODULE demo {\n"
            "  FUNCTION main {\n"
            "    RESULT 0 \"two-channel-ok\"\n"
            "  }\n"
            "}\n"
            "Ω\n"
        )

        result = execute_two_channel_hlf(source, entrypoint="main", tier="hearth")

        assert result["two_channel"] is True
        assert result["compiled"] is True
        assert "instruction_channel" in result
        assert "data_channel" in result
        assert "provenance" in result

    def test_dry_run(self) -> None:
        from hlf_mcp.hlf.code_execution import execute_two_channel_hlf

        source = "[HLF-v3]\nFUNCTION main {\n  RESULT 0 \"dry\"\n}\nΩ\n"

        result = execute_two_channel_hlf(source, dry_run=True, tier="hearth")

        assert result["status"] == "dry_run_ok"
        assert result["executed"] is False
        assert result["sandbox_mode"] == "two-channel-dry-run"
        assert result["two_channel"] is True

    def test_variables_become_provenance(self) -> None:
        from hlf_mcp.hlf.code_execution import execute_two_channel_hlf

        source = (
            "[HLF-v3]\n"
            "MODULE demo {\n"
            "  FUNCTION main {\n"
            "    RESULT 0 \"ok\"\n"
            "  }\n"
            "}\n"
            "Ω\n"
        )

        result = execute_two_channel_hlf(
            source,
            variables={"agent_input": "delegated_task"},
            tier="hearth",
        )

        assert result["two_channel"] is True
        assert "agent_input" in result["data_channel"]["provenance"]

    def test_compile_error_returns_blocked(self) -> None:
        from hlf_mcp.hlf.code_execution import execute_two_channel_hlf

        source = "not valid HLF at all {{{"

        result = execute_two_channel_hlf(source, tier="hearth")

        assert result["status"] == "compile_error"
        assert result["compiled"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionResult tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_success_result_to_dict(self) -> None:
        result = ExecutionResult(
            status="ok",
            executed=True,
            gate_decision=GateDecision.PROCEED,
            instruction_intact=True,
            manifest_ok=True,
            runtime_result={"status": "ok", "result": 42},
            trace_ref="abc123",
        )
        d = result.to_dict()
        assert d["status"] == "ok"
        assert d["executed"] is True
        assert d["gate_decision"] == "proceed"
        assert d["instruction_intact"] is True

    def test_blocked_result_to_dict(self) -> None:
        result = ExecutionResult(
            status="blocked",
            executed=False,
            gate_decision=GateDecision.BLOCK,
            instruction_intact=True,
            manifest_ok=False,
            manifest_blocked_reasons=["Missing capabilities: network"],
            trace_ref="abc123",
            error_message="Capability manifest blocked: Missing capabilities: network",
        )
        d = result.to_dict()
        assert d["status"] == "blocked"
        assert d["executed"] is False
        assert len(d["manifest_blocked_reasons"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Integration with CapabilityManifest (Phase 5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapabilityManifestIntegration:
    """Tests that InstructionChannel properly integrates with CapabilityManifest."""

    def test_instruction_channel_manifest_integrity(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report(all_proven=True)

        channel = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )

        # Manifest should be intact and match
        assert channel.is_intact() is True
        assert channel.manifest.program_id == manifest.program_id

    def test_capability_check_flows_to_executor(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        manifest.required_capabilities = {"model"}  # requires model capability
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})  # no model capability

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        assert result.manifest_ok is False
        assert "model" in result.manifest_blocked_reasons[0].lower()

    def test_trust_tier_check_flows_to_executor(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest(trust_tier="hearth")
        verification = _make_verification_report(all_proven=True)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="advisory")

        assert result.manifest_ok is False
        assert any("trust tier" in r.lower() for r in result.manifest_blocked_reasons)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration with VerificationGate (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestVerificationGateIntegration:
    """Tests that TwoChannelExecutor properly integrates with VerificationGate."""

    def test_hearth_blocks_counterexample(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = _make_verification_report(all_proven=False)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        assert result.gate_decision == GateDecision.BLOCK
        assert result.status == "blocked"

    def test_sovereign_proceeds_regardless(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest(trust_tier="sovereign")
        verification = _make_verification_report(all_proven=False)

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="sovereign")

        assert result.gate_decision == GateDecision.PROCEED

    def test_empty_verification_report_blocks_at_hearth(self) -> None:
        bytecode = _make_bytecode()
        manifest = _make_manifest()
        verification = VerificationReport()  # empty — no results

        instruction = InstructionChannel(
            bytecode=bytecode,
            manifest=manifest,
            verification=verification,
            signature="",
        )
        data = build_data_channel(capabilities={"local"})

        executor = TwoChannelExecutor()
        result = executor.execute(instruction, data, tier="hearth")

        # Empty report at hearth → BLOCK
        assert result.gate_decision == GateDecision.BLOCK


# ═══════════════════════════════════════════════════════════════════════════════
# Data trust boundary crossing tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDataTrustBoundaries:
    """Tests that data crossing trust boundaries gets provenance recorded."""

    def test_boundary_crossing_produces_new_chain(self) -> None:
        data = DataChannel()
        data.track("raw_sensor", "sensor_driver", trust=0.9, value={"rpm": 3000})

        # Simulate crossing from sensor to planner
        crossed = data.cross_boundary("raw_sensor", "sensor→planner", "planner_agent")

        assert crossed.source == "planner_agent"
        assert crossed.trust == 0.5  # baseline reset
        assert len(crossed.path) == 1
        assert "boundary:sensor→planner" in crossed.path[0]

    def test_multiple_boundary_crossings(self) -> None:
        data = DataChannel()
        data.track("data", "source", trust=1.0, value="original")

        data.cross_boundary("data", "source→parser", "parser")
        data.cross_boundary("data", "parser→validator", "validator")
        data.cross_boundary("data", "validator→executor", "executor")

        chain = data.get_provenance("data")
        assert chain.source == "executor"
        assert chain.trust == 0.5
        assert len(chain.path) == 3

    def test_degrade_then_cross_boundary(self) -> None:
        data = DataChannel()
        data.track("data", "source", trust=1.0, value="original")
        data.degrade("data", 0.8)
        data.cross_boundary("data", "source→vm", "vm")

        chain = data.get_provenance("data")
        assert chain.source == "vm"
        assert chain.trust == 0.5  # boundary crossing resets to baseline
        assert len(chain.path) == 2  # one degrade + one boundary
